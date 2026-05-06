#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
宏观数据加载服务
=============
基于 TdxAdapter 获取原始数据，根据 MacroIndicator 定义进行标准化转换。
支持批量加载、单指标查询和同比/环比计算。
"""

from typing import Optional, Dict, List

import pandas as pd

from macro_analysis_system.config.macro_indicators import MacroIndicator, get_default_indicators
# from data_service.tdx_adapter import TdxAdapter
from base_services.cache_service import CacheService, get_global_cache
from base_services.logger_service import LoggerService, get_global_logger_service


class DataLoaderService:
    """宏观数据加载服务

    将 TdxAdapter 的原始数据与 MacroIndicator 定义结合，
    提供标准化的宏观数据加载和预处理接口。

    Usage:
        loader = DataLoaderService()
        df = loader.fetch('VGDP', count=120)
        all_data = loader.fetch_all(count=120)
    """

    def __init__(self, tdx_adapter: Optional[TdxAdapter] = None,
                 indicators: Optional[Dict[str, MacroIndicator]] = None,
                 cache: Optional[CacheService] = None,
                 logger: Optional[LoggerService] = None):
        """初始化数据加载服务

        Args:
            tdx_adapter: 通达信适配器实例，None 则创建默认实例
            indicators: 指标定义字典，None 使用默认注册表
            cache: 缓存服务实例
            logger: 日志服务实例
        """
        self._adapter = tdx_adapter or TdxAdapter()
        self._indicators = indicators or get_default_indicators()
        self._cache = cache or get_global_cache()
        self._logger = (logger or get_global_logger_service()).get_logger('data_loader')

    def fetch(self, key: str, count: int = 120) -> pd.DataFrame:
        """获取指定指标的历史数据（已标准化）"""
        cache_key = f"macro_{key}_{count}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        if key not in self._indicators:
            self._logger.warning(f"未知指标: {key}")
            return pd.DataFrame()

        ind = self._indicators[key]
        raw_df = self._adapter.get_macro_bars(code=ind.code, count=count)
        if raw_df is None or len(raw_df) == 0:
            return pd.DataFrame()

        result = pd.DataFrame()
        result['date'] = pd.to_datetime(raw_df['datetime'])
        result['value'] = raw_df['close'] * ind.scale
        result['open'] = raw_df['open'] * ind.scale
        result['high'] = raw_df['high'] * ind.scale
        result['low'] = raw_df['low'] * ind.scale
        result['close'] = raw_df['close'] * ind.scale
        result = result.sort_values('date').reset_index(drop=True)

        # 特殊指标转换
        if ind.transform == 'index_minus_100':
            for col in ['value', 'open', 'high', 'low', 'close']:
                result[col] = result[col] - 100

        self._cache.set(cache_key, result, ttl=3600)
        return result

    def fetch_latest(self, key: str) -> Optional[float]:
        """获取指标最新值"""
        df = self.fetch(key, count=5)
        if len(df) > 0:
            return df.iloc[-1]['value']
        return None

    def fetch_yoy_change(self, key: str) -> Optional[float]:
        """获取指标同比变化百分比"""
        df = self.fetch(key, count=24)
        if len(df) >= 13:
            current = df.iloc[-1]['value']
            year_ago = df.iloc[-13]['value']
            if year_ago != 0:
                return (current - year_ago) / abs(year_ago) * 100
        return None

    def fetch_all(self, keys: Optional[List[str]] = None,
                  count: int = 120) -> Dict[str, pd.DataFrame]:
        """批量获取多个指标的数据"""
        if keys is None:
            keys = list(self._indicators.keys())

        result = {}
        success_count = 0
        for key in keys:
            try:
                df = self.fetch(key, count)
                if len(df) > 0:
                    result[key] = df
                    success_count += 1
            except Exception as e:
                ind = self._indicators.get(key)
                name = ind.name if ind else key
                self._logger.warning(f"获取 {key} ({name}) 失败: {e}")

        self._logger.info(f"成功加载 {success_count}/{len(keys)} 个指标")
        return result

    def get_latest_snapshot(self, data: Dict[str, pd.DataFrame]) -> Dict:
        """获取最新宏观指标快照"""
        snapshot = {}
        for key, df in data.items():
            ind = self._indicators.get(key)
            if ind and len(df) > 0:
                latest = df.iloc[-1]
                prev = df.iloc[-2] if len(df) > 1 else None
                snapshot[key] = {
                    'name': ind.name,
                    'category': ind.category,
                    'unit': ind.unit,
                    'value': latest['value'],
                    'date': latest['date'],
                    'prev_value': prev['value'] if prev is not None else None,
                    'change': latest['value'] - prev['value'] if prev is not None else None,
                    'change_pct': (
                        (latest['value'] - prev['value']) / abs(prev['value']) * 100
                        if prev is not None and prev['value'] != 0 else None
                    ),
                }
        return snapshot

    def disconnect(self):
        """断开数据源连接"""
        self._adapter.disconnect()

    @property
    def indicators(self) -> Dict[str, MacroIndicator]:
        """获取当前使用的指标定义"""
        return self._indicators

    def __repr__(self):
        return f"DataLoaderService(indicators={len(self._indicators)})"