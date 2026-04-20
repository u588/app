#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QMTAdapter：MiniQMT 交易适配器
依赖：pip install xtquant
"""
from .base_broker import BaseBroker, OrderRequest, OrderStatus, OrderSide, OrderType
from typing import Dict, List, Optional, Any
import logging
import time
from xtquant import xttrader, xtconstant

logger = logging.getLogger(__name__)

class QMTAdapter(BaseBroker):
    def __init__(self, path: str, session_id: int):
        self.path = path
        self.session_id = session_id
        self.xt_trader: Optional[xttrader.XtTrader] = None
        self._connected = False
        self._order_callback = None
        self._trade_callback = None
        
    def connect(self, **kwargs) -> bool:
        try:
            self.xt_trader = xttrader.XtTrader(self.path, self.session_id)
            self.xt_trader.register_callback(self)
            self.xt_trader.start()
            self._connected = True
            logger.info(f"✅ MiniQMT 连接成功 (session_id={self.session_id})")
            return True
        except Exception as e:
            logger.error(f"❌ MiniQMT 连接失败: {e}")
            return False
            
    def disconnect(self):
        if self.xt_trader:
            self.xt_trader.stop()
            self._connected = False
            logger.info("🔌 MiniQMT 已断开")
            
    def get_account_info(self) -> Dict[str, float]:
        if not self._connected:
            raise ConnectionError("未连接券商")
        asset = self.xt_trader.query_asset()
        return {
            "available_cash": asset.cash,
            "total_asset": asset.total_asset,
            "frozen_cash": asset.frozen_cash,
            "daily_pnl": asset.daily_pnl
        }
        
    def get_positions(self) -> List[Dict[str, Any]]:
        if not self._connected:
            raise ConnectionError("未连接券商")
        positions = self.xt_trader.query_positions()
        return [
            {
                "code": pos.stock_code,
                "volume": pos.volume,
                "can_use_volume": pos.can_use_volume,
                "cost_price": pos.open_price,
                "market_value": pos.market_value,
                "profit": pos.profit
            } for pos in positions
        ]
        
    def get_orders(self, status: Optional[str] = None) -> List[Dict]:
        if not self._connected:
            raise ConnectionError("未连接券商")
        orders = self.xt_trader.query_orders()
        if status:
            orders = [o for o in orders if o.status == status]
        return [o.__dict__ for o in orders]
        
    def place_order(self, order: OrderRequest) -> str:
        if not self._connected:
            raise ConnectionError("未连接券商")
            
        # 映射侧边与类型
        side = xtconstant.STOCK_BUY if order.side == OrderSide.BUY else xtconstant.STOCK_SELL
        order_type = xtconstant.LATEST_PRICE if order.order_type == OrderType.MARKET else xtconstant.FIX_PRICE
        
        try:
            order_id = self.xt_trader.order_stock(
                account=self.session_id,
                stock_code=order.code,
                order_type=order_type,
                order_volume=order.volume,
                price_type=order.price if order.price > 0 else -1,
                strategy_name=order.strategy_name,
                order_remark=order.client_order_id
            )
            logger.info(f"📤 下单成功: {order.code} {order.side.name} {order.volume} @ {order.price} | 订单号:{order_id}")
            return str(order_id)
        except Exception as e:
            logger.error(f"❌ 下单失败 {order.code}: {e}")
            raise
            
    def cancel_order(self, order_id: str) -> bool:
        if not self._connected:
            raise ConnectionError("未连接券商")
        try:
            self.xt_trader.cancel_order_stock(self.session_id, int(order_id))
            logger.info(f"🗑️ 撤单成功: {order_id}")
            return True
        except Exception as e:
            logger.error(f"❌ 撤单失败 {order_id}: {e}")
            return False
            
    # xtquant 回调接口（可选实现）
    def on_order_stock_async_response(self, response):
        logger.debug(f"🔄 委托回报: {response.order_id} -> {response.status}")
        
    def on_trade_async_response(self, response):
        logger.debug(f"💰 成交回报: {response.order_id} 成交 {response.traded_volume} @ {response.traded_price}")