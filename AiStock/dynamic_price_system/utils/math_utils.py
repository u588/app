#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MathUtils：数值计算工具模块
职责：
1. 统计计算
2. 数值格式化
3. 比例计算
4. 数据验证
"""

import logging
from typing import List, Dict, Optional, Any, Union
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class MathUtils:
    """数值计算工具"""
    
    def __init__(self):
        """初始化工具"""
        logger.info("✅ MathUtils 初始化成功")
    
    def calculate_mean(self, values: List[float]) -> float:
        """计算平均值"""
        if not values:
            return 0.0
        return float(np.mean(values))
    
    def calculate_std(self, values: List[float]) -> float:
        """计算标准差"""
        if len(values) < 2:
            return 0.0
        return float(np.std(values, ddof=1))
    
    def calculate_volatility(
        self,
        prices: List[float],
        annualize: bool = True,
        periods_per_year: int = 252
    ) -> float:
        """
        计算波动率
        
        参数:
            prices: 价格序列
            annualize: 是否年化
            periods_per_year: 每年周期数
        
        返回:
            波动率
        """
        if len(prices) < 2:
            return 0.0
        
        # 计算收益率
        returns = np.diff(prices) / prices[:-1]
        
        # 计算标准差
        volatility = np.std(returns, ddof=1)
        
        # 年化
        if annualize:
            volatility *= np.sqrt(periods_per_year)
        
        return float(volatility)
    
    def calculate_sharpe_ratio(
        self,
        returns: List[float],
        risk_free_rate: float = 0.03,
        periods_per_year: int = 252
    ) -> float:
        """
        计算夏普比率
        
        参数:
            returns: 收益率序列
            risk_free_rate: 无风险利率
            periods_per_year: 每年周期数
        
        返回:
            夏普比率
        """
        if len(returns) < 2:
            return 0.0
        
        mean_return = np.mean(returns) * periods_per_year
        std_return = np.std(returns, ddof=1) * np.sqrt(periods_per_year)
        
        if std_return == 0:
            return 0.0
        
        sharpe = (mean_return - risk_free_rate) / std_return
        return float(sharpe)
    
    def calculate_max_drawdown(self, values: List[float]) -> float:
        """
        计算最大回撤
        
        参数:
            values: 净值序列
        
        返回:
            最大回撤（负值）
        """
        if len(values) < 2:
            return 0.0
        
        values = np.array(values)
        peak = np.maximum.accumulate(values)
        drawdown = (values - peak) / peak
        
        return float(np.min(drawdown))
    
    def calculate_correlation(
        self,
        series1: List[float],
        series2: List[float]
    ) -> float:
        """
        计算相关系数
        
        参数:
            series1: 序列 1
            series2: 序列 2
        
        返回:
            相关系数
        """
        if len(series1) != len(series2) or len(series1) < 2:
            return 0.0
        
        correlation = np.corrcoef(series1, series2)[0, 1]
        return float(correlation)
    
    def format_number(
        self,
        value: float,
        decimals: int = 2,
        add_comma: bool = True,
        add_percent: bool = False
    ) -> str:
        """
        格式化数字
        
        参数:
            value: 数值
            decimals: 小数位数
            add_comma: 是否添加千分位
            add_percent: 是否添加百分号
        
        返回:
            格式化后的字符串
        """
        if add_percent:
            value *= 100
            format_str = f"{{:.{decimals}f}}%"
        elif add_comma:
            format_str = f"{{:,.{decimals}f}}"
        else:
            format_str = f"{{:.{decimals}f}}"
        
        return format_str.format(value)
    
    def format_currency(
        self,
        value: float,
        currency: str = '¥',
        decimals: int = 2
    ) -> str:
        """
        格式化货币
        
        参数:
            value: 金额
            currency: 货币符号
            decimals: 小数位数
        
        返回:
            格式化后的货币字符串
        """
        return f"{currency}{value:,.{decimals}f}"
    
    def calculate_position_size(
        self,
        total_capital: float,
        target_weight: float,
        current_price: float,
        min_lot: int = 100
    ) -> int:
        """
        计算仓位数量
        
        参数:
            total_capital: 总资金
            target_weight: 目标权重
            current_price: 当前价格
            min_lot: 最小交易单位（A 股 100 股）
        
        返回:
            交易数量
        """
        target_value = total_capital * target_weight
        quantity = int(target_value / current_price)
        
        # 调整为最小交易单位的整数倍
        quantity = (quantity // min_lot) * min_lot
        
        return max(0, quantity)
    
    def calculate_profit_loss(
        self,
        entry_price: float,
        current_price: float,
        quantity: int
    ) -> Dict[str, float]:
        """
        计算盈亏
        
        参数:
            entry_price: 入场价
            current_price: 当前价
            quantity: 数量
        
        返回:
            盈亏字典
        """
        profit = (current_price - entry_price) * quantity
        profit_ratio = (current_price - entry_price) / entry_price if entry_price > 0 else 0
        
        return {
            'profit': profit,
            'profit_ratio': profit_ratio,
            'entry_value': entry_price * quantity,
            'current_value': current_price * quantity,
        }
    
    def validate_price(
        self,
        price: float,
        min_price: float = 0.01,
        max_price: float = 1000000
    ) -> bool:
        """
        验证价格合理性
        
        参数:
            price: 价格
            min_price: 最小合理价格
            max_price: 最大合理价格
        
        返回:
            是否有效
        """
        if price is None or np.isnan(price):
            return False
        
        return min_price <= price <= max_price
    
    def calculate_percentile(
        self,
        value: float,
        values: List[float]
    ) -> float:
        """
        计算百分位
        
        参数:
            value: 当前值
            values: 历史值列表
        
        返回:
            百分位（0-100）
        """
        if not values:
            return 50.0
        
        count_below = sum(1 for v in values if v < value)
        percentile = (count_below / len(values)) * 100
        
        return float(percentile)
    
    def safe_divide(
        self,
        numerator: float,
        denominator: float,
        default: float = 0.0
    ) -> float:
        """
        安全除法
        
        参数:
            numerator: 分子
            denominator: 分母
            default: 分母为 0 时的默认值
        
        返回:
            除法结果
        """
        if denominator == 0 or np.isnan(denominator):
            return default
        
        return float(numerator / denominator)


# ==================== 使用示例 ====================
def example_math_utils():
    """数值工具使用示例"""
    
    print("=" * 80)
    print("🧪 MathUtils 使用示例")
    print("=" * 80)
    
    utils = MathUtils()
    
    # 计算波动率
    print("\n1️⃣ 计算波动率...")
    prices = [100, 102, 101, 103, 105, 104, 106, 108, 107, 109]
    volatility = utils.calculate_volatility(prices)
    print(f"   • 波动率：{volatility:.2%}")
    
    # 计算最大回撤
    print("\n2️⃣ 计算最大回撤...")
    net_values = [100, 105, 110, 108, 112, 115, 110, 118, 120, 115]
    max_dd = utils.calculate_max_drawdown(net_values)
    print(f"   • 最大回撤：{max_dd:.2%}")
    
    # 格式化数字
    print("\n3️⃣ 格式化数字...")
    print(f"   • 百分比：{utils.format_number(0.1234, decimals=2, add_percent=True)}")
    print(f"   • 千分位：{utils.format_number(1234567.89, add_comma=True)}")
    print(f"   • 货币：{utils.format_currency(1234567.89, currency='¥')}")
    
    # 计算仓位
    print("\n4️⃣ 计算仓位...")
    quantity = utils.calculate_position_size(
        total_capital=1000000,
        target_weight=0.10,
        current_price=42.24
    )
    print(f"   • 建议仓位：{quantity}股")
    
    # 计算盈亏
    print("\n5️⃣ 计算盈亏...")
    pl = utils.calculate_profit_loss(
        entry_price=40.00,
        current_price=42.24,
        quantity=5000
    )
    print(f"   • 盈利：{utils.format_currency(pl['profit'])}")
    print(f"   • 盈利率：{utils.format_number(pl['profit_ratio'], add_percent=True)}")
    
    # 安全除法
    print("\n6️⃣ 安全除法...")
    result = utils.safe_divide(100, 0, default=0)
    print(f"   • 100/0 = {result}（避免除零错误）")
    
    print("\n" + "=" * 80)
    print("✅ MathUtils 示例运行完成")
    print("=" * 80)


if __name__ == "__main__":
    example_math_utils()