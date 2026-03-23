#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统配置参数
"""

from datetime import datetime

# ==================== 基础配置 ====================

# 18 只精选标的
STOCKS_CONFIG = [
    {'code': '600938', 'name': '中国海油', 'sector': '油气开采', 'weight': 0.10},
    {'code': '601857', 'name': '中国石油', 'sector': '油气开采', 'weight': 0.08},
    {'code': '600256', 'name': '广汇能源', 'sector': 'LNG', 'weight': 0.06},
    {'code': '600803', 'name': '新奥股份', 'sector': 'LNG', 'weight': 0.06},
    {'code': '601808', 'name': '中海油服', 'sector': '油服', 'weight': 0.06},
    {'code': '002353', 'name': '杰瑞股份', 'sector': '油服', 'weight': 0.06},
    {'code': '601088', 'name': '中国神华', 'sector': '煤炭化工', 'weight': 0.08},
    {'code': '600426', 'name': '华鲁恒升', 'sector': '煤炭化工', 'weight': 0.04},
    {'code': '600406', 'name': '国电南瑞', 'sector': '特高压', 'weight': 0.12},
    {'code': '000400', 'name': '许继电气', 'sector': '特高压', 'weight': 0.06},
    {'code': '300750', 'name': '宁德时代', 'sector': '新能源', 'weight': 0.12},
    {'code': '300274', 'name': '阳光电源', 'sector': '新能源', 'weight': 0.08},
    {'code': '601899', 'name': '紫金矿业', 'sector': '黄金', 'weight': 0.10},
    {'code': '600489', 'name': '中金黄金', 'sector': '黄金', 'weight': 0.08},
    {'code': '600760', 'name': '中航沈飞', 'sector': '军工', 'weight': 0.08},
    {'code': '002179', 'name': '中航光电', 'sector': '军工', 'weight': 0.07},
    {'code': '603019', 'name': '中科曙光', 'sector': '政策方向', 'weight': 0.08},
    {'code': '600536', 'name': '中国软件', 'sector': '政策方向', 'weight': 0.04},
]

# 三维权重配置
WEIGHTS = {
    'technical': 0.40,    # 技术面 40%
    'fundamental': 0.35,  # 基本面 35%
    'macro': 0.25         # 宏观面 25%
}

# 宏观指标映射（TDX 代码）
MACRO_INDICATORS = {
    'brent_crude': 'OIL',          # 布伦特原油（外盘 ak.futures_foreign_commodity_realtime()）
    'comex_gold': 'GC',            # COMEX 黄金（外盘）
    'lme_copper': 'CAD',           # LME 铜（外盘）
    'nymex_gas': 'NG',             # NYMEX 天然气（外盘）
    'usd_cny': '5_RMBUS',          # 美元兑人民币（TDX扩展行情 market_code=38）
    'china_10y_bond': '5_CNTY',    # 中国 10 年期国债（TDX）
    'pmi': '3_PMI',                # 制造业 PMI（TDX）
    'm2_growth': '5_M2',           # M2 增速（TDX）
    'cpi': '2_CPI',                # CPI（TDX）
    'ppi': '2_PPI',                # PPI（TDX）
}

# 板块与宏观指标联动配置
SECTOR_MACRO_LINK = {
    '油气开采': ['brent_crude', 'pmi'],
    'LNG': ['nymex_gas', 'usd_cny'],
    '油服': ['brent_crude', 'pmi'],
    '煤炭化工': ['ppi', 'cpi'],
    '特高压': ['lme_copper', 'china_10y_bond'],
    '新能源': ['lme_copper', 'm2_growth'],
    '黄金': ['comex_gold', 'china_10y_bond'],
    '军工': ['pmi', 'm2_growth'],
    '政策方向': ['m2_growth', 'china_10y_bond'],
}

# 数据库配置
DB_CONFIG = {
    'stocks_daily': 'postgresql+psycopg://sa:11111111@10.3.18.56/tdxIndex',
    'fundamentals': 'data/fundamentals.db',
    # 'macro_indicators': 'data/macro_indicators.db',
    # 'dynamic_prices': 'data/dynamic_prices.db',
}

# 预警阈值
ALERT_THRESHOLDS = {
    'price_drop': -0.10,      # 价格下跌 10% 预警
    'price_rise': 0.30,       # 价格上涨 30% 止盈预警
    'stop_loss': -0.15,       # 止损阈值 15%
    'weight_deviation': 0.15, # 权重偏离 15% 再平衡
    'portfolio_drawdown': -0.20,  # 组合回撤 20% 预警
}

# 更新频率配置
UPDATE_SCHEDULE = {
    'daily_data': '16:30',      # 日线数据更新
    'macro_data': '09:00',      # 宏观数据更新
    'dynamic_price': '17:00',   # 动态价格计算
    'alert_check': '09:30',     # 预警检查
}

# 文件路径
FILE_PATHS = {
    'output_excel': f'output/dynamic_price_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx',
    'log_file': 'logs/system.log',
}

# ========== TDX 接口配置 ==========
tdx = {
  'exhq_host': "47.112.95.207",
  'exhq_port': 7720,
  'hq_host': "180.153.18.170",
  'hq_port': 7709,
  'use_tdx': 'true',
  'timeout': 30,
  'retry_count': 3,
  'parallel_workers': 5,
}