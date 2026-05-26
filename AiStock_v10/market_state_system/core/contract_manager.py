#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AiStock V9.1 — 动态合约代码推导引擎 (ContractManager)

V7 → V9.1 升级改进:
  1. 完整移植 V7 ContractManager 的日期驱动动态合约推导
  2. 整合 V8 OptionCodeParser 三格式期权代码解析能力
  3. xlsx 代码表作为唯一数据源 — code 列与 TDX 接口 code 参数严格对齐
  4. code / code_name 双码制:
     - code (内部码): HO8Q0438, 10009633, 90005865 → TDX API get_instrument_bars() 参数
     - code_name (显示码): HO2602-P-2650, 510050C3A02700, 159901C3M002700A → 解析/展示用
  5. 所有与 TDX 接口交互的 code 参数从 xlsx code 列获取
  6. 合约到期自动滚动 + 预警

核心职责:
  - 从 xlsx 加载完整合约代码表 (code/code_name/market_code/category 映射)
  - 基于当前日期动态推导商品期货近月/远月合约代码
  - 基于当前日期动态推导股指期货当月/下季月合约代码
  - 基于当前日期动态推导期权近月/远月合约组
  - 提供 code ↔ code_name 双向查找
  - 管理 code 列值与 TDX 接口 code 参数的对齐

依赖:
  - openpyxl (读取 xlsx 代码表)
  - pandas
