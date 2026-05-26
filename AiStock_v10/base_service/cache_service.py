#!/usr/bin/env python3
"""AiStock V10 — 统一缓存服务 (CacheService)

特性:
  - 命名空间隔离: 各子系统/服务使用独立命名空间
  - TTL 过期: 每个缓存项独立TTL
  - LRU 淘汰: 命名空间级别最大容量
  - 线程安全
  - 统计信息: 命中率/未命中/淘汰数
"""
from __future__ import annotations

import threading
import time
import logging
from typing import Any, Dict, List, Optional, Tuple
from collections import OrderedDict

logger = logging.getLogger(__name__)


class _NamespaceCache:
    """命名空间级缓存"""
    
    def __init__(self, ttl: float = 300, max_size: int = 500):
        self._store: OrderedDict[str, Tuple[Any, float]] = OrderedDict()
        self._ttl = ttl
        self._max_size = max_size
        self._hits = 0
        self._misses = 0
        self._evictions = 0
    
    def get(self, key: str) -> Optional[Any]:
        if key in self._store:
            value, expire_at = self._store[key]
            if time.time() < expire_at:
                self._hits += 1
                self._store.move_to_end(key)
                return value
            else:
                del self._store[key]
        self._misses += 1
        return None
    
    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        effective_ttl = ttl if ttl is not None else self._ttl
        expire_at = time.time() + effective_ttl
        
        if key in self._store:
            self._store.move_to_end(key)
        self._store[key] = (value, expire_at)
        
        while len(self._store) > self._max_size:
            self._store.popitem(last=False)
            self._evictions += 1
    
    def delete(self, key: str) -> bool:
        if key in self._store:
            del self._store[key]
            return True
        return False
    
    def clear(self) -> None:
        self._store.clear()
    
    def cleanup(self) -> int:
        """清理过期项, 返回清理数量"""
        now = time.time()
        expired = [k for k, (_, exp) in self._store.items() if exp <= now]
        for k in expired:
            del self._store[k]
        return len(expired)
    
    @property
    def stats(self) -> Dict[str, Any]:
        total = self._hits + self._misses
        return {
            "size": len(self._store),
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self._hits / total if total > 0 else 0.0,
            "evictions": self._evictions,
        }


class CacheService:
    """V10 统一缓存服务"""
    
    def __init__(self, default_ttl: float = 300, default_max_size: int = 500):
        self._namespaces: Dict[str, _NamespaceCache] = {}
        self._default_ttl = default_ttl
        self._default_max_size = default_max_size
        self._lock = threading.RLock()
        
        # 预创建常用命名空间
        self.ensure_namespace("config", ttl=0, max_size=100)
        self.ensure_namespace("data", ttl=300, max_size=500)
        self.ensure_namespace("computation", ttl=600, max_size=200)
        self.ensure_namespace("contract", ttl=1800, max_size=100)
    
    def ensure_namespace(self, name: str, ttl: Optional[float] = None, max_size: Optional[int] = None) -> None:
        """确保命名空间存在"""
        with self._lock:
            if name not in self._namespaces:
                self._namespaces[name] = _NamespaceCache(
                    ttl=ttl if ttl is not None else self._default_ttl,
                    max_size=max_size if max_size is not None else self._default_max_size,
                )
    
    def get(self, key: str, namespace: str = "data") -> Optional[Any]:
        """获取缓存值"""
        with self._lock:
            ns = self._namespaces.get(namespace)
            if ns is None:
                return None
            return ns.get(key)
    
    def set(self, key: str, value: Any, ttl: Optional[float] = None, namespace: str = "data") -> None:
        """设置缓存值"""
        with self._lock:
            if namespace not in self._namespaces:
                self.ensure_namespace(namespace)
            self._namespaces[namespace].set(key, value, ttl)
    
    def delete(self, key: str, namespace: str = "data") -> bool:
        """删除缓存项"""
        with self._lock:
            ns = self._namespaces.get(namespace)
            return ns.delete(key) if ns else False
    
    def invalidate(self, namespace: Optional[str] = None) -> None:
        """使缓存失效"""
        with self._lock:
            if namespace:
                ns = self._namespaces.get(namespace)
                if ns:
                    ns.clear()
            else:
                for ns in self._namespaces.values():
                    ns.clear()
    
    def cleanup(self) -> int:
        """清理所有命名空间的过期项"""
        total = 0
        with self._lock:
            for ns in self._namespaces.values():
                total += ns.cleanup()
        return total
    
    def get_stats(self, namespace: Optional[str] = None) -> Dict[str, Any]:
        """获取缓存统计"""
        if namespace:
            ns = self._namespaces.get(namespace)
            return ns.stats if ns else {}
        return {name: ns.stats for name, ns in self._namespaces.items()}
