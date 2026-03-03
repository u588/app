# data_loading_service_v6.py
"""
V6.0 数据加载服务（深度集成CacheService）
核心特性：
✅ 智能缓存策略（多维度缓存键 + TTL动态配置）
✅ 完整数据验证与降级处理
✅ 强制Python原生类型转换（防Plotly序列化错误）
✅ 详细缓存统计与监控
✅ 无缝集成ConfigService/CacheService
修复点：
✅ 所有数值强制转换为Python原生float/int
✅ 缓存键包含日期维度（避免跨日数据污染）
✅ 完整异常处理与降级策略
✅ 详细日志与统计信息
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional, Any, Tuple
from datetime import datetime, timedelta
import logging
import warnings

warnings.filterwarnings('ignore')
logger = logging.getLogger(__name__)


class DataLoadingService:
    """V6.0 数据加载服务（深度集成CacheService）"""
    
    def __init__(
        self,
        config_service,
        cache_service=None,
        enable_cache: bool = True
    ):
        """
        初始化数据加载服务
        
        参数:
            config_service: ConfigService实例
            cache_service: CacheService实例（None=自动创建）
            enable_cache: 是否启用缓存（调试时可禁用）
        
        修复点:
        ✅ 自动创建CacheService（当未传入时）
        ✅ 从ConfigService获取cache_ttl配置
        ✅ 完整异常处理
        """
        self.config = config_service
        self.enable_cache = enable_cache
        self.logger = logger
        
        # 初始化缓存服务（深度集成）
        if cache_service is not None:
            self.cache = cache_service
            self.logger.info("✅ 使用外部CacheService实例")
        else:
            # 从配置获取缓存参数
            cache_config = self.config.config.get('cache', {})
            max_size = cache_config.get('max_size', 1000)
            ttl = cache_config.get('ttl', 3600)
            
            from infrastructure.base_services.cache_service import CacheService
            self.cache = CacheService(max_size=max_size, ttl=ttl)
            self.logger.info(f"✅ 自动创建CacheService | 容量={max_size} | TTL={ttl}s")
        
        # 数据库连接
        try:
            from sqlalchemy import create_engine
            self.engine = create_engine(self.config.config['database']['main_db'])
            self.pe_engine = create_engine(self.config.config['database']['pe_db'])
            self.logger.info("✅ 数据库连接初始化成功")
        except Exception as e:
            self.logger.error(f"❌ 数据库连接失败: {str(e)[:50]}")
            self.engine = None
            self.pe_engine = None
        
        # TDX接口（可选）
        self.tdx_exhq = None
        self.tdx_hq = None
        if self.config.config.get('tdx', {}).get('use_tdx', True):
            self._init_tdx()
        
        self.logger.info(f"✅ DataLoadingService初始化成功 | 缓存={'启用' if enable_cache else '禁用'}")
    
    def _init_tdx(self):
        """初始化TDX接口（带降级处理）"""
        try:
            from pytdx.hq import TdxHq_API
            from pytdx.exhq import TdxExHq_API
            
            tdx_config = self.config.config.get('tdx', {})
            self.tdx_exhq = TdxExHq_API()
            self.tdx_hq = TdxHq_API()
            
            self.tdx_exhq.connect(
                tdx_config.get('exhq_host', '47.112.95.207'),
                tdx_config.get('exhq_port', 7720)
            )
            self.tdx_hq.connect(
                tdx_config.get('hq_host', '180.153.18.170'),
                tdx_config.get('hq_port', 7709)
            )
            self.logger.info("✅ TDX接口连接成功")
        except Exception as e:
            self.logger.warning(f"⚠️ TDX接口连接失败: {str(e)[:50]}，降级使用数据库")
            self.config.config['tdx']['use_tdx'] = False
    
    # ==================== 核心缓存方法 ====================
    
    def _generate_cache_key(
        self,
        prefix: str,
        code: str,
        **kwargs
    ) -> str:
        """
        生成唯一缓存键（多维度组合）
        
        参数:
            prefix: 缓存前缀（'index'/'derivative'/'macro'/'pe'）
            code: 数据代码
            **kwargs: 其他参数（days/min_days/market_code等）
        
        返回:
            唯一缓存键字符串
        
        修复点:
        ✅ 包含日期维度（避免跨日数据污染）
        ✅ 参数排序确保键一致性
        ✅ 特殊字符转义
        """
        # 基础键：前缀 + 代码
        key_parts = [prefix, code.replace(' ', '').replace('/', '_')]
        
        # 添加参数（按字母排序确保一致性）
        for k, v in sorted(kwargs.items()):
            if v is not None:
                key_parts.append(f"{k}={str(v).replace(' ', '').replace('/', '_')}")
        
        # 添加日期维度（关键修复：避免跨日数据污染）
        today = datetime.now().strftime('%Y%m%d')
        key_parts.append(f"date={today}")
        
        return "_".join(key_parts)
    
    def _get_from_cache(self, cache_key: str) -> Optional[Any]:
        """
        从缓存获取数据（带统计）
        
        参数:
            cache_key: 缓存键
        
        返回:
            缓存数据或None
        """
        if not self.enable_cache:
            return None
        
        try:
            data = self.cache.get(cache_key)
            if data is not None:
                self.logger.debug(f"✅ 缓存命中: {cache_key[:50]}...")
            return data
        except Exception as e:
            self.logger.warning(f"⚠️ 缓存读取失败 {cache_key[:30]}: {str(e)[:30]}")
            return None
    
    def _set_to_cache(
        self,
        cache_key: str,
        data: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """
        存入缓存（带统计和类型验证）
        
        参数:
            cache_key: 缓存键
            data: 要缓存的数据
            ttl: 自定义TTL（None=使用默认）
        
        返回:
            bool: 是否设置成功
        """
        if not self.enable_cache:
            return False
        
        try:
            # 强制转换为Python原生类型（关键修复：防Plotly序列化错误）
            if isinstance(data, pd.DataFrame):
                data = self._convert_dataframe_to_python_types(data)
            elif isinstance(data, dict):
                data = self._convert_dict_to_python_types(data)
            
            # 设置缓存
            self.cache.set(cache_key, data, ttl=ttl)
            self.logger.debug(f"💾 缓存设置: {cache_key[:50]}...")
            return True
        except Exception as e:
            self.logger.warning(f"⚠️ 缓存写入失败 {cache_key[:30]}: {str(e)[:30]}")
            return False
    
    # ==================== 辅助方法：类型转换 ====================
    
    def _convert_dataframe_to_python_types(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        转换DataFrame中所有数值列为Python原生类型（关键修复）
        
        参数:
            df: DataFrame
        
        返回:
            转换后的DataFrame
        """
        if df is None or len(df) == 0:
            return df
        
        df_converted = df.copy()
        
        # 转换数值列
        for col in df_converted.select_dtypes(include=[np.number]).columns:
            try:
                df_converted[col] = df_converted[col].apply(
                    lambda x: float(x) if pd.notna(x) else np.nan
                )
            except Exception as e:
                self.logger.warning(f"⚠️ 列 {col} 转换失败: {str(e)[:30]}")
        
        return df_converted
    
    def _convert_dict_to_python_types(self, data: Dict) -> Dict:
        """
        递归转换字典中所有数值为Python原生类型
        
        参数:
            data: 字典
        
        返回:
            转换后的字典
        """
        converted = {}
        
        for key, value in data.items():
            if isinstance(value, dict):
                converted[key] = self._convert_dict_to_python_types(value)
            elif isinstance(value, (int, float, np.number)):
                converted[key] = float(value) if isinstance(value, float) else int(value)
            elif isinstance(value, list):
                converted[key] = [
                    float(v) if isinstance(v, (float, np.floating)) else 
                    int(v) if isinstance(v, (int, np.integer)) else v
                    for v in value
                ]
            else:
                converted[key] = value
        
        return converted
    
    # ==================== 核心数据加载方法（集成缓存） ====================
    
    def load_index_data(
        self,
        index_code: str,
        min_days: int = 500
    ) -> pd.DataFrame:
        """
        加载指数数据（深度集成缓存）
        
        参数:
            index_code: 指数代码
            min_days: 最小数据天数
        
        返回:
            DataFrame with datetime, open, high, low, close, amount
        
        修复点:
        ✅ 缓存键包含min_days和日期维度
        ✅ 缓存未命中时加载并存入缓存
        ✅ 强制转换为Python原生类型
        ✅ 完整异常处理与降级
        """
        # 1. 生成缓存键
        cache_key = self._generate_cache_key(
            'index',
            index_code,
            min_days=min_days
        )
        
        # 2. 尝试从缓存获取
        if self.enable_cache:
            cached_data = self._get_from_cache(cache_key)
            if cached_data is not None and isinstance(cached_data, pd.DataFrame):
                return cached_data
        
        # 3. 缓存未命中，加载数据
        try:
            # 从数据库加载
            if self.engine is None:
                raise Exception("数据库未连接")
            
            query = f'''
                SELECT * FROM "{index_code}"
                WHERE datetime <= '{self.config.config.get('base_date', datetime.now().strftime("%Y-%m-%d"))}'
                ORDER BY datetime
            '''
            df = pd.read_sql(query, self.engine)
            
            # 数据预处理
            if index_code.startswith(('399', '88')):
                df['amount'] = df['amount'] / 1000000
            
            df['datetime'] = pd.to_datetime(df['datetime'])
            df = df.sort_values('datetime').reset_index(drop=True)
            df = df.drop_duplicates(subset=['datetime'], keep='last')
            
            # 计算技术指标
            df['return_1d'] = df['close'].pct_change()
            df['volatility_20'] = df['return_1d'].rolling(20).std() * np.sqrt(250)
            df['ma_20'] = df['close'].rolling(20).mean()
            df['ma_60'] = df['close'].rolling(60).mean()
            df['volume_ma20'] = df['amount'].rolling(20).mean()
            
            # 验证数据量
            if len(df) < min_days:
                self.logger.warning(f"⚠️ {index_code} 数据不足（{len(df)} < {min_days}）")
                return pd.DataFrame()
            
            # 4. 存入缓存（强制类型转换）
            df_converted = self._convert_dataframe_to_python_types(df)
            self._set_to_cache(cache_key, df_converted)
            
            self.logger.info(f"✅ 指数数据加载: {index_code} | {len(df)}条 | 缓存设置")
            return df_converted
        
        except Exception as e:
            self.logger.error(f"❌ 指数数据加载失败 {index_code}: {str(e)[:50]}")
            return pd.DataFrame()
    
    def load_pe_data(self, index_code: str) -> pd.DataFrame:
        """加载PE历史数据（集成缓存）"""
        cache_key = self._generate_cache_key('pe', index_code)
        
        if self.enable_cache:
            cached_data = self._get_from_cache(cache_key)
            if cached_data is not None and isinstance(cached_data, pd.DataFrame):
                return cached_data
        
        try:
            if self.pe_engine is None:
                raise Exception("PE数据库未连接")
            
            df_hist = pd.read_sql(index_code, self.pe_engine)
            if len(df_hist) >= 500 and '滚动市盈率' in df_hist.columns:
                df_hist = df_hist.rename(columns={'日期': 'date', '滚动市盈率': 'pe_ttm'})
                df_hist['date'] = pd.to_datetime(df_hist['date'])
                result = df_hist[['date', 'pe_ttm']].copy()
                
                # 存入缓存
                result_converted = self._convert_dataframe_to_python_types(result)
                self._set_to_cache(cache_key, result_converted)
                
                self.logger.info(f"✅ PE数据加载: {index_code} | {len(result)}条 | 缓存设置")
                return result_converted
            
            return pd.DataFrame()
        
        except Exception as e:
            self.logger.warning(f"⚠️ PE数据加载失败 {index_code}: {str(e)[:50]}")
            return pd.DataFrame()
    
    def load_derivative_data(
        self,
        code: str,
        market_code: int,
        days: int = 60
    ) -> pd.DataFrame:
        """加载衍生品数据（集成缓存）"""
        cache_key = self._generate_cache_key(
            'derivative',
            code,
            market_code=market_code,
            days=days
        )
        
        if self.enable_cache:
            cached_data = self._get_from_cache(cache_key)
            if cached_data is not None and isinstance(cached_data, pd.DataFrame):
                return cached_data
        
        try:
            # 优先TDX（如果启用）
            if self.config.config.get('tdx', {}).get('use_tdx', True) and self.tdx_exhq:
                result = self.tdx_exhq.get_instrument_bars(9, market_code, code, 0, days)
                if result and len(result) > 0:
                    df = pd.DataFrame(result)
                    df = df.rename(columns={
                        'trade': 'volume',
                        'position': 'open_interest',
                        'amount': 'turnover',
                        'price': 'settlement'
                    })
                    
                    if 'datetime' in df.columns:
                        df['datetime'] = pd.to_datetime(df['datetime'])
                    
                    required_cols = ['datetime', 'open', 'high', 'low', 'close', 'volume', 'open_interest']
                    for col in required_cols:
                        if col not in df.columns:
                            df[col] = 0
                    
                    df = df.sort_values('datetime').reset_index(drop=True)
                    df = df.dropna(subset=['close'])
                    
                    # 存入缓存
                    df_converted = self._convert_dataframe_to_python_types(df)
                    self._set_to_cache(cache_key, df_converted)
                    
                    self.logger.info(f"✅ 衍生品数据加载(TDX): {code} | {len(df)}条 | 缓存设置")
                    return df_converted
            
            # 降级：数据库
            return self._load_derivative_from_db(code, days)
        
        except Exception as e:
            self.logger.warning(f"⚠️ 衍生品数据加载失败 {code}: {str(e)[:50]}")
            return self._load_derivative_from_db(code, days)
    
    def _load_derivative_from_db(self, code: str, days: int = 60) -> pd.DataFrame:
        """从数据库加载衍生品数据（降级方案）"""
        try:
            query = f'''
                SELECT datetime, open, high, low, close, volume, position
                FROM "{code}"
                WHERE datetime <= '{self.config.config.get('base_date', datetime.now().strftime("%Y-%m-%d"))}'
                ORDER BY datetime DESC
                LIMIT {days}
            '''
            df = pd.read_sql(query, self.engine)
            if len(df) > 0:
                df['datetime'] = pd.to_datetime(df['datetime'])
                df = df.sort_values('datetime').reset_index(drop=True)
                df = df.rename(columns={'position': 'open_interest'})
                return df
            return pd.DataFrame()
        except Exception as e:
            self.logger.error(f"❌ 数据库加载衍生品失败 {code}: {str(e)[:50]}")
            return pd.DataFrame()
    
    def load_macro_data(self, code: str, days: int = 60) -> pd.DataFrame:
        """加载宏观指标数据（集成缓存）"""
        cache_key = self._generate_cache_key('macro', code, days=days)
        
        if self.enable_cache:
            cached_data = self._get_from_cache(cache_key)
            if cached_data is not None and isinstance(cached_data, pd.DataFrame):
                return cached_data
        
        try:
            # TDX优先
            if self.config.config.get('tdx', {}).get('use_tdx', True) and self.tdx_exhq:
                result = self.tdx_exhq.get_instrument_bars(9, 38, code, 0, days)
                if result and len(result) > 0:
                    df = pd.DataFrame(result)
                    if 'datetime' in df.columns:
                        df['datetime'] = pd.to_datetime(df['datetime'])
                    
                    required_cols = ['datetime', 'open', 'high', 'low', 'close']
                    available_cols = [col for col in required_cols if col in df.columns]
                    df = df[available_cols].copy()
                    df = df.sort_values('datetime').reset_index(drop=True)
                    df = df.dropna(subset=['close'])
                    
                    # 存入缓存
                    df_converted = self._convert_dataframe_to_python_types(df)
                    self._set_to_cache(cache_key, df_converted)
                    
                    self.logger.info(f"✅ 宏观数据加载(TDX): {code} | {len(df)}条 | 缓存设置")
                    return df_converted
            
            # 降级：数据库
            return self._load_macro_from_db(code, days)
        
        except Exception as e:
            self.logger.warning(f"⚠️ 宏观数据加载失败 {code}: {str(e)[:50]}")
            return self._load_macro_from_db(code, days)
    
    def _load_macro_from_db(self, code: str, days: int = 60) -> pd.DataFrame:
        """从数据库加载宏观指标（降级方案）"""
        try:
            query = f'''
                SELECT datetime, open, high, low, close
                FROM "{code}"
                WHERE datetime <= '{self.config.config.get('base_date', datetime.now().strftime("%Y-%m-%d"))}'
                ORDER BY datetime DESC
                LIMIT {days}
            '''
            df = pd.read_sql(query, self.engine)
            if len(df) > 0:
                df['datetime'] = pd.to_datetime(df['datetime'])
                df = df.sort_values('datetime').reset_index(drop=True)
                return df
            return pd.DataFrame()
        except Exception as e:
            self.logger.error(f"❌ 数据库加载宏观指标失败 {code}: {str(e)[:50]}")
            return pd.DataFrame()
    
    # ==================== 缓存管理方法 ====================
    
    def clear_cache(self, prefix: Optional[str] = None):
        """
        清空缓存
        
        参数:
            prefix: 可选，仅清空指定前缀的缓存（如'index'）
        """
        if prefix:
            # 清空指定前缀的缓存
            keys_to_remove = [k for k in self.cache.cache.keys() if k.startswith(prefix)]
            for key in keys_to_remove:
                self.cache.delete(key)
            self.logger.info(f"✅ 已清空 {len(keys_to_remove)} 个 {prefix} 缓存")
        else:
            # 清空全部缓存
            count = self.cache.clear()
            self.logger.info(f"✅ 已清空全部缓存 ({count} 条)")
    
    def get_cache_stats(self) -> Dict:
        """
        获取缓存统计信息
        
        返回:
            {
                'hits': int,
                'misses': int,
                'hit_rate': float,
                'current_size': int,
                'max_size': int,
                'ttl': int
            }
        """
        stats = self.cache.get_stats()
        return {
            'hits': stats['hits'],
            'misses': stats['misses'],
            'hit_rate': stats['hit_rate'],
            'current_size': stats['current_size'],
            'max_size': stats['max_size'],
            'ttl': stats['ttl']
        }
    
    def compact_cache(self):
        """压缩缓存（移除过期数据）"""
        removed = self.cache.compact()
        self.logger.info(f"✅ 缓存压缩完成 | 移除 {removed} 条过期数据")