"""

from __future__ import annotations

import os
import re
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

import pandas as pd

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
#  数据结构定义
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class ContractInfo:
    """单个合约的完整信息（从代码表解析而来）。

    V9 关键改进: 区分 code (TDX接口用) 和 code_name (显示/解析用)

    Attributes:
        code:           TDX 内部合约代码 (用于 API 调用), 如 HO8Q0438, 10009633
        code_name:      合约显示名称 (用于解析), 如 HO2602-P-2650, 510050C3A02700
        market_code:    TDX 市场代码整数, 如 7, 8, 9, 28, 29, 30, 47, 66
        market_type:    V9 市场类型字符串, 如 future_sh, option_zj
        market_name:    市场中文名, 如 中金所期权
        category:       类别 (3=期货, 8=股票, 10=宏观, 12=期权)
        variety:        品种代码, 如 CU, IO
        delivery_year:  交割年, 如 2026 (0=非交割合约)
        delivery_month: 交割月, 如 6 (0=非交割合约)
    """
    code: str               # TDX内部码 — 传给 TDX API 的 code 参数
    code_name: str          # 显示码 — 传给 OptionCodeParser 解析
    market_code: int
    market_type: str
    market_name: str
    category: int
    variety: str
    delivery_year: int
    delivery_month: int


@dataclass
class FuturesContractPair:
    """商品期货近月/远月合约对。

    Attributes:
        variety_key:  品种英文键名, 如 copper
        variety_code: 品种 TDX 代码, 如 CU
        near_code:    近月合约 code (TDX内部码), 如 CU2606
        far_code:     远月合约 code (TDX内部码), 如 CU2609
        market_code:  TDX 市场代码整数
        market_type:  V9 市场类型字符串, 如 future_sh
        near_year:    近月交割年
        near_month:   近月交割月
        far_year:     远月交割年
        far_month:    远月交割月
    """
    variety_key: str
    variety_code: str
    near_code: str
    far_code: str
    market_code: int
    market_type: str
    near_year: int
    near_month: int
    far_year: int
    far_month: int


@dataclass
class IndexFuturesContract:
    """股指期货合约信息。

    Attributes:
        key:                品种英文键名, 如 if
        variety_code:       品种 TDX 代码, 如 IF
        futures_code:       当月合约 code, 如 IF2606
        next_quarter_code:  下季月合约 code, 如 IF2609
        spot_code:          现货指数代码, 如 000300
        market_code:        TDX 市场代码整数
        market_type:        V9 市场类型字符串
        delivery_year:      交割年
        delivery_month:     交割月
    """
    key: str
    variety_code: str
    futures_code: str
    next_quarter_code: str
    spot_code: str
    market_code: int
    market_type: str
    delivery_year: int
    delivery_month: int


@dataclass
class OptionContractGroup:
    """期权合约组（某标的某月的全部行权价合约）。

    V9 关键: call_codes / put_codes 使用 TDX 内部码 (code 列),
    code_names 使用显示码 (code_name 列).

    Attributes:
        underlying:     标的代码, 如 IO 或 510300
        market_code:    TDX 市场代码整数
        market_type:    V9 市场类型字符串
        delivery_year:  交割年
        delivery_month: 交割月
        contracts:      命中的 ContractInfo 列表
        call_codes:     看涨合约 code 列表 (TDX内部码, 用于API调用)
        put_codes:      看跌合约 code 列表 (TDX内部码, 用于API调用)
        call_code_names: 看涨合约 code_name 列表 (显示码, 用于解析)
        put_code_names:  看跌合约 code_name 列表 (显示码, 用于解析)
    """
    underlying: str
    market_code: int
    market_type: str
    delivery_year: int
    delivery_month: int
    contracts: List[ContractInfo] = field(default_factory=list)
    call_codes: List[str] = field(default_factory=list)
    put_codes: List[str] = field(default_factory=list)
    call_code_names: List[str] = field(default_factory=list)
    put_code_names: List[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════
#  品种交割月份规则
# ═══════════════════════════════════════════════════════════════════════

#: 商品期货交割月份规则
#: key = 品种 TDX 代码，value = 允许交割的月份列表
COMMODITY_DELIVERY_MONTHS: Dict[str, List[int]] = {
    # ── 上海期货 (market_type='future_sh') ──────────────────────
    'CU': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    'AL': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    'ZN': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    'PB': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    'NI': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    'SN': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    'AU': [2, 4, 6, 8, 10, 12],
    'AG': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    'RB': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    'HC': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    'SS': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    'BU': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    'RU': [1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    'NR': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    'FU': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    'LU': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    'SP': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    'BC': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    'AO': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    'BR': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    'EC': [2, 4, 6, 8, 10, 12],
    'AD': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    'OP': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    'SC': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    'WR': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],  # 线材：每月

    # ── 大连商品 (market_type='future_dl') ──────────────────────
    'M':  [1, 3, 5, 7, 8, 9, 11, 12],
    'Y':  [1, 3, 5, 7, 8, 9, 11, 12],
    'A':  [1, 3, 5, 7, 9, 11],
    'B':  [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    'C':  [1, 3, 5, 7, 9, 11],
    'CS': [1, 3, 5, 7, 9, 11],
    'I':  [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    'J':  [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    'JM': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    'L':  [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    'PP': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    'V':  [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    'EG': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    'EB': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    'PG': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    'P':  [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    'FB': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    'BB': [1, 3, 5, 7, 9, 11],
    'JD': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    'RR': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    'LH': [1, 3, 5, 7, 9, 11],
    'BZ': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    'LG': [1, 3, 5, 7, 9, 11],

    # ── 郑州商品 (market_type='future_zj') ──────────────────────
    'CF': [1, 3, 5, 7, 9, 11],
    'SR': [1, 3, 5, 7, 9, 11],
    'TA': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    'MA': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    'FG': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    'SA': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    'AP': [1, 3, 5, 10, 11, 12],
    'CJ': [1, 3, 5, 7, 9, 11],
    'OI': [1, 3, 5, 7, 9, 11],
    'RM': [1, 3, 5, 7, 8, 9, 11],
    'ZC': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    'SF': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    'SM': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    'PF': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    'SH': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    'UR': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    'PK': [1, 3, 4, 5, 10, 11, 12],
    'CY': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    'WH': [1, 3, 5, 7, 9, 11],
    'PM': [1, 3, 5, 7, 9, 11],
    'RI': [1, 3, 5, 7, 9, 11],
    'JR': [1, 3, 5, 7, 9, 11],
    'RS': [7, 8, 9, 11],
    'PR': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    'PX': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    'PL': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],

    # ── 广州期货 (market_type='future_gz') ──────────────────────
    'LC': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    'SI': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    'PS': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    'PD': [6, 8, 10, 12],
    'PT': [6, 8, 10, 12],
}

#: 股指期货交割季月
INDEX_FUTURES_QUARTER_MONTHS: List[int] = [3, 6, 9, 12]

# ═══════════════════════════════════════════════════════════════════════
#  品种 → 市场 映射
# ═══════════════════════════════════════════════════════════════════════

#: 品种 → TDX market_code 整数
VARIETY_MARKET_CODE: Dict[str, int] = {
    # 上海期货
    'CU': 30, 'AL': 30, 'ZN': 30, 'PB': 30, 'NI': 30, 'SN': 30,
    'AU': 30, 'AG': 30, 'RB': 30, 'HC': 30, 'SS': 30, 'BU': 30,
    'RU': 30, 'NR': 30, 'FU': 30, 'LU': 30, 'SP': 30, 'BC': 30,
    'AO': 30, 'BR': 30, 'EC': 30, 'AD': 30, 'OP': 30, 'SC': 30, 'WR': 30,
    # 大连商品
    'M': 29, 'Y': 29, 'A': 29, 'B': 29, 'C': 29, 'CS': 29,
    'I': 29, 'J': 29, 'JM': 29, 'L': 29, 'PP': 29, 'V': 29,
    'EG': 29, 'EB': 29, 'PG': 29, 'P': 29, 'FB': 29, 'BB': 29,
    'JD': 29, 'RR': 29, 'LH': 29, 'BZ': 29, 'LG': 29,
    # 郑州商品
    'CF': 28, 'SR': 28, 'TA': 28, 'MA': 28, 'FG': 28, 'SA': 28,
    'AP': 28, 'CJ': 28, 'OI': 28, 'RM': 28, 'ZC': 28,
    'SF': 28, 'SM': 28, 'PF': 28, 'SH': 28, 'UR': 28, 'PK': 28,
    'CY': 28, 'WH': 28, 'PM': 28, 'RI': 28, 'JR': 28, 'RS': 28,
    'PR': 28, 'PX': 28, 'PL': 28,
    # 广州期货
    'LC': 66, 'SI': 66, 'PS': 66, 'PD': 66, 'PT': 66,
    # 中金所
    'IF': 47, 'IH': 47, 'IC': 47, 'IM': 47,
    'T': 47, 'TF': 47, 'TL': 47, 'TS': 47,
}

#: 品种 → V9 market_type 字符串
VARIETY_MARKET_TYPE: Dict[str, str] = {
    # 上海期货
    'CU': 'future_sh', 'AL': 'future_sh', 'ZN': 'future_sh',
    'PB': 'future_sh', 'NI': 'future_sh', 'SN': 'future_sh',
    'AU': 'future_sh', 'AG': 'future_sh', 'RB': 'future_sh',
    'HC': 'future_sh', 'SS': 'future_sh', 'BU': 'future_sh',
    'RU': 'future_sh', 'NR': 'future_sh', 'FU': 'future_sh',
    'LU': 'future_sh', 'SP': 'future_sh', 'BC': 'future_sh',
    'AO': 'future_sh', 'BR': 'future_sh', 'EC': 'future_sh',
    'AD': 'future_sh', 'OP': 'future_sh', 'SC': 'future_sh', 'WR': 'future_sh',
    # 大连商品
    'M': 'future_dl', 'Y': 'future_dl', 'A': 'future_dl',
    'B': 'future_dl', 'C': 'future_dl', 'CS': 'future_dl',
    'I': 'future_dl', 'J': 'future_dl', 'JM': 'future_dl',
    'L': 'future_dl', 'PP': 'future_dl', 'V': 'future_dl',
    'EG': 'future_dl', 'EB': 'future_dl', 'PG': 'future_dl',
    'P': 'future_dl', 'FB': 'future_dl', 'BB': 'future_dl',
    'JD': 'future_dl', 'RR': 'future_dl', 'LH': 'future_dl',
    'BZ': 'future_dl', 'LG': 'future_dl',
    # 郑州商品
    'CF': 'future_zj', 'SR': 'future_zj', 'TA': 'future_zj',
    'MA': 'future_zj', 'FG': 'future_zj', 'SA': 'future_zj',
    'AP': 'future_zj', 'CJ': 'future_zj', 'OI': 'future_zj',
    'RM': 'future_zj', 'ZC': 'future_zj', 'SF': 'future_zj',
    'SM': 'future_zj', 'PF': 'future_zj', 'SH': 'future_zj',
    'UR': 'future_zj', 'PK': 'future_zj', 'CY': 'future_zj',
    'WH': 'future_zj', 'PM': 'future_zj', 'RI': 'future_zj',
    'JR': 'future_zj', 'RS': 'future_zj', 'PR': 'future_zj',
    'PX': 'future_zj', 'PL': 'future_zj',
    # 广州期货
    'LC': 'future_gz', 'SI': 'future_gz', 'PS': 'future_gz',
    'PD': 'future_gz', 'PT': 'future_gz',
    # 中金所
    'IF': 'future_zj', 'IH': 'future_zj', 'IC': 'future_zj', 'IM': 'future_zj',
    'T': 'future_zj', 'TF': 'future_zj', 'TL': 'future_zj', 'TS': 'future_zj',
}

#: 品种 → 中文名称
VARIETY_NAMES: Dict[str, str] = {
    'CU': '沪铜', 'AL': '沪铝', 'ZN': '沪锌', 'PB': '沪铅', 'NI': '沪镍',
    'SN': '沪锡', 'AU': '黄金', 'AG': '白银', 'RB': '螺纹钢', 'HC': '热卷',
    'SS': '不锈钢', 'BU': '沥青', 'RU': '橡胶', 'NR': '20号胶', 'FU': '燃油',
    'LU': '低硫燃油', 'SP': '纸浆', 'BC': '国际铜', 'AO': '氧化铝',
    'BR': '丁二烯橡胶', 'EC': '集运指数', 'AD': '铝合金', 'OP': '石油沥青',
    'SC': '原油', 'WR': '线材',
    'M': '豆粕', 'Y': '豆油', 'A': '豆一', 'B': '豆二', 'C': '玉米',
    'CS': '淀粉', 'I': '铁矿', 'J': '焦炭', 'JM': '焦煤', 'L': '塑料',
    'PP': '聚丙烯', 'V': 'PVC', 'EG': '乙二醇', 'EB': '苯乙烯', 'PG': 'LPG',
    'P': '棕榈油', 'FB': '纤维板', 'BB': '胶合板', 'JD': '鸡蛋', 'RR': '粳米',
    'LH': '生猪', 'BZ': '苯乙烯', 'LG': '铁合金',
    'CF': '棉花', 'SR': '白糖', 'TA': 'PTA', 'MA': '甲醇', 'FG': '玻璃',
    'SA': '纯碱', 'AP': '苹果', 'CJ': '红枣', 'OI': '菜油', 'RM': '菜粕',
    'ZC': '动力煤', 'SF': '硅铁', 'SM': '锰硅', 'PF': '短纤', 'SH': '烧碱',
    'UR': '尿素', 'PK': '花生', 'CY': '棉纱', 'WH': '强麦', 'PM': '普麦',
    'RI': '早籼稻', 'JR': '粳稻', 'RS': '菜籽', 'PR': '瓶片', 'PX': '对二甲苯',
    'PL': '油脂',
    'LC': '碳酸锂', 'SI': '工业硅', 'PS': '碳酸锂', 'PD': '铂', 'PT': '钯',
    'IF': '沪深300', 'IH': '上证50', 'IC': '中证500', 'IM': '中证1000',
}

# ═══════════════════════════════════════════════════════════════════════
#  系统监控品种 & 期货/期权配置
# ═══════════════════════════════════════════════════════════════════════

#: 系统监控的商品品种
MONITORED_COMMODITIES: Dict[str, str] = {
    'copper': 'CU', 'aluminum': 'AL', 'lithium': 'LC',
    'silicon': 'SI', 'crude': 'SC', 'rebar': 'RB',
    'gold': 'AU', 'soybean': 'M',
}

#: 股指期货配置
INDEX_FUTURES_CONFIG: Dict[str, Dict[str, str]] = {
    'if': {'variety': 'IF', 'spot_code': '000300', 'spot_name': '沪深300', 'market_type': 'future_zj'},
    'ih': {'variety': 'IH', 'spot_code': '000016', 'spot_name': '上证50', 'market_type': 'future_zj'},
    'ic': {'variety': 'IC', 'spot_code': '000905', 'spot_name': '中证500', 'market_type': 'future_zj'},
    'im': {'variety': 'IM', 'spot_code': '000852', 'spot_name': '中证1000', 'market_type': 'future_zj'},
}

#: 期权标的配置
OPTION_UNDERLYING_CONFIG: Dict[str, Dict] = {
    # 中金所指数期权
    'IO': {'spot_code': '000300', 'market_code': 7, 'market_type': 'option_zj', 'name': '沪深300指数期权'},
    'HO': {'spot_code': '000016', 'market_code': 7, 'market_type': 'option_zj', 'name': '上证50指数期权'},
    'MO': {'spot_code': '000852', 'market_code': 7, 'market_type': 'option_zj', 'name': '中证1000指数期权'},
    # 上交所ETF期权
    '510050': {'spot_code': '510050', 'market_code': 8, 'market_type': 'option_sh', 'name': '上证50ETF期权'},
    '510300': {'spot_code': '510300', 'market_code': 8, 'market_type': 'option_sh', 'name': '沪深300ETF期权(沪)'},
    '510500': {'spot_code': '510500', 'market_code': 8, 'market_type': 'option_sh', 'name': '中证500ETF期权'},
    '588000': {'spot_code': '588000', 'market_code': 8, 'market_type': 'option_sh', 'name': '科创50ETF期权'},
    '588080': {'spot_code': '588080', 'market_code': 8, 'market_type': 'option_sh', 'name': '科创板50ETF期权'},
    # 深交所ETF期权
    '159901': {'spot_code': '159901', 'market_code': 9, 'market_type': 'option_sz', 'name': '深证100ETF期权'},
    '159915': {'spot_code': '159915', 'market_code': 9, 'market_type': 'option_sz', 'name': '创业板ETF期权'},
    '159919': {'spot_code': '159919', 'market_code': 9, 'market_type': 'option_sz', 'name': '沪深300ETF期权(深)'},
    '159922': {'spot_code': '159922', 'market_code': 9, 'market_type': 'option_sz', 'name': '中证500ETF期权(深)'},
    # ── 郑州商品期权 (market_code=4, option_czce) ───────────────
    'AP': {'spot_code': 'AP', 'market_code': 4, 'market_type': 'option_czce', 'name': '苹果期权'},
    'CF': {'spot_code': 'CF', 'market_code': 4, 'market_type': 'option_czce', 'name': '棉花期权'},
    'CJ': {'spot_code': 'CJ', 'market_code': 4, 'market_type': 'option_czce', 'name': '红枣期权'},
    'FG': {'spot_code': 'FG', 'market_code': 4, 'market_type': 'option_czce', 'name': '玻璃期权'},
    'MA': {'spot_code': 'MA', 'market_code': 4, 'market_type': 'option_czce', 'name': '甲醇期权'},
    'OI': {'spot_code': 'OI', 'market_code': 4, 'market_type': 'option_czce', 'name': '菜油期权'},
    'PF': {'spot_code': 'PF', 'market_code': 4, 'market_type': 'option_czce', 'name': '短纤期权'},
    'PK': {'spot_code': 'PK', 'market_code': 4, 'market_type': 'option_czce', 'name': '花生期权'},
    'PL': {'spot_code': 'PL', 'market_code': 4, 'market_type': 'option_czce', 'name': '油脂期权'},
    'PR': {'spot_code': 'PR', 'market_code': 4, 'market_type': 'option_czce', 'name': '瓶片期权'},
    'PX': {'spot_code': 'PX', 'market_code': 4, 'market_type': 'option_czce', 'name': '对二甲苯期权'},
    'RM': {'spot_code': 'RM', 'market_code': 4, 'market_type': 'option_czce', 'name': '菜粕期权'},
    'SA': {'spot_code': 'SA', 'market_code': 4, 'market_type': 'option_czce', 'name': '纯碱期权'},
    'SF': {'spot_code': 'SF', 'market_code': 4, 'market_type': 'option_czce', 'name': '硅铁期权'},
    'SH': {'spot_code': 'SH', 'market_code': 4, 'market_type': 'option_czce', 'name': '烧碱期权'},
    'SM': {'spot_code': 'SM', 'market_code': 4, 'market_type': 'option_czce', 'name': '锰硅期权'},
    'SR': {'spot_code': 'SR', 'market_code': 4, 'market_type': 'option_czce', 'name': '白糖期权'},
    'TA': {'spot_code': 'TA', 'market_code': 4, 'market_type': 'option_czce', 'name': 'PTA期权'},
    'UR': {'spot_code': 'UR', 'market_code': 4, 'market_type': 'option_czce', 'name': '尿素期权'},
    'ZC': {'spot_code': 'ZC', 'market_code': 4, 'market_type': 'option_czce', 'name': '动力煤期权'},
    # ── 大连商品期权 (market_code=5, option_dce) ────────────────
    'A': {'spot_code': 'A', 'market_code': 5, 'market_type': 'option_dce', 'name': '豆一期权'},
    'B': {'spot_code': 'B', 'market_code': 5, 'market_type': 'option_dce', 'name': '豆二期权'},
    'BZ': {'spot_code': 'BZ', 'market_code': 5, 'market_type': 'option_dce', 'name': '苯乙烯期权'},
    'C': {'spot_code': 'C', 'market_code': 5, 'market_type': 'option_dce', 'name': '玉米期权'},
    'CS': {'spot_code': 'CS', 'market_code': 5, 'market_type': 'option_dce', 'name': '淀粉期权'},
    'EB': {'spot_code': 'EB', 'market_code': 5, 'market_type': 'option_dce', 'name': '苯乙烯期权'},
    'EG': {'spot_code': 'EG', 'market_code': 5, 'market_type': 'option_dce', 'name': '乙二醇期权'},
    'I': {'spot_code': 'I', 'market_code': 5, 'market_type': 'option_dce', 'name': '铁矿期权'},
    'JD': {'spot_code': 'JD', 'market_code': 5, 'market_type': 'option_dce', 'name': '鸡蛋期权'},
    'JM': {'spot_code': 'JM', 'market_code': 5, 'market_type': 'option_dce', 'name': '焦煤期权'},
    'L': {'spot_code': 'L', 'market_code': 5, 'market_type': 'option_dce', 'name': '塑料期权'},
    'LG': {'spot_code': 'LG', 'market_code': 5, 'market_type': 'option_dce', 'name': '铁合金期权'},
    'LH': {'spot_code': 'LH', 'market_code': 5, 'market_type': 'option_dce', 'name': '生猪期权'},
    'M': {'spot_code': 'M', 'market_code': 5, 'market_type': 'option_dce', 'name': '豆粕期权'},
    'P': {'spot_code': 'P', 'market_code': 5, 'market_type': 'option_dce', 'name': '棕榈油期权'},
    'PG': {'spot_code': 'PG', 'market_code': 5, 'market_type': 'option_dce', 'name': 'LPG期权'},
    'PP': {'spot_code': 'PP', 'market_code': 5, 'market_type': 'option_dce', 'name': '聚丙烯期权'},
    'V': {'spot_code': 'V', 'market_code': 5, 'market_type': 'option_dce', 'name': 'PVC期权'},
    'Y': {'spot_code': 'Y', 'market_code': 5, 'market_type': 'option_dce', 'name': '豆油期权'},
    # ── 上海商品期权 (market_code=6, option_shfe) ───────────────
    'AD': {'spot_code': 'AD', 'market_code': 6, 'market_type': 'option_shfe', 'name': '铝合金期权'},
    'AG': {'spot_code': 'AG', 'market_code': 6, 'market_type': 'option_shfe', 'name': '白银期权'},
    'AL': {'spot_code': 'AL', 'market_code': 6, 'market_type': 'option_shfe', 'name': '沪铝期权'},
    'AO': {'spot_code': 'AO', 'market_code': 6, 'market_type': 'option_shfe', 'name': '氧化铝期权'},
    'AU': {'spot_code': 'AU', 'market_code': 6, 'market_type': 'option_shfe', 'name': '黄金期权'},
    'BC': {'spot_code': 'BC', 'market_code': 6, 'market_type': 'option_shfe', 'name': '国际铜期权'},
    'BR': {'spot_code': 'BR', 'market_code': 6, 'market_type': 'option_shfe', 'name': '丁二烯橡胶期权'},
    'BU': {'spot_code': 'BU', 'market_code': 6, 'market_type': 'option_shfe', 'name': '沥青期权'},
    'CU': {'spot_code': 'CU', 'market_code': 6, 'market_type': 'option_shfe', 'name': '沪铜期权'},
    'FU': {'spot_code': 'FU', 'market_code': 6, 'market_type': 'option_shfe', 'name': '燃油期权'},
    'NI': {'spot_code': 'NI', 'market_code': 6, 'market_type': 'option_shfe', 'name': '沪镍期权'},
    'NR': {'spot_code': 'NR', 'market_code': 6, 'market_type': 'option_shfe', 'name': '20号胶期权'},
    'OP': {'spot_code': 'OP', 'market_code': 6, 'market_type': 'option_shfe', 'name': '石油沥青期权'},
    'PB': {'spot_code': 'PB', 'market_code': 6, 'market_type': 'option_shfe', 'name': '沪铅期权'},
    'RB': {'spot_code': 'RB', 'market_code': 6, 'market_type': 'option_shfe', 'name': '螺纹钢期权'},
    'RU': {'spot_code': 'RU', 'market_code': 6, 'market_type': 'option_shfe', 'name': '橡胶期权'},
    'SC': {'spot_code': 'SC', 'market_code': 6, 'market_type': 'option_shfe', 'name': '原油期权'},
    'SN': {'spot_code': 'SN', 'market_code': 6, 'market_type': 'option_shfe', 'name': '沪锡期权'},
    'SP': {'spot_code': 'SP', 'market_code': 6, 'market_type': 'option_shfe', 'name': '纸浆期权'},
    'ZN': {'spot_code': 'ZN', 'market_code': 6, 'market_type': 'option_shfe', 'name': '沪锌期权'},
    # ── 广州期权 (market_code=67, option_gz) ────────────────────
    'LC': {'spot_code': 'LC', 'market_code': 67, 'market_type': 'option_gz', 'name': '碳酸锂期权'},
    'PD': {'spot_code': 'PD', 'market_code': 67, 'market_type': 'option_gz', 'name': '铂期权'},
    'PS': {'spot_code': 'PS', 'market_code': 67, 'market_type': 'option_gz', 'name': '碳酸锂期权'},
    'PT': {'spot_code': 'PT', 'market_code': 67, 'market_type': 'option_gz', 'name': '钯期权'},
    'SI': {'spot_code': 'SI', 'market_code': 67, 'market_type': 'option_gz', 'name': '工业硅期权'},
}

EXPIRY_WARNING_DAYS: int = 5
ROLLOVER_DAY: int = 15


# ═══════════════════════════════════════════════════════════════════════
#  ContractManager
# ═══════════════════════════════════════════════════════════════════════

class ContractManager:
    """V9.1 合约管理器: 基于日期动态推导合约代码 + xlsx 代码表对齐。

    V9.1 核心设计原则:
    - **xlsx 代码表为唯一数据源**: code 列 = TDX 接口参数, code_name 列 = 解析用
    - **code/code_name 双码制**: TDX API 用 code, OptionCodeParser 用 code_name
    - **零硬编码**: 所有合约代码由日期 + 品种规则 + 代码表动态生成
    - **自动滚动**: 合约到期后自动切换到下月
    - **精确匹配**: 不同品种交割月份规则精确编码

    公共接口:
    - :meth:`get_commodity_contracts`        — 获取商品期货近月/远月合约对
    - :meth:`get_index_futures_contracts`     — 获取股指期货当月/下季月合约
    - :meth:`get_option_contracts`            — 获取期权近月合约组
    - :meth:`get_option_near_month`           — 获取期权近月交割月份
    - :meth:`get_contract_code`               — 获取品种合约代码 (DerivativesSignalEngine 用)
    - :meth:`lookup_code_by_code_name`        — code_name → code 反查
    - :meth:`lookup_code_name_by_code`        — code → code_name 反查
    - :meth:`check_expiry_warnings`           — 检查即将到期合约
    - :meth:`generate_full_config_updates`    — 生成动态配置更新
    - :meth:`get_contract_summary`            — 获取合约推导摘要
    - :meth:`update`                          — 刷新合约映射 (main.py 调用)
    """

    def __init__(
        self,
        code_table_path: Optional[str] = None,
        reference_date: Optional[datetime] = None,
        rollover_day: int = ROLLOVER_DAY,
        expiry_warning_days: int = EXPIRY_WARNING_DAYS,
        option_code_parser: Optional[Any] = None,
    ) -> None:
        """初始化合约管理器。

        Args:
            code_table_path:      TDX 代码表 xlsx 路径 (含 code/code_name/market_code/category 列)
            reference_date:       参考日期, 默认今天
            rollover_day:         每月第 N 天后视为需切换下月合约
            expiry_warning_days:  到期提醒天数
            option_code_parser:   OptionCodeParser 实例 (可选, 用于期权代码解析)
        """
        self.reference_date = reference_date or datetime.now()
        self.code_table_path = code_table_path
        self.rollover_day = rollover_day
        self.expiry_warning_days = expiry_warning_days
        self._logger = logger
        self._parser = option_code_parser

        # TDX 代码表数据
        self._code_table: Dict[str, ContractInfo] = {}          # code → ContractInfo
        self._code_name_to_code: Dict[str, str] = {}            # code_name → code
        self._code_to_code_name: Dict[str, str] = {}            # code → code_name
        self._variety_codes: Dict[str, List[ContractInfo]] = defaultdict(list)  # variety → [ContractInfo] (期货)
        self._option_by_underlying: Dict[str, List[ContractInfo]] = defaultdict(list)  # underlying/variety → [ContractInfo] (期权)
        self._option_by_market: Dict[int, List[ContractInfo]] = defaultdict(list)  # market_code → [ContractInfo] (期权)

        # 加载代码表
        if code_table_path and os.path.exists(code_table_path):
            self._load_code_table(code_table_path)

        self._logger.info(
            f"ContractManager V9.1 初始化完成 | "
            f"参考日期: {self.reference_date.strftime('%Y-%m-%d')} | "
            f"已加载 {len(self._code_table)} 个合约 | "
            f"期货品种: {len(self._variety_codes)} | "
            f"期权标的: {len(self._option_by_underlying)}"
        )

    # ──────────────────────────────────────────────────────────────
    #  代码表加载 — xlsx 为唯一数据源
    # ──────────────────────────────────────────────────────────────

    def _load_code_table(self, path: str) -> None:
        """从 xlsx 加载 TDX 代码表。

        xlsx 列说明:
          - code:        TDX 内部码 (用于 API 调用), 如 HO8Q0438, 10009633, CU2606
          - code_name:   合约显示名称 (用于解析), 如 HO2602-P-2650, 510050C3A02700
          - market_code: TDX 市场代码, 如 7, 8, 9, 28, 29, 30, 47, 66
          - market_name: 市场中文名, 如 中金所期权
          - category:    类别 (3=期货, 8=股票, 10=宏观, 12=期权)

        Args:
            path: xlsx 文件路径
        """
        try:
            df = pd.read_excel(path)
            if df.empty:
                self._logger.warning("代码表为空: %s", path)
                return

            for _, row in df.iterrows():
                code = str(row.get("code", "")).strip()
                code_name = str(row.get("code_name", "")).strip()
                market_code = int(row.get("market_code", 0)) if pd.notna(row.get("market_code")) else 0
                market_name = str(row.get("market_name", "")).strip() if pd.notna(row.get("market_name")) else ""
                category = int(row.get("category", 0)) if pd.notna(row.get("category")) else 0

                if not code:
                    continue

                # 解析品种和交割年月
                variety, delivery_year, delivery_month = self._parse_contract_code(
                    code, code_name, category,
                )

                # 推断 market_type
                market_type = self._infer_market_type(variety, market_code, category)

                info = ContractInfo(
                    code=code,
                    code_name=code_name,
                    market_code=market_code,
                    market_type=market_type,
                    market_name=market_name,
                    category=category,
                    variety=variety,
                    delivery_year=delivery_year,
                    delivery_month=delivery_month,
                )

                self._code_table[code] = info

                # code ↔ code_name 双向映射
                if code_name:
                    self._code_name_to_code[code_name] = code
                self._code_to_code_name[code] = code_name

                # 按类别分类存储
                if category == 3 and delivery_month > 0:       # 期货 (排除主连/指数)
                    self._variety_codes[variety].append(info)
                elif category == 12:                            # 期权
                    self._option_by_underlying[variety].append(info)
                    self._option_by_market[market_code].append(info)

            self._logger.info(
                f"代码表加载完成 | "
                f"总合约: {len(self._code_table)} | "
                f"期货品种: {len(self._variety_codes)} | "
                f"期权标的: {len(self._option_by_underlying)} | "
                f"code_name→code映射: {len(self._code_name_to_code)}"
            )

        except Exception as exc:
            self._logger.error(f"代码表加载失败: {exc}")

    # ──────────────────────────────────────────────────────────────
    #  code / code_name 双向查询
    # ──────────────────────────────────────────────────────────────

    def lookup_code_by_code_name(self, code_name: str) -> Optional[str]:
        """code_name (显示码) → code (TDX内部码)

        用于: 从 OptionCodeParser 解析结果反查 TDX API 所需的 code 参数。

        Args:
            code_name: 显示码, 如 '510050C3A02700', 'HO2602-P-2650'

        Returns:
            TDX 内部码, 如 '10009633', 'HO8Q0438', 或 None
        """
        return self._code_name_to_code.get(code_name)

    def lookup_code_name_by_code(self, code: str) -> Optional[str]:
        """code (TDX内部码) → code_name (显示码)

        用于: 从 TDX API 返回的 code 查找可解析的 code_name。

        Args:
            code: TDX 内部码

        Returns:
            显示码, 或 None
        """
        return self._code_to_code_name.get(code)

    def get_contract_info(self, code: str) -> Optional[ContractInfo]:
        """通过 code 查找完整合约信息"""
        return self._code_table.get(code)

    # ──────────────────────────────────────────────────────────────
    #  market_type 推断
    # ──────────────────────────────────────────────────────────────

    def _infer_market_type(self, variety: str, market_code: int, category: int) -> str:
        """根据品种代码 / market_code / category 推断 V9.1 market_type。"""
        if category == 3:  # 期货
            mt = VARIETY_MARKET_TYPE.get(variety)
            if mt:
                return mt

        if category == 12:  # 期权
            if variety in ('IO', 'HO', 'MO'):
                return 'option_zj'
            if market_code == 8:
                return 'option_sh'
            if market_code == 9:
                return 'option_sz'
            # V9.1: 商品期权按 market_code 精确归属交易所
            if market_code == 4:
                return 'option_czce'
            if market_code == 5:
                return 'option_dce'
            if market_code == 6:
                return 'option_shfe'
            if market_code == 67:
                return 'option_gz'
            # 兜底: 商品期权归属对应交易所 (基于期货品种映射)
            mt = VARIETY_MARKET_TYPE.get(variety, '')
            if mt.startswith('future_'):
                return mt.replace('future_', 'option_')
            return 'option_sh'

        # 回退: 按 market_code
        market_code_to_type = {
            30: 'future_sh', 29: 'future_dl', 28: 'future_zj',
            66: 'future_gz', 47: 'future_zj',
            7: 'option_zj', 8: 'option_sh', 9: 'option_sz',
            4: 'option_czce', 5: 'option_dce', 6: 'option_shfe', 67: 'option_gz',
            12: 'index_intl', 46: 'gold_sh', 62: 'index_csi', 102: 'index_cni',
        }
        return market_code_to_type.get(market_code, 'future_sh')

    def _parse_contract_code(
        self, code: str, code_name: str, category: int,
    ) -> Tuple[str, int, int]:
        """解析合约代码, 提取品种 / 交割年 / 交割月。

        对于期货: code 列 = 品种+YYMM 格式 (如 CU2606, M2603)
        对于期权: code 列是 TDX 内部编码 (如 HO8Q0438, 10009633), 需从 code_name 解析

        Returns:
            (variety, delivery_year, delivery_month)
        """
        code_upper = code.upper().strip()

        if category == 3:  # 期货
            # 主连: CUL8, ALL8
            if code_upper.endswith('L8') or code_upper.endswith('L9'):
                return code_upper[:-2], 0, 0
            # 指数: IFM0, IFM1 (主力/次主力)
            if code_upper.endswith('M0') or code_upper.endswith('M1'):
                return code_upper[:-2], 0, 0

            # 普通合约: CU2606, M2603
            match = re.match(r'^([A-Z]+)(\d{3,4})$', code_upper)
            if match:
                variety = match.group(1)
                num = match.group(2)
                if len(num) == 4:  # YYMM
                    return variety, 2000 + int(num[:2]), int(num[2:])
                elif len(num) == 3:  # YMM
                    return variety, 2000 + int(num[0]) + 20, int(num[-2:])

            # 兜底: 从 code_name 提取
            if code_name:
                match = re.search(r'(\d{4})', code_name)
                if match:
                    num = match.group(1)
                    return code_upper.rstrip('0123456789'), 2000 + int(num[:2]), int(num[2:4])

            return code_upper, 0, 0

        elif category == 12:  # 期权
            # 期权 code 列是 TDX 内部码, 无法直接解析
            # 必须从 code_name 列解析
            if code_name:
                # 中金所/商品期权: HO2602-P-2650, CU2606-C-100000
                match = re.match(r'^([A-Z]+)(\d{4})', code_name)
                if match:
                    variety = match.group(1)
                    yy = int(match.group(2)[:2])
                    mm = int(match.group(2)[2:4])
                    return variety, 2000 + yy, mm

                # ETF期权: 510050C3A02700, 159901C6M002700A
                # 格式: underlying(6) + C/P(1) + year_digit(1) + month_letter(1) + strike
                match = re.match(r'^(\d{6})([CP])(\d)([A-X])', code_name)
                if match:
                    underlying = match.group(1)
                    dir_letter = match.group(2)
                    year_digit = int(match.group(3))
                    month_letter = match.group(4)

                    # 解析年份
                    current_year = datetime.now().year
                    decade_start = (current_year // 10) * 10
                    delivery_year = decade_start + year_digit
                    if delivery_year > current_year + 5:
                        delivery_year -= 10
                    if delivery_year < current_year - 5:
                        delivery_year += 10

                    # 解析月份
                    call_month_map = {
                        "A": 1, "B": 2, "C": 3, "D": 4,
                        "E": 5, "F": 6, "G": 7, "H": 8,
                        "I": 9, "J": 10, "K": 11, "L": 12,
                    }
                    put_month_map = {
                        "M": 1, "N": 2, "O": 3, "P": 4,
                        "Q": 5, "R": 6, "S": 7, "T": 8,
                        "U": 9, "V": 10, "W": 11, "X": 12,
                    }

                    if dir_letter == 'C' and month_letter in call_month_map:
                        delivery_month = call_month_map[month_letter]
                    elif dir_letter == 'P' and month_letter in put_month_map:
                        delivery_month = put_month_map[month_letter]
                    elif month_letter in call_month_map:
                        delivery_month = call_month_map[month_letter]
                    elif month_letter in put_month_map:
                        delivery_month = put_month_map[month_letter]
                    else:
                        delivery_month = 0

                    return underlying, delivery_year, delivery_month

                # 兜底: 只提取6位数字标的
                match = re.match(r'^(\d{6})', code_name)
                if match:
                    underlying = match.group(1)
                    return underlying, 0, 0

            return code_upper, 0, 0

        return code_upper, 0, 0

    # ──────────────────────────────────────────────────────────────
    #  核心: 动态合约推导
    # ──────────────────────────────────────────────────────────────

    def _get_next_delivery_month(
        self, variety: str, ref_date: datetime, skip_months: int = 0,
    ) -> Tuple[int, int]:
        """获取品种从 ref_date 起第 skip_months+1 个交割月。"""
        delivery_months = COMMODITY_DELIVERY_MONTHS.get(
            variety, list(range(1, 13)),
        )

        current_year = ref_date.year
        current_month = ref_date.month
        current_day = ref_date.day

        is_rollover = current_day >= self.rollover_day

        found_count = 0
        search_year = current_year
        search_month = current_month

        if not is_rollover and current_month in delivery_months:
            if skip_months == 0:
                return search_year, current_month
            found_count += 1

        for _ in range(36):
            search_month += 1
            if search_month > 12:
                search_month = 1
                search_year += 1

            if search_month in delivery_months:
                if found_count >= skip_months:
                    return search_year, search_month
                found_count += 1

        return current_year + 1, 1

    @staticmethod
    def _make_futures_code(variety: str, year: int, month: int) -> str:
        """生成期货合约代码 (用于代码表查询)。

        >>> ContractManager._make_futures_code('CU', 2026, 6)
        'CU2606'
        """
        yy = year % 100
        return f"{variety}{yy:02d}{month:02d}"

    @staticmethod
    def _make_main_contract_code(variety: str) -> str:
        """生成主力合约代码 (TDX XL8 格式)。"""
        return f"{variety}L8"

    # ──────────────────────────────────────────────────────────────
    #  公共接口
    # ──────────────────────────────────────────────────────────────

    def get_commodity_contracts(
        self, commodity_key: Optional[str] = None,
    ) -> Dict[str, FuturesContractPair]:
        """获取商品期货近月/远月合约对。"""
        results: Dict[str, FuturesContractPair] = {}

        commodities = (
            {commodity_key: MONITORED_COMMODITIES[commodity_key]}
            if commodity_key and commodity_key in MONITORED_COMMODITIES
            else MONITORED_COMMODITIES
        )

        for key, variety in commodities.items():
            try:
                market_code = VARIETY_MARKET_CODE.get(variety, 30)
                market_type = VARIETY_MARKET_TYPE.get(variety, 'future_sh')

                near_year, near_month = self._get_next_delivery_month(
                    variety, self.reference_date, skip_months=0,
                )
                far_year, far_month = self._get_next_delivery_month(
                    variety, self.reference_date, skip_months=1,
                )

                near_code = self._make_futures_code(variety, near_year, near_month)
                far_code = self._make_futures_code(variety, far_year, far_month)

                # 从代码表验证 code 是否存在
                near_code = self._validate_code(near_code, variety, near_year, near_month)
                far_code = self._validate_code(far_code, variety, far_year, far_month)

                results[key] = FuturesContractPair(
                    variety_key=key, variety_code=variety,
                    near_code=near_code, far_code=far_code,
                    market_code=market_code, market_type=market_type,
                    near_year=near_year, near_month=near_month,
                    far_year=far_year, far_month=far_month,
                )

            except Exception as exc:
                self._logger.warning(f"  {key} ({variety}) 合约推导失败: {exc}")
                continue

        self._logger.info(f"动态推导商品期货合约: {len(results)} 个品种")
        return results

    def get_index_futures_contracts(
        self,
    ) -> Dict[str, IndexFuturesContract]:
        """获取股指期货当月/下季月合约。"""
        results: Dict[str, IndexFuturesContract] = {}

        current_year = self.reference_date.year
        current_month = self.reference_date.month
        current_day = self.reference_date.day

        for key, config in INDEX_FUTURES_CONFIG.items():
            variety = config['variety']
            spot_code = config['spot_code']
            market_type = config.get('market_type', 'future_zj')

            # 确定当月合约
            if current_day < self.rollover_day:
                active_month = current_month
                active_year = current_year
            else:
                active_month = current_month + 1
                active_year = current_year
                if active_month > 12:
                    active_month = 1
                    active_year += 1

            # 确定下季月
            next_quarter_month = None
            next_quarter_year = active_year
            for qm in INDEX_FUTURES_QUARTER_MONTHS:
                if qm > active_month:
                    next_quarter_month = qm
                    break
            if next_quarter_month is None:
                next_quarter_month = INDEX_FUTURES_QUARTER_MONTHS[0]
                next_quarter_year += 1

            active_code = self._make_futures_code(variety, active_year, active_month)
            next_quarter_code = self._make_futures_code(variety, next_quarter_year, next_quarter_month)

            results[key] = IndexFuturesContract(
                key=key, variety_code=variety,
                futures_code=active_code, next_quarter_code=next_quarter_code,
                spot_code=spot_code, market_code=47, market_type=market_type,
                delivery_year=active_year, delivery_month=active_month,
            )

        self._logger.info(f"动态推导股指期货合约: {len(results)} 个品种")
        return results

    def get_index_futures_main_code(self, key: str) -> str:
        """获取股指期货主力合约代码 (TDX 主连格式)。"""
        config = INDEX_FUTURES_CONFIG.get(key)
        if not config:
            return f"{key.upper()}L8"
        return self._make_main_contract_code(config['variety'])

    def get_option_near_month(self, underlying: str) -> Tuple[int, int]:
        """获取期权近月交割月份。"""
        current_year = self.reference_date.year
        current_month = self.reference_date.month
        current_day = self.reference_date.day

        if current_day >= self.rollover_day:
            near_month = current_month + 1
            near_year = current_year
            if near_month > 12:
                near_month = 1
                near_year += 1
        else:
            near_month = current_month
            near_year = current_year

        return near_year, near_month

    def get_option_contracts(
        self,
        underlying: str,
        market_code: Optional[int] = None,
        market_type: Optional[str] = None,
    ) -> Optional[OptionContractGroup]:
        """获取期权近月合约组 (基于代码表筛选)。

        V9 关键: 返回的 call_codes/put_codes 使用 TDX 内部码 (code 列),
        call_code_names/put_code_names 使用显示码 (code_name 列)。
        """
        config = OPTION_UNDERLYING_CONFIG.get(underlying, {})
        if market_code is None:
            market_code = config.get('market_code', 7)
        if market_type is None:
            market_type = config.get('market_type', 'option_zj')

        near_year, near_month = self.get_option_near_month(underlying)

        # 从代码表筛选近月合约
        matching: List[ContractInfo] = []
        for info in self._option_by_underlying.get(underlying, []):
            if info.delivery_year == near_year and info.delivery_month == near_month:
                matching.append(info)

        # 近月无数据 → 尝试下月
        if not matching:
            if near_month == 12:
                next_year, next_month = near_year + 1, 1
            else:
                next_year, next_month = near_year, near_month + 1
            for info in self._option_by_underlying.get(underlying, []):
                if info.delivery_year == next_year and info.delivery_month == next_month:
                    matching.append(info)
            near_year, near_month = next_year, next_month

        # 分类看涨/看跌 — V9 使用 code_name 解析方向
        call_codes: List[str] = []
        put_codes: List[str] = []
        call_code_names: List[str] = []
        put_code_names: List[str] = []

        for info in matching:
            direction = self._infer_option_direction(info)
            if direction == 'call':
                call_codes.append(info.code)          # TDX 内部码
                call_code_names.append(info.code_name) # 显示码
            elif direction == 'put':
                put_codes.append(info.code)
                put_code_names.append(info.code_name)

        return OptionContractGroup(
            underlying=underlying,
            market_code=market_code,
            market_type=market_type,
            delivery_year=near_year,
            delivery_month=near_month,
            contracts=matching,
            call_codes=call_codes,
            put_codes=put_codes,
            call_code_names=call_code_names,
            put_code_names=put_code_names,
        )

    def _infer_option_direction(self, info: ContractInfo) -> str:
        """推断期权合约方向 (call/put)

        使用 code_name 列判断:
          - 中金所/商品: HO2602-P-2650 → put, HO2602-C-2650 → call
          - ETF期权: 510050C3A02700 → call, 510050P3A02700 → put
          - 深交所: 159901C3M002700A → call, 159901P3M002700A → put
        """
        cn = info.code_name.upper()

        # 中金所/商品期权格式: 含 -C- 或 -P-
        if '-C-' in cn:
            return 'call'
        if '-P-' in cn:
            return 'put'

        # ETF 期权格式: 标的代码 + C/P 字母
        # 找 6 位数字后的第 7 个字符
        match = re.match(r'^\d{6}([CP])', cn)
        if match:
            return 'call' if match.group(1) == 'C' else 'put'

        # 兜底
        return 'call'

    def get_contract_code(
        self, variety: str, month_offset: int = 0,
    ) -> str:
        """获取品种合约代码 (DerivativesSignalEngine 调用)。

        Args:
            variety:      品种代码, 如 'CU', 'IF'
            month_offset: 0=近月/主力, 1=远月/次月

        Returns:
            合约 code (TDX内部码), 如 'CU2606', 'IFM0'
        """
        # 股指期货: 使用主连/次主力
        if variety in ('IF', 'IH', 'IC', 'IM', 'T', 'TF', 'TL', 'TS'):
            suffix = "L8" if month_offset == 0 else "L9"
            return f"{variety}{suffix}"

        # 商品期货: 动态推导近月/远月
        try:
            near_year, near_month = self._get_next_delivery_month(
                variety, self.reference_date, skip_months=month_offset,
            )
            code = self._make_futures_code(variety, near_year, near_month)

            # 验证 code 在代码表中存在
            if code in self._code_table:
                return code

            # 尝试主连
            return f"{variety}L8"
        except Exception:
            return f"{variety}M0"

    def _validate_code(self, code: str, variety: str, year: int, month: int) -> str:
        """验证合约代码在代码表中是否存在, 不存在则回退。"""
        if code in self._code_table:
            return code

        # 代码表中找不到 → 尝试主连
        main_code = f"{variety}L8"
        if main_code in self._code_table:
            self._logger.debug(f"合约 {code} 不在代码表, 回退到主连 {main_code}")
            return main_code

        # 主连也没有 → 尝试 M0
        m0_code = f"{variety}M0"
        if m0_code in self._code_table:
            return m0_code

        # 都没有 → 返回原始推导结果
        self._logger.debug(f"合约 {code} / {main_code} / {m0_code} 均不在代码表, 使用推导值")
        return code

    # ──────────────────────────────────────────────────────────────
    #  合约到期预警
    # ──────────────────────────────────────────────────────────────

    def check_expiry_warnings(self) -> List[Dict[str, Any]]:
        """检查即将到期合约。"""
        warnings: List[Dict[str, Any]] = []
        today = self.reference_date.date() if isinstance(self.reference_date, datetime) else self.reference_date

        for code, info in self._code_table.items():
            if info.delivery_year == 0 or info.delivery_month == 0:
                continue

            try:
                expiry = date(info.delivery_year, info.delivery_month, 1)
                days_to_expiry = (expiry - today).days

                if 0 <= days_to_expiry <= self.expiry_warning_days:
                    warnings.append({
                        "code": code,
                        "code_name": info.code_name,
                        "variety": info.variety,
                        "expiry": f"{info.delivery_year}-{info.delivery_month:02d}",
                        "days_to_expiry": days_to_expiry,
                        "category": "期货" if info.category == 3 else "期权",
                    })
            except Exception:
                continue

        if warnings:
            self._logger.warning(f"到期预警: {len(warnings)} 个合约即将到期")

        return warnings

    # ──────────────────────────────────────────────────────────────
    #  配置更新 & 摘要
    # ──────────────────────────────────────────────────────────────

    def generate_full_config_updates(self) -> Dict[str, Any]:
        """生成动态配置更新。"""
        commodity_updates = {}
        for key, pair in self.get_commodity_contracts().items():
            commodity_updates[key] = {
                "near_code": pair.near_code,
                "far_code": pair.far_code,
                "market_type": pair.market_type,
            }

        index_updates = {}
        for key, contract in self.get_index_futures_contracts().items():
            index_updates[key] = {
                "futures_code": contract.futures_code,
                "next_quarter_code": contract.next_quarter_code,
                "spot_code": contract.spot_code,
            }

        return {
            "commodity_contracts": commodity_updates,
            "index_futures_contracts": index_updates,
            "reference_date": self.reference_date.strftime("%Y-%m-%d"),
        }

    def get_contract_summary(self) -> Dict[str, Any]:
        """获取合约推导摘要。"""
        return {
            "version": "9.1",
            "reference_date": self.reference_date.strftime("%Y-%m-%d"),
            "rollover_day": self.rollover_day,
            "total_contracts_in_table": len(self._code_table),
            "futures_varieties": len(self._variety_codes),
            "option_underlyings": len(self._option_by_underlying),
            "code_name_to_code_mappings": len(self._code_name_to_code),
            "commodity_contracts": {
                k: {"near": v.near_code, "far": v.far_code}
                for k, v in self.get_commodity_contracts().items()
            },
            "index_futures": {
                k: {"active": v.futures_code, "next_quarter": v.next_quarter_code}
                for k, v in self.get_index_futures_contracts().items()
            },
        }

    def update(self) -> None:
        """刷新合约映射 (main.py Step 2 调用)。"""
        self.reference_date = datetime.now()
        self._logger.info(
            f"ContractManager V9.1: 合约映射刷新 | "
            f"参考日期: {self.reference_date.strftime('%Y-%m-%d')} | "
            f"合约总数: {len(self._code_table)}"
        )

    @property
    def contracts(self) -> Dict[str, ContractInfo]:
        """返回全部合约信息 (兼容 V8 main.py 的 cm.contracts 属性)"""
        return self._code_table


# 导入 Any 用于类型注解
from typing import Any
from datetime import date as date_cls
