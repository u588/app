#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
组合跟踪模块
"""

import pandas as pd
import sqlite3
from datetime import datetime
import logging
from config import STOCKS_CONFIG, ALERT_THRESHOLDS, DB_CONFIG

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PortfolioTracker:
    """组合跟踪器"""
    
    def __init__(self, initial_capital=1000000):
        """
        初始化
        :param initial_capital: 初始资金
        """
        self.initial_capital = initial_capital
        self.positions = {}  # 持仓 {code: {'quantity': 数量，'cost': 成本}}
        self.cash = initial_capital
        self.history = []  # 交易历史
    
    def buy(self, code, price, quantity):
        """买入"""
        cost = price * quantity
        if cost > self.cash:
            logger.warning(f"❌ 资金不足：需要{cost}，可用{self.cash}")
            return False
        
        self.cash -= cost
        
        if code in self.positions:
            old_qty = self.positions[code]['quantity']
            old_cost = self.positions[code]['cost']
            new_qty = old_qty + quantity
            new_cost = (old_cost * old_qty + cost) / new_qty
            self.positions[code] = {'quantity': new_qty, 'cost': new_cost}
        else:
            self.positions[code] = {'quantity': quantity, 'cost': price}
        
        self._record_transaction(code, 'buy', price, quantity, cost)
        logger.info(f"✅ 买入 {code} {quantity}股 @ {price}")
        return True
    
    def sell(self, code, price, quantity):
        """卖出"""
        if code not in self.positions:
            logger.warning(f"❌ 无持仓：{code}")
            return False
        
        if quantity > self.positions[code]['quantity']:
            logger.warning(f"❌ 持仓不足：持有{self.positions[code]['quantity']}，卖出{quantity}")
            return False
        
        revenue = price * quantity
        self.cash += revenue
        
        self.positions[code]['quantity'] -= quantity
        if self.positions[code]['quantity'] == 0:
            del self.positions[code]
        
        self._record_transaction(code, 'sell', price, quantity, revenue)
        logger.info(f"✅ 卖出 {code} {quantity}股 @ {price}")
        return True
    
    def get_portfolio_value(self, current_prices):
        """获取组合总市值"""
        stock_value = sum(
            self.positions[code]['quantity'] * current_prices.get(code, 0)
            for code in self.positions
        )
        return stock_value + self.cash
    
    def get_portfolio_return(self, current_prices):
        """获取组合收益率"""
        total_value = self.get_portfolio_value(current_prices)
        return (total_value - self.initial_capital) / self.initial_capital
    
    def check_rebalance(self, current_prices, dynamic_prices):
        """检查再平衡需求"""
        actions = []
        total_value = self.get_portfolio_value(current_prices)
        
        if total_value == 0:
            return actions
        
        for stock in STOCKS_CONFIG:
            code = stock['code']
            target_weight = stock['weight']
            target_value = total_value * target_weight
            
            if code in self.positions:
                current_value = self.positions[code]['quantity'] * current_prices.get(code, 0)
                current_weight = current_value / total_value
                
                deviation = abs(current_weight - target_weight)
                if deviation > ALERT_THRESHOLDS['weight_deviation']:
                    action = 'buy' if current_weight < target_weight else 'sell'
                    adjust_qty = abs(target_value - current_value) / current_prices.get(code, 1)
                    
                    actions.append({
                        'code': code,
                        'action': action,
                        'quantity': int(adjust_qty),
                        'reason': f"权重偏离{deviation:.1%}"
                    })
        
        return actions
    
    def check_stop_loss(self, current_prices, stop_prices):
        """检查止损"""
        alerts = []
        
        for code, pos in self.positions.items():
            current_price = current_prices.get(code, 0)
            stop_price = stop_prices.get(code, 0)
            cost = pos['cost']
            
            if current_price <= stop_price:
                loss_pct = (current_price - cost) / cost
                alerts.append({
                    'code': code,
                    'type': 'stop_loss',
                    'current_price': current_price,
                    'stop_price': stop_price,
                    'loss_pct': f"{loss_pct:.1%}"
                })
        
        return alerts
    
    def _record_transaction(self, code, action, price, quantity, amount):
        """记录交易"""
        self.history.append({
            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'code': code,
            'action': action,
            'price': price,
            'quantity': quantity,
            'amount': amount,
        })
    
    def get_summary(self, current_prices):
        """获取组合摘要"""
        total_value = self.get_portfolio_value(current_prices)
        total_return = self.get_portfolio_return(current_prices)
        
        positions_summary = []
        for code, pos in self.positions.items():
            current_price = current_prices.get(code, 0)
            market_value = pos['quantity'] * current_price
            profit = (current_price - pos['cost']) * pos['quantity']
            profit_pct = (current_price - pos['cost']) / pos['cost']
            
            positions_summary.append({
                'code': code,
                'quantity': pos['quantity'],
                'cost': pos['cost'],
                'current_price': current_price,
                'market_value': market_value,
                'profit': profit,
                'profit_pct': f"{profit_pct:.1%}",
                'weight': f"{market_value/total_value:.1%}" if total_value > 0 else "0%"
            })
        
        return {
            'total_value': total_value,
            'cash': self.cash,
            'total_return': f"{total_return:.1%}",
            'positions': positions_summary,
            'transaction_count': len(self.history)
        }


# 测试
if __name__ == '__main__':
    tracker = PortfolioTracker(initial_capital=1000000)
    
    # 模拟买入
    tracker.buy('600938', 40.00, 5000)
    tracker.buy('601899', 32.00, 8000)
    
    # 模拟当前价格
    current_prices = {'600938': 42.24, '601899': 32.40}
    
    # 获取摘要
    summary = tracker.get_summary(current_prices)
    
    print("\n" + "="*60)
    print("组合跟踪测试结果")
    print("="*60)
    print(f"总市值：{summary['total_value']:,.2f}")
    print(f"现金：{summary['cash']:,.2f}")
    print(f"总收益：{summary['total_return']}")
    print(f"交易次数：{summary['transaction_count']}")
    print("\n持仓明细：")
    for pos in summary['positions']:
        print(f"  {pos['code']}: {pos['quantity']}股 盈利{pos['profit_pct']} 权重{pos['weight']}")