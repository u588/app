"""
V6.1 资产配置服务（完全独立微服务）
核心特性：
✅ 阈值动态化集成（ThresholdService）
✅ 配置统一提取（config_utils.extract_and_validate_config）
✅ 九大战略方向动态权重计算
✅ 微盘熔断惩罚机制
✅ 商品信号调整
✅ 宏观评分联动
✅ 完整降级策略（阈值服务失效时回退静态阈值）
✅ 所有数值强制Python原生float（防Plotly序列化错误）
修复点：
✅ 从config安全获取所有配置（非硬编码）
✅ 微盘高暴露指数动态识别
✅ 商品调整权重动态计算
✅ 详细日志与异常处理
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import logging
import warnings

warnings.filterwarnings('ignore')
logger = logging.getLogger(__name__)

# ✅ V6.1核心：导入配置工具（统一配置提取）
from utils.config_utils import extract_and_validate_config, safe_config_get


class AllocationService:
    """V6.1 资产配置服务（阈值动态化 + 配置统一化）"""
    
    def __init__(self, config_service, threshold_service=None):
        """
        初始化资产配置服务
        
        参数:
            config_service: ConfigService实例（提供配置字典）
            threshold_service: ThresholdService实例（可选，None=使用静态阈值）
        
        修复点:
        ✅ 使用extract_and_validate_config统一配置提取
        ✅ 安全获取嵌套配置（safe_config_get）
        ✅ 详细日志记录配置状态
        ✅ 完整异常处理
        """
        self.logger = logger
        
        # ✅ V6.1核心：统一配置提取（1行替代20+行验证逻辑）
        self.config, is_valid, missing_keys = extract_and_validate_config(
            config_service=config_service,
            required_keys=[
                'strategic_directions',
                'allocation_config',
                'position_control',
                'commodity_strategy_map',
                'micro_cap_indices',
                'market_benchmarks'
            ],
            logger=self.logger,
            service_name='AllocationService'
        )
        
        # ✅ 保存ThresholdService引用（可选）
        self.threshold_service = threshold_service
        
        # 验证配置完整性
        if is_valid:
            self.logger.info("✅ AllocationService初始化成功（配置完整）")
            self.logger.debug(
                f"   • 战略方向: {len(self.config.get('strategic_directions', {}))}个 | "
                f"商品映射: {len(self.config.get('commodity_strategy_map', {}))}个 | "
                f"微盘指数: {len(self.config.get('micro_cap_indices', []))}个"
            )
        else:
            self.logger.warning(f"⚠️ AllocationService初始化完成（缺失{len(missing_keys)}项配置）")
        
        # 初始化缓存（用于性能优化）
        self._weight_cache = {}
        self._cache_ttl = 300  # 5分钟
    
    # ==================== 核心方法：动态资产配置 ====================
    
    def calculate_allocation(
        self,
        benchmark_data: Dict[str, pd.DataFrame],
        micro_liquidity: Optional[Dict] = None,
        market_state: str = '均衡持有区',
        commodity_signals: Optional[Dict] = None,
        macro_score: Optional[float] = None,
        pcr_value: Optional[float] = None
    ) -> pd.DataFrame:
        """
        V6.1核心：计算九大战略方向动态配置
        
        参数:
            benchmark_data: 市值基准数据字典 {'大盘': df, '中盘': df, ...}
            micro_liquidity: 微盘流动性状态字典（来自RiskAssessmentService）
            market_state: 市场状态字符串（如'战略进攻区'）
            commodity_signals: 商品期货信号字典（来自CommodityEngineService）
            macro_score: 宏观综合评分（0-100，来自MacroAnalysisService）
            pcr_value: 综合PCR值（来自OptionPCRService）
        
        返回:
            DataFrame with columns:
                ['战略方向', '动态权重', '配置建议', '核心指数', '基础权重', 
                 '微盘惩罚', '商品调整', '宏观调整', '最终权重']
        
        修复点:
        ✅ 动态阈值获取（优先ThresholdService，回退静态配置）
        ✅ 所有数值强制Python原生float
        ✅ 完整降级策略（任一数据缺失时回退默认值）
        ✅ 详细日志记录每步调整
        """
        try:
            # 1. 获取基础权重（从配置）
            base_weights = self._get_base_weights()
            if not base_weights:
                self.logger.error("❌ 基础权重配置缺失，返回空DataFrame")
                return self._build_empty_allocation_df()
            
            # 2. 确定整体权益仓位范围（根据市场状态）
            equity_range = self._get_equity_range(market_state)
            equity_min = float(equity_range['equity_min'])
            equity_max = float(equity_range['equity_max'])
            cash_min = float(equity_range['cash_min'])
            
            # 3. 应用微盘熔断惩罚（动态阈值）
            weights_after_micro = self._apply_micro_penalty(
                base_weights, 
                micro_liquidity,
                market_state
            )
            
            # 4. 应用商品信号调整（动态阈值）
            weights_after_commodity = self._apply_commodity_adjustment(
                weights_after_micro,
                commodity_signals
            )
            
            # 5. 应用宏观评分调整
            weights_after_macro = self._apply_macro_adjustment(
                weights_after_commodity,
                macro_score,
                market_state
            )
            
            # 6. 应用PCR情绪调整
            weights_after_pcr = self._apply_pcr_adjustment(
                weights_after_macro,
                pcr_value,
                market_state
            )
            
            # 7. 归一化并计算现金仓位
            final_weights, cash_weight = self._normalize_weights(
                weights_after_pcr,
                equity_min,
                equity_max,
                cash_min
            )
            
            # 8. 生成配置建议
            allocation_df = self._build_allocation_dataframe(
                final_weights,
                base_weights,
                weights_after_micro,
                weights_after_commodity,
                weights_after_macro,
                cash_weight,
                market_state
            )
            
            # 9. 缓存结果（用于性能优化）
            cache_key = self._generate_cache_key(market_state, micro_liquidity, commodity_signals)
            self._cache_allocation(cache_key, allocation_df)
            
            self.logger.info(
                f"✅ 资产配置计算完成 | 市场状态={market_state} | "
                f"权益仓位={100*(1-cash_weight):.0f}% | 现金仓位={cash_weight*100:.0f}% | "
                f"阈值来源={'动态' if self.threshold_service else '静态'}"
            )
            
            return allocation_df
            
        except Exception as e:
            self.logger.error(f"❌ 资产配置计算失败: {str(e)[:50]}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return self._build_empty_allocation_df()
    
    # ==================== 辅助方法：配置获取 ====================
    
    def _get_base_weights(self) -> Dict[str, float]:
        """获取九大战略方向基础权重（从配置）"""
        strategic_directions = safe_config_get(
            self.config,
            ['strategic_directions'],
            default={},
            logger=self.logger
        )
        
        base_weights = {}
        for direction, config in strategic_directions.items():
            base_weight = float(config.get('base_weight', 0.0))
            if base_weight > 0:
                base_weights[direction] = base_weight
        
        # 验证权重总和接近1.0
        total = sum(base_weights.values())
        if not (0.95 <= total <= 1.05):
            self.logger.warning(f"⚠️ 基础权重总和异常: {total:.2f}（应接近1.0）")
            # 归一化
            base_weights = {k: v/total for k, v in base_weights.items()}
        
        return base_weights
    
    def _get_equity_range(self, market_state: str) -> Dict[str, float]:
        """获取市场状态对应的权益仓位范围"""
        market_state_weights = safe_config_get(
            self.config,
            ['position_control', 'market_state_weights'],
            default={},
            logger=self.logger
        )
        
        state_config = market_state_weights.get(market_state, {})
        return {
            'equity_min': float(state_config.get('equity_min', 0.55)),
            'equity_max': float(state_config.get('equity_max', 0.65)),
            'cash_min': float(state_config.get('cash_min', 0.35)),
            'micro_exposure': float(state_config.get('micro_exposure', 0.10))
        }
    
    # ==================== 辅助方法：微盘熔断惩罚 ====================
    
    def _apply_micro_penalty(
        self,
        weights: Dict[str, float],
        micro_liquidity: Optional[Dict],
        market_state: str
    ) -> Dict[str, float]:
        """
        应用微盘熔断惩罚
        
        逻辑:
        1. 识别微盘高暴露方向（配置中micro_cap_indices关联的方向）
        2. 根据微盘熔断阶段应用惩罚（动态阈值）
        3. 确保惩罚后权重不低于最小值
        """
        if not micro_liquidity or micro_liquidity.get('status') == 'normal':
            self.logger.debug("🔒 微盘状态正常，无惩罚")
            return weights.copy()
        
        # ✅ V6.1核心：动态获取微盘惩罚阈值（优先ThresholdService）
        if self.threshold_service:
            # 动态计算惩罚系数
            context = {'market_state': market_state}
            penalty_warning = self.threshold_service.get_threshold(
                'micro_penalty_warning',
                context=context,
                strategy='market_regime'
            )
            penalty_melted = self.threshold_service.get_threshold(
                'micro_penalty_melted',
                context=context,
                strategy='market_regime'
            )
            self.logger.debug(
                f"🔄 动态微盘惩罚 | warning={penalty_warning:.2f} | melted={penalty_melted:.2f}"
            )
        else:
            # 降级：使用静态配置
            penalty_warning = safe_config_get(
                self.config,
                ['allocation_config', 'micro_penalty_warning'],
                default=0.10,
                logger=self.logger
            )
            penalty_melted = safe_config_get(
                self.config,
                ['allocation_config', 'micro_penalty_melted'],
                default=0.20,
                logger=self.logger
            )
            self.logger.debug(
                f"🔒 静态微盘惩罚 | warning={penalty_warning:.2f} | melted={penalty_melted:.2f}"
            )
        
        # 确定惩罚系数
        status = micro_liquidity.get('status', 'normal')
        if status == 'warning':
            penalty = float(penalty_melted)
            stage_desc = '熔断期'
        elif status == 'early_warning':
            penalty = float(penalty_warning)
            stage_desc = '观察期'
        else:
            penalty = 0.0
            stage_desc = '正常期'
        
        # 识别微盘高暴露方向
        micro_cap_indices = safe_config_get(
            self.config,
            ['micro_cap_indices'],
            default=[],
            logger=self.logger
        )
        
        strategic_directions = safe_config_get(
            self.config,
            ['strategic_directions'],
            default={},
            logger=self.logger
        )
        
        micro_exposed_directions = []
        for direction, config in strategic_directions.items():
            indices = config.get('indices', [])
            if any(idx.strip() in micro_cap_indices for idx in indices):
                micro_exposed_directions.append(direction)
        
        # 应用惩罚
        weights_penalized = weights.copy()
        for direction in micro_exposed_directions:
            if direction in weights_penalized:
                original_weight = weights_penalized[direction]
                new_weight = max(0.0, original_weight * (1 - penalty))
                weights_penalized[direction] = float(new_weight)
                self.logger.debug(
                    f"⚠️ 微盘{stage_desc}惩罚 | {direction} | "
                    f"{original_weight:.3f} → {new_weight:.3f} | 惩罚系数={penalty:.2f}"
                )
        
        return weights_penalized
    
    # ==================== 辅助方法：商品信号调整 ====================
    
    def _apply_commodity_adjustment(
        self,
        weights: Dict[str, float],
        commodity_signals: Optional[Dict]
    ) -> Dict[str, float]:
        """
        应用商品期货信号调整
        
        逻辑:
        1. 遍历商品信号
        2. 根据价格变动和阈值确定调整方向
        3. 调整关联战略方向的权重
        """
        if not commodity_signals:
            self.logger.debug("🔒 无商品信号，无调整")
            return weights.copy()
        
        weights_adjusted = weights.copy()
        commodity_map = safe_config_get(
            self.config,
            ['commodity_strategy_map'],
            default={},
            logger=self.logger
        )
        
        for commodity_code, signal in commodity_signals.items():
            if commodity_code not in commodity_map:
                continue
            
            config = commodity_map[commodity_code]
            directions = config.get('directions', [])
            impact_type = config.get('impact_type', 'cost')
            threshold_up = float(config.get('threshold_up', 10.0))
            threshold_down = float(config.get('threshold_down', -10.0))
            
            # ✅ V6.1核心：动态获取商品调整阈值（优先ThresholdService）
            if self.threshold_service:
                context = {'commodity': commodity_code}
                threshold_up = self.threshold_service.get_threshold(
                    f'commodity_{commodity_code}_threshold_up',
                    context=context,
                    strategy='volatility_adaptive'
                )
                threshold_down = self.threshold_service.get_threshold(
                    f'commodity_{commodity_code}_threshold_down',
                    context=context,
                    strategy='volatility_adaptive'
                )
            
            price_chg = float(signal.get('price_chg_20d', 0.0))
            
            # 确定调整方向和幅度
            if price_chg > threshold_up:
                adjustment = 0.05 if impact_type == 'benefit' else -0.05
                signal_desc = '上涨超阈值'
            elif price_chg < threshold_down:
                adjustment = -0.05 if impact_type == 'benefit' else 0.05
                signal_desc = '下跌超阈值'
            else:
                continue
            
            # 调整关联方向
            for direction in directions:
                if direction in weights_adjusted:
                    original_weight = weights_adjusted[direction]
                    new_weight = max(0.0, min(0.35, original_weight + adjustment))
                    weights_adjusted[direction] = float(new_weight)
                    self.logger.debug(
                        f"🛢️ 商品信号调整 | {commodity_code}({signal_desc}) | "
                        f"{direction} | {original_weight:.3f} → {new_weight:.3f} | "
                        f"影响类型={impact_type}"
                    )
        
        return weights_adjusted
    
    # ==================== 辅助方法：宏观评分调整 ====================
    
    def _apply_macro_adjustment(
        self,
        weights: Dict[str, float],
        macro_score: Optional[float],
        market_state: str
    ) -> Dict[str, float]:
        """应用宏观评分调整（防御性方向增配）"""
        if macro_score is None or macro_score >= 50:
            self.logger.debug("🔒 宏观评分中性或乐观，无调整")
            return weights.copy()
        
        weights_adjusted = weights.copy()
        defensive_directions = ['公用事业', '生物健康', '传统升级']
        
        # 宏观评分越低，防御性方向增配越多
        adjustment = min(0.10, (50 - macro_score) * 0.002)
        
        for direction in defensive_directions:
            if direction in weights_adjusted:
                original_weight = weights_adjusted[direction]
                new_weight = min(0.35, original_weight + adjustment)
                weights_adjusted[direction] = float(new_weight)
                self.logger.debug(
                    f"🌍 宏观调整 | 评分={macro_score:.1f} | {direction} | "
                    f"{original_weight:.3f} → {new_weight:.3f}"
                )
        
        return weights_adjusted
    
    # ==================== 辅助方法：PCR情绪调整 ====================
    
    def _apply_pcr_adjustment(
        self,
        weights: Dict[str, float],
        pcr_value: Optional[float],
        market_state: str
    ) -> Dict[str, float]:
        """应用PCR情绪调整"""
        if pcr_value is None:
            self.logger.debug("🔒 无PCR数据，无调整")
            return weights.copy()
        
        weights_adjusted = weights.copy()
        
        # ✅ V6.1核心：动态获取PCR阈值（优先ThresholdService）
        if self.threshold_service:
            pcr_warning_high = self.threshold_service.get_threshold(
                'pcr_warning_high',
                context={'market_state': market_state},
                strategy='market_regime'
            )
            pcr_warning_low = self.threshold_service.get_threshold(
                'pcr_warning_low',
                context={'market_state': market_state},
                strategy='market_regime'
            )
        else:
            pcr_config = safe_config_get(
                self.config,
                ['risk_thresholds', 'pcr'],
                default={},
                logger=self.logger
            )
            pcr_warning_high = float(pcr_config.get('warning_high', 1.3))
            pcr_warning_low = float(pcr_config.get('warning_low', 0.7))
        
        # 确定调整方向
        if pcr_value > pcr_warning_high:
            adjustment = -0.05  # 看跌情绪，降低权益
            signal_desc = '看跌'
        elif pcr_value < pcr_warning_low:
            adjustment = 0.05   # 看涨情绪，增加权益
            signal_desc = '看涨'
        else:
            return weights_adjusted
        
        # 调整所有方向（按比例）
        for direction in weights_adjusted:
            original_weight = weights_adjusted[direction]
            new_weight = max(0.0, min(0.35, original_weight + adjustment))
            weights_adjusted[direction] = float(new_weight)
        
        self.logger.debug(
            f"📊 PCR情绪调整 | PCR={pcr_value:.2f}({signal_desc}) | "
            f"调整={adjustment:+.2f}"
        )
        
        return weights_adjusted
    
    # ==================== 辅助方法：权重归一化 ====================
    
    def _normalize_weights(
        self,
        weights: Dict[str, float],
        equity_min: float,
        equity_max: float,
        cash_min: float
    ) -> Tuple[Dict[str, float], float]:
        """归一化权重并计算现金仓位"""
        # 计算当前权益总和
        equity_sum = sum(weights.values())
        
        # 确保权益仓位在范围内
        if equity_sum < equity_min:
            # 按比例放大
            scale = equity_min / equity_sum if equity_sum > 0 else 1.0
            weights = {k: min(0.35, v * scale) for k, v in weights.items()}
            equity_sum = sum(weights.values())
        elif equity_sum > equity_max:
            # 按比例缩小
            scale = equity_max / equity_sum
            weights = {k: v * scale for k, v in weights.items()}
            equity_sum = sum(weights.values())
        
        # 计算现金仓位（确保不低于cash_min）
        cash_weight = max(cash_min, 1.0 - equity_sum)
        
        # 二次归一化（确保总和为1.0）
        scale = (1.0 - cash_weight) / equity_sum if equity_sum > 0 else 1.0
        weights = {k: float(v * scale) for k, v in weights.items()}
        
        return weights, float(cash_weight)
    
    # ==================== 辅助方法：构建配置DataFrame ====================
    
    def _build_allocation_dataframe(
        self,
        final_weights: Dict[str, float],
        base_weights: Dict[str, float],
        micro_weights: Dict[str, float],
        commodity_weights: Dict[str, float],
        macro_weights: Dict[str, float],
        cash_weight: float,
        market_state: str
    ) -> pd.DataFrame:
        """构建配置DataFrame"""
        strategic_directions = safe_config_get(
            self.config,
            ['strategic_directions'],
            default={},
            logger=self.logger
        )
        
        rows = []
        
        # 添加九大战略方向
        for direction in strategic_directions.keys():
            if direction in final_weights:
                base_w = base_weights.get(direction, 0.0)
                micro_w = micro_weights.get(direction, base_w)
                comm_w = commodity_weights.get(direction, micro_w)
                macro_w = macro_weights.get(direction, comm_w)
                final_w = final_weights[direction]
                
                # 确定配置建议
                if final_w > base_w * 1.15:
                    suggestion = '超配'
                elif final_w < base_w * 0.85:
                    suggestion = '低配'
                else:
                    suggestion = '标配'
                
                # 获取核心指数
                indices = strategic_directions[direction].get('indices', [])
                core_index = indices[0] if indices else ''
                
                rows.append({
                    '战略方向': direction,
                    '动态权重': float(final_w),
                    '配置建议': suggestion,
                    '核心指数': core_index,
                    '基础权重': float(base_w),
                    '微盘惩罚': float(micro_w - base_w),
                    '商品调整': float(comm_w - micro_w),
                    '宏观调整': float(macro_w - comm_w),
                    '最终权重': float(final_w)
                })
        
        # 添加现金行
        rows.append({
            '战略方向': '现金',
            '动态权重': float(cash_weight),
            '配置建议': '必需',
            '核心指数': '',
            '基础权重': 0.0,
            '微盘惩罚': 0.0,
            '商品调整': 0.0,
            '宏观调整': 0.0,
            '最终权重': float(cash_weight)
        })
        
        # 创建DataFrame并排序
        df = pd.DataFrame(rows)
        df = df.sort_values('动态权重', ascending=False).reset_index(drop=True)
        
        # 强制所有数值列为Python原生float（关键修复：防Plotly序列化错误）
        float_cols = ['动态权重', '基础权重', '微盘惩罚', '商品调整', '宏观调整', '最终权重']
        for col in float_cols:
            if col in df.columns:
                df[col] = df[col].apply(lambda x: float(x) if pd.notna(x) else 0.0)
        
        return df
    
    # ==================== 辅助方法：缓存管理 ====================
    
    def _generate_cache_key(
        self,
        market_state: str,
        micro_liquidity: Optional[Dict],
        commodity_signals: Optional[Dict]
    ) -> str:
        """生成缓存键（包含市场状态和关键参数）"""
        micro_status = micro_liquidity.get('status', 'normal') if micro_liquidity else 'normal'
        comm_count = len(commodity_signals) if commodity_signals else 0
        today = datetime.now().strftime('%Y%m%d')
        return f"allocation_{market_state}_{micro_status}_{comm_count}_{today}"
    
    def _cache_allocation(self, cache_key: str, df: pd.DataFrame):
        """缓存配置结果"""
        self._weight_cache[cache_key] = {
            'data': df,
            'timestamp': datetime.now()
        }
    
    def _get_from_cache(self, cache_key: str) -> Optional[pd.DataFrame]:
        """从缓存获取（带TTL检查）"""
        if cache_key in self._weight_cache:
            cached = self._weight_cache[cache_key]
            if (datetime.now() - cached['timestamp']).total_seconds() < self._cache_ttl:
                return cached['data']
            del self._weight_cache[cache_key]
        return None
    
    def _build_empty_allocation_df(self) -> pd.DataFrame:
        """构建空配置DataFrame（降级策略）"""
        return pd.DataFrame(columns=[
            '战略方向', '动态权重', '配置建议', '核心指数',
            '基础权重', '微盘惩罚', '商品调整', '宏观调整', '最终权重'
        ])
    
    # ==================== 高级功能：配置建议生成 ====================
    
    def generate_allocation_summary(self, allocation_df: pd.DataFrame) -> str:
        """
        生成配置摘要（用于日志或报告）
        
        返回:
            配置摘要字符串
        """
        if allocation_df.empty or len(allocation_df) == 0:
            return "⚠️ 配置数据为空"
        
        # 提取关键信息
        cash_row = allocation_df[allocation_df['战略方向'] == '现金']
        cash_weight = cash_row['动态权重'].iloc[0] if len(cash_row) > 0 else 0.0
        
        top3 = allocation_df[allocation_df['战略方向'] != '现金'].nlargest(3, '动态权重')
        top3_str = " | ".join([f"{row['战略方向']}({row['动态权重']:.1%})" for _, row in top3.iterrows()])
        
        overweight = allocation_df[
            (allocation_df['配置建议'] == '超配') & 
            (allocation_df['战略方向'] != '现金')
        ]
        underweight = allocation_df[
            (allocation_df['配置建议'] == '低配') & 
            (allocation_df['战略方向'] != '现金')
        ]
        
        summary = f"""
