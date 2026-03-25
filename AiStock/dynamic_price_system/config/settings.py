#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统常量配置（不可变，用 Python 管理）
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# ==================== 路径配置 ====================
BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"
OUTPUT_DIR = BASE_DIR / "output"

# 确保目录存在
for dir_path in [DATA_DIR, LOG_DIR, OUTPUT_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# 配置文件路径
SYSTEM_CONFIG_PATH = CONFIG_DIR / "system_config.yaml"
STOCKS_CONFIG_PATH = CONFIG_DIR / "stocks_config.yaml"

# ==================== 数据库连接字符串（从环境变量读取） ====================
def get_db_url(env_key: str, default: str) -> str:
    """安全获取数据库连接字符串"""
    env_value = os.getenv(env_key)
    if env_value and env_value.startswith(('postgresql://', 'mysql://', 'sqlite:///')):
        return env_value
    return default

DATABASE_MAIN_URL = get_db_url(
    'DB_MAIN_URL',
    'sqlite:///data/stocks_daily.db'
)
DATABASE_PE_URL = get_db_url(
    'DB_PE_URL',
    'sqlite:///data/pe_history.db'
)

# ==================== 日志配置 ====================
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
LOG_FILE_MAX_BYTES = 10 * 1024 * 1024  # 10MB
LOG_FILE_BACKUP_COUNT = 5

# ==================== 类型转换配置（防 Plotly 序列化错误） ====================
PYTHON_NATIVE_TYPES = {
    'float': float,
    'int': int,
    'bool': bool,
    'str': str,
}

NUMPY_TO_PYTHON_MAP = {
    'float16': float,
    'float32': float,
    'float64': float,
    'int8': int,
    'int16': int,
    'int32': int,
    'int64': int,
    'uint8': int,
    'uint16': int,
    'uint32': int,
    'uint64': int,
}

# ==================== 缓存键配置 ====================
CACHE_KEY_SEPARATOR = "_"
CACHE_KEY_DATE_FORMAT = "%Y%m%d"
CACHE_KEY_MAX_LENGTH = 200  # 避免缓存键过长

# ==================== 数据验证阈值 ====================
DATA_VALIDATION = {
    'min_price': 0.01,      # 最小合理价格
    'max_price': 1000000,   # 最大合理价格
    'max_daily_change': 0.30,  # 单日最大涨跌幅 30%
    'min_volume': 100,      # 最小合理成交量
    'max_null_ratio': 0.10, # 最大允许空值比例
}

# ==================== 系统版本 ====================
SYSTEM_VERSION = "6.0.0"
SYSTEM_NAME = "三维动态价格调整系统"