#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
V6.2 DataLoadingService：数据加载主服务（复权逻辑移除版 + 外部数据支持）
✅ 三类市场精准路由：股票/指数/衍生品分离加载
✅ 支持 source: "external" 的外盘期货数据获取
✅ 依赖注入 + 配置驱动 + 缓存协调
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, Any, List
from datetime import datetime
import logging
import warnings

warnings.filterwarnings('ignore')
logger = logging.getLogger(__name__)


class DataLoadingService:
    """V6.2 数据加载服务（缓存协调器 + 外部数据支持）"""
    
    # 市场类型路由映射（与 TDXAdapter MARKET_CATEGORY 对齐）
    MARKET_ROUTING = {
        'stock': ['stock_sh', 'stock_sz', 'stock_xg'],
        'index': ['index_sh', 'index_sz', 'index_zz', 'index_gz', 'index_xg'],
        'derivative': [
            'future_zz', 'future_dl', 'future_sh', 'future_gz', 'future_zj',
            'option_zj', 'option_sh', 'option_sz', 'open_fund', 'macro'
        ]
    }
    
    def __init__(
        self,
        config_service,
        database_reader,
        tdx_adapter: Optional[Any] = None,
        ak_adapter=None,
        cache_service=None,
        enable_cache: bool = True
    ):
        """
        初始化数据加载服务
        
        参数:
            config_service: 配置服务实例
            database_reader: DatabaseReader 实例（依赖注入）
            tdx_adapter: TDXAdapter 实例（可选，依赖注入）
            external_api: AKAdapter 实例（可选，用于外部数据）
            cache_service: 缓存服务实例（可选）
            enable_cache: 是否启用缓存
        """
        self.config = config_service
        self.db = database_reader
        self.tdx = tdx_adapter
        self.external_api = ak_adapter
        self.enable_cache = enable_cache
        self.logger = logger
        
        # 初始化缓存服务
        self._init_cache(cache_service)
        
        # 缓存 TTL 配置
        self.cache_ttl = self.config.config.get('cache', {})
        
        self.logger.info(f"✅ DataLoadingService V6.2 初始化成功 | 缓存={'启用' if enable_cache else '禁用'} | 复权逻辑已移除")
    
    def _init_cache(self, cache_service):
        """初始化缓存服务"""
        if cache_service is not None:
            self.cache = cache_service
            self.logger.info("✅ 使用外部 CacheService 实例")
        else:
            cache_config = self.config.config.get('cache', {})
            from base_services.cache_service import CacheService
            self.cache = CacheService(
                max_size=cache_config.get('max_size', 1000),
                ttl=cache_config.get('ttl', 3600)
            )
            self.logger.info(f"✅ 自动创建 CacheService (max_size={cache_config.get('max_size', 1000)})")
    
    # ==================== 缓存键生成（精简版） ====================
    
    def _generate_cache_key(self, prefix: str, code: str, **kwargs) -> str:
        """生成唯一缓存键（移除 adjust 等冗余参数）"""
        from config.global_settings import CACHE_KEY_SEPARATOR, CACHE_KEY_DATE_FORMAT
        
        key_parts = [prefix, code.replace(' ', '').replace('/', '_')]
        
        # 仅保留必要参数（移除 adjust）
        for k, v in sorted(kwargs.items()):
            if v is not None and k not in {'adjust'}:  # 显式排除 adjust
                key_parts.append(f"{k}={str(v).replace(' ', '').replace('/', '_')}")
        
        key_parts.append(f"date={datetime.now().strftime(CACHE_KEY_DATE_FORMAT)}")
        
        cache_key = CACHE_KEY_SEPARATOR.join(key_parts)
        
        # 限制长度 + 哈希截断
        if len(cache_key) > 200:
            import hashlib
            suffix = cache_key[-50:]
            prefix_hash = hashlib.md5(cache_key[:-50].encode()).hexdigest()[:16]
            cache_key = f"{prefix_hash}::{suffix}"
        
        return cache_key
    
    # ==================== 缓存操作封装 ====================
    
    def _get_cached(self, key: str, expected_type: type) -> Optional[Any]:
        """从缓存获取并类型校验"""
        if not self.enable_cache:
            return None
        try:
            data = self.cache.get(key)
            if data is not None and isinstance(data, expected_type):
                self.logger.debug(f"✅ 缓存命中: {key[:60]}...")
                return data
        except Exception as e:
            self.logger.warning(f"⚠️ 缓存读取失败: {e}")
        return None
    
    def _cache_set(self, key: str, data: Any, ttl: Optional[int] = None) -> bool:
        """存入缓存（自动类型转换）"""
        if not self.enable_cache or data is None:
            return False
        try:
            if isinstance(data, pd.DataFrame):
                data = self._convert_df_types(data)
            elif isinstance(data, dict):
                data = self._convert_dict_types(data)
            
            self.cache.set(key, data, ttl=ttl)
            return True
        except Exception as e:
            self.logger.warning(f"⚠️ 缓存写入失败: {e}")
            return False
    
    # ==================== 类型转换（关键） ====================
    
    def _convert_df_types(self, df: pd.DataFrame) -> pd.DataFrame:
        """DataFrame 数值列转 Python 原生类型"""
        if df is None or df.empty:
            return df
        
        df_out = df.copy()
        for col in df_out.select_dtypes(include=[np.number]).columns:
            try:
                df_out[col] = pd.to_numeric(df_out[col], errors='coerce').astype(float)
            except:
                pass
        return df_out
    
    def _convert_dict_types(self, data: Dict) -> Dict:
        """字典递归类型转换"""
        result = {}
        for k, v in data.items():
            if isinstance(v, dict):
                result[k] = self._convert_dict_types(v)
            elif isinstance(v, (np.integer, np.floating)):
                result[k] = int(v) if isinstance(v, np.integer) else float(v)
            elif isinstance(v, list):
                result[k] = [
                    float(x) if isinstance(x, np.floating) else 
                    int(x) if isinstance(x, np.integer) else x
                    for x in v
                ]
            else:
                result[k] = v
        return result
    
    # ==================== 核心业务方法（三类市场分离） ====================
    
    def load_stock_daily(
        self, 
        code: str, 
        min_days: int = 500,
        engine_name: str = 'stock_db'
    ) -> pd.DataFrame:
        """
        加载单只股票日线数据（无复权）
        
        参数:
            code: 股票代码 (如 '000001', '600519')
            min_days: 最小数据天数
            engine_name: 数据库引擎名称
        
        返回:
            pd.DataFrame: 标准化日线数据（不复权）
        """
        # 精简缓存键：移除 adjust 参数
        cache_key = self._generate_cache_key('stock_daily', code, min_days=min_days)
        
        # 1. 缓存优先
        cached = self._get_cached(cache_key, pd.DataFrame)
        if cached is not None:
            return cached
        
        # 2. TDX 优先获取（三类市场精准路由）
        if self.tdx and self.tdx.is_available():
            market_type = 'stock_sh' if code.startswith(('6', '7')) else 'stock_sz'  # 沪市:6/7开头, 深市:0/3开头
            df = self.tdx.get_bars(code, market_type, days=min_days + 50)  # 多取50天防截断
            
            if df is not None and len(df) >= min_days:
                df = df.tail(min_days).reset_index(drop=True)
                df_out = self._convert_df_types(df)
                self._cache_set(cache_key, df_out, ttl=self.cache_ttl.get('stock_ttl', 7200))
                self.logger.info(f"✅ 股票日线(TDX): {code} | {len(df)}条 | 市场={market_type}")
                return df_out
        
        # 3. 数据库降级加载
        base_date = self.config.config.get('base_date', datetime.now().strftime("%Y-%m-%d"))
        df = self.db.read_table(
            table_name=code,
            engine_name=engine_name,
            conditions={'datetime': base_date},
            order_by='datetime ASC',
            parse_dates=['datetime']
        )
        
        if df.empty or len(df) < min_days:
            self.logger.warning(f"⚠️ 股票 {code} 数据不足: {len(df)}/{min_days}")
            return pd.DataFrame()
        
        # 4. 数据标准化（无复权处理）
        df = df.sort_values('datetime').drop_duplicates('datetime', keep='last').reset_index(drop=True)
        
        # 5. 缓存 + 返回
        df_out = self._convert_df_types(df)
        self._cache_set(cache_key, df_out, ttl=self.cache_ttl.get('stock_ttl', 7200))
        self.logger.info(f"✅ 股票日线(DB): {code} | {len(df)}条")
        return df_out
    
    def load_index_data(
        self, 
        index_code: str, 
        min_days: int = 500, 
        engine_name: str = 'index_db'
    ) -> pd.DataFrame:
        """加载指数数据（缓存 + 降级）"""
        cache_key = self._generate_cache_key('index', index_code, min_days=min_days)
        
        cached = self._get_cached(cache_key, pd.DataFrame)
        if cached is not None:
            return cached
        
        # 1. TDX 优先（指数类市场路由）
        if self.tdx and self.tdx.is_available():
            # 智能识别指数市场类型
            if index_code.startswith(('000', '880')):  # 上证指数
                market_type = 'index_sh'
            elif index_code.startswith(('399', '39')):  # 深证指数
                market_type = 'index_sz'
            elif index_code.startswith('399'):  # 国证指数
                market_type = 'index_gz'
            elif index_code.startswith('H'):  # 恒生指数
                market_type = 'index_xg'
            else:
                market_type = 'index_zz'  # 默认中证
            
            df = self.tdx.get_bars(index_code, market_type, days=min_days + 20)
            if df is not None and len(df) >= min_days:
                df = df.tail(min_days).reset_index(drop=True)
                df_out = self._convert_df_types(df)
                self._cache_set(cache_key, df_out, ttl=self.cache_ttl.get('index_ttl', 7200))
                self.logger.info(f"✅ 指数数据(TDX): {index_code} | {len(df)}条 | 市场={market_type}")
                return df_out
        
        # 2. 数据库降级
        base_date = self.config.config.get('base_date', datetime.now().strftime("%Y-%m-%d"))
        df = self.db.read_table(
            table_name=index_code,
            engine_name=engine_name,
            conditions={'datetime': base_date},
            order_by='datetime ASC',
            parse_dates=['datetime']
        )
        
        if df.empty or len(df) < min_days:
            self.logger.warning(f"⚠️ 指数 {index_code} 数据不足: {len(df)}/{min_days}")
            return pd.DataFrame()
        
        # 3. 数据预处理
        if index_code.startswith(('399', '88')):
            df['amount'] = df['amount'] / 1e6  # 单位转换
        
        df = df.sort_values('datetime').drop_duplicates('datetime', keep='last')
        
        # 4. 技术指标计算
        df['return_1d'] = df['close'].pct_change()
        df['volatility_20'] = df['return_1d'].rolling(20).std() * np.sqrt(250)
        df['ma_20'] = df['close'].rolling(20).mean()
        df['ma_60'] = df['close'].rolling(60).mean()
        
        # 5. 缓存 + 返回
        df_out = self._convert_df_types(df)
        ttl = self.cache_ttl.get('index_ttl', 7200)
        self._cache_set(cache_key, df_out, ttl=ttl)
        self.logger.info(f"✅ 指数数据(DB): {index_code} | {len(df)}条")
        return df_out
    
    def load_pe_data(self, index_code: str, engine_name: str = 'index_pe_db') -> pd.DataFrame:
        """加载 PE 历史数据（无复权）"""
        cache_key = self._generate_cache_key('pe', index_code)
        
        cached = self._get_cached(cache_key, pd.DataFrame)
        if cached is not None:
            return cached
        
        try:
            df = self.db.read_table(
                table_name=index_code,
                engine_name=engine_name,
                parse_dates=['date']
            )
            
            if len(df) < 500 or '滚动市盈率' not in df.columns:
                return pd.DataFrame()
            
            result = df.rename(columns={'日期': 'date', '滚动市盈率': 'pe_ttm'})[['date', 'pe_ttm']].copy()
            result_out = self._convert_df_types(result)
            
            self._cache_set(cache_key, result_out, ttl=self.cache_ttl.get('pe_ttl', 86400))
            return result_out
            
        except Exception as e:
            self.logger.warning(f"⚠️ PE 数据加载失败 {index_code}: {e}")
            return pd.DataFrame()

    def load_stock_fs(self, code: str, engine_name: str = 'stock_fs_db') -> pd.DataFrame:
        """加载 股票财务历史数据（无复权）"""
        cache_key = self._generate_cache_key('stock_fs', code)
        
        cached = self._get_cached(cache_key, pd.DataFrame)
        if cached is not None:
            return cached
        
        try:
            df = self.db.read_table(
                table_name=code,
                engine_name=engine_name,
                # parse_dates=['report_date']
            )
            
            if df.empty :
                self.logger.warning(f"⚠️ 股票 {code} 数据不足")
                return pd.DataFrame()
                
            # 4. 数据标准化（无复权处理）
            # df = df.sort_values('report_date').drop_duplicates('report_date', keep='last').reset_index(drop=True)
            df['report_date'] = pd.to_datetime(df['report_date'], format='%Y%m%d', errors='coerce')
            
            # 5. 缓存 + 返回
            df_out = self._convert_df_types(df)
            self._cache_set(cache_key, df_out, ttl=self.cache_ttl.get('stock_ttl', 7200))
            self.logger.info(f"✅ 股票财务(DB): {code} | {len(df)}条")
            return df_out
            
        except Exception as e:
            self.logger.warning(f"⚠️ 股票财务数据加载失败 {code}: {e}")
            return pd.DataFrame()
    
    def load_derivative_data(
        self, 
        code: str, 
        market_type: str, 
        days: int = 60
    ) -> pd.DataFrame:
        """
        加载衍生品数据（期货/期权/基金/宏观）
        
        参数:
            code: 合约代码（如 'IF2406'）
            market_type: 市场类型（需在 MARKET_ROUTING['derivative'] 中）
            days: 获取天数
        """
        if market_type not in self.MARKET_ROUTING['derivative']:
            self.logger.error(f"❌ 无效的衍生品市场类型: {market_type}，有效类型: {self.MARKET_ROUTING['derivative']}")
            return pd.DataFrame()
        
        cache_key = self._generate_cache_key('derivative', code, market=market_type, days=days)
        
        cached = self._get_cached(cache_key, pd.DataFrame)
        if cached is not None:
            return cached
        
        # 1. TDX 优先（衍生品类专用接口）
        if self.tdx and self.tdx.is_available():
            df = self.tdx.get_bars(code, market_type, days)
            if df is not None and not df.empty:
                df_out = self._convert_df_types(df)
                self._cache_set(cache_key, df_out, ttl=self.cache_ttl.get('derivative_ttl', 1800))
                self.logger.info(f"✅ 衍生品(TDX): {code} | {len(df)}条 | 市场={market_type}")
                return df_out
        
        # 2. 数据库降级
        df = self.db.read_table(
            table_name=code,
            engine_name='stock_db',
            conditions={'datetime': datetime.now().strftime("%Y-%m-%d")},
            order_by='datetime DESC',
            limit=days,
            parse_dates=['datetime']
        )
        
        if not df.empty:
            df = df.sort_values('datetime').reset_index(drop=True)
            if 'position' in df.columns:
                df = df.rename(columns={'position': 'open_interest'})
            df_out = self._convert_df_types(df)
            self._cache_set(cache_key, df_out, ttl=self.cache_ttl.get('derivative_ttl', 1800))
            self.logger.info(f"✅ 衍生品(DB): {code} | {len(df)}条")
            return df_out
        
        self.logger.warning(f"⚠️ 衍生品数据获取失败: {code} | 市场={market_type}")
        return pd.DataFrame()
    
    def load_macro_data(self, code: str, days: int = 60) -> pd.DataFrame:
        """
        加载宏观指标数据（智能路由：external/TDX/DB）
        
        参数:
            code: 指标代码（如 'brent_crude', 'pmi'）
            days: 历史天数
        """
        # 1. 获取指标配置
        macro_config = getattr(self.config, 'config', {}).get('macro_indicators', {}).get(code, {})
        source = macro_config.get('source', 'tdx')
        external_code = macro_config.get('code')
        
        # 2. 路由到外部数据源
        if source == 'external' and external_code and self.external_api:
            result = self.external_api.get_futures_realtime(external_code)
            if result:
                # 转换为 DataFrame 格式（兼容现有接口）
                df = pd.DataFrame([{
                    'datetime': pd.to_datetime(f"{result['update_date']} {result['update_time']}"),
                    'close': result['price'],
                    'open': result['open'],
                    'high': result['high'],
                    'low': result['low'],
                    'prev_close': result['prev_close'],
                    'change': result['change'],
                    'change_pct': result['change_pct'],
                    'volume': result.get('volume', 0),
                    'name': result['name'],
                    'unit': result['unit'],
                    'source': 'external'
                }])
                self.logger.info(f"✅ 宏观数据 (外部): {code} -> {external_code} | 价格={result['price']}")
                return df
            else:
                self.logger.warning(f"⚠️ 外部数据获取失败 {code}，尝试降级到 TDX")
        
        # 3. 默认路由到 TDX/DB
        tdx_code = macro_config.get('code', code)
        return self._load_macro_from_tdx(tdx_code, days)
    
    def _load_macro_from_tdx(self, tdx_code: str, days: int) -> pd.DataFrame:
        """内部方法：从 TDX 加载宏观数据"""
        cache_key = self._generate_cache_key('macro', tdx_code, days=days)
        
        cached = self._get_cached(cache_key, pd.DataFrame)
        if cached is not None:
            return cached
        
        if self.tdx and self.tdx.is_available():
            df = self.tdx.get_bars(tdx_code, 'macro', days)
            if df is not None and not df.empty:
                df_out = self._convert_df_types(df)
                self._cache_set(cache_key, df_out, ttl=self.cache_ttl.get('macro_ttl', 3600))
                return df_out
        
        # DB 降级
        df = self.db.read_table(
            table_name=tdx_code,
            engine_name='stock_db',
            conditions={'datetime': datetime.now().strftime("%Y-%m-%d")},
            order_by='datetime DESC',
            limit=days,
            parse_dates=['datetime']
        )
        
        if not df.empty:
            df = df.sort_values('datetime').reset_index(drop=True)
            df_out = self._convert_df_types(df)
            self._cache_set(cache_key, df_out, ttl=self.cache_ttl.get('macro_ttl', 3600))
            return df_out
        
        return pd.DataFrame()
    
    def load_all_macro_indicators(self, indicator_codes: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        批量加载所有配置的宏观指标（智能路由 + 缓存协调）
        
        返回:
            Dict[code -> value]，value 为最新价格或 DataFrame
        """
        all_macros = getattr(self.config, 'config', {}).get('macro_indicators', {})
        codes_to_load = indicator_codes or list(all_macros.keys())
        
        results = {}
        external_codes = []
        
        # 分类：外部数据源 vs 内部数据源
        for code in codes_to_load:
            config = all_macros.get(code, {})
            if config.get('source') == 'external':
                external_codes.append(code)
            else:
                df = self.load_macro_data(code)
                if not df.empty:
                    results[code] = float(df['close'].iloc[-1]) if 'close' in df.columns else None
        
        # 批量加载外部数据
        if external_codes and self.external_api:
            external_results = self.external_api.get_futures_batch(external_codes)
            for code, data in external_results.items():
                if data:
                    results[code] = data['price']
        
        self.logger.info(f"✅ 宏观指标批量加载完成: {len(results)}/{len(codes_to_load)}")
        return results
    
    # ==================== 缓存管理 ====================
    
    def clear_cache(self, prefix: Optional[str] = None) -> int:
        """清空缓存"""
        if prefix:
            keys = [k for k in self.cache.cache.keys() if k.startswith(prefix)]
            for k in keys:
                self.cache.delete(k)
            self.logger.info(f"🗑️ 清空 {prefix}* 缓存: {len(keys)} 条")
            return len(keys)
        else:
            count = self.cache.clear()
            self.logger.info(f"🗑️ 清空全部缓存: {count} 条")
            return count
    
    def get_cache_stats(self) -> Dict:
        """获取缓存统计"""
        stats = self.cache.get_stats()
        return {
            'hits': stats['hits'],
            'misses': stats['misses'], 
            'hit_rate': stats['hit_rate'],
            'size': f"{stats['current_size']}/{stats['max_size']}",
            'ttl': stats['ttl']
        }
    
    def close(self):
        """资源清理"""
        if self.db:
            self.db.close()
        if self.tdx:
            self.tdx.close()
        if self.external_api:
            self.external_api.clear_cache()
        self.logger.info("✅ DataLoadingService 已关闭")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False