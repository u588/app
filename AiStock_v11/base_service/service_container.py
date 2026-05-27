#!/usr/bin/env python3
"""AiStock V10 — 服务容器 (ServiceContainer)

轻量级依赖注入容器:
  - 单例注册: register_singleton(name, instance)
  - 懒加载: register_factory(name, factory)
  - 获取服务: get(name)
  - 子系统基础类: SubsystemBase (自动注入 shared services)
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional, Type

logger = logging.getLogger(__name__)


class ServiceContainer:
    """V10 服务容器 — 轻量级 DI"""
    
    def __init__(self):
        self._singletons: Dict[str, Any] = {}
        self._factories: Dict[str, Callable] = {}
        self._initialized: Dict[str, bool] = {}
    
    def register_singleton(self, name: str, instance: Any) -> None:
        """注册单例实例"""
        self._singletons[name] = instance
        self._initialized[name] = True
        logger.debug("服务注册(单例): %s", name)
    
    def register_factory(self, name: str, factory: Callable[[], Any]) -> None:
        """注册工厂函数 (懒加载)"""
        self._factories[name] = factory
        self._initialized[name] = False
        logger.debug("服务注册(工厂): %s", name)
    
    def get(self, name: str) -> Any:
        """获取服务实例"""
        if name in self._singletons:
            return self._singletons[name]
        
        if name in self._factories:
            if not self._initialized.get(name, False):
                instance = self._factories[name]()
                self._singletons[name] = instance
                self._initialized[name] = True
                logger.info("服务懒加载: %s", name)
            return self._singletons[name]
        
        raise KeyError(f"未注册的服务: {name}")
    
    def has(self, name: str) -> bool:
        """检查服务是否已注册"""
        return name in self._singletons or name in self._factories
    
    def list_services(self) -> list:
        """列出所有已注册服务"""
        return list(set(list(self._singletons.keys()) + list(self._factories.keys())))


class SubsystemBase:
    """子系统基类 — 自动注入共享服务

    所有子系统继承此类, 自动获得:
    - config: ConfigService (子系统隔离配置)
    - cache: CacheService (命名空间隔离)
    - event_bus: EventBus (系统间通信)
    - logger: Logger
    
    Usage:
        class MarketStateSubsystem(SubsystemBase):
            def __init__(self, container: ServiceContainer):
                super().__init__("market_state", container)
                # self.config, self.cache, self.event_bus, self.logger 已可用
    """
    
    def __init__(self, name: str, container: ServiceContainer):
        self._name = name
        self._container = container
        
        # 自动注入共享服务
        self.config = container.get("config")
        self.cache = container.get("cache")
        self.event_bus = container.get("event_bus")
        self.logger = logging.getLogger(f"aistock.subsystems.{name}")
        
        # 获取子系统专属配置 (4层合并)
        self._subsystem_config = self.config.get_subsystem_config(name)
        
        self.logger.info("子系统 [%s] 初始化完成", name)
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def subsystem_config(self) -> Dict:
        """获取子系统专属配置 (合并后的)"""
        return self._subsystem_config
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """便捷方法: 从子系统配置中获取值"""
        return self.config.get(key, default)
    
    def publish_event(self, topic_suffix: str, data: Any = None) -> None:
        """便捷方法: 发布子系统事件"""
        from .event_bus import EventBus
        topic = f"{self._name}.{topic_suffix}"
        self.event_bus.publish(topic, data, source=self._name)
    
    def start(self) -> None:
        """子系统集成动 — 子类可重写"""
        self.event_bus.publish(
            f"subsystem.started", 
            {"name": self._name}, 
            source=self._name
        )
    
    def stop(self) -> None:
        """子系统停止 — 子类可重写"""
        self.event_bus.publish(
            f"subsystem.stopped", 
            {"name": self._name}, 
            source=self._name
        )
