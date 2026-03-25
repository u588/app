#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PriceValidator：价格合理性校验模块
职责：
1. 验证动态价格的合理性（入场/止损/目标）
2. 防止异常价格导致错误交易信号
3. 基于历史波动率的价格边界检查
"""

import logging
from typing import Dict, Optional, Tuple
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class PriceValidator:
    """价格合理性校验器"""
    
    def __init__(self, config=None):
        """
        初始化价格校验器
        
        参数:
            config: 配置服务实例（可选）
        """
        self.config = config
        
        # 默认验证阈值
        self.max_daily_change = 0.30  # 单日最大涨跌幅 30%
        self.min_price = 0.01  # 最小合理价格
        self.max_price = 1000000  # 最大合理价格
        self.max_stop_loss_ratio = 0.20  # 最大止损比例 20%
        self.min_profit_loss_ratio = 1.0  # 最小盈亏比 1.0
        
        # 从配置加载阈值（如果提供）
        if config:
            self._load_config_thresholds()
        
        logger.info("✅ PriceValidator 初始化成功")
    
    def _load_config_thresholds(self):
        """从配置加载验证阈值"""
        try:
            data_validation = self.config.get('data_validation', {})
            if data_validation:
                self.max_daily_change = data_validation.get('max_daily_change', 0.30)
                self.min_price = data_validation.get('min_price', 0.01)
                self.max_price = data_validation.get('max_price', 1000000)
            
            risk_control = self.config.get('risk_control', {})
            if risk_control:
                self.max_stop_loss_ratio = risk_control.get('stop_loss_fixed', 0.20) * -1
        except Exception as e:
            logger.warning(f"⚠️ 加载配置阈值失败：{e}，使用默认值")
    
    def validate_price(self, price: float, current_price: float) -> float:
        """
        验证单个价格的合理性
        
        参数:
            price: 待验证价格
            current_price: 当前市场价格
        
        返回:
            修正后的价格
        """
        if price is None or np.isnan(price):
            logger.warning("⚠️ 价格为空或 NaN，使用当前价")
            return current_price
        
        # 检查价格范围
        if price < self.min_price:
            logger.warning(f"⚠️ 价格过低 {price} < {self.min_price}，修正为{self.min_price}")
            price = self.min_price
        
        if price > self.max_price:
            logger.warning(f"⚠️ 价格过高 {price} > {self.max_price}，修正为{self.max_price}")
            price = self.max_price
        
        # 检查与当前价的偏离度
        if current_price > 0:
            deviation = abs(price - current_price) / current_price
            if deviation > self.max_daily_change:
                logger.warning(f"⚠️ 价格偏离过大 {deviation:.1%}，修正为当前价的±{self.max_daily_change:.0%}")
                if price > current_price:
                    price = current_price * (1 + self.max_daily_change)
                else:
                    price = current_price * (1 - self.max_daily_change)
        
        return round(price, 2)
    
    def validate(self, entry_price: float, current_price: float) -> float:
        """
        验证入场价格
        
        参数:
            entry_price: 计算的入场价
            current_price: 当前市场价格
        
        返回:
            修正后的入场价
        """
        validated_price = self.validate_price(entry_price, current_price)
        
        # 入场价不应高于当前价太多（避免追高）
        if validated_price > current_price * 1.05:
            logger.warning(f"⚠️ 入场价过高，调整为当前价的 105%")
            validated_price = current_price * 1.05
        
        return round(validated_price, 2)
    
    def validate_stop(self, stop_price: float, entry_price: float) -> float:
        """
        验证止损价格
        
        参数:
            stop_price: 计算的止损价
            entry_price: 入场价格
        
        返回:
            修正后的止损价
        """
        if stop_price is None or np.isnan(stop_price):
            logger.warning("⚠️ 止损价为空，使用入场价的 85%")
            return round(entry_price * 0.85, 2)
        
        # 止损价必须低于入场价
        if stop_price >= entry_price:
            logger.warning(f"⚠️ 止损价 {stop_price} >= 入场价 {entry_price}，调整为入场价的 90%")
            stop_price = entry_price * 0.90
        
        # 检查止损幅度
        stop_ratio = (stop_price - entry_price) / entry_price
        if stop_ratio < -self.max_stop_loss_ratio:
            logger.warning(f"⚠️ 止损幅度过大 {stop_ratio:.1%}，调整为-{self.max_stop_loss_ratio:.0%}")
            stop_price = entry_price * (1 - self.max_stop_loss_ratio)
        
        return round(stop_price, 2)
    
    def validate_target(self, target_price: float, entry_price: float) -> float:
        """
        验证目标价格
        
        参数:
            target_price: 计算的目标价
            entry_price: 入场价格
        
        返回:
            修正后的目标价
        """
        if target_price is None or np.isnan(target_price):
            logger.warning("⚠️ 目标价为空，使用入场价的 120%")
            return round(entry_price * 1.20, 2)
        
        # 目标价必须高于入场价
        if target_price <= entry_price:
            logger.warning(f"⚠️ 目标价 {target_price} <= 入场价 {entry_price}，调整为入场价的 120%")
            target_price = entry_price * 1.20
        
        # 检查目标幅度（避免过度乐观）
        target_ratio = (target_price - entry_price) / entry_price
        if target_ratio > 1.0:  # 超过 100% 收益
            logger.warning(f"⚠️ 目标幅度过大 {target_ratio:.1%}，调整为 100%")
            target_price = entry_price * 2.0
        
        return round(target_price, 2)
    
    def validate_profit_loss_ratio(self, entry: float, stop: float, target: float) -> float:
        """
        验证盈亏比
        
        参数:
            entry: 入场价
            stop: 止损价
            target: 目标价
        
        返回:
            盈亏比
        """
        if entry <= stop:
            logger.error("❌ 入场价必须高于止损价")
            return 0.0
        
        potential_loss = entry - stop
        potential_profit = target - entry
        
        if potential_loss <= 0:
            return 0.0
        
        pl_ratio = potential_profit / potential_loss
        
        if pl_ratio < self.min_profit_loss_ratio:
            logger.warning(f"⚠️ 盈亏比 {pl_ratio:.2f} < {self.min_profit_loss_ratio}，风险收益不佳")
        
        return round(pl_ratio, 2)
    
    def validate_all(self, entry: float, stop: float, target: float, 
                     current_price: float) -> Dict[str, float]:
        """
        一次性验证所有价格
        
        参数:
            entry: 入场价
            stop: 止损价
            target: 目标价
            current_price: 当前市场价格
        
        返回:
            验证后的价格字典
        """
        validated_entry = self.validate(entry, current_price)
        validated_stop = self.validate_stop(stop, validated_entry)
        validated_target = self.validate_target(target, validated_entry)
        pl_ratio = self.validate_profit_loss_ratio(validated_entry, validated_stop, validated_target)
        
        return {
            'entry_price': validated_entry,
            'stop_loss': validated_stop,
            'target_price': validated_target,
            'profit_loss_ratio': pl_ratio,
            'is_valid': pl_ratio >= self.min_profit_loss_ratio
        }


# ==================== 使用示例 ====================
def example_price_validator():
    """价格校验器使用示例"""
    
    print("=" * 80)
    print("🧪 PriceValidator 使用示例")
    print("=" * 80)
    
    validator = PriceValidator()
    
    # 测试正常价格
    print("\n1️⃣ 测试正常价格...")
    result = validator.validate_all(
        entry=40.00,
        stop=36.00,
        target=48.00,
        current_price=42.00
    )
    print(f"   ✅ 入场价：{result['entry_price']}")
    print(f"   ✅ 止损价：{result['stop_loss']}")
    print(f"   ✅ 目标价：{result['target_price']}")
    print(f"   ✅ 盈亏比：{result['profit_loss_ratio']}")
    print(f"   ✅ 有效性：{result['is_valid']}")
    
    # 测试异常价格（止损高于入场）
    print("\n2️⃣ 测试异常价格（止损高于入场）...")
    result = validator.validate_all(
        entry=40.00,
        stop=42.00,  # 异常：止损高于入场
        target=48.00,
        current_price=42.00
    )
    print(f"   ⚠️ 入场价：{result['entry_price']}")
    print(f"   ⚠️ 止损价：{result['stop_loss']}（已修正）")
    print(f"   ✅ 目标价：{result['target_price']}")
    print(f"   ✅ 盈亏比：{result['profit_loss_ratio']}")
    
    # 测试异常价格（盈亏比过低）
    print("\n3️⃣ 测试异常价格（盈亏比过低）...")
    result = validator.validate_all(
        entry=40.00,
        stop=38.00,  # 止损过近
        target=42.00,  # 目标过近
        current_price=42.00
    )
    print(f"   ✅ 入场价：{result['entry_price']}")
    print(f"   ✅ 止损价：{result['stop_loss']}")
    print(f"   ✅ 目标价：{result['target_price']}")
    print(f"   ⚠️ 盈亏比：{result['profit_loss_ratio']}（偏低）")
    print(f"   ⚠️ 有效性：{result['is_valid']}")
    
    print("\n" + "=" * 80)
    print("✅ PriceValidator 示例运行完成")
    print("=" * 80)


if __name__ == "__main__":
    example_price_validator()