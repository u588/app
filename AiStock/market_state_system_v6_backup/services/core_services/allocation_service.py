# ==================== 4.1.3 资产配置服务 （资产配置：九大战略方向）AllocationService ====================
class AllocationService:
    """资产配置服务（Jupyter调试版）"""
    
    def __init__(self, config_service: ConfigService):
        """初始化资产配置服务"""
        self.config_service = config_service
        self.base_weights = {
            '高端制造': 0.28,
            '信息技术': 0.25,
            '新能源': 0.15,
            '生物健康': 0.10,
            '公用事业': 0.08,
            '供应链': 0.06,
            '传统升级': 0.04,
            '文化消费': 0.03,
            '现代农业': 0.01
        }
        print("✅ 资产配置服务初始化成功")
    
    def calculate_allocation(
        self,
        benchmark_data: Dict[str, pd.DataFrame],
        micro_liquidity: Dict,
        market_state: str = '均衡持有区'
    ) -> pd.DataFrame:
        """
        计算战略方向配置
        
        返回:
            DataFrame with columns:
                - 战略方向
                - 基础权重
                - 估值得分
                - 趋势得分
                - 资金得分
                - 情绪得分
                - 商品调整
                - 微盘惩罚
                - 动态权重
                - 配置建议
                - 核心指数
        """
        results = []
        total_weight = 0.0
        
        # 模拟各方向评分（实际应计算）
        direction_scores = {
            '高端制造': {'valuation': 65.2, 'trend': 72.1, 'fund': 58.3},
            '信息技术': {'valuation': 68.5, 'trend': 75.3, 'fund': 62.1},
            '新能源': {'valuation': 58.7, 'trend': 65.2, 'fund': 55.8},
            '生物健康': {'valuation': 72.3, 'trend': 58.9, 'fund': 63.4},
            '公用事业': {'valuation': 78.1, 'trend': 52.6, 'fund': 68.2},
            '供应链': {'valuation': 63.8, 'trend': 61.4, 'fund': 59.7},
            '传统升级': {'valuation': 70.5, 'trend': 55.2, 'fund': 61.8},
            '文化消费': {'valuation': 67.9, 'trend': 63.7, 'fund': 57.4},
            '现代农业': {'valuation': 75.6, 'trend': 59.3, 'fund': 64.5}
        }
        
        # 模拟商品调整（实际应计算）
        commodity_adjustments = {
            '高端制造': -0.02,
            '信息技术': -0.01,
            '新能源': -0.03,
            '生物健康': 0.01,
            '公用事业': 0.02,
            '供应链': -0.01,
            '传统升级': 0.01,
            '文化消费': 0.00,
            '现代农业': 0.01
        }
        
        # 模拟情绪得分
        pcr_score = 55.0  # 模拟PCR情绪得分
        
        for direction, base_weight in self.base_weights.items():
            scores = direction_scores[direction]
            
            # 计算基础调整
            base_adjustment = (
                1.0 +
                0.35 * (scores['valuation'] / 100) +  # 情绪权重
                0.30 * (scores['trend'] / 100) +      # 趋势权重
                0.20 * (scores['valuation'] / 100) +  # 估值权重
                0.15 * (scores['fund'] / 100)         # 资金权重
            )
            base_adjustment = np.clip(base_adjustment, 0.7, 1.5)
            
            # 微盘惩罚
            micro_penalty = 0.0
            if micro_liquidity and micro_liquidity.get('status') in ['warning', 'early_warning']:
                # 检查是否包含微盘高暴露指数（简化逻辑）
                if direction in ['文化消费', '高端制造']:
                    micro_penalty = 0.2 if micro_liquidity['status'] == 'warning' else 0.1
            
            # 商品调整
            commodity_adj = commodity_adjustments.get(direction, 0.0)
            
            # 最终调整
            final_adjustment = np.clip(base_adjustment + commodity_adj - micro_penalty, 0.6, 1.6)
            dynamic_weight = base_weight * final_adjustment
            total_weight += dynamic_weight
            
            # 核心指数（简化）
            core_indices = {
                '高端制造': '932042 + 931865',
                '信息技术': '931087 + 930851',
                '新能源': '931798 + 931772',
                '生物健康': '931140 + 931152',
                '公用事业': '000917 + 000937',
                '供应链': '931465 + 931235',
                '传统升级': '932039 + 931231',
                '文化消费': '931066 + 931480',
                '现代农业': '930910 + 930707'
            }
            
            results.append({
                '战略方向': direction,
                '基础权重': f"{base_weight:.1%}",
                '估值得分': f"{scores['valuation']:.1f}",
                '趋势得分': f"{scores['trend']:.1f}",
                '资金得分': f"{scores['fund']:.1f}",
                '情绪得分': f"{pcr_score:.1f}",
                '商品调整': f"{commodity_adj:+.2f}",
                '微盘惩罚': f"{micro_penalty:+.2f}" if micro_penalty > 0 else '-',
                '动态权重': dynamic_weight,
                '核心指数': core_indices[direction]
            })
        
        # 归一化
        output_df = pd.DataFrame(results)
        if total_weight > 0:
            output_df['动态权重'] = output_df['动态权重'] / total_weight
        
        # 现金仓位
        cash_weight = 0.0
        if '防御' in market_state:
            cash_weight = 0.15
        
        # 微盘熔断额外现金
        if micro_liquidity and micro_liquidity.get('status') == 'warning':
            cash_weight += 0.10
        elif micro_liquidity and micro_liquidity.get('status') == 'early_warning':
            cash_weight += 0.05
        
        cash_weight = min(cash_weight, 0.7)
        
        if cash_weight > 0:
            equity_weight = 1 - cash_weight
            output_df['动态权重'] *= equity_weight
            results.append({
                '战略方向': '现金',
                '基础权重': '-',
                '估值得分': '-',
                '趋势得分': '-',
                '资金得分': '-',
                '情绪得分': '-',
                '商品调整': '-',
                '微盘惩罚': '-',
                '动态权重': cash_weight,
                '核心指数': '-'
            })
            output_df = pd.DataFrame(results)
        
        output_df['配置建议'] = output_df['动态权重'].apply(lambda x: f"{x*100:.1f}%")
        
        return output_df[[
            '战略方向', '基础权重', '估值得分', '趋势得分', '资金得分', 
            '情绪得分', '商品调整', '微盘惩罚', '动态权重', '配置建议', '核心指数'
        ]]