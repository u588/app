#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析缓存管理器
===============
管理分析结果的内存缓存，避免重复计算。
基于 base_services.cache_service 提供 TTL 缓存能力，
同时支持按维度粒度的缓存失效和刷新。
"""

from typing import Dict, Optional
from datetime import datetime

from base_services.cache_service import CacheService
from base_services.logger_service import LoggerService
# from base_services.cache_service import CacheService, get_global_cache
# from base_services.logger_service import LoggerService, get_global_logger_service


class AnalysisCacheManager:
    """分析缓存管理器

    为分析结果提供带 TTL 的内存缓存，支持按维度失效。

    Usage:
        cache_mgr = AnalysisCacheManager()
        cache_mgr.put_dimension('economic_growth', result)
        cached = cache_mgr.get_dimension('economic_growth')
    """

    # 缓存键前缀
    PREFIX_DIM = 'analysis_dim_'
    PREFIX_OUTLOOK = 'analysis_outlook'
    PREFIX_SNAPSHOT = 'analysis_snapshot'

    def __init__(self, cache: Optional[CacheService] = None,
                 ttl: int = 1800,
                 logger: Optional[LoggerService] = None):
        """初始化缓存管理器

        Args:
            cache: 缓存服务实例
            ttl: 缓存有效期（秒），默认30分钟
            logger: 日志服务实例
        """
        self._cache = cache
        # self._cache = cache or get_global_cache()
        self._ttl = ttl
        self._logger = logger.get_logger('analysis_cache')
        # self._logger = (logger or get_global_logger_service()).get_logger('analysis_cache')

    def put_dimension(self, key: str, result: Dict):
        """缓存单个维度的分析结果"""
        self._cache.set(f"{self.PREFIX_DIM}{key}", result, ttl=self._ttl)

    def get_dimension(self, key: str) -> Optional[Dict]:
        """获取单个维度的缓存结果"""
        return self._cache.get(f"{self.PREFIX_DIM}{key}")

    def put_outlook(self, outlook: Dict):
        """缓存综合展望结果"""
        self._cache.set(self.PREFIX_OUTLOOK, outlook, ttl=self._ttl)

    def get_outlook(self) -> Optional[Dict]:
        """获取缓存的综合展望"""
        return self._cache.get(self.PREFIX_OUTLOOK)

    def put_snapshot(self, snapshot: Dict):
        """缓存指标快照"""
        self._cache.set(self.PREFIX_SNAPSHOT, snapshot, ttl=self._ttl)

    def get_snapshot(self) -> Optional[Dict]:
        """获取缓存的指标快照"""
        return self._cache.get(self.PREFIX_SNAPSHOT)

    def invalidate_dimension(self, key: str):
        """失效单个维度的缓存"""
        self._cache.delete(f"{self.PREFIX_DIM}{key}")

    def invalidate_all(self):
        """失效所有分析缓存"""
        self._cache.delete(self.PREFIX_OUTLOOK)
        self._cache.delete(self.PREFIX_SNAPSHOT)
        # 维度缓存通过 TTL 自然过期
        self._logger.info("已清除所有分析缓存")

    def is_analysis_cached(self) -> bool:
        """检查是否已有完整的分析缓存"""
        return self._cache.has(self.PREFIX_OUTLOOK)