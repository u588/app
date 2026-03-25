#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
V6.0 缓存服务（完全独立，无循环依赖）
职责：
1. 统一缓存管理（LRU 策略）
2. 缓存命中率统计
3. 缓存失效策略
4. 缓存监控与清理
依赖：
- 无外部依赖（仅使用标准库）
- 不依赖任何业务服务
"""

import time
from typing import Any, Optional, Dict, List
from collections import OrderedDict
import logging

logger = logging.getLogger(__name__)


class CacheService:
    """V6.0 缓存服务（修复版：完全独立）"""
    
    def __init__(self, max_size: int = 1000, ttl: int = 3600):
        """
        初始化缓存服务
        
        参数:
            max_size: 缓存最大容量（默认 1000）
            ttl: 缓存过期时间（秒，默认 3600=1 小时）
        """
        self.max_size = max_size
        self.ttl = ttl
        self.cache: OrderedDict = OrderedDict()  # LRU 缓存
        self.cache_metadata: Dict[str, Dict] = {}  # 缓存元数据
        self.stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'total_requests': 0
        }
        self.logger = logger
        self.logger.info(f"✅ 缓存服务初始化成功 | 容量={max_size} | TTL={ttl}s")
    
    # ==================== 核心方法 ====================
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存数据"""
        self.stats['total_requests'] += 1
        
        if key not in self.cache:
            self.stats['misses'] += 1
            self.logger.debug(f"❌ 缓存未命中：{key}")
            return None
        
        # 检查 TTL
        metadata = self.cache_metadata.get(key, {})
        if 'timestamp' in metadata:
            age = time.time() - metadata['timestamp']
            if age > self.ttl:
                self._remove(key)
                self.stats['misses'] += 1
                self.logger.debug(f"❌ 缓存过期：{key} (age={age:.0f}s > TTL={self.ttl}s)")
                return None
        
        # LRU: 移动到末尾
        value = self.cache.pop(key)
        self.cache[key] = value
        
        self.stats['hits'] += 1
        self.logger.debug(f"✅ 缓存命中：{key} | 命中率={self.get_hit_rate():.1%}")
        return value
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """设置缓存数据"""
        # 移除旧缓存
        if key in self.cache:
            self._remove(key)
        
        # LRU: 添加到末尾
        self.cache[key] = value
        self.cache_metadata[key] = {
            'timestamp': time.time(),
            'ttl': ttl or self.ttl,
            'size': self._estimate_size(value)
        }
        
        # 检查容量
        if len(self.cache) > self.max_size:
            oldest_key = next(iter(self.cache))
            self._remove(oldest_key)
            self.stats['evictions'] += 1
            self.logger.debug(f"⚠️ 缓存驱逐：{oldest_key} (容量={self.max_size})")
        
        self.logger.debug(f"✅ 缓存设置：{key} | TTL={ttl or self.ttl}s")
        return True
    
    def delete(self, key: str) -> bool:
        """删除指定缓存"""
        return self._remove(key)
    
    def clear(self) -> int:
        """清空所有缓存"""
        count = len(self.cache)
        self.cache.clear()
        self.cache_metadata.clear()
        self.logger.info(f"✅ 缓存已清空 | 清除{count}条")
        return count
    
    # ==================== 辅助方法 ====================
    
    def _remove(self, key: str) -> bool:
        """内部移除方法"""
        if key in self.cache:
            del self.cache[key]
            if key in self.cache_metadata:
                del self.cache_metadata[key]
            return True
        return False
    
    def _estimate_size(self, value: Any) -> int:
        """估算缓存大小（字节）"""
        try:
            if isinstance(value, (str, bytes)):
                return len(value)
            elif isinstance(value, (list, dict, tuple)):
                return sum(self._estimate_size(v) for v in (value.values() if isinstance(value, dict) else value))
            elif hasattr(value, '__sizeof__'):
                return value.__sizeof__()
            else:
                return 100
        except:
            return 100
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        hit_rate = self.stats['hits'] / self.stats['total_requests'] if self.stats['total_requests'] > 0 else 0.0
        
        return {
            'hits': self.stats['hits'],
            'misses': self.stats['misses'],
            'hit_rate': float(hit_rate),
            'evictions': self.stats['evictions'],
            'total_requests': self.stats['total_requests'],
            'current_size': len(self.cache),
            'max_size': self.max_size,
            'ttl': self.ttl,
            'cache_keys': list(self.cache.keys())
        }
    
    def get_hit_rate(self) -> float:
        """获取缓存命中率"""
        if self.stats['total_requests'] == 0:
            return 0.0
        return float(self.stats['hits'] / self.stats['total_requests'])
    
    def invalidate(self, prefix: str) -> int:
        """使指定前缀的缓存失效"""
        keys_to_remove = [k for k in self.cache.keys() if k.startswith(prefix)]
        for key in keys_to_remove:
            self._remove(key)
        
        count = len(keys_to_remove)
        if count > 0:
            self.logger.info(f"✅ 缓存失效：{count}条 (前缀='{prefix}')")
        return count
    
    def compact(self) -> int:
        """压缩缓存：移除所有过期缓存"""
        expired_keys = []
        current_time = time.time()
        
        for key, metadata in self.cache_metadata.items():
            age = current_time - metadata['timestamp']
            if age > metadata['ttl']:
                expired_keys.append(key)
        
        for key in expired_keys:
            self._remove(key)
        
        if expired_keys:
            self.logger.info(f"✅ 缓存压缩：移除{len(expired_keys)}条过期缓存")
        return len(expired_keys)
    
    # ==================== 调试工具 ====================
    
    def inspect_key(self, key: str) -> Optional[Dict]:
        """检查指定缓存键的详细信息"""
        if key not in self.cache:
            return None
        
        metadata = self.cache_metadata[key]
        current_time = time.time()
        age = current_time - metadata['timestamp']
        expires_in = metadata['ttl'] - age
        
        return {
            'exists': True,
            'value_type': str(type(self.cache[key]).__name__),
            'value_size': metadata['size'],
            'age': float(age),
            'ttl': metadata['ttl'],
            'expires_in': float(expires_in)
        }
    
    def __len__(self) -> int:
        """返回当前缓存大小"""
        return len(self.cache)
    
    def __contains__(self, key: str) -> bool:
        """检查缓存键是否存在"""
        return key in self.cache and self.get(key) is not None


# ==================== 使用示例 ====================
def example_cache_service():
    """缓存服务使用示例"""
    
    print("=" * 80)
    print("🧪 CacheService 使用示例")
    print("=" * 80)
    
    cache = CacheService(max_size=100, ttl=60)
    
    # 设置缓存
    print("\n1️⃣ 设置缓存...")
    cache.set('user:1001', {'name': '张三', 'age': 30})
    cache.set('stock:000300', [4000, 4050, 4100, 4080, 4120])
    
    # 获取缓存
    print("\n2️⃣ 获取缓存...")
    user = cache.get('user:1001')
    print(f"   ✅ user:1001 = {user}")
    
    # 缓存统计
    print("\n3️⃣ 缓存统计...")
    stats = cache.get_stats()
    print(f"   命中率：{stats['hit_rate']:.1%}")
    print(f"   命中/未命中：{stats['hits']}/{stats['misses']}")
    
    # 清空缓存
    print("\n4️⃣ 清空缓存...")
    count = cache.clear()
    print(f"   ✅ 已清空 {count} 条缓存")
    
    print("\n" + "=" * 80)
    print("✅ CacheService 示例运行完成")
    print("=" * 80)


if __name__ == "__main__":
    example_cache_service()