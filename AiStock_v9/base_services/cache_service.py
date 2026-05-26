"""AiStock V8 缓存服务

提供线程安全的 LRU 内存缓存:
- 单键 TTL (Time-To-Live) 支持
- LRU 淘汰策略
- 命名空间隔离 (前缀键)
- 批量 get / set
- 缓存命中/未命中/淘汰统计
- 线程安全 (threading.Lock)

Usage:
    >>> from base_services import CacheService
    >>> cache = CacheService(max_size=1000, default_ttl=300)
    >>>
    >>> # 基本操作
    >>> cache.set('stock:000001', {'name': '平安银行', 'price': 15.2})
    >>> data = cache.get('stock:000001')
    >>>
    >>> # 带独立 TTL
    >>> cache.set('kline:000001', bars, ttl=60)
    >>>
    >>> # 命名空间
    >>> ns = cache.namespace('market')
    >>> ns.set('sh000001', index_data, ttl=30)
    >>> ns.get('sh000001')
    >>>
    >>> # 批量操作
    >>> cache.set_batch({'a': 1, 'b': 2}, ttl=120)
    >>> result = cache.get_batch(['a', 'b', 'c'])  # {'a': 1, 'b': 2}
    >>>
    >>> # 统计
    >>> print(cache.stats)
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ─── 缓存条目 ────────────────────────────────────────────────────────

@dataclass
class _CacheEntry:
    """缓存条目, 存储值与过期时间"""
    value: Any
    expire_at: float  # Unix timestamp, 0 表示永不过期

    @property
    def is_expired(self) -> bool:
        """是否已过期"""
        if self.expire_at <= 0:
            return False
        return time.time() > self.expire_at


# ─── 缓存统计 ────────────────────────────────────────────────────────

@dataclass
class CacheStats:
    """缓存统计数据"""
    hit_count: int = 0
    miss_count: int = 0
    eviction_count: int = 0

    @property
    def total_requests(self) -> int:
        """总请求次数"""
        return self.hit_count + self.miss_count

    @property
    def hit_rate(self) -> float:
        """命中率 (0.0 ~ 1.0)"""
        if self.total_requests == 0:
            return 0.0
        return self.hit_count / self.total_requests

    def __repr__(self) -> str:
        return (
            f'CacheStats('
            f'hit={self.hit_count}, '
            f'miss={self.miss_count}, '
            f'evictions={self.eviction_count}, '
            f'hit_rate={self.hit_rate:.2%})'
        )


# ─── 命名空间代理 ────────────────────────────────────────────────────

class _NamespaceProxy:
    """命名空间代理, 为缓存键添加前缀

    所有通过此代理的操作都会自动添加命名空间前缀,
    实现逻辑隔离而无需创建独立的缓存实例.

    Args:
        cache: 底层 CacheService 实例
        prefix: 命名空间前缀
    """

    def __init__(self, cache: 'CacheService', prefix: str) -> None:
        self._cache = cache
        self._prefix = prefix

    def _key(self, key: str) -> str:
        """为键添加命名空间前缀"""
        return f'{self._prefix}:{key}'

    def get(self, key: str, default: Any = None) -> Any:
        """获取缓存值"""
        return self._cache.get(self._key(key), default)

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """设置缓存值"""
        self._cache.set(self._key(key), value, ttl)

    def delete(self, key: str) -> bool:
        """删除缓存键"""
        return self._cache.delete(self._key(key))

    def exists(self, key: str) -> bool:
        """检查键是否存在且未过期"""
        return self._cache.exists(self._key(key))

    def get_batch(self, keys: List[str]) -> Dict[str, Any]:
        """批量获取, 返回的键为不含前缀的原始键"""
        prefixed = {k: self._key(k) for k in keys}
        raw = self._cache.get_batch(list(prefixed.values()))
        # 将前缀键映射回原始键
        result: Dict[str, Any] = {}
        for original_key, prefixed_key in prefixed.items():
            if prefixed_key in raw:
                result[original_key] = raw[prefixed_key]
        return result

    def set_batch(
        self,
        mapping: Dict[str, Any],
        ttl: Optional[float] = None,
    ) -> None:
        """批量设置"""
        prefixed_mapping = {self._key(k): v for k, v in mapping.items()}
        self._cache.set_batch(prefixed_mapping, ttl)

    def clear(self) -> int:
        """清除本命名空间下所有键"""
        return self._cache.clear_namespace(self._prefix)

    @property
    def stats(self) -> CacheStats:
        """统计信息 (共享底层统计)"""
        return self._cache.stats


# ─── 缓存服务主体 ────────────────────────────────────────────────────

class CacheService:
    """AiStock V8 线程安全 LRU 缓存服务

    使用 OrderedDict 实现 LRU 淘汰策略:
    - 读取时将条目移至末尾 (最近使用)
    - 淘汰时从头部移除 (最久未使用)

    支持功能:
    - 单键 TTL: 每个键可设定独立的过期时间
    - 命名空间: 通过前缀实现逻辑隔离
    - 批量操作: 一次性 get/set 多个键
    - 统计信息: 命中率、淘汰数等

    Args:
        max_size: 最大缓存条目数, 默认 10000
        default_ttl: 默认 TTL (秒), 0 表示永不过期, 默认 300
        cleanup_interval: 过期条目清理间隔 (秒), 默认 60

    Example:
        >>> cache = CacheService(max_size=5000, default_ttl=600)
        >>> cache.set('quote:000001', quote_data, ttl=30)
        >>> data = cache.get('quote:000001')
    """

    def __init__(
        self,
        max_size: int = 10000,
        default_ttl: float = 300,
        cleanup_interval: float = 60,
    ) -> None:
        if max_size <= 0:
            raise ValueError(f'max_size 必须为正整数, 收到: {max_size}')
        if default_ttl < 0:
            raise ValueError(f'default_ttl 不能为负数, 收到: {default_ttl}')

        self._max_size = max_size
        self._default_ttl = default_ttl
        self._cleanup_interval = cleanup_interval

        self._store: OrderedDict[str, _CacheEntry] = OrderedDict()
        self._lock = threading.Lock()
        self._stats = CacheStats()
        self._last_cleanup = time.time()

    # ─── 属性 ─────────────────────────────────────────────

    @property
    def max_size(self) -> int:
        """最大缓存条目数"""
        return self._max_size

    @property
    def size(self) -> int:
        """当前缓存条目数"""
        with self._lock:
            return len(self._store)

    @property
    def stats(self) -> CacheStats:
        """缓存统计信息 (快照)"""
        with self._lock:
            return CacheStats(
                hit_count=self._stats.hit_count,
                miss_count=self._stats.miss_count,
                eviction_count=self._stats.eviction_count,
            )

    # ─── 基本操作 ─────────────────────────────────────────

    def get(self, key: str, default: Any = None) -> Any:
        """获取缓存值

        命中时将条目移至 LRU 末尾 (标记为最近使用).
        过期条目视为未命中, 会被惰性删除.

        Args:
            key: 缓存键
            default: 未命中时的默认值

        Returns:
            缓存值, 未命中或已过期返回 default
        """
        with self._lock:
            self._maybe_cleanup()

            entry = self._store.get(key)
            if entry is None:
                self._stats.miss_count += 1
                return default

            if entry.is_expired:
                # 惰性删除过期条目
                del self._store[key]
                self._stats.miss_count += 1
                return default

            # LRU: 移至末尾
            self._store.move_to_end(key)
            self._stats.hit_count += 1
            return entry.value

    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[float] = None,
    ) -> None:
        """设置缓存值

        若键已存在, 更新值并移至 LRU 末尾.
        若缓存已满, 淘汰最久未使用的条目.

        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间 (秒), None 使用 default_ttl, 0 表示永不过期
        """
        effective_ttl = self._default_ttl if ttl is None else ttl
        expire_at = 0.0 if effective_ttl <= 0 else time.time() + effective_ttl

        with self._lock:
            self._maybe_cleanup()

            if key in self._store:
                # 更新已有条目, 移至末尾
                self._store.move_to_end(key)
                self._store[key] = _CacheEntry(value=value, expire_at=expire_at)
            else:
                # 新增条目
                if len(self._store) >= self._max_size:
                    self._evict_one()
                self._store[key] = _CacheEntry(value=value, expire_at=expire_at)

    def delete(self, key: str) -> bool:
        """删除缓存键

        Args:
            key: 缓存键

        Returns:
            是否成功删除 (键是否存在)
        """
        with self._lock:
            if key in self._store:
                del self._store[key]
                return True
            return False

    def exists(self, key: str) -> bool:
        """检查键是否存在且未过期

        Args:
            key: 缓存键

        Returns:
            键是否存在且有效
        """
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return False
            if entry.is_expired:
                del self._store[key]
                return False
            return True

    # ─── 批量操作 ─────────────────────────────────────────

    def get_batch(self, keys: List[str]) -> Dict[str, Any]:
        """批量获取缓存值

        Args:
            keys: 缓存键列表

        Returns:
            命中的键值对字典 (仅包含有效且未过期的条目)
        """
        result: Dict[str, Any] = {}
        with self._lock:
            self._maybe_cleanup()
            for key in keys:
                entry = self._store.get(key)
                if entry is None:
                    self._stats.miss_count += 1
                    continue
                if entry.is_expired:
                    del self._store[key]
                    self._stats.miss_count += 1
                    continue
                self._store.move_to_end(key)
                self._stats.hit_count += 1
                result[key] = entry.value
        return result

    def set_batch(
        self,
        mapping: Dict[str, Any],
        ttl: Optional[float] = None,
    ) -> None:
        """批量设置缓存值

        Args:
            mapping: 键值对字典
            ttl: 统一的过期时间 (秒), None 使用 default_ttl
        """
        effective_ttl = self._default_ttl if ttl is None else ttl
        expire_at = 0.0 if effective_ttl <= 0 else time.time() + effective_ttl

        with self._lock:
            self._maybe_cleanup()
            for key, value in mapping.items():
                if key in self._store:
                    self._store.move_to_end(key)
                    self._store[key] = _CacheEntry(value=value, expire_at=expire_at)
                else:
                    if len(self._store) >= self._max_size:
                        self._evict_one()
                    self._store[key] = _CacheEntry(value=value, expire_at=expire_at)

    # ─── 命名空间 ─────────────────────────────────────────

    def namespace(self, prefix: str) -> _NamespaceProxy:
        """创建命名空间代理

        通过代理访问的所有键都会自动添加前缀,
        实现不同业务模块的缓存逻辑隔离.

        Args:
            prefix: 命名空间前缀, 如 'market', 'strategy'

        Returns:
            _NamespaceProxy 命名空间代理实例

        Example:
            >>> market_cache = cache.namespace('market')
            >>> market_cache.set('sh000001', data)  # 实际键: market:sh000001
        """
        return _NamespaceProxy(cache=self, prefix=prefix)

    def clear_namespace(self, prefix: str) -> int:
        """清除指定命名空间下的所有键

        Args:
            prefix: 命名空间前缀

        Returns:
            删除的条目数
        """
        removed = 0
        namespace_prefix = f'{prefix}:'
        with self._lock:
            keys_to_remove = [
                k for k in self._store if k.startswith(namespace_prefix)
            ]
            for key in keys_to_remove:
                del self._store[key]
                removed += 1
        return removed

    # ─── 维护操作 ─────────────────────────────────────────

    def clear(self) -> None:
        """清除所有缓存条目, 重置统计"""
        with self._lock:
            self._store.clear()
            self._stats = CacheStats()

    def cleanup(self) -> int:
        """主动清理所有过期条目

        Returns:
            清理的条目数
        """
        removed = 0
        with self._lock:
            expired_keys = [
                k for k, v in self._store.items() if v.is_expired
            ]
            for key in expired_keys:
                del self._store[key]
                removed += 1
                self._stats.eviction_count += 1
        return removed

    # ─── 内部方法 ─────────────────────────────────────────

    def _evict_one(self) -> None:
        """淘汰最久未使用的条目 (LRU 头部)

        注意: 调用方需持有 self._lock
        """
        if self._store:
            # popitem(last=False) 弹出最老的条目 (LRU 头部)
            self._store.popitem(last=False)
            self._stats.eviction_count += 1

    def _maybe_cleanup(self) -> None:
        """按时间间隔执行过期清理

        注意: 调用方需持有 self._lock
        """
        now = time.time()
        if now - self._last_cleanup < self._cleanup_interval:
            return
        self._last_cleanup = now
        expired_keys = [
            k for k, v in self._store.items() if v.is_expired
        ]
        for key in expired_keys:
            del self._store[key]
            self._stats.eviction_count += 1

    # ─── 魔术方法 ─────────────────────────────────────────

    def __len__(self) -> int:
        return self.size

    def __contains__(self, key: str) -> bool:
        return self.exists(key)

    def __repr__(self) -> str:
        return (
            f'CacheService('
            f'size={self.size}/{self._max_size}, '
            f'default_ttl={self._default_ttl}s, '
            f'hit_rate={self.stats.hit_rate:.2%})'
        )
