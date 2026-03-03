# ==================== 4.1.1 市场状态服务 （市场状态判定：九宫格定位）MarketStateService ====================
class MarketStateService:
    """市场状态服务（Jupyter调试版）"""
    
    def __init__(self, data_service: DataLoadingService, config_service: ConfigService):
        """初始化市场状态服务"""
        self.data_service = data_service
        self.config_service = config_service
        print("✅ 市场状态服务初始化成功")
    
    def calculate_valuation_score(self, df: pd.DataFrame, index_code: str) -> float:
        """计算估值评分（0-100）"""
        if len(df) < 250:
            return 50.0
        
        # 模拟PE分位数（实际应从PE数据计算）
        current_price = df['close'].iloc[-1]
        price_history = df['close'].iloc[-250:-1]
        price_percentile = (price_history < current_price).mean() * 100
        
        # 估值越低得分越高
        return 100 - price_percentile
    
    def calculate_trend_score(self, df: pd.DataFrame) -> float:
        """计算趋势评分（0-100）"""
        if len(df) < 120:
            return 50.0
        
        # 20日动量
        if len(df) >= 21:
            mom_20 = (df['close'].iloc[-1] / df['close'].iloc[-21] - 1) * 100
        else:
            mom_20 = 0
        
        # 价格在20日均线之上天数占比
        if 'ma_20' not in df.columns:
            df['ma_20'] = df['close'].rolling(20).mean()
        
        if len(df) >= 20:
            above_ma20 = (df['close'].iloc[-20:] > df['ma_20'].iloc[-20:]).mean() * 100
        else:
            above_ma20 = 50
        
        # 综合评分
        trend_score = 0.6 * mom_20 + 0.4 * above_ma20
        return np.clip(trend_score, 0, 100)
    
    def determine_market_state(
        self,
        benchmark_data: Dict[str, pd.DataFrame]
    ) -> Tuple[str, float, float, Dict]:
        """
        判定市场状态
        
        返回:
            (市场状态, 估值安全边际, 趋势动能强度, 各层诊断)
        """
        layer_scores = {}
        valid_layers = []
        
        for size in ['大盘', '中盘', '小盘']:
            df = benchmark_data.get(size, pd.DataFrame())
            if len(df) >= 250:
                code = self.config_service.get_config()['market_benchmarks'][size]['code']
                val_score = self.calculate_valuation_score(df, code)
                trend_score = self.calculate_trend_score(df)
                layer_scores[size] = {
                    'valuation': val_score,
                    'trend': trend_score,
                    'composite': 0.6 * val_score + 0.4 * trend_score
                }
                valid_layers.append(size)
        
        # 计算加权市场得分
        if not valid_layers:
            return "数据不足", 50.0, 50.0, {}
        
        total_weight = sum(self.config_service.get_config()['market_benchmarks'][size]['weight'] 
                          for size in valid_layers)
        
        market_val_score = sum(
            layer_scores[size]['valuation'] * 
            self.config_service.get_config()['market_benchmarks'][size]['weight']
            for size in valid_layers
        ) / total_weight
        
        market_trend_score = sum(
            layer_scores[size]['trend'] * 
            self.config_service.get_config()['market_benchmarks'][size]['weight']
            for size in valid_layers
        ) / total_weight
        
        # 状态映射
        val_state = '低估' if market_val_score < 40 else ('合理' if market_val_score <= 60 else '高估')
        trend_state = '弱势' if market_trend_score < 40 else ('中性' if market_trend_score <= 70 else '强势')
        
        state_map = {
            ('低估', '强势'): '战略进攻区',
            ('合理', '强势'): '积极配置区',
            ('高估', '强势'): '防御进攻区',
            ('低估', '中性'): '左侧布局区',
            ('合理', '中性'): '均衡持有区',
            ('高估', '中性'): '防御观望区',
            ('低估', '弱势'): '左侧防御区',
            ('合理', '弱势'): '谨慎持有区',
            ('高估', '弱势'): '战略防御区'
        }
        
        market_state = state_map.get((val_state, trend_state), '均衡持有区')
        
        # 各层诊断
        layer_diagnosis = {}
        for size in ['大盘', '中盘', '小盘', '微盘']:
            if size in layer_scores:
                scores = layer_scores[size]
                val_status = '↑低估' if scores['valuation'] > 65 else ('↓高估' if scores['valuation'] < 35 else '→合理')
                trend_status = '↑强势' if scores['trend'] > 70 else ('↓弱势' if scores['trend'] < 40 else '→中性')
                layer_diagnosis[size] = f"{val_status}{trend_status} | 估值{scores['valuation']:.0f} 趋势{scores['trend']:.0f}"
            else:
                layer_diagnosis[size] = "数据缺失"
        
        return market_state, market_val_score, market_trend_score, layer_diagnosis