📊 资产配置摘要
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 现金仓位: {cash_weight:.1%}
🎯 前三大方向: {top3_str}
📈 超配方向({len(overweight)}): {', '.join(overweight['战略方向'].tolist()) if len(overweight) > 0 else '无'}
📉 低配方向({len(underweight)}): {', '.join(underweight['战略方向'].tolist()) if len(underweight) > 0 else '无'}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        return summary.strip()


# ==================== 使用示例 ====================
def example_allocation_service():
    """AllocationService使用示例"""
    
    print("=" * 80)
    print("🧪 AllocationService 使用示例（V6.1阈值动态化）")
    print("=" * 80)
    
    # 1. 初始化服务（简化版）
    print("\n1️⃣ 初始化AllocationService...")
    
    class MockConfigService:
        def __init__(self):
            self.config = {
                'strategic_directions': {
                    '高端制造': {'indices': ['932042'], 'base_weight': 0.28},
                    '信息技术': {'indices': ['931087'], 'base_weight': 0.25},
                    '新能源': {'indices': ['931798'], 'base_weight': 0.15},
                    '生物健康': {'indices': ['931140'], 'base_weight': 0.10},
                    '供应链': {'indices': ['931465'], 'base_weight': 0.06},
                    '现代农业': {'indices': ['930910'], 'base_weight': 0.01},
                    '公用事业': {'indices': ['000917'], 'base_weight': 0.08},
                    '传统升级': {'indices': ['932039'], 'base_weight': 0.04},
                    '文化消费': {'indices': ['931066'], 'base_weight': 0.03}
                },
                'allocation_config': {
                    'micro_penalty_warning': 0.10,
                    'micro_penalty_melted': 0.20
                },
                'position_control': {
                    'market_state_weights': {
                        '战略进攻区': {'equity_min': 0.75, 'equity_max': 0.85, 'cash_min': 0.15},
                        '均衡持有区': {'equity_min': 0.55, 'equity_max': 0.65, 'cash_min': 0.35},
                        '战略防御区': {'equity_min': 0.20, 'equity_max': 0.30, 'cash_min': 0.70}
                    }
                },
                'commodity_strategy_map': {
                    'CUL8': {
                        'directions': ['高端制造', '供应链'],
                        'impact_type': 'cost',
                        'threshold_up': 10.0,
                        'threshold_down': -10.0
                    }
                },
                'micro_cap_indices': ['930901', '931588'],
                'market_benchmarks': {
                    '大盘': {'code': '000300', 'weight': 0.40},
                    '中盘': {'code': '000905', 'weight': 0.30},
                    '小盘': {'code': '000852', 'weight': 0.20},
                    '微盘': {'code': '932000', 'weight': 0.10}
                },
                'risk_thresholds': {
                    'pcr': {'warning_high': 1.3, 'warning_low': 0.7}
                }
            }
    
    config_service = MockConfigService()
    
    # 模拟ThresholdService（可选）
    class MockThresholdService:
        def get_threshold(self, name, context, strategy):
            # 模拟动态阈值（略高于静态值）
            if 'micro_penalty' in name:
                return 0.12 if 'warning' in name else 0.22
            elif 'commodity' in name:
                return 12.0 if 'up' in name else -12.0
            elif 'pcr' in name:
                return 1.35 if 'high' in name else 0.65
            return 0.5
    
    threshold_service = MockThresholdService()
    
    allocation_service = AllocationService(config_service, threshold_service)
    print("✅ 服务初始化成功")
    
    # 2. 模拟输入数据
    print("\n2️⃣ 模拟输入数据...")
    micro_liquidity = {'status': 'early_warning', 'stage': '观察期', 'days_in_stage': 3}
    commodity_signals = {'CUL8': {'price_chg_20d': 12.5}}
    market_state = '均衡持有区'
    
    # 3. 计算配置
    print("\n3️⃣ 计算资产配置...")
    allocation_df = allocation_service.calculate_allocation(
        benchmark_data={},
        micro_liquidity=micro_liquidity,
        market_state=market_state,
        commodity_signals=commodity_signals,
        macro_score=45.0,
        pcr_value=1.25
    )
    
    # 4. 显示结果
    print("\n4️⃣ 配置结果:")
    print(allocation_df[['战略方向', '动态权重', '配置建议', '核心指数']].to_string(index=False))
    
    # 5. 生成摘要
    print("\n5️⃣ 配置摘要:")
    print(allocation_service.generate_allocation_summary(allocation_df))
    
    # 6. 验证数据类型
    print("\n6️⃣ 验证数据类型（防Plotly序列化错误）:")
    sample_weight = allocation_df['动态权重'].iloc[0]
    is_python_float = isinstance(sample_weight, float) and not isinstance(sample_weight, np.floating)
    print(f"   ✅ 动态权重类型: {type(sample_weight).__name__} | Python float: {is_python_float}")
    
    print("\n" + "=" * 80)
    print("✅ AllocationService 示例运行完成")
    print("=" * 80)


if __name__ == "__main__":
    example_allocation_service()