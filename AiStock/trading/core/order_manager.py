#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OrderManager：订单状态机与幂等控制
职责：防重复提交、状态追踪、超时撤单、成交回报处理
"""
from typing import Dict, Optional, Any, List
from datetime import datetime, timedelta
import uuid
import logging
import time

logger = logging.getLogger(__name__)

class OrderManager:
    def __init__(self, timeout_seconds: int = 300):
        self.orders: Dict[str, Dict] = {}  # client_order_id -> order_info
        self.timeout = timeout_seconds
        self.max_retries = 3
        
    def generate_client_id(self, code: str, side: str) -> str:
        """生成幂等客户端订单号"""
        return f"AI_{code}_{side}_{uuid.uuid4().hex[:8]}_{int(time.time())}"
        
    def submit_order(self, client_id: str, broker_order_id: str, code: str, side: str, 
                     volume: int, price: float) -> None:
        """记录提交订单"""
        self.orders[client_id] = {
            'client_id': client_id,
            'broker_order_id': broker_order_id,
            'code': code,
            'side': side,
            'volume': volume,
            'price': price,
            'traded_volume': 0,
            'status': 'submitted',
            'submit_time': datetime.now(),
            'update_time': datetime.now(),
            'retry_count': 0
        }
        logger.info(f"📦 订单已提交: {client_id} -> {broker_order_id}")
        
    def update_order_status(self, client_id: str, status: str, traded_vol: int = 0, 
                            avg_price: float = 0.0, reject_reason: str = "") -> bool:
        """更新订单状态"""
        if client_id not in self.orders:
            logger.warning(f"⚠️ 未知订单更新: {client_id}")
            return False
            
        order = self.orders[client_id]
        order['status'] = status
        order['traded_volume'] = traded_vol
        order['avg_price'] = avg_price
        order['update_time'] = datetime.now()
        if reject_reason:
            order['reject_reason'] = reject_reason
            
        logger.info(f"🔄 订单状态更新: {client_id} -> {status} (成交:{traded_vol})")
        return True
        
    def check_timeout_orders(self) -> List[str]:
        """检查超时未成交订单，返回需撤单的 client_id"""
        timeout_ids = []
        now = datetime.now()
        for cid, order in self.orders.items():
            if order['status'] in ('submitted', 'partial_filled') and \
               (now - order['update_time']).total_seconds() > self.timeout:
                timeout_ids.append(cid)
        return timeout_ids
        
    def get_pending_orders(self) -> List[Dict]:
        """获取未完成订单"""
        return [o for o in self.orders.values() if o['status'] not in ('filled', 'cancelled', 'rejected')]