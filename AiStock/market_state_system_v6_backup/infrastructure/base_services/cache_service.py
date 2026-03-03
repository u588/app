# ==================== 2.1 缓存管理 (LRU缓存 + TTL + 统计) CacheService ====================
# cache_service_v6.py
"""
V6.0 缓存服务（完全独立，无循环依赖）
职责：
1. 统一缓存管理（LRU策略）
2. 缓存命中率统计
3. 缓存失效策略
4. 缓存监控与清理
依赖：
- 无外部依赖（仅使用标准库）
- 不依赖任何业务服务
"""
import time
from typing import Any, Optional, Dict, Tuple
from collections import OrderedDict
import logging

logger = logging.getLogger(__name__)


class CacheService:
    """V6.0 缓存服务（修复版：完全独立）"""
    
    def __init__(self, max_size: int = 1000, ttl: int = 3600):
        """
        初始化缓存服务
        
        参数:
            max_size: 缓存最大容量（默认1000）
            ttl: 缓存过期时间（秒，默认3600=1小时）
        """
        self.max_size = max_size
        self.ttl = ttl
        self.cache: OrderedDict = OrderedDict()  # LRU缓存
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
        """
        获取缓存数据
        
        参数:
            key: 缓存键
        
        返回:
            缓存数据（存在且未过期）或 None（不存在或已过期）
        """
        self.stats['total_requests'] += 1
        
        # 检查缓存是否存在
        if key not in self.cache:
            self.stats['misses'] += 1
            self.logger.debug(f"❌ 缓存未命中: {key}")
            return None
        
        # 检查TTL
        metadata = self.cache_metadata.get(key, {})
        if 'timestamp' in metadata:
            age = time.time() - metadata['timestamp']
            if age > self.ttl:
                self._remove(key)
                self.stats['misses'] += 1
                self.logger.debug(f"❌ 缓存过期: {key} (age={age:.0f}s > TTL={self.ttl}s)")
                return None
        
        # LRU: 移动到末尾（最近使用）
        value = self.cache.pop(key)
        self.cache[key] = value
        
        self.stats['hits'] += 1
        self.logger.debug(f"✅ 缓存命中: {key} | 命中率={self.get_hit_rate():.1%}")
        return value
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        设置缓存数据
        
        参数:
            key: 缓存键
            value: 缓存值
            ttl: 自定义TTL（秒），None=使用默认TTL
        
        返回:
            bool: 是否设置成功
        """
        # 移除旧缓存（如果存在）
        if key in self.cache:
            self._remove(key)
        
        # LRU: 添加到末尾
        self.cache[key] = value
        self.cache_metadata[key] = {
            'timestamp': time.time(),
            'ttl': ttl or self.ttl,
            'size': self._estimate_size(value)
        }
        
        # 检查容量，移除最旧的
        if len(self.cache) > self.max_size:
            oldest_key = next(iter(self.cache))
            self._remove(oldest_key)
            self.stats['evictions'] += 1
            self.logger.debug(f"⚠️ 缓存驱逐: {oldest_key} (容量={self.max_size})")
        
        self.logger.debug(f"✅ 缓存设置: {key} | TTL={ttl or self.ttl}s")
        return True
    
    def delete(self, key: str) -> bool:
        """删除指定缓存"""
        return self._remove(key)
    
    def clear(self) -> int:
        """清空所有缓存，返回清除数量"""
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
            del self.cache_metadata[key]
            return True
        return False
    
    def _estimate_size(self, value: Any) -> int:
        """估算缓存大小（字节）"""
        try:
            if isinstance(value, (str, bytes)):
                return len(value)
            elif isinstance(value, (list, dict, tuple)):
                return sum(self._estimate_size(v) for v in value) if isinstance(value, dict) else sum(self._estimate_size(v) for v in value)
            elif hasattr(value, '__sizeof__'):
                return value.__sizeof__()
            else:
                return 100  # 默认估算
        except:
            return 100
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息
        
        返回:
            {
                'hits': int,
                'misses': int,
                'hit_rate': float,  # 命中率（0-1）
                'evictions': int,
                'total_requests': int,
                'current_size': int,
                'max_size': int,
                'ttl': int,
                'cache_keys': List[str]
            }
        """
        hit_rate = self.stats['hits'] / self.stats['total_requests'] if self.stats['total_requests'] > 0 else 0.0
        
        return {
            'hits': self.stats['hits'],
            'misses': self.stats['misses'],
            'hit_rate': float(hit_rate),  # ⭐ 强制转换为Python float
            'evictions': self.stats['evictions'],
            'total_requests': self.stats['total_requests'],
            'current_size': len(self.cache),
            'max_size': self.max_size,
            'ttl': self.ttl,
            'cache_keys': list(self.cache.keys())
        }
    
    def get_hit_rate(self) -> float:
        """获取缓存命中率（0-1）"""
        if self.stats['total_requests'] == 0:
            return 0.0
        return float(self.stats['hits'] / self.stats['total_requests'])  # ⭐ 强制转换
    
    def invalidate(self, prefix: str) -> int:
        """
        使指定前缀的缓存失效
        
        参数:
            prefix: 缓存键前缀（如'index_'）
        
        返回:
            失效的缓存数量
        """
        keys_to_remove = [k for k in self.cache.keys() if k.startswith(prefix)]
        for key in keys_to_remove:
            self._remove(key)
        
        count = len(keys_to_remove)
        if count > 0:
            self.logger.info(f"✅ 缓存失效: {count}条 (前缀='{prefix}')")
        return count
    
    def compact(self) -> int:
        """
        压缩缓存：移除所有过期缓存
        
        返回:
            移除的缓存数量
        """
        expired_keys = []
        current_time = time.time()
        
        for key, metadata in self.cache_metadata.items():
            age = current_time - metadata['timestamp']
            if age > metadata['ttl']:
                expired_keys.append(key)
        
        for key in expired_keys:
            self._remove(key)
        
        if expired_keys:
            self.logger.info(f"✅ 缓存压缩: 移除{len(expired_keys)}条过期缓存")
        return len(expired_keys)
    
    # ==================== 调试工具 ====================
    
    def inspect_key(self, key: str) -> Optional[Dict]:
        """
        检查指定缓存键的详细信息
        
        返回:
            {
                'exists': bool,
                'value_type': str,
                'value_size': int,
                'age': float,
                'ttl': int,
                'expires_in': float
            } or None
        """
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
            'age': float(age),  # ⭐ 强制转换
            'ttl': metadata['ttl'],
            'expires_in': float(expires_in)  # ⭐ 强制转换
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
    
    # 1. 初始化缓存服务
    cache = CacheService(max_size=100, ttl=60)  # 小容量+短TTL（示例用）
    
    # 2. 设置缓存
    print("\n1️⃣ 设置缓存...")
    cache.set('user:1001', {'name': '张三', 'age': 30})
    cache.set('stock:000300', [4000, 4050, 4100, 4080, 4120])
    cache.set('config:system', {'timeout': 30, 'retry': 3})
    
    # 3. 获取缓存
    print("\n2️⃣ 获取缓存...")
    user = cache.get('user:1001')
    print(f"   ✅ user:1001 = {user}")
    
    stock = cache.get('stock:000300')
    print(f"   ✅ stock:000300 = {stock[:3]}... (共{len(stock)}个)")
    
    # 4. 缓存统计
    print("\n3️⃣ 缓存统计...")
    stats = cache.get_stats()
    print(f"   命中率: {stats['hit_rate']:.1%}")
    print(f"   命中/未命中: {stats['hits']}/{stats['misses']}")
    print(f"   当前容量: {stats['current_size']}/{stats['max_size']}")
    
    # 5. 缓存失效
    print("\n4️⃣ 缓存失效...")
    count = cache.invalidate('user:')
    print(f"   ✅ 失效'user:'前缀的缓存: {count}条")
    
    # 6. 检查缓存键
    print("\n5️⃣ 检查缓存键...")
    info = cache.inspect_key('stock:000300')
    if info:
        print(f"   ✅ stock:000300 存在 | 类型={info['value_type']} | 年龄={info['age']:.1f}s | TTL={info['ttl']}s")
    else:
        print("   ❌ stock:000300 不存在")
    
    # 7. 清空缓存
    print("\n6️⃣ 清空缓存...")
    count = cache.clear()
    print(f"   ✅ 已清空 {count} 条缓存")
    
    print("\n" + "=" * 80)
    print("✅ CacheService 示例运行完成")
    print("=" * 80)


if __name__ == "__main__":
    example_cache_service()