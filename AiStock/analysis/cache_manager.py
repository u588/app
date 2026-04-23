#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CacheManager：分析结果缓存管理器
功能：
  - LRU + TTL 双策略缓存
  - 支持内存 + 磁盘混合缓存
  - 自动失效 + 手动清理
  - 缓存统计 + 监控
"""

import logging
import json
import hashlib
import time
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Union
from collections import OrderedDict
from datetime import datetime, timedelta
import threading

logger = logging.getLogger(__name__)


class CacheEntry:
    """缓存条目"""
    __slots__ = ['key', 'value', 'created_at', 'expires_at', 'access_count']
    
    def __init__(self, key: str, value: Any, ttl_seconds: int):
        self.key = key
        self.value = value
        self.created_at = time.time()
        self.expires_at = self.created_at + ttl_seconds if ttl_seconds > 0 else float('inf')
        self.access_count = 0
    
    def is_expired(self) -> bool:
        return time.time() > self.expires_at
    
    def touch(self):
        """更新访问时间"""
        self.access_count += 1


class CacheManager:
    """缓存管理器（LRU + TTL）"""
    
    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: int = 3600,
        disk_cache_dir: Optional[Union[str, Path]] = None,
        enable_stats: bool = True
    ):
        """
        初始化缓存管理器
        
        参数:
            max_size: 最大缓存条目数（内存）
            default_ttl: 默认过期时间（秒）
            disk_cache_dir: 磁盘缓存目录（可选）
            enable_stats: 是否启用统计
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.disk_cache_dir = Path(disk_cache_dir) if disk_cache_dir else None
        self.enable_stats = enable_stats
        
        # 内存缓存（LRU）
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        
        # 统计信息
        self._stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'expirations': 0,
            'disk_reads': 0,
            'disk_writes': 0
        } if enable_stats else None
        
        # 初始化磁盘缓存
        if self.disk_cache_dir:
            self.disk_cache_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"✅ 磁盘缓存目录: {self.disk_cache_dir}")
        
        logger.info(f"✅ CacheManager 初始化 | max_size={max_size} | ttl={default_ttl}s")
    
    def _generate_key(self,  Union[str, Dict, List], prefix: str = '') -> str:
        """生成缓存键"""
        if isinstance(data, str):
            raw = data
        else:
            raw = json.dumps(data, sort_keys=True, default=str)
        
        key_hash = hashlib.md5(raw.encode()).hexdigest()[:16]
        return f"{prefix}:{key_hash}" if prefix else key_hash
    
    def get(
        self,
        key: str,
        default: Any = None,
        ttl: Optional[int] = None,
        loader: Optional[Callable[[], Any]] = None
    ) -> Any:
        """
        获取缓存值（支持自动加载）
        
        参数:
            key: 缓存键
            default: 默认值（缓存未命中时返回）
            ttl: 自定义过期时间（秒）
            loader: 自动加载函数（缓存未命中时调用）
        
        返回:
            缓存值或默认值
        """
        with self._lock:
            # 1. 检查内存缓存
            if key in self._cache:
                entry = self._cache[key]
                
                if entry.is_expired():
                    # 过期：删除并统计
                    del self._cache[key]
                    if self.enable_stats:
                        self._stats['expirations'] += 1
                else:
                    # 命中：更新访问计数 + LRU 顺序
                    entry.touch()
                    self._cache.move_to_end(key)
                    if self.enable_stats:
                        self._stats['hits'] += 1
                    return entry.value
            
            # 2. 检查磁盘缓存
            if self.disk_cache_dir:
                disk_path = self.disk_cache_dir / f"{key}.json"
                if disk_path.exists():
                    try:
                        with open(disk_path, 'r', encoding='utf-8') as f:
                            cached = json.load(f)
                        
                        # 检查过期
                        if cached.get('expires_at', 0) > time.time():
                            if self.enable_stats:
                                self._stats['hits'] += 1
                                self._stats['disk_reads'] += 1
                            
                            # 加载到内存
                            ttl = cached.get('ttl', self.default_ttl)
                            self._set_internal(key, cached['value'], ttl, update_disk=False)
                            return cached['value']
                        else:
                            # 磁盘缓存过期
                            disk_path.unlink(missing_ok=True)
                            if self.enable_stats:
                                self._stats['expirations'] += 1
                    except Exception as e:
                        logger.warning(f"⚠️ 读取磁盘缓存失败 {key}: {e}")
            
            # 3. 缓存未命中
            if self.enable_stats:
                self._stats['misses'] += 1
            
            # 4. 自动加载（如果提供 loader）
            if loader:
                try:
                    value = loader()
                    actual_ttl = ttl or self.default_ttl
                    self.set(key, value, ttl=actual_ttl)
                    return value
                except Exception as e:
                    logger.warning(f"⚠️ 自动加载缓存 {key} 失败: {e}")
            
            return default
    
    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        persist_to_disk: bool = True
    ) -> bool:
        """
        设置缓存值
        
        参数:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒），None 使用默认
            persist_to_disk: 是否持久化到磁盘
        
        返回:
            bool: 设置是否成功
        """
        with self._lock:
            return self._set_internal(key, value, ttl or self.default_ttl, persist_to_disk)
    
    def _set_internal(
        self,
        key: str,
        value: Any,
        ttl: int,
        update_disk: bool = True
    ) -> bool:
        """内部设置方法（需持有锁）"""
        try:
            # 1. 创建缓存条目
            entry = CacheEntry(key, value, ttl)
            
            # 2. LRU 淘汰
            while len(self._cache) >= self.max_size:
                # 淘汰最久未使用的
                oldest_key, oldest_entry = next(iter(self._cache.items()))
                del self._cache[oldest_key]
                if self.enable_stats:
                    self._stats['evictions'] += 1
                logger.debug(f"🗑️ LRU 淘汰: {oldest_key}")
            
            # 3. 存入内存
            self._cache[key] = entry
            self._cache.move_to_end(key)  # 标记为最近使用
            
            # 4. 持久化到磁盘（可选）
            if update_disk and self.disk_cache_dir and ttl > 0:
                disk_path = self.disk_cache_dir / f"{key}.json"
                disk_data = {
                    'value': value,
                    'ttl': ttl,
                    'expires_at': entry.expires_at,
                    'created_at': entry.created_at
                }
                with open(disk_path, 'w', encoding='utf-8') as f:
                    json.dump(disk_data, f, default=str)
                if self.enable_stats:
                    self._stats['disk_writes'] += 1
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 设置缓存 {key} 失败: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """删除缓存"""
        with self._lock:
            # 删除内存缓存
            if key in self._cache:
                del self._cache[key]
            
            # 删除磁盘缓存
            if self.disk_cache_dir:
                disk_path = self.disk_cache_dir / f"{key}.json"
                if disk_path.exists():
                    disk_path.unlink()
            
            logger.debug(f"🗑️ 删除缓存: {key}")
            return True
    
    def clear(self, pattern: Optional[str] = None) -> int:
        """
        清理缓存
        
        参数:
            pattern: 键匹配模式（支持 * 通配符）
        
        返回:
            int: 清理的条目数
        """
        with self._lock:
            count = 0
            
            # 清理内存缓存
            if pattern:
                import fnmatch
                keys_to_delete = [k for k in self._cache.keys() if fnmatch.fnmatch(k, pattern)]
            else:
                keys_to_delete = list(self._cache.keys())
            
            for key in keys_to_delete:
                del self._cache[key]
                count += 1
            
            # 清理磁盘缓存
            if self.disk_cache_dir:
                for file in self.disk_cache_dir.glob(f"{pattern or ''}*.json"):
                    try:
                        file.unlink()
                        count += 1
                    except:
                        pass
            
            logger.info(f"🧹 清理缓存: {count} 条 | 模式: {pattern or 'all'}")
            return count
    
    def cleanup_expired(self) -> int:
        """清理过期条目"""
        with self._lock:
            count = 0
            expired_keys = [k for k, v in self._cache.items() if v.is_expired()]
            
            for key in expired_keys:
                del self._cache[key]
                count += 1
            
            # 清理磁盘过期缓存
            if self.disk_cache_dir:
                now = time.time()
                for file in self.disk_cache_dir.glob('*.json'):
                    try:
                        with open(file, 'r', encoding='utf-8') as f:
                            cached = json.load(f)
                        if cached.get('expires_at', 0) < now:
                            file.unlink()
                            count += 1
                    except:
                        pass
            
            if count > 0:
                logger.debug(f"🧹 清理过期缓存: {count} 条")
            return count
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        if not self.enable_stats:
            return {}
        
        with self._lock:
            total_requests = self._stats['hits'] + self._stats['misses']
            hit_rate = self._stats['hits'] / total_requests if total_requests > 0 else 0
            
            return {
                'size': len(self._cache),
                'max_size': self.max_size,
                'hits': self._stats['hits'],
                'misses': self._stats['misses'],
                'hit_rate': round(hit_rate, 3),
                'evictions': self._stats['evictions'],
                'expirations': self._stats['expirations'],
                'disk_reads': self._stats['disk_reads'],
                'disk_writes': self._stats['disk_writes'],
                'default_ttl': self.default_ttl
            }
    
    def warm_up(self, items: List[tuple], ttl: Optional[int] = None):
        """
        预热缓存
        
        参数:
            items: [(key, value), ...] 列表
            ttl: 过期时间
        """
        logger.info(f"🔥 预热缓存: {len(items)} 条")
        for key, value in items:
            self.set(key, value, ttl=ttl or self.default_ttl, persist_to_disk=False)
    
    def close(self):
        """清理资源"""
        self.cleanup_expired()
        logger.debug("🧹 CacheManager 资源清理完成")