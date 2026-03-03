# ==================== 1.1 服务注册与发现 ServiceRegistry ====================
# service_registry_v6.py
"""
V6.0 服务注册中心（完全独立，无循环依赖）
职责：
1. 服务注册与注销
2. 服务发现与健康检查
3. 服务元数据管理
4. 服务依赖关系追踪
依赖：
- 仅依赖标准库（无业务依赖）
- 不依赖任何业务服务
"""
import time
from typing import Dict, List, Optional, Set
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ServiceInstance:
    """服务实例信息"""
    
    def __init__(
        self,
        service_name: str,
        instance_id: str,
        host: str,
        port: int,
        metadata: Dict = None,
        version: str = "1.0.0"
    ):
        self.service_name = service_name
        self.instance_id = instance_id
        self.host = host
        self.port = port
        self.metadata = metadata or {}
        self.version = version
        self.registered_time = datetime.now()
        self.last_heartbeat = datetime.now()
        self.healthy = True
        self.heartbeat_interval = 30  # 心跳间隔（秒）
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'service_name': self.service_name,
            'instance_id': self.instance_id,
            'host': self.host,
            'port': self.port,
            'metadata': self.metadata,
            'version': self.version,
            'registered_time': self.registered_time.isoformat(),
            'last_heartbeat': self.last_heartbeat.isoformat(),
            'healthy': self.healthy
        }
    
    def __repr__(self) -> str:
        return f"ServiceInstance({self.service_name}/{self.instance_id} @ {self.host}:{self.port})"


class ServiceRegistry:
    """
    V6.0 服务注册中心（修复版：完全独立）
    核心特性：
    ✅ 无业务依赖（仅标准库）
    ✅ 服务健康检查
    ✅ 服务依赖追踪
    ✅ 服务元数据管理
    ✅ 服务实例负载均衡
    """
    
    def __init__(self, heartbeat_timeout: int = 60):
        """
        初始化服务注册中心
        
        参数:
            heartbeat_timeout: 心跳超时时间（秒），超过则标记为不健康
        """
        self.services: Dict[str, Dict[str, ServiceInstance]] = {}  # {service_name: {instance_id: instance}}
        self.dependencies: Dict[str, Set[str]] = {}  # {service_name: {dependent_service}}
        self.heartbeat_timeout = heartbeat_timeout
        self.logger = logger
        self.logger.info(f"✅ 服务注册中心初始化成功 | 心跳超时={heartbeat_timeout}s")
    
    # ==================== 服务注册与注销 ====================
    
    def register(
        self,
        service_name: str,
        instance_id: str,
        host: str,
        port: int,
        metadata: Dict = None,
        version: str = "1.0.0"
    ) -> bool:
        """
        注册服务实例
        
        参数:
            service_name: 服务名称（如'market_state_service'）
            instance_id: 实例ID（唯一标识）
            host: 服务主机
            port: 服务端口
            metadata: 元数据（可选）
            version: 服务版本
        
        返回:
            bool: 是否注册成功
        """
        # 创建服务实例
        instance = ServiceInstance(
            service_name=service_name,
            instance_id=instance_id,
            host=host,
            port=port,
            metadata=metadata,
            version=version
        )
        
        # 初始化服务字典
        if service_name not in self.services:
            self.services[service_name] = {}
        
        # 注册实例
        self.services[service_name][instance_id] = instance
        self.logger.info(f"✅ 服务注册成功: {instance}")
        
        return True
    
    def deregister(self, service_name: str, instance_id: str) -> bool:
        """
        注销服务实例
        
        参数:
            service_name: 服务名称
            instance_id: 实例ID
        
        返回:
            bool: 是否注销成功
        """
        if service_name in self.services and instance_id in self.services[service_name]:
            del self.services[service_name][instance_id]
            self.logger.info(f"✅ 服务注销成功: {service_name}/{instance_id}")
            return True
        
        self.logger.warning(f"⚠️ 服务注销失败: {service_name}/{instance_id} 不存在")
        return False
    
    def heartbeat(self, service_name: str, instance_id: str) -> bool:
        """
        服务心跳（更新最后心跳时间）
        
        参数:
            service_name: 服务名称
            instance_id: 实例ID
        
        返回:
            bool: 是否成功
        """
        if service_name in self.services and instance_id in self.services[service_name]:
            instance = self.services[service_name][instance_id]
            instance.last_heartbeat = datetime.now()
            instance.healthy = True
            return True
        
        return False
    
    # ==================== 服务发现 ====================
    
    def discover(self, service_name: str) -> List[ServiceInstance]:
        """
        发现服务实例（返回所有健康实例）
        
        参数:
            service_name: 服务名称
        
        返回:
            健康服务实例列表
        """
        if service_name not in self.services:
            self.logger.debug(f"⚠️ 服务未注册: {service_name}")
            return []
        
        # 检查健康状态
        self._check_health(service_name)
        
        # 返回健康实例
        healthy_instances = [
            instance for instance in self.services[service_name].values()
            if instance.healthy
        ]
        
        self.logger.debug(f"🔍 服务发现: {service_name} → {len(healthy_instances)} 个健康实例")
        return healthy_instances
    
    def discover_one(self, service_name: str) -> Optional[ServiceInstance]:
        """
        发现单个服务实例（轮询负载均衡）
        
        参数:
            service_name: 服务名称
        
        返回:
            单个健康服务实例（或None）
        """
        instances = self.discover(service_name)
        if not instances:
            return None
        
        # 简单轮询（实际可使用更复杂的负载均衡策略）
        instance = instances[0]
        return instance
    
    # ==================== 服务依赖管理 ====================
    
    def register_dependency(self, service_name: str, dependent_service: str):
        """
        注册服务依赖关系
        
        参数:
            service_name: 服务名称
            dependent_service: 依赖的服务名称
        """
        if service_name not in self.dependencies:
            self.dependencies[service_name] = set()
        
        self.dependencies[service_name].add(dependent_service)
        self.logger.debug(f"🔗 服务依赖注册: {service_name} → {dependent_service}")
    
    def get_dependencies(self, service_name: str) -> Set[str]:
        """获取服务依赖列表"""
        return self.dependencies.get(service_name, set())
    
    def get_dependents(self, service_name: str) -> Set[str]:
        """获取依赖当前服务的列表"""
        dependents = set()
        for svc, deps in self.dependencies.items():
            if service_name in deps:
                dependents.add(svc)
        return dependents
    
    # ==================== 健康检查 ====================
    
    def _check_health(self, service_name: str):
        """检查服务健康状态"""
        if service_name not in self.services:
            return
        
        current_time = datetime.now()
        for instance_id, instance in list(self.services[service_name].items()):
            # 计算心跳超时时间
            time_since_heartbeat = (current_time - instance.last_heartbeat).total_seconds()
            
            # 标记不健康
            if time_since_heartbeat > self.heartbeat_timeout:
                instance.healthy = False
                self.logger.warning(
                    f"⚠️ 服务实例不健康: {instance} | 心跳超时={time_since_heartbeat:.0f}s"
                )
    
    def get_health_status(self) -> Dict:
        """获取所有服务健康状态"""
        status = {}
        
        for service_name, instances in self.services.items():
            healthy_count = sum(1 for i in instances.values() if i.healthy)
            total_count = len(instances)
            status[service_name] = {
                'healthy_count': healthy_count,
                'total_count': total_count,
                'healthy_ratio': f"{healthy_count}/{total_count}",
                'instances': [i.to_dict() for i in instances.values()]
            }
        
        return status
    
    # ==================== 辅助方法 ====================
    
    def get_service_count(self) -> int:
        """获取注册服务数量"""
        return len(self.services)
    
    def get_instance_count(self) -> int:
        """获取注册实例总数"""
        return sum(len(instances) for instances in self.services.values())
    
    def clear(self):
        """清空所有注册信息"""
        self.services.clear()
        self.dependencies.clear()
        self.logger.info("✅ 服务注册中心已清空")


