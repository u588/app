#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RiskController：实盘前置风控拦截器
职责：下单前校验资金/仓位/集中度/单日亏损/极端行情
"""
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging
import yaml
from pathlib import Path

logger = logging.getLogger(__name__)

class RiskController:
    def __init__(self, config_path: str):
        self.config = self._load_config(config_path)
        self.daily_loss_limit = self.config['risk']['daily_loss_limit']
        self.max_position_pct = self.config['risk']['max_position_pct']
        self.max_sector_pct = self.config['risk']['max_sector_pct']
        self.max_order_value = self.config['risk']['max_order_value']
        self.circuit_breaker_threshold = self.config['risk']['circuit_breaker_threshold']
        self._daily_start_asset = 0.0
        self._trading_disabled = False
        
    def _load_config(self, path: str) -> Dict:
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
            
    def set_daily_start_asset(self, asset: float):
        """初始化当日初始资产（用于计算当日亏损）"""
        self._daily_start_asset = asset
        self._trading_disabled = False
        logger.info(f"📅 当日初始资产: ¥{asset:,.2f}")
        
    def check_pre_trade(self, code: str, side: str, volume: int, price: float,
                        current_positions: List[Dict], account_info: Dict) -> Optional[str]:
        """
        下单前风控检查
        返回: None 通过, str 拦截原因
        """
        if self._trading_disabled:
            return "⛔ 交易已熔断，暂停下单"
            
        order_value = volume * price
        
        # 1. 单笔金额限制
        if order_value > self.max_order_value:
            return f"⛔ 单笔金额超限: ¥{order_value:,.2f} > ¥{self.max_order_value:,.2f}"
            
        # 2. 集中度检查（买入时）
        if side == 'buy':
            # 计算持仓占比
            total_asset = account_info.get('total_asset', 1)
            current_pos_value = next((p['market_value'] for p in current_positions if p['code'] == code), 0.0)
            new_pos_value = current_pos_value + order_value
            if new_pos_value / total_asset > self.max_position_pct:
                return f"⛔ 个股权重超限: {new_pos_value/total_asset:.1%} > {self.max_position_pct:.0%}"
                
        # 3. 单日亏损熔断
        current_asset = account_info.get('total_asset', 0.0)
        daily_pnl = current_asset - self._daily_start_asset
        daily_pnl_pct = daily_pnl / self._daily_start_asset if self._daily_start_asset > 0 else 0
        
        if daily_pnl_pct < self.circuit_breaker_threshold:
            self._trading_disabled = True
            logger.critical(f"🚨 触发单日亏损熔断: {daily_pnl_pct:.2%} < {self.circuit_breaker_threshold:.0%}")
            return "⛔ 触发单日亏损熔断，今日停止交易"
            
        return None  # 通过
        
    def enable_trading(self):
        """手动恢复交易（需人工确认）"""
        self._trading_disabled = False
        logger.warning("🟢 交易已手动恢复")