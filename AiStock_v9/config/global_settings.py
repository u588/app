#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AiStock V9.1 全局系统常量配置
V9.1升级: tdxAPICode180.xlsx代码表(57371条) + 新增市场码4/5/6/67商品期权 + 新品类5/11
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ==================== 基础路径配置 ====================
BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"
LOG_DIR = BASE_DIR / "logs"
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
ENV_FILE = BASE_DIR / "config" / ".env"

load_dotenv(ENV_FILE)

for dir_path in [LOG_DIR, DATA_DIR, OUTPUT_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# ==================== 数据库配置 ====================
def get_db_url(env_key: str, default: str) -> str:
    env_value = os.getenv(env_key)
    if env_value and env_value.startswith(('postgresql://', 'postgresql+psycopg://')):
        return env_value
    return default

DATABASE_ENGINES = {
    'index_db': get_db_url('DB_INDEX', 'postgresql://sa:11111111@10.3.18.56:5432/tdxIndex'),
    'stock_db': get_db_url('DB_STOCK', 'postgresql://sa:11111111@10.3.18.56:5432/tdxStocks'),
    'stock_base_db': get_db_url('DB_STOCK_BASE', 'postgresql://sa:11111111@10.3.18.56:5432/StockBase'),
    'stock_fs_db': get_db_url('DB_STOCK_FS', 'postgresql://sa:11111111@10.3.18.56:5432/tdxFS'),
    'index_pe_db': get_db_url('DB_INDEX_PE', 'postgresql://sa:11111111@10.3.18.56:5432/csiIndexPE'),
}

DB_POOL_CONFIG = {
    'pool_size': int(os.getenv('DB_POOL_SIZE', 10)),
    'max_overflow': int(os.getenv('DB_MAX_OVERFLOW', 20)),
    'pool_pre_ping': os.getenv('DB_POOL_PRE_PING', 'true').lower() == 'true',
    'pool_recycle': int(os.getenv('DB_POOL_RECYCLE', 3600)),
    'pool_timeout': 30,
}

# ==================== TDX双端口配置 ====================
TDX_STANDARD_HOST = "180.153.18.170"
TDX_STANDARD_PORT = 7709
TDX_EXTENSION_HOST = "180.153.18.176"
TDX_EXTENSION_PORT = 7721

# ==================== TDX 代码表路径 ====================
# V9.1: 使用 tdxAPICode180.xlsx (57371条, 含商品期权市场码4/5/6/67, 新品类5/11)
TDX_CODE_TABLE_PATH = str(BASE_DIR / "notebooks" / "tdxAPICode180.xlsx")
# 旧代码表 (31692条, 仅含市场码7/8/9/28/29/30/47/66)
TDX_CODE_TABLE_PATH_LEGACY = str(BASE_DIR / "notebooks" / "tdx基金期货期权代码表.xlsx")

# ==================== 日志配置 ====================
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
LOG_FILE_MAX_BYTES = 50 * 1024 * 1024
LOG_FILE_BACKUP_COUNT = 10

# ==================== 类型转换配置 ====================
PYTHON_NATIVE_TYPES = {'float': float, 'int': int, 'bool': bool, 'str': str}
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
    'min_price': 0.01, 'max_price': 1000000,
    'max_daily_change': 0.30, 'min_volume': 100, 'max_null_ratio': 0.10,
}

# ==================== 系统版本 ====================
SYSTEM_VERSION = "9.1.0"
SYSTEM_NAME = "AiStock V9.1 A股市场状态量化系统"