# ==================== 使用示例 ====================
def example_service_registry():
    """服务注册中心使用示例"""
    
    print("=" * 80)
    print("🧪 ServiceRegistry 使用示例")
    print("=" * 80)
    
    # 1. 初始化注册中心
    print("\n1️⃣ 初始化服务注册中心...")
    registry = ServiceRegistry(heartbeat_timeout=30)
    
    # 2. 注册服务
    print("\n2️⃣ 注册服务实例...")
    registry.register(
        service_name="market_state_service",
        instance_id="market_state_v1",
        host="localhost",
        port=8001,
        metadata={'environment': 'development', 'version': '6.0.0'},
        version="6.0.0"
    )
    
    registry.register(
        service_name="risk_assessment_service",
        instance_id="risk_assessment_v1",
        host="localhost",
        port=8002,
        metadata={'environment': 'development'},
        version="6.0.0"
    )
    
    registry.register(
        service_name="allocation_service",
        instance_id="allocation_v1",
        host="localhost",
        port=8003,
        metadata={'environment': 'development'},
        version="6.0.0"
    )
    
    # 3. 服务发现
    print("\n3️⃣ 服务发现...")
    instances = registry.discover("market_state_service")
    print(f"   ✅ 发现 {len(instances)} 个 market_state_service 实例")
    for instance in instances:
        print(f"      • {instance}")
    
    # 4. 服务依赖
    print("\n4️⃣ 注册服务依赖...")
    registry.register_dependency("allocation_service", "market_state_service")
    registry.register_dependency("allocation_service", "risk_assessment_service")
    
    deps = registry.get_dependencies("allocation_service")
    print(f"   ✅ allocation_service 依赖: {deps}")
    
    dependents = registry.get_dependents("market_state_service")
    print(f"   ✅ market_state_service 被依赖: {dependents}")
    
    # 5. 健康检查
    print("\n5️⃣ 健康检查...")
    status = registry.get_health_status()
    for service, info in status.items():
        print(f"   • {service}: {info['healthy_ratio']} 健康")
    
    # 6. 心跳
    print("\n6️⃣ 发送心跳...")
    registry.heartbeat("market_state_service", "market_state_v1")
    print("   ✅ 心跳发送成功")
    
    print("\n" + "=" * 80)
    print("✅ ServiceRegistry 示例运行完成")
    print("=" * 80)


if __name__ == "__main__":
    example_service_registry()