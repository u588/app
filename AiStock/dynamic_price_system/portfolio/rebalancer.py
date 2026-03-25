#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rebalancer：再平衡策略模块
职责：
1. 检测权重偏离
2. 生成调仓建议
3. 计算最优调整方案
4. 考虑交易成本和税收
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from base_services.config_service import ConfigService

logger = logging.getLogger(__name__)


class Rebalancer:
    """再平衡策略引擎"""
    
    def __init__(self, config: Optional[ConfigService] = None):
        """
        初始化再平衡器
        
        参数:
            config: 配置服务实例
        """
        self.config = config
        
        # 默认阈值
        self.weight_deviation_threshold = 0.15  # 权重偏离 15% 触发
        self.min_trade_amount = 10000  # 最小交易金额 1 万
        self.transaction_cost_rate = 0.0003  # 交易成本 0.03%
        
        # 从配置加载
        if config:
            self._load_config()
        
        logger.info("✅ Rebalancer 初始化成功")
    
    def _load_config(self):
        """从配置加载参数"""
        try:
            risk_control = self.config.get('risk_control', {})
            if risk_control:
                self.weight_deviation_threshold = risk_control.get(
                    'weight_deviation_threshold', 0.15
                )
        except Exception as e:
            logger.warning(f"⚠️ 加载配置失败：{e}，使用默认值")
    
    def check_rebalance(
        self,
        current_positions: Dict[str, Dict],
        current_prices: Dict[str, float],
        target_weights: Dict[str, float],
        total_value: float
    ) -> List[Dict]:
        """
        检查再平衡需求
        
        参数:
            current_positions: 当前持仓 {code: {'quantity', 'cost'}}
            current_prices: 当前价格 {code: price}
            target_weights: 目标权重 {code: weight}
            total_value: 组合总市值
        
        返回:
            再平衡操作列表
        """
        actions = []
        
        if total_value == 0:
            logger.warning("⚠️ 组合总市值为 0，无法计算再平衡")
            return actions
        
        # 计算当前权重
        current_weights = self._calculate_current_weights(
            current_positions, current_prices, total_value
        )
        
        # 检查每只标的的权重偏离
        for code, target_weight in target_weights.items():
            current_weight = current_weights.get(code, 0)
            deviation = current_weight - target_weight
            
            # 判断是否超过阈值
            if abs(deviation) > self.weight_deviation_threshold:
                action = self._generate_action(
                    code=code,
                    current_weight=current_weight,
                    target_weight=target_weight,
                    current_price=current_prices.get(code, 0),
                    total_value=total_value,
                    deviation=deviation
                )
                
                if action and self._validate_action(action):
                    actions.append(action)
        
        # 按优先级排序（先买后卖，减少资金占用）
        actions = sorted(actions, key=lambda x: (0 if x['action'] == 'buy' else 1))
        
        logger.info(f"✅ 生成 {len(actions)} 个再平衡建议")
        return actions
    
    def _calculate_current_weights(
        self,
        positions: Dict[str, Dict],
        prices: Dict[str, float],
        total_value: float
    ) -> Dict[str, float]:
        """计算当前持仓权重"""
        weights = {}
        
        for code, pos in positions.items():
            quantity = pos.get('quantity', 0)
            price = prices.get(code, 0)
            market_value = quantity * price
            
            if total_value > 0:
                weights[code] = market_value / total_value
            else:
                weights[code] = 0
        
        return weights
    
    def _generate_action(
        self,
        code: str,
        current_weight: float,
        target_weight: float,
        current_price: float,
        total_value: float,
        deviation: float
    ) -> Optional[Dict]:
        """生成单个调仓动作"""
        if current_price <= 0:
            logger.warning(f"⚠️ {code} 价格无效，跳过")
            return None
        
        # 计算需要调整的市值
        adjust_value = abs(deviation) * total_value
        
        # 计算需要调整的数量
        adjust_quantity = int(adjust_value / current_price)
        
        # 检查最小交易金额
        if adjust_value < self.min_trade_amount:
            logger.debug(f"⚠️ {code} 调整金额{adjust_value:,.0f} < 最小交易金额，跳过")
            return None
        
        # 计算交易成本
        transaction_cost = adjust_value * self.transaction_cost_rate
        
        action = {
            'code': code,
            'action': 'buy' if deviation < 0 else 'sell',
            'quantity': adjust_quantity,
            'price': current_price,
            'adjust_value': adjust_value,
            'current_weight': f"{current_weight:.1%}",
            'target_weight': f"{target_weight:.1%}",
            'deviation': f"{deviation:.1%}",
            'transaction_cost': transaction_cost,
            'reason': f"权重偏离{abs(deviation):.1%} > 阈值{self.weight_deviation_threshold:.0%}",
            'priority': 1 if deviation < 0 else 2,  # 买入优先
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        return action
    
    def _validate_action(self, action: Dict) -> bool:
        """验证调仓动作的合理性"""
        # 检查数量
        if action['quantity'] <= 0:
            return False
        
        # 检查价格
        if action['price'] <= 0:
            return False
        
        # 检查金额
        if action['adjust_value'] < self.min_trade_amount:
            return False
        
        return True
    
    def optimize_actions(
        self,
        actions: List[Dict],
        available_cash: float
    ) -> List[Dict]:
        """
        优化调仓动作（考虑资金约束）
        
        参数:
            actions: 原始调仓动作列表
            available_cash: 可用现金
        
        返回:
            优化后的动作列表
        """
        if not actions:
            return actions
        
        optimized = []
        remaining_cash = available_cash
        
        # 按优先级排序
        sorted_actions = sorted(actions, key=lambda x: x.get('priority', 99))
        
        for action in sorted_actions:
            if action['action'] == 'buy':
                # 买入需要现金
                required_cash = action['adjust_value'] + action['transaction_cost']
                
                if required_cash <= remaining_cash:
                    optimized.append(action)
                    remaining_cash -= required_cash
                else:
                    # 现金不足，按比例调整
                    adjust_ratio = remaining_cash / required_cash
                    if adjust_ratio > 0.5:  # 至少执行 50%
                        action['quantity'] = int(action['quantity'] * adjust_ratio)
                        action['adjust_value'] *= adjust_ratio
                        action['transaction_cost'] *= adjust_ratio
                        action['note'] = f"现金不足，按比例执行{adjust_ratio:.0%}"
                        optimized.append(action)
                        remaining_cash = 0
                    else:
                        logger.warning(f"⚠️ {action['code']} 现金不足，跳过")
            else:
                # 卖出增加现金
                optimized.append(action)
                remaining_cash += action['adjust_value'] - action['transaction_cost']
        
        logger.info(f"✅ 优化后执行 {len(optimized)}/{len(actions)} 个动作")
        return optimized
    
    def generate_rebalance_report(
        self,
        actions: List[Dict],
        current_portfolio: Dict,
        target_portfolio: Dict
    ) -> Dict[str, Any]:
        """
        生成再平衡报告
        
        参数:
            actions: 调仓动作列表
            current_portfolio: 当前组合
            target_portfolio: 目标组合
        
        返回:
            再平衡报告字典
        """
        total_buy_value = sum(
            a['adjust_value'] for a in actions if a['action'] == 'buy'
        )
        total_sell_value = sum(
            a['adjust_value'] for a in actions if a['action'] == 'sell'
        )
        total_cost = sum(a['transaction_cost'] for a in actions)
        
        report = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_actions': len(actions),
            'buy_actions': sum(1 for a in actions if a['action'] == 'buy'),
            'sell_actions': sum(1 for a in actions if a['action'] == 'sell'),
            'total_buy_value': total_buy_value,
            'total_sell_value': total_sell_value,
            'net_cash_flow': total_sell_value - total_buy_value,
            'total_transaction_cost': total_cost,
            'actions': actions,
            'current_portfolio': current_portfolio,
            'target_portfolio': target_portfolio,
        }
        
        logger.info(f"✅ 生成再平衡报告：{len(actions)}个动作，净现金流{report['net_cash_flow']:,.0f}")
        return report


