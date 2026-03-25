#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PortfolioTracker：持仓跟踪模块
职责：
1. 持仓管理（买入/卖出）
2. 盈亏计算
3. 权重计算
4. 组合摘要生成
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from base_services.config_service import ConfigService

logger = logging.getLogger(__name__)


class PortfolioTracker:
    """持仓跟踪器"""
    
    def __init__(self, initial_capital: float = 1000000, config: Optional[ConfigService] = None):
        """
        初始化持仓跟踪器
        
        参数:
            initial_capital: 初始资金
            config: 配置服务实例
        """
        self.initial_capital = initial_capital
        self.config = config
        self.cash = initial_capital
        self.positions: Dict[str, Dict] = {}  # {code: {'quantity', 'cost', 'entry_date'}}
        self.history: List[Dict] = []  # 交易历史
        
        logger.info(f"✅ PortfolioTracker 初始化成功 | 初始资金={initial_capital:,.0f}")
    
    def buy(self, code: str, price: float, quantity: int) -> bool:
        """
        买入
        
        参数:
            code: 股票代码
            price: 买入价格
            quantity: 买入数量
        
        返回:
            是否成功
        """
        cost = price * quantity
        if cost > self.cash:
            logger.warning(f"❌ 资金不足：需要{cost:,.2f}，可用{self.cash:,.2f}")
            return False
        
        self.cash -= cost
        
        if code in self.positions:
            # 加仓：计算加权平均成本
            old_qty = self.positions[code]['quantity']
            old_cost = self.positions[code]['cost']
            new_qty = old_qty + quantity
            new_cost = (old_cost * old_qty + cost) / new_qty
            self.positions[code] = {
                'quantity': new_qty,
                'cost': new_cost,
                'entry_date': self.positions[code].get('entry_date', datetime.now())
            }
        else:
            # 新建仓位
            self.positions[code] = {
                'quantity': quantity,
                'cost': price,
                'entry_date': datetime.now()
            }
        
        self._record_transaction(code, 'buy', price, quantity, cost)
        logger.info(f"✅ 买入 {code} {quantity}股 @ {price:.2f}")
        return True
    
    def sell(self, code: str, price: float, quantity: int) -> bool:
        """
        卖出
        
        参数:
            code: 股票代码
            price: 卖出价格
            quantity: 卖出数量
        
        返回:
            是否成功
        """
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
        logger.info(f"✅ 卖出 {code} {quantity}股 @ {price:.2f}")
        return True
    
    def get_portfolio_value(self, current_prices: Dict[str, float]) -> float:
        """
        获取组合总市值
        
        参数:
            current_prices: 当前价格字典 {code: price}
        
        返回:
            总市值
        """
        stock_value = sum(
            self.positions[code]['quantity'] * current_prices.get(code, 0)
            for code in self.positions
        )
        return stock_value + self.cash
    
    def get_portfolio_return(self, current_prices: Dict[str, float]) -> float:
        """
        获取组合收益率
        
        参数:
            current_prices: 当前价格字典
        
        返回:
            收益率
        """
        total_value = self.get_portfolio_value(current_prices)
        return (total_value - self.initial_capital) / self.initial_capital
    
    def get_position_weights(self, current_prices: Dict[str, float]) -> Dict[str, float]:
        """
        获取持仓权重
        
        参数:
            current_prices: 当前价格字典
        
        返回:
            权重的字典 {code: weight}
        """
        total_value = self.get_portfolio_value(current_prices)
        if total_value == 0:
            return {}
        
        weights = {}
        for code, pos in self.positions.items():
            market_value = pos['quantity'] * current_prices.get(code, 0)
            weights[code] = market_value / total_value
        
        return weights
    
    def check_rebalance(self, current_prices: Dict[str, float], 
                       dynamic_prices: List[Dict]) -> List[Dict]:
        """
        检查再平衡需求
        
        参数:
            current_prices: 当前价格字典
            dynamic_prices: 动态价格结果列表
        
        返回:
            再平衡操作列表
        """
        actions = []
        
        if not self.config:
            return actions
        
        total_value = self.get_portfolio_value(current_prices)
        if total_value == 0:
            return actions
        
        current_weights = self.get_position_weights(current_prices)
        
        # 获取目标权重配置
        stock_configs = self.config.get('stocks', [])
        target_weights = {cfg['code']: cfg['weight'] for cfg in stock_configs}
        
        # 检查权重偏离
        deviation_threshold = self.config.get('risk_control.weight_deviation_threshold', 0.15)
        
        for code, target_weight in target_weights.items():
            current_weight = current_weights.get(code, 0)
            deviation = abs(current_weight - target_weight)
            
            if deviation > deviation_threshold:
                action = 'buy' if current_weight < target_weight else 'sell'
                adjust_value = abs(target_weight * total_value - current_weight * total_value)
                adjust_qty = int(adjust_value / current_prices.get(code, 1))
                
                if adjust_qty > 0:
                    actions.append({
                        'code': code,
                        'action': action,
                        'quantity': adjust_qty,
                        'reason': f"权重偏离{deviation:.1%}"
                    })
        
        return actions
    
    def get_summary(self, current_prices: Dict[str, float]) -> Dict[str, Any]:
        """
        获取组合摘要
        
        参数:
            current_prices: 当前价格字典
        
        返回:
            组合摘要字典
        """
        total_value = self.get_portfolio_value(current_prices)
        total_return = self.get_portfolio_return(current_prices)
        
        positions_summary = []
        for code, pos in self.positions.items():
            current_price = current_prices.get(code, 0)
            market_value = pos['quantity'] * current_price
            profit = (current_price - pos['cost']) * pos['quantity']
            profit_pct = (current_price - pos['cost']) / pos['cost'] if pos['cost'] > 0 else 0
            
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
            'transaction_count': len(self.history),
            'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    
    def _record_transaction(self, code: str, action: str, price: float, 
                           quantity: int, amount: float):
        """记录交易"""
        self.history.append({
            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'code': code,
            'action': action,
            'price': price,
            'quantity': quantity,
            'amount': amount,
        })


# ==================== 使用示例 ====================
def example_portfolio_tracker():
    """持仓跟踪器使用示例"""
    
    print("=" * 80)
    print("🧪 PortfolioTracker 使用示例")
    print("=" * 80)
    
    tracker = PortfolioTracker(initial_capital=1000000)
    
    # 模拟买入
    print("\n1️⃣ 买入操作...")
    tracker.buy('600938', 40.00, 5000)
    tracker.buy('601899', 32.00, 8000)
    
    # 模拟当前价格
    current_prices = {'600938': 42.24, '601899': 32.40}
    
    # 获取摘要
    print("\n2️⃣ 组合摘要...")
    summary = tracker.get_summary(current_prices)
    print(f"   总市值：¥{summary['total_value']:,.2f}")
    print(f"   现金：¥{summary['cash']:,.2f}")
    print(f"   总收益：{summary['total_return']}")
    
    print("\n" + "=" * 80)
    print("✅ PortfolioTracker 示例运行完成")
    print("=" * 80)


if __name__ == "__main__":
    example_portfolio_tracker()