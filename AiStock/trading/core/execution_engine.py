#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ExecutionEngine：实盘交易执行引擎
职责：信号接收 -> 风控校验 -> 订单拆分 -> 路由下单 -> 状态同步 -> 日志归档
"""
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging
import yaml
from pathlib import Path

from ..adapters.base_broker import BaseBroker, OrderRequest, OrderSide
from .risk_controller import RiskController
from .order_manager import OrderManager
from ..dynamic_price_system.portfolio.tracker import PortfolioTracker

logger = logging.getLogger(__name__)

class ExecutionEngine:
    def __init__(self, broker: BaseBroker, config_path: str):
        self.broker = broker
        self.risk = RiskController(config_path)
        self.order_mgr = OrderManager(timeout_seconds=300)
        self.portfolio = PortfolioTracker(initial_capital=1_000_000)  # 与策略同步
        
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        self.dry_run = self.config.get('execution', {}).get('dry_run', True)
        
    def start_trading_day(self):
        """开盘初始化"""
        if not self.broker.is_connected():
            self.broker.connect()
            
        asset = self.broker.get_account_info()
        self.risk.set_daily_start_asset(asset['total_asset'])
        self.portfolio.cash = asset['available_cash']
        logger.info("🌅 交易日初始化完成 | 干跑模式: ON" if self.dry_run else "🔴 实盘模式: ON")
        
    def execute_rebalance(self, target_weights: Dict[str, float], 
                          current_positions: List[Dict], market_prices: Dict[str, float]) -> List[str]:
        """
        执行调仓（核心方法）
        返回: 成功提交的 client_order_id 列表
        """
        executed_ids = []
        total_asset = sum(p['market_value'] for p in current_positions) + self.portfolio.cash
        
        for code, target_w in target_weights.items():
            if target_w <= 0:
                continue
                
            # 计算目标数量
            target_value = total_asset * target_w
            current_pos = next((p for p in current_positions if p['code'] == code), None)
            current_value = current_pos['market_value'] if current_pos else 0.0
            delta_value = target_value - current_value
            
            if abs(delta_value) < 1000:  # 忽略小额调仓
                continue
                
            price = market_prices.get(code, 0)
            if price <= 0:
                logger.warning(f"⚠️ 无行情价格跳过: {code}")
                continue
                
            side = 'buy' if delta_value > 0 else 'sell'
            volume = int(abs(delta_value) / price / 100) * 100  # A股100整数倍
            if volume <= 0:
                continue
                
            # 风控拦截
            account_info = self.broker.get_account_info()
            reject_reason = self.risk.check_pre_trade(code, side, volume, price, current_positions, account_info)
            if reject_reason:
                logger.warning(f"🛑 风控拦截 {code}: {reject_reason}")
                continue
                
            # 生成幂等订单
            client_id = self.order_mgr.generate_client_id(code, side)
            
            if self.dry_run:
                logger.info(f"🧪 [DRY-RUN] 模拟下单: {code} {side} {volume} @ {price} | ID:{client_id}")
                executed_ids.append(client_id)
                continue
                
            # 实盘下单
            try:
                order_req = OrderRequest(
                    code=code,
                    side=OrderSide.BUY if side == 'buy' else OrderSide.SELL,
                    volume=volume,
                    price=price,
                    client_order_id=client_id,
                    strategy_name='dynamic_price_v6'
                )
                broker_order_id = self.broker.place_order(order_req)
                self.order_mgr.submit_order(client_id, broker_order_id, code, side, volume, price)
                executed_ids.append(client_id)
            except Exception as e:
                logger.error(f"❌ 下单异常 {code}: {e}")
                
        return executed_ids
        
    def sync_positions(self):
        """同步券商持仓到本地组合"""
        broker_positions = self.broker.get_positions()
        self.portfolio.positions.clear()
        for pos in broker_positions:
            self.portfolio.positions[pos['code']] = {
                'quantity': pos['volume'],
                'cost': pos['cost_price'],
                'current_price': pos.get('market_value', 0) / pos['volume'] if pos['volume'] > 0 else 0
            }
        logger.info("🔄 持仓已同步")
        
    def close_trading_day(self):
        """收盘清理"""
        self.broker.disconnect()
        logger.info("🌙 交易日结束 | 数据已归档")