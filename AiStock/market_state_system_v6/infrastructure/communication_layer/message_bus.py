# ==================== 1.2 发布/订阅消息总线 MessageBus ====================
# message_bus_v6.py
"""
V6.0 消息总线（完全独立，无循环依赖）
职责：
1. 发布/订阅模式消息传递
2. 事件驱动架构支持
3. 异步消息队列
4. 消息持久化（可选）
依赖：
- 仅依赖标准库（无业务依赖）
- 不依赖任何业务服务
"""
import queue
import threading
from typing import Dict, List, Callable, Any, Optional
from datetime import datetime
import logging
import json

logger = logging.getLogger(__name__)


class Message:
    """消息对象"""
    
    def __init__(
        self,
        topic: str,
        payload: Any,
        sender: str = "unknown",
        timestamp: datetime = None,
        message_id: str = None
    ):
        self.topic = topic
        self.payload = payload
        self.sender = sender
        self.timestamp = timestamp or datetime.now()
        self.message_id = message_id or f"msg_{int(self.timestamp.timestamp() * 1000)}"
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'topic': self.topic,
            'payload': self.payload,
            'sender': self.sender,
            'timestamp': self.timestamp.isoformat(),
            'message_id': self.message_id
        }
    
    def __repr__(self) -> str:
        return f"Message({self.topic} from {self.sender} @ {self.timestamp})"


class MessageBus:
    """
    V6.0 消息总线（修复版：完全独立）
    核心特性：
    ✅ 无业务依赖（仅标准库）
    ✅ 发布/订阅模式
    ✅ 异步消息处理
    ✅ 消息持久化（内存队列）
    ✅ 事件驱动架构支持
    """
    
    def __init__(self, max_queue_size: int = 1000):
        """
        初始化消息总线
        
        参数:
            max_queue_size: 消息队列最大容量
        """
        self.subscribers: Dict[str, List[Callable]] = {}  # {topic: [callback]}
        self.message_queue = queue.Queue(maxsize=max_queue_size)
        self.running = False
        self.worker_thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()
        self.logger = logger
        self.logger.info(f"✅ 消息总线初始化成功 | 队列容量={max_queue_size}")
    
    # ==================== 订阅管理 ====================
    
    def subscribe(self, topic: str, callback: Callable):
        """
        订阅主题
        
        参数:
            topic: 主题名称（支持通配符 *）
            callback: 回调函数（接收Message对象）
        """
        with self.lock:
            if topic not in self.subscribers:
                self.subscribers[topic] = []
            
            self.subscribers[topic].append(callback)
            self.logger.info(f"✅ 订阅成功: {topic} → {callback.__name__}")
    
    def unsubscribe(self, topic: str, callback: Callable):
        """取消订阅"""
        with self.lock:
            if topic in self.subscribers and callback in self.subscribers[topic]:
                self.subscribers[topic].remove(callback)
                self.logger.info(f"✅ 取消订阅: {topic} ← {callback.__name__}")
    
    def unsubscribe_all(self, topic: str):
        """取消主题所有订阅"""
        with self.lock:
            if topic in self.subscribers:
                count = len(self.subscribers[topic])
                del self.subscribers[topic]
                self.logger.info(f"✅ 取消 {count} 个订阅: {topic}")
    
    # ==================== 消息发布 ====================
    
    def publish(self, topic: str, payload: Any, sender: str = "unknown"):
        """
        发布消息
        
        参数:
            topic: 主题名称
            payload: 消息载荷（任意类型）
            sender: 发送者名称
        """
        message = Message(topic=topic, payload=payload, sender=sender)
        
        # 尝试放入队列（非阻塞）
        try:
            self.message_queue.put_nowait(message)
            self.logger.debug(f"📤 消息发布: {message}")
        except queue.Full:
            self.logger.warning(f"⚠️ 消息队列已满，丢弃消息: {topic}")
    
    # ==================== 消息处理 ====================
    
    def start(self):
        """启动消息处理线程"""
        if self.running:
            self.logger.warning("⚠️ 消息总线已在运行")
            return
        
        self.running = True
        self.worker_thread = threading.Thread(target=self._process_messages, daemon=True)
        self.worker_thread.start()
        self.logger.info("✅ 消息总线已启动")
    
    def stop(self):
        """停止消息处理线程"""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=2.0)
        self.logger.info("✅ 消息总线已停止")
    
    def _process_messages(self):
        """处理消息队列（工作线程）"""
        while self.running:
            try:
                # 阻塞等待消息（超时1秒）
                message = self.message_queue.get(timeout=1.0)
                
                # 处理消息
                self._dispatch_message(message)
                
                # 标记任务完成
                self.message_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"❌ 消息处理异常: {str(e)}")
    
    def _dispatch_message(self, message: Message):
        """分发消息到订阅者"""
        # 1. 精确匹配
        if message.topic in self.subscribers:
            for callback in self.subscribers[message.topic]:
                try:
                    callback(message)
                except Exception as e:
                    self.logger.error(f"❌ 订阅者回调异常 {callback.__name__}: {str(e)}")
        
        # 2. 通配符匹配（topic/*）
        wildcard_topic = message.topic.rsplit('/', 1)[0] + '/*'
        if wildcard_topic in self.subscribers:
            for callback in self.subscribers[wildcard_topic]:
                try:
                    callback(message)
                except Exception as e:
                    self.logger.error(f"❌ 订阅者回调异常 {callback.__name__}: {str(e)}")
    
    # ==================== 辅助方法 ====================
    
    def get_subscriber_count(self, topic: str) -> int:
        """获取主题订阅者数量"""
        return len(self.subscribers.get(topic, []))
    
    def get_all_topics(self) -> List[str]:
        """获取所有主题"""
        return list(self.subscribers.keys())
    
    def clear(self):
        """清空所有订阅"""
        with self.lock:
            self.subscribers.clear()
        self.logger.info("✅ 消息总线订阅已清空")


