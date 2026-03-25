#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
V6.0 数据加载服务（深度集成 CacheService）
核心特性：
✅ 智能缓存策略（多维度缓存键 + TTL 动态配置）
✅ 完整数据验证与降级处理
✅ 强制 Python 原生类型转换（防 Plotly 序列化错误）
✅ 详细缓存统计与监控
✅ 无缝集成 ConfigService/CacheService
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, Any, List, Tuple
from datetime import datetime, timedelta
import logging
import warnings

warnings.filterwarnings('ignore')
logger = logging.getLogger(__name__)


class DataLoadingService:
    """V6.0 数据加载服务（深度集成 CacheService）"""
    
    def __init__(
        self,
        config_service,
        cache_service=None,
        enable_cache: bool = True
    ):
        """初始化数据加载服务"""
        self.config = config_service
        self.enable_cache = enable_cache
        self.logger = logger
        
        # 初始化缓存服务
        if cache_service is not None:
            self.cache = cache_service
            self.logger.info("✅ 使用外部 CacheService 实例")
        else:
            cache_config = self.config.config.get('cache', {})
            max_size = cache_config.get('max_size', 1000)
            ttl = cache_config.get('ttl', 3600)
            
            from infrastructure.base_services.cache_service import CacheService
            self.cache = CacheService(max_size=max_size, ttl=ttl)
            self.logger.info(f"✅ 自动创建 CacheService | 容量={max_size} | TTL={ttl}s")
        
        # 数据库连接
        self._init_database()
        
        # TDX 接口
        self._init_tdx()
        
        self.logger.info(f"✅ DataLoadingService 初始化成功 | 缓存={'启用' if enable_cache else '禁用'}")
    
    def _init_database(self):
        """初始化数据库连接"""
        try:
            from sqlalchemy import create_engine
            db_config = self.config.config.get('database', {})
            self.engine = create_engine(db_config.get('main_db', 'sqlite:///data/stocks_daily.db'))
            self.pe_engine = create_engine(db_config.get('pe_db', 'sqlite:///data/pe_history.db'))
            self.logger.info("✅ 数据库连接初始化成功")
        except Exception as e:
            self.logger.error(f"❌ 数据库连接失败：{str(e)[:50]}")
            self.engine = None
            self.pe_engine = None
    
    def _init_tdx(self):
        """初始化 TDX 接口（带降级处理）"""
        self.tdx_exhq = None
        self.tdx_hq = None
        
        if not self.config.config.get('tdx', {}).get('use_tdx', True):
            return
        
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
            self.logger.info("✅ TDX 接口连接成功")
        except Exception as e:
            self.logger.warning(f"⚠️ TDX 接口连接失败：{str(e)[:50]}，降级使用数据库")
            self.config.config['tdx']['use_tdx'] = False
    
    # ==================== 缓存键生成 ====================
    
    def _generate_cache_key(self, prefix: str, code: str, **kwargs) -> str:
        """生成唯一缓存键（多维度组合）"""
        from config.settings import CACHE_KEY_SEPARATOR, CACHE_KEY_DATE_FORMAT
        
        key_parts = [prefix, code.replace(' ', '').replace('/', '_')]
        
        for k, v in sorted(kwargs.items()):
            if v is not None:
                key_parts.append(f"{k}={str(v).replace(' ', '').replace('/', '_')}")
        
        today = datetime.now().strftime(CACHE_KEY_DATE_FORMAT)
        key_parts.append(f"date={today}")
        
        cache_key = CACHE_KEY_SEPARATOR.join(key_parts)
        
        # 限制长度
        if len(cache_key) > 200:
            cache_key = cache_key[:200]
        
        return cache_key
    
    # ==================== 缓存操作 ====================
    
    def _get_from_cache(self, cache_key: str) -> Optional[Any]:
        """从缓存获取数据"""
        if not self.enable_cache:
            return None
        
        try:
            data = self.cache.get(cache_key)
            if data is not None:
                self.logger.debug(f"✅ 缓存命中：{cache_key[:50]}...")
            return data
        except Exception as e:
            self.logger.warning(f"⚠️ 缓存读取失败 {cache_key[:30]}: {str(e)[:30]}")
            return None
    
    def _set_to_cache(self, cache_key: str, data: Any, ttl: Optional[int] = None) -> bool:
        """存入缓存（带类型转换）"""
        if not self.enable_cache:
            return False
        
        try:
            # 强制转换为 Python 原生类型
            if isinstance(data, pd.DataFrame):
                data = self._convert_dataframe_to_python_types(data)
            elif isinstance(data, dict):
                data = self._convert_dict_to_python_types(data)
            
            self.cache.set(cache_key, data, ttl=ttl)
            self.logger.debug(f"💾 缓存设置：{cache_key[:50]}...")
            return True
        except Exception as e:
            self.logger.warning(f"⚠️ 缓存写入失败 {cache_key[:30]}: {str(e)[:30]}")
            return False
    
    # ==================== 类型转换（关键修复） ====================
    
    def _convert_dataframe_to_python_types(self, df: pd.DataFrame) -> pd.DataFrame:
        """转换 DataFrame 中所有数值列为 Python 原生类型"""
        if df is None or len(df) == 0:
            return df
        
        df_converted = df.copy()
        
        for col in df_converted.select_dtypes(include=[np.number]).columns:
            try:
                df_converted[col] = df_converted[col].apply(
                    lambda x: float(x) if pd.notna(x) else np.nan
                )
            except Exception as e:
                self.logger.warning(f"⚠️ 列 {col} 转换失败：{str(e)[:30]}")
        
        return df_converted
    
    def _convert_dict_to_python_types(self, data: Dict) -> Dict:
        """递归转换字典中所有数值为 Python 原生类型"""
        converted = {}
        
        for key, value in data.items():
            if isinstance(value, dict):
                converted[key] = self._convert_dict_to_python_types(value)
            elif isinstance(value, (int, float, np.number)):
                converted[key] = float(value) if isinstance(value, (float, np.floating)) else int(value)
            elif isinstance(value, list):
                converted[key] = [
                    float(v) if isinstance(v, (float, np.floating)) else 
                    int(v) if isinstance(v, (int, np.integer)) else v
                    for v in value
                ]
            else:
                converted[key] = value
        
        return converted
    
    # ==================== 核心数据加载方法 ====================
    
    def load_index_data(self, index_code: str, min_days: int = 500) -> pd.DataFrame:
        """加载指数数据（深度集成缓存）"""
        cache_key = self._generate_cache_key('index', index_code, min_days=min_days)
        
        if self.enable_cache:
            cached_data = self._get_from_cache(cache_key)
            if cached_data is not None and isinstance(cached_data, pd.DataFrame):
                return cached_data
        
        try:
            if self.engine is None:
                raise Exception("数据库未连接")
            
            base_date = self.config.config.get('base_date', datetime.now().strftime("%Y-%m-%d"))
            query = f'''
                SELECT * FROM "{index_code}"
                WHERE datetime <= '{base_date}'
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
            
            if len(df) < min_days:
                self.logger.warning(f"⚠️ {index_code} 数据不足（{len(df)} < {min_days}）")
                return pd.DataFrame()
            
            # 存入缓存
            df_converted = self._convert_dataframe_to_python_types(df)
            ttl = self.config.config.get('cache', {}).get('index_ttl', 7200)
            self._set_to_cache(cache_key, df_converted, ttl=ttl)
            
            self.logger.info(f"✅ 指数数据加载：{index_code} | {len(df)}条 | 缓存设置")
            return df_converted
        
        except Exception as e:
            self.logger.error(f"❌ 指数数据加载失败 {index_code}: {str(e)[:50]}")
            return pd.DataFrame()
    
    def load_pe_data(self, index_code: str) -> pd.DataFrame:
        """加载 PE 历史数据（集成缓存）"""
        cache_key = self._generate_cache_key('pe', index_code)
        
        if self.enable_cache:
            cached_data = self._get_from_cache(cache_key)
            if cached_data is not None and isinstance(cached_data, pd.DataFrame):
                return cached_data
        
        try:
            if self.pe_engine is None:
                raise Exception("PE 数据库未连接")
            
            df_hist = pd.read_sql(index_code, self.pe_engine)
            if len(df_hist) >= 500 and '滚动市盈率' in df_hist.columns:
                df_hist = df_hist.rename(columns={'日期': 'date', '滚动市盈率': 'pe_ttm'})
                df_hist['date'] = pd.to_datetime(df_hist['date'])
                result = df_hist[['date', 'pe_ttm']].copy()
                
                result_converted = self._convert_dataframe_to_python_types(result)
                self._set_to_cache(cache_key, result_converted)
                
                self.logger.info(f"✅ PE 数据加载：{index_code} | {len(result)}条 | 缓存设置")
                return result_converted
            
            return pd.DataFrame()
        
        except Exception as e:
            self.logger.warning(f"⚠️ PE 数据加载失败 {index_code}: {str(e)[:50]}")
            return pd.DataFrame()
    
    def load_derivative_data(self, code: str, market_code: int, days: int = 60) -> pd.DataFrame:
        """加载衍生品数据（集成缓存）"""
        cache_key = self._generate_cache_key('derivative', code, market_code=market_code, days=days)
        
        if self.enable_cache:
            cached_data = self._get_from_cache(cache_key)
            if cached_data is not None and isinstance(cached_data, pd.DataFrame):
                return cached_data
        
        try:
            # 优先 TDX
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
                    
                    df_converted = self._convert_dataframe_to_python_types(df)
                    ttl = self.config.config.get('cache', {}).get('derivative_ttl', 1800)
                    self._set_to_cache(cache_key, df_converted, ttl=ttl)
                    
                    self.logger.info(f"✅ 衍生品数据加载 (TDX): {code} | {len(df)}条 | 缓存设置")
                    return df_converted
            
            return self._load_derivative_from_db(code, days)
        
        except Exception as e:
            self.logger.warning(f"⚠️ 衍生品数据加载失败 {code}: {str(e)[:50]}")
            return self._load_derivative_from_db(code, days)
    
    def _load_derivative_from_db(self, code: str, days: int = 60) -> pd.DataFrame:
        """从数据库加载衍生品数据（降级方案）"""
        try:
            base_date = self.config.config.get('base_date', datetime.now().strftime("%Y-%m-%d"))
            query = f'''
                SELECT datetime, open, high, low, close, volume, position
                FROM "{code}"
                WHERE datetime <= '{base_date}'
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
            # TDX 优先
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
                    
                    df_converted = self._convert_dataframe_to_python_types(df)
                    ttl = self.config.config.get('cache', {}).get('macro_ttl', 3600)
                    self._set_to_cache(cache_key, df_converted, ttl=ttl)
                    
                    self.logger.info(f"✅ 宏观数据加载 (TDX): {code} | {len(df)}条 | 缓存设置")
                    return df_converted
            
            return self._load_macro_from_db(code, days)
        
        except Exception as e:
            self.logger.warning(f"⚠️ 宏观数据加载失败 {code}: {str(e)[:50]}")
            return self._load_macro_from_db(code, days)
    
    def _load_macro_from_db(self, code: str, days: int = 60) -> pd.DataFrame:
        """从数据库加载宏观指标（降级方案）"""
        try:
            base_date = self.config.config.get('base_date', datetime.now().strftime("%Y-%m-%d"))
            query = f'''
                SELECT datetime, open, high, low, close
                FROM "{code}"
                WHERE datetime <= '{base_date}'
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
    
    def get_option_contracts(self, underlying: str, market_code: int) -> List[Dict]:
        """获取指定标的的期权合约列表"""
        try:
            if self.engine:
                query = '''
                SELECT code, code_name, market_code 
                FROM "tdxAPIcode" 
                WHERE category = 12
                '''
                df = pd.read_sql(query, self.engine)
                
                contracts = []
                for _, row in df.iterrows():
                    code_name = row['code_name'].strip()
                    code = row['code'].strip()
                    market_code = row['market_code']
                    
                    option_type = self._extract_option_type(code_name)
                    strike_price = self._extract_strike_price(code_name)
                    expiry_month = self._extract_expiry_month(code_name)
                    
                    contracts.append({
                        'code': code,
                        'name': code_name,
                        'market_code': market_code,
                        'option_type': option_type,
                        'strike_price': strike_price,
                        'expiry_month': expiry_month
                    })
                
                self.logger.debug(f"✅ 从数据库加载{len(contracts)}个{underlying}期权合约")
                return contracts
            
        except Exception as e:
            self.logger.warning(f"⚠️ 加载{underlying}期权合约失败：{str(e)[:50]}")
            return []
    
    def _extract_option_type(self, code_name: str) -> str:
        """提取期权类型"""
        if 'C' in code_name:
            return 'call'
        elif 'P' in code_name:
            return 'put'
        return 'unknown'
    
    def _extract_strike_price(self, code_name: str) -> float:
        """提取行权价"""
        if '-' in code_name:
            parts = code_name.split('-')
            if len(parts) >= 3:
                try:
                    return float(parts[2]) / 100
                except:
                    return 0.0
        elif len(code_name) >= 10:
            try:
                strike_str = code_name[-4:]
                return float(strike_str) / 1000
            except:
                return 0.0
        return 0.0
    
    def _extract_expiry_month(self, code_name: str) -> str:
        """提取到期年月"""
        if '-' in code_name:
            parts = code_name.split('-')
            if len(parts) >= 2:
                return parts[0][-4:]
        
        type_idx = -1
        if 'C' in code_name:
            type_idx = code_name.find('C')
        elif 'P' in code_name:
            type_idx = code_name.find('P')
        
        if type_idx != -1 and len(code_name) > type_idx + 1:
            suffix = code_name[type_idx+1:]
            month_digits = ''
            for char in suffix:
                if char.isdigit():
                    month_digits += char
                elif month_digits:
                    break
            
            if month_digits:
                if len(month_digits) >= 2:
                    return month_digits[:2]
                else:
                    return month_digits
        
        return '00'
    
    # ==================== 缓存管理方法 ====================
    
    def clear_cache(self, prefix: Optional[str] = None):
        """清空缓存"""
        if prefix:
            keys_to_remove = [k for k in self.cache.cache.keys() if k.startswith(prefix)]
            for key in keys_to_remove:
                self.cache.delete(key)
            self.logger.info(f"✅ 已清空 {len(keys_to_remove)} 个 {prefix} 缓存")
        else:
            count = self.cache.clear()
            self.logger.info(f"✅ 已清空全部缓存 ({count} 条)")
    
    def get_cache_stats(self) -> Dict:
        """获取缓存统计信息"""
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