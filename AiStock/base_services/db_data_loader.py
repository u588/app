#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DataLoader：数据加载服务（深度集成 CacheService）
职责：
1. 统一数据加载接口（股票/宏观/财务）
2. 智能缓存策略（多维度缓存键 + TTL 动态配置）
3. 完整数据验证与降级处理
4. 强制 Python 原生类型转换（防序列化错误）
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, Any, List
from datetime import datetime, timedelta
import logging

from base_services.config_service import ConfigService
from base_services.cache_service import CacheService
from base_services.database_service import DatabaseService
from dynamic_price_system.data.tdx_adapter import TDXAdapter
from dynamic_price_system.data.external_api import ExternalAPI

logger = logging.getLogger(__name__)


class DataLoader:
    """数据加载服务"""
    
    def __init__(
        self,
        config_service: ConfigService,
        cache_service: Optional[CacheService] = None,
        db_main: Optional[DatabaseService] = None,
        enable_cache: bool = True
    ):
        """
        初始化数据加载服务
        
        参数:
            config_service: 配置服务实例
            cache_service: 缓存服务实例
            db_main: 主数据库连接
            db_pe: PE 数据库连接
            enable_cache: 是否启用缓存
        """
        self.config = config_service
        self.cache = cache_service
        self.db_main = db_main
        self.enable_cache = enable_cache
        
        # 初始化数据适配器
        self.tdx = TDXAdapter(config_service)
        
        logger.info(f"✅ DataLoader 初始化成功 | 缓存={'启用' if enable_cache else '禁用'}")
    
    def _generate_cache_key(self, prefix: str, code: str, **kwargs) -> str:
        """生成唯一缓存键"""
        from config.global_settings import CACHE_KEY_SEPARATOR, CACHE_KEY_DATE_FORMAT
        
        key_parts = [prefix, code.replace(' ', '').replace('/', '_')]
        
        for k, v in sorted(kwargs.items()):
            if v is not None:
                key_parts.append(f"{k}={str(v).replace(' ', '').replace('/', '_')}")
        
        today = datetime.now().strftime(CACHE_KEY_DATE_FORMAT)
        key_parts.append(f"date={today}")
        
        cache_key = CACHE_KEY_SEPARATOR.join(key_parts)
        
        if len(cache_key) > 250:
            cache_key = cache_key[:250]
        
        return cache_key
    
    def _convert_to_python_types(self, df: pd.DataFrame) -> pd.DataFrame:
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
                logger.warning(f"⚠️ 列 {col} 转换失败：{e}")
        
        return df_converted
    
    def load_all_stocks(self) -> Dict[str, pd.DataFrame]:
        """
        加载所有标的的日线数据
        
        返回:
            {code: DataFrame} 字典
        """
        stocks_data = {}
        stock_configs = self.config.get('stocks', [])
        
        if not stock_configs:
            logger.error("❌ 未找到标的配置")
            return stocks_data
        
        for stock_config in stock_configs:
            code = stock_config.get('code')
            if not code:
                continue
            
            df = self.load_stock_daily(code)
            if df is not None and not df.empty:
                stocks_data[code] = df
        
        logger.info(f"✅ 加载完成 {len(stocks_data)} 只标的日线数据")
        return stocks_data
    
    def load_stock_daily(self, code: str, min_days: int = 500) -> Optional[pd.DataFrame]:
        """
        加载单只标的日线数据
        
        参数:
            code: 股票代码
            min_days: 最小数据天数
        
        返回:
            DataFrame 或 None
        """
        cache_key = self._generate_cache_key('stock', code, min_days=min_days)
        
        # 尝试从缓存获取
        if self.enable_cache and self.cache:
            cached_data = self.cache.get(cache_key)
            if cached_data is not None and isinstance(cached_data, pd.DataFrame):
                logger.debug(f"✅ 缓存命中：{code}")
                return cached_data
        
        # 从数据库加载
        df = self._load_stock_from_db(code, min_days)
        
        # 如果数据库无数据，尝试从 TDX 获取
        if df is None or len(df) < min_days:
            logger.warning(f"⚠️ 数据库数据不足 {len(df) if df is not None else 0} 条，尝试 TDX")
            df = self.tdx.get_stock_daily(code, min_days)
        
        # 存入缓存
        if df is not None and len(df) >= min_days and self.enable_cache and self.cache:
            df_converted = self._convert_to_python_types(df)
            ttl = self.config.get('cache.index_ttl', 7200)
            self.cache.set(cache_key, df_converted, ttl=ttl)
            logger.debug(f"💾 缓存设置：{code}")
        
        return df
    
    def _load_stock_from_db(self, code: str, min_days: int) -> Optional[pd.DataFrame]:
        """从数据库加载股票日线数据"""
        if self.db_main is None:
            return None
        
        try:
            base_date = self.config.get('system.base_date', datetime.now().strftime("%Y-%m-%d"))
            query = f'''
                SELECT *  FROM "{code}"  WHERE datetime <= '{base_date}'
                ORDER BY datetime 
            '''
            records = pd.read_sql(query, self.db_main._engine)
            
            if not records:
                return None
            
            df = pd.DataFrame(records)
            df['datetime'] = pd.to_datetime(df['datetime'])
            df = df.sort_values('datetime').reset_index(drop=True)
            
            return df
        except Exception as e:
            logger.error(f"❌ 数据库加载股票数据失败 {code}: {e}")
            return None
    
    def load_all_financial(self) -> Dict[str, Dict]:
        """
        加载所有标的的财务数据
        
        返回:
            {code: financial_data} 字典
        """
        financial_data = {}
        stock_configs = self.config.get('stocks', [])
        
        for stock_config in stock_configs:
            code = stock_config.get('code')
            if not code:
                continue
            
            data = self.load_financial(code)
            if data:
                financial_data[code] = data
        
        logger.info(f"✅ 加载完成 {len(financial_data)} 只标的财务数据")
        return financial_data
    
    def load_financial(self, code: str) -> Optional[Dict]:
        """
        加载单只标的财务数据
        
        参数:
            code: 股票代码
        
        返回:
            财务数据字典
        """
        cache_key = self._generate_cache_key('financial', code)
        
        # 尝试从缓存获取
        if self.enable_cache and self.cache:
            cached_data = self.cache.get(cache_key)
            if cached_data is not None and isinstance(cached_data, dict):
                logger.debug(f"✅ 缓存命中：{code} 财务数据")
                return cached_data
        
        # 从数据库加载
        data = self._load_financial_from_db(code)
        
        # 存入缓存
        if data and self.enable_cache and self.cache:
            ttl = self.config.get('cache.pe_ttl', 86400)
            self.cache.set(cache_key, data, ttl=ttl)
        
        return data
    
    def _load_financial_from_db(self, code: str) -> Optional[Dict]:
        """从数据库加载财务数据"""
        if self.db_pe is None:
            return None
        # revenue_growth营业收入增长率, profit_growth净利润增长率, roe净资产收益率, gross_margin毛利率, debt_ratio资产负债率, 扣非每股利润
        try:
            query = f'''
                
                SELECT col183, col184, col197, col202, col201, col2
                FROM stocks_fundamental
                WHERE ts_code = '{code}'
                ORDER BY report_date DESC
                LIMIT 1
            '''
            records = self.db_pe.execute_query(query)
            
            if records and len(records) > 0:
                return records[0]
            return None
        except Exception as e:
            logger.error(f"❌ 数据库加载财务数据失败 {code}: {e}")
            return None
    
    def get_cache_stats(self) -> Dict:
        """获取缓存统计信息"""
        if self.cache:
            return self.cache.get_stats()
        return {'hits': 0, 'misses': 0, 'hit_rate': 0.0}
    
    def clear_cache(self, prefix: Optional[str] = None):
        """清空缓存"""
        if self.cache:
            self.cache.invalidate(prefix) if prefix else self.cache.clear()


# ==================== 使用示例 ====================
def example_data_loader():
    """数据加载器使用示例"""
    
    print("=" * 80)
    print("🧪 DataLoader 使用示例")
    print("=" * 80)
    
    # 注意：实际使用需要完整的配置和服务初始化
    # 这里仅展示接口调用方式
    
    print("\n1️⃣ 加载所有标的日线数据...")
    print("   📊 stocks_data = data_loader.load_all_stocks()")
    
    print("\n2️⃣ 加载所有宏观指标...")
    print("   📊 macro_data = data_loader.load_all_macro()")
    
    print("\n3️⃣ 加载所有财务数据...")
    print("   📊 financial_data = data_loader.load_all_financial()")
    
    print("\n4️⃣ 获取缓存统计...")
    print("   📊 stats = data_loader.get_cache_stats()")
    
    print("\n" + "=" * 80)
    print("✅ DataLoader 示例说明完成")
    print("=" * 80)


if __name__ == "__main__":
    example_data_loader()