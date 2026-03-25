#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全局系统常量配置（所有系统共用，不可变）
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# ==================== 基础路径配置 ====================
BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"
LOG_DIR = BASE_DIR / "logs"
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"

# 确保目录存在
for dir_path in [LOG_DIR, DATA_DIR, OUTPUT_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# ==================== 数据库配置（从环境变量读取） ====================
def get_db_url(env_key: str, default: str) -> str:
    """安全获取数据库连接字符串"""
    env_value = os.getenv(env_key)
    if env_value and env_value.startswith(('postgresql://', 'postgresql+psycopg://')):
        return env_value
    return default

# PostgreSQL 主数据库（指数/日线数据）
DATABASE_MAIN_URL = get_db_url(
    'DB_MAIN_URL',
    'postgresql+psycopg://sa:11111111@10.3.18.56/tdxIndex'
)

# PostgreSQL PE 数据库（估值历史数据）
DATABASE_PE_URL = get_db_url(
    'DB_PE_URL',
    'postgresql+psycopg://sa:11111111@10.3.18.56/tdxPE'
)

# 连接池配置
DB_POOL_CONFIG = {
    'pool_size': int(os.getenv('DB_POOL_SIZE', 10)),
    'max_overflow': int(os.getenv('DB_MAX_OVERFLOW', 20)),
    'pool_pre_ping': os.getenv('DB_POOL_PRE_PING', 'true').lower() == 'true',
    'pool_recycle': int(os.getenv('DB_POOL_RECYCLE', 3600)),
    'connect_timeout': 30,
}

# ==================== 日志配置 ====================
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
LOG_FILE_MAX_BYTES = 50 * 1024 * 1024  # 50MB
LOG_FILE_BACKUP_COUNT = 10

# ==================== 类型转换配置（防序列化错误） ====================
PYTHON_NATIVE_TYPES = {
    'float': float, 'int': int, 'bool': bool, 'str': str,
}

NUMPY_TO_PYTHON_MAP = {
    'float16': float, 'float32': float, 'float64': float,
    'int8': int, 'int16': int, 'int32': int, 'int64': int,
    'uint8': int, 'uint16': int, 'uint32': int, 'uint64': int,
}

# ==================== 缓存配置 ====================
CACHE_KEY_SEPARATOR = "_"
CACHE_KEY_DATE_FORMAT = "%Y%m%d"
CACHE_KEY_MAX_LENGTH = 250

# ==================== 数据验证阈值 ====================
DATA_VALIDATION = {
    'min_price': 0.01,
    'max_price': 1000000,
    'max_daily_change': 0.30,
    'min_volume': 100,
    'max_null_ratio': 0.10,
}

# ==================== 系统版本 ====================
SYSTEM_VERSION = "6.2.0"
SYSTEM_NAME = "AiStock 多系统架构"
