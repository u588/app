# ==================== 3.1 数据加载服务 （统一数据加载 + 缓存管理） DataLoadingService ====================
class DataLoadingService:
    """数据加载服务（Jupyter调试版）"""
    
    def __init__(self, config_service: ConfigService):
        """初始化数据加载服务"""
        self.config_service = config_service
        self.cache = {}
        self.cache_hits = 0
        self.cache_misses = 0
        print("✅ 数据加载服务初始化成功")
    
    def load_index_data(
        self, 
        index_code: str, 
        min_days: int = 500,
        use_cache: bool = True
    ) -> pd.DataFrame:
        """
        加载指数数据
        
        参数:
            index_code: 指数代码
            min_days: 最小数据天数
            use_cache: 是否使用缓存
        
        返回:
            DataFrame with columns: datetime, open, high, low, close, amount
        """
        cache_key = f"index_{index_code}_{min_days}"
        
        # 检查缓存
        if use_cache and cache_key in self.cache:
            self.cache_hits += 1
            return self.cache[cache_key].copy()
        
        self.cache_misses += 1
        
        # 模拟数据加载（实际应从数据库/TDX加载）
        print(f"🔍 加载指数数据: {index_code} (模拟数据)")
        dates = pd.date_range(end=datetime.now(), periods=min_days)
        df = pd.DataFrame({
            'datetime': dates,
            'open': np.random.randn(min_days).cumsum() + 100,
            'high': np.random.randn(min_days).cumsum() + 101,
            'low': np.random.randn(min_days).cumsum() + 99,
            'close': np.random.randn(min_days).cumsum() + 100,
            'amount': np.random.rand(min_days) * 1000 + 500
        })
        
        # 计算技术指标
        df['return_1d'] = df['close'].pct_change()
        df['volatility_20'] = df['return_1d'].rolling(20).std() * np.sqrt(250) * 100
        df['ma_20'] = df['close'].rolling(20).mean()
        df['ma_60'] = df['close'].rolling(60).mean()
        df['volume_ma20'] = df['amount'].rolling(20).mean()
        
        # 缓存数据
        if use_cache:
            self.cache[cache_key] = df.copy()
        
        return df
    
    def load_derivative_data(
        self,
        code: str,
        market_code: int,
        days: int = 60
    ) -> pd.DataFrame:
        """加载衍生品数据（模拟）"""
        print(f"🔍 加载衍生品数据: {code} (市场{market_code}, 模拟数据)")
        dates = pd.date_range(end=datetime.now(), periods=days)
        df = pd.DataFrame({
            'datetime': dates,
            'open': np.random.randn(days).cumsum() + 100,
            'high': np.random.randn(days).cumsum() + 101,
            'low': np.random.randn(days).cumsum() + 99,
            'close': np.random.randn(days).cumsum() + 100,
            'volume': np.random.rand(days) * 10000 + 5000,
            'open_interest': np.random.rand(days) * 50000 + 20000
        })
        return df
    
    def preload_benchmarks(self) -> Dict[str, pd.DataFrame]:
        """预加载市值基准数据"""
        print("🔄 预加载市值基准数据...")
        benchmarks = {}
        config = self.config_service.get_config()
        
        for size, info in config['market_benchmarks'].items():
            df = self.load_index_data(info['code'], min_days=500)
            benchmarks[size] = df
            print(f"  ✅ {size} ({info['code']}): {len(df)} 条")
        
        return benchmarks
    
    def get_cache_stats(self) -> Dict:
        """获取缓存统计信息"""
        total = self.cache_hits + self.cache_misses
        hit_rate = self.cache_hits / total if total > 0 else 0
        return {
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'hit_rate': f"{hit_rate:.1%}",
            'cache_size': len(self.cache)
        }
    
    def clear_cache(self):
        """清空缓存"""
        self.cache.clear()
        self.cache_hits = 0
        self.cache_misses = 0
        print("✅ 缓存已清空")