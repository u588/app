#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
动态价格系统专属常量配置
"""

from pathlib import Path
from config.global_settings import BASE_DIR

# ==================== 系统路径配置 ====================
SYSTEM_DIR = BASE_DIR / "dynamic_price_system"
CONFIG_DIR = SYSTEM_DIR / "config"
LOG_DIR = BASE_DIR / "logs" / "dynamic_price"
OUTPUT_DIR = BASE_DIR / "output" / "dynamic_price"

# 确保目录存在
for dir_path in [LOG_DIR, OUTPUT_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# ==================== 配置文件路径 ====================
SYSTEM_CONFIG_PATH = CONFIG_DIR / "system_config.yaml"
STOCKS_CONFIG_PATH = CONFIG_DIR / "stocks_config.yaml"

# ==================== 系统版本 ====================
SYSTEM_VERSION = "6.2.0"
SYSTEM_NAME = "三维动态价格调整系统"

# ==================== 三维权重默认值 ====================
DEFAULT_WEIGHTS = {
    'technical': 0.40,
    'fundamental': 0.35,
    'macro': 0.25,
}

# ==================== 价格计算参数 ====================
PRICE_CALC_PARAMS = {
    'atr_multiplier_entry': 1.5,
    'atr_multiplier_stop': 3.0,
    'atr_multiplier_target': 8.0,
    'ma_entry_period': 20,
    'ma_stop_period': 60,
    'rsi_oversold': 30,
    'rsi_overbought': 70,
}

# ==================== 风控阈值 ====================
RISK_THRESHOLDS = {
    'max_position_single': 0.15,
    'max_position_sector': 0.30,
    'stop_loss_fixed': -0.15,
    'take_profit_fixed': 0.30,
    'portfolio_drawdown_limit': -0.20,
}

# ==================== 缓存键前缀 ====================
CACHE_PREFIXES = {
    'index': 'idx',
    'derivative': 'drv',
    'macro': 'mac',
    'pe': 'pe',
    'dynamic_price': 'dp',
}