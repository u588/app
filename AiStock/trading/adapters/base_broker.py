#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BaseBroker：券商交易接口抽象基类
职责：定义标准交易方法，支持多券商无缝切换
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class OrderSide(Enum):
    BUY = 1
    SELL = -1

class OrderType(Enum):
    LIMIT = 0
    MARKET = 1
    FOK = 2
    FAK = 3

@dataclass
class OrderRequest:
    code: str
    side: OrderSide
    volume: int
    price: float = 0.0
    order_type: OrderType = OrderType.LIMIT
    client_order_id: str = ""
    strategy_name: str = "dynamic_price"

@dataclass
class OrderStatus:
    order_id: str
    client_order_id: str
    code: str
    side: OrderSide
    volume: int
    traded_volume: int = 0
    avg_price: float = 0.0
    status: str = "pending"  # pending/submitted/partial_filled/filled/cancelled/rejected
    reject_reason: str = ""
    update_time: str = ""

class BaseBroker(ABC):
    """券商适配器基类"""
    
    @abstractmethod
    def connect(self, **kwargs) -> bool:
        """连接券商柜台"""
        pass
    
    @abstractmethod
    def disconnect(self):
        """断开连接"""
        pass
    
    @abstractmethod
    def get_account_info(self) -> Dict[str, float]:
        """获取账户资金 {可用资金, 总资产, 冻结资金, 当日盈亏}"""
        pass
    
    @abstractmethod
    def get_positions(self) -> List[Dict[str, Any]]:
        """获取持仓列表 [{code, volume, cost_price, market_value, profit}]"""
        pass
    
    @abstractmethod
    def get_orders(self, status: Optional[str] = None) -> List[Dict]:
        """获取委托列表"""
        pass
    
    @abstractmethod
    def place_order(self, order: OrderRequest) -> str:
        """下单，返回券商订单号"""
        pass
    
    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """撤单"""
        pass
    
    def is_connected(self) -> bool:
        """检查连接状态"""
        return getattr(self, '_connected', False)