# ==================== 使用示例 ====================
def example_message_bus():
    """消息总线使用示例"""
    
    print("=" * 80)
    print("🧪 MessageBus 使用示例")
    print("=" * 80)
    
    # 1. 初始化消息总线
    print("\n1️⃣ 初始化消息总线...")
    bus = MessageBus(max_queue_size=100)
    bus.start()
    
    # 2. 定义订阅者回调
    def on_market_update(message: Message):
        print(f"   📊 市场状态更新: {message.payload}")
    
    def on_risk_alert(message: Message):
        print(f"   ⚠️ 风险预警: {message.payload}")
    
    def on_allocation_change(message: Message):
        print(f"   💼 配置变更: {message.payload}")
    
    # 3. 订阅主题
    print("\n2️⃣ 订阅主题...")
    bus.subscribe("market/state", on_market_update)
    bus.subscribe("risk/alert", on_risk_alert)
    bus.subscribe("allocation/*", on_allocation_change)  # 通配符订阅
    
    # 4. 发布消息
    print("\n3️⃣ 发布消息...")
    bus.publish("market/state", {"state": "战略进攻区", "score": 85}, sender="market_state_service")
    bus.publish("risk/alert", {"level": "high", "message": "微盘熔断"}, sender="risk_service")
    bus.publish("allocation/update", {"direction": "高端制造", "weight": 0.28}, sender="allocation_service")
    bus.publish("allocation/rebalance", {"timestamp": "2026-03-02"}, sender="allocation_service")
    
    # 等待消息处理
    import time
    time.sleep(0.5)
    
    # 5. 查询订阅信息
    print("\n4️⃣ 订阅信息...")
    print(f"   • market/state 订阅者: {bus.get_subscriber_count('market/state')} 个")
    print(f"   • risk/alert 订阅者: {bus.get_subscriber_count('risk/alert')} 个")
    print(f"   • allocation/* 订阅者: {bus.get_subscriber_count('allocation/*')} 个")
    
    # 6. 停止消息总线
    print("\n5️⃣ 停止消息总线...")
    bus.stop()
    
    print("\n" + "=" * 80)
    print("✅ MessageBus 示例运行完成")
    print("=" * 80)


if __name__ == "__main__":
    example_message_bus()