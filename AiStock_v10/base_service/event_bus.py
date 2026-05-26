#!/usr/bin/env python3
"""AiStock V10 — 系统间事件总线 (EventBus)

特性:
  - 主题发布/订阅: 支持精确匹配和通配符
  - 系统间数据交互: 子系统通过事件总线交换数据
  - 事件历史: 支持后订阅者回放
  - 线程安全
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class Event:
    """事件数据类"""
    topic: str
    data: Any = None
    source: str = ""
    timestamp: float = field(default_factory=time.time)


class Topics:
    """预定义主题常量"""
    CONFIG_CHANGED = "config.changed"
    DATA_LOADED = "data.loaded"
    MARKET_STATE_UPDATED = "market_state.updated"
    CONTRACT_ROLLOVER = "contract.rollover"
    SUBSYSTEM_STARTED = "subsystem.started"
    SUBSYSTEM_STOPPED = "subsystem.stopped"
    PRICE_SIGNAL = "price_quant.signal"


class _Subscription:
    """订阅记录"""
    def __init__(self, topic_pattern: str, callback: Callable[[Event], None]):
        self.topic_pattern = topic_pattern
        self.callback = callback
        self.active = True


class EventBus:
    """V10 系统间事件总线"""
    
    def __init__(self, history_size: int = 100):
        self._subscriptions: List[_Subscription] = []
        self._history: List[Event] = []
        self._history_size = history_size
        self._lock = threading.RLock()
    
    def subscribe(self, topic: str, callback: Callable[[Event], None]) -> str:
        """订阅主题

        Args:
            topic: 主题, 支持通配符:
                   "config.changed" — 精确匹配
                   "config.*" — 单层通配
                   "market_state.**" — 多层通配
            callback: 事件回调函数

        Returns:
            订阅ID (用于取消订阅)
        """
        sub = _Subscription(topic, callback)
        with self._lock:
            self._subscriptions.append(sub)
        logger.debug("事件订阅: %s", topic)
        return id(sub)
    
    def unsubscribe(self, sub_id: str) -> None:
        """取消订阅"""
        with self._lock:
            for sub in self._subscriptions:
                if id(sub) == sub_id:
                    sub.active = False
                    break
    
    def publish(self, topic: str, data: Any = None, source: str = "") -> None:
        """发布事件"""
        event = Event(topic=topic, data=data, source=source)
        
        with self._lock:
            self._history.append(event)
            if len(self._history) > self._history_size:
                self._history = self._history[-self._history_size:]
            
            subscribers = [s for s in self._subscriptions if s.active]
        
        for sub in subscribers:
            if self._match_topic(sub.topic_pattern, topic):
                try:
                    sub.callback(event)
                except Exception as e:
                    logger.error("事件回调异常 [%s → %s]: %s", topic, sub.topic_pattern, e)
    
    def replay(self, topic: str, callback: Callable[[Event], None], limit: int = 10) -> None:
        """回放历史事件"""
        with self._lock:
            matching = [
                e for e in reversed(self._history)
                if self._match_topic(topic, e.topic)
            ][:limit]
        
        for event in matching:
            try:
                callback(event)
            except Exception as e:
                logger.error("回放回调异常: %s", e)
    
    @staticmethod
    def _match_topic(pattern: str, topic: str) -> bool:
        """匹配主题"""
        if pattern == topic:
            return True
        if pattern == "*":
            return True
        if pattern.endswith(".**"):
            prefix = pattern[:-3]
            return topic == prefix or topic.startswith(prefix + ".")
        if pattern.endswith(".*"):
            prefix = pattern[:-2]
            if not topic.startswith(prefix + "."):
                return False
            remainder = topic[len(prefix) + 1:]
            return "." not in remainder
        return False