# ==================== 使用示例 ====================
def example_rebalancer():
    """再平衡器使用示例"""
    
    print("=" * 80)
    print("🧪 Rebalancer 使用示例")
    print("=" * 80)
    
    rebalancer = Rebalancer()
    
    # 模拟当前持仓
    current_positions = {
        '600938': {'quantity': 5000, 'cost': 40.00},
        '601899': {'quantity': 8000, 'cost': 32.00},
    }
    
    # 模拟当前价格
    current_prices = {
        '600938': 42.24,
        '601899': 32.40,
    }
    
    # 目标权重
    target_weights = {
        '600938': 0.15,  # 目标 15%
        '601899': 0.10,  # 目标 10%
    }
    
    # 组合总市值
    total_value = 500000
    
    # 检查再平衡
    print("\n1️⃣ 检查再平衡需求...")
    actions = rebalancer.check_rebalance(
        current_positions=current_positions,
        current_prices=current_prices,
        target_weights=target_weights,
        total_value=total_value
    )
    
    for action in actions:
        print(f"   • {action['code']} {action['action']} {action['quantity']}股 "
              f"@ {action['price']:.2f} ({action['reason']})")
    
    # 优化动作（考虑现金约束）
    print("\n2️⃣ 优化调仓动作...")
    optimized = rebalancer.optimize_actions(actions, available_cash=50000)
    print(f"   ✅ 优化后执行 {len(optimized)}/{len(actions)} 个动作")
    
    # 生成报告
    print("\n3️⃣ 生成再平衡报告...")
    report = rebalancer.generate_rebalance_report(
        actions=optimized,
        current_portfolio={'total_value': total_value},
        target_portfolio={'total_value': total_value}
    )
    print(f"   • 总动作数：{report['total_actions']}")
    print(f"   • 买入总额：¥{report['total_buy_value']:,.0f}")
    print(f"   • 卖出总额：¥{report['total_sell_value']:,.0f}")
    print(f"   • 净现金流：¥{report['net_cash_flow']:,.0f}")
    print(f"   • 交易成本：¥{report['total_transaction_cost']:,.0f}")
    
    print("\n" + "=" * 80)
    print("✅ Rebalancer 示例运行完成")
    print("=" * 80)


if __name__ == "__main__":
    example_rebalancer()