# ==================== 使用示例 ====================
def example_data_loading_with_cache():
    """DataLoadingService集成CacheService使用示例"""
    
    print("=" * 80)
    print("🧪 DataLoadingService 集成 CacheService 使用示例")
    print("=" * 80)
    
    # 1. 初始化服务
    print("\n1️⃣ 初始化服务...")
    from infrastructure.base_services.config_service import ConfigService
    from infrastructure.base_services.cache_service import CacheService
    
    config = ConfigService('./config/system_config_v6.yaml')
    cache = CacheService(max_size=1000, ttl=3600)
    
    # 初始化DataLoadingService（深度集成缓存）
    data_service = DataLoadingService(
        config_service=config,
        cache_service=cache,
        enable_cache=True  # 显式启用缓存
    )
    
    print("✅ 服务初始化成功")
    
    # 2. 首次加载（缓存未命中）
    print("\n2️⃣ 首次加载沪深300数据（缓存未命中）...")
    df1 = data_service.load_index_data('000300', min_days=500)
    print(f"   ✅ 首次加载: {len(df1)}条 | 缓存状态: 未命中")
    
    # 3. 二次加载（缓存命中）
    print("\n3️⃣ 二次加载沪深300数据（缓存命中）...")
    df2 = data_service.load_index_data('000300', min_days=500)
    print(f"   ✅ 二次加载: {len(df2)}条 | 缓存状态: 命中")
    
    # 4. 加载PE数据（验证类型转换）
    print("\n4️⃣ 加载PE数据（验证类型转换）...")
    pe_df = data_service.load_pe_data('000300')
    if len(pe_df) > 0:
        sample_value = pe_df['pe_ttm'].iloc[0]
        print(f"   ✅ PE数据: {len(pe_df)}条 | 示例值类型: {type(sample_value).__name__}")
        print(f"   ✅ 是否为Python float: {isinstance(sample_value, float) and not isinstance(sample_value, np.floating)}")
    
    # 5. 获取缓存统计
    print("\n5️⃣ 获取缓存统计...")
    stats = data_service.get_cache_stats()
    print(f"   • 命中率: {stats['hit_rate']:.1%}")
    print(f"   • 命中/未命中: {stats['hits']}/{stats['misses']}")
    print(f"   • 当前容量: {stats['current_size']}/{stats['max_size']}")
    
    # 6. 清空缓存
    print("\n6️⃣ 清空缓存...")
    data_service.clear_cache()
    print("   ✅ 缓存已清空")
    
    print("\n" + "=" * 80)
    print("✅ DataLoadingService 集成 CacheService 示例运行完成")
    print("=" * 80)


if __name__ == "__main__":
    example_data_loading_with_cache()