#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
V7 ContractManager — 动态合约代码推导引擎
==========================================

V6.1 → V7 关键改进：
  1. 修复 FuturesContractPair 缺少 `near_year` 字段的 bug（V6.1 的
     check_expiry_warnings 试图访问 pair.near_year 但该字段不存在）
  2. 全面使用 market_type 字符串（'future_sh', 'option_zj' …）替代裸
     market_code 整数，与 TDXAdapter MARKET_MAP 无缝对接
  3. 所有合约代码推导纯日期驱动，零硬编码
  4. dataclass 定义整洁，字段完整
  5. 完整 docstring + 类型注解

核心职责：
  - 基于当前日期动态推导商品期货近月/远月合约代码
  - 基于当前日期动态推导股指期货当月/下季月合约代码
  - 基于当前日期动态推导期权近月/远月合约组
  - 管理合约滚动逻辑（到期自动切换）
  - 从 TDX 代码表加载完整合约信息
  - 为全系统提供统一的合约代码查询接口

依赖：
  - openpyxl（读取 TDX 代码表，可选）
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

    Attributes:
        code:           TDX 合约代码，如 ``CU2606``
        name:           合约中文名，如 ``沪铜2606``
        market_code:    TDX 市场代码整数，如 ``30``
        market_type:    V7 市场类型字符串，如 ``future_sh``
        market_name:    市场中文名，如 ``上海期货``
        category:       类别（3=期货, 12=期权）
        variety:        品种代码，如 ``CU``
        delivery_year:  交割年，如 ``2026``
        delivery_month: 交割月，如 ``6``
    """
    code: str
    name: str
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

    V7 修复：新增 ``near_year`` / ``far_year`` 字段，解决 V6.1 中
    ``check_expiry_warnings`` 访问 ``pair.near_year`` 不存在的 bug。

    Attributes:
        variety_key:  品种英文键名，如 ``copper``
        variety_code: 品种 TDX 代码，如 ``CU``
        near_code:    近月合约代码，如 ``CU2606``
        far_code:     远月合约代码，如 ``CU2609``
        market_code:  TDX 市场代码整数
        market_type:  V7 市场类型字符串，如 ``future_sh``
        near_year:    近月交割年（V7 新增）
        near_month:   近月交割月
        far_year:     远月交割年（V7 新增）
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
        key:             品种英文键名，如 ``if``
        variety_code:    品种 TDX 代码，如 ``IF``
        futures_code:    当月合约代码，如 ``IF2606``
        next_quarter_code: 下季月合约代码，如 ``IF2609``
        spot_code:       现货指数代码，如 ``000300``
        market_code:     TDX 市场代码整数
        market_type:     V7 市场类型字符串
        delivery_year:   交割年
        delivery_month:  交割月
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

    Attributes:
        underlying:     标的代码，如 ``IO`` 或 ``510300``
        market_code:    TDX 市场代码整数
        market_type:    V7 市场类型字符串
        delivery_year:  交割年
        delivery_month: 交割月
        contracts:      命中的 ContractInfo 列表
        call_codes:     看涨合约代码列表
        put_codes:      看跌合约代码列表
    """
    underlying: str
    market_code: int
    market_type: str
    delivery_year: int
    delivery_month: int
    contracts: List[ContractInfo] = field(default_factory=list)
    call_codes: List[str] = field(default_factory=list)
    put_codes: List[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════
#  品种交割月份规则
# ═══════════════════════════════════════════════════════════════════════

#: 商品期货交割月份规则（关键业务知识）
#: key = 品种 TDX 代码，value = 允许交割的月份列表
COMMODITY_DELIVERY_MONTHS: Dict[str, List[int]] = {
    # ── 上海期货 (market_type='future_sh') ──────────────────────
    'CU': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],   # 沪铜：每月
    'AL': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],   # 沪铝：每月
    'ZN': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],   # 沪锌：每月
    'PB': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],   # 沪铅：每月
    'NI': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],   # 沪镍：每月
    'SN': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],   # 沪锡：每月
    'AU': [2, 4, 6, 8, 10, 12],                       # 黄金：双月
    'AG': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],   # 白银：每月
    'RB': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],   # 螺纹钢：每月
    'HC': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],   # 热卷：每月
    'SS': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],   # 不锈钢：每月
    'BU': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],   # 沥青：每月
    'RU': [1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],      # 橡胶：1月及3-12月
    'NR': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],   # 20号胶：每月
    'FU': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],   # 燃油：每月
    'LU': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],   # 低硫燃油：每月
    'SP': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],   # 纸浆：每月
    'BC': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],   # 国际铜：每月
    'AO': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],   # 氧化铝：每月
    'BR': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],   # 丁二烯橡胶：每月
    'EC': [2, 4, 6, 8, 10, 12],                       # 集运指数(欧线)：双月
    'AD': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],   # 铝合金：每月
    'OP': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],   # 石油沥青：每月
    'SC': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],   # 原油：每月

    # ── 大连商品 (market_type='future_dl') ──────────────────────
    'M':  [1, 3, 5, 7, 8, 9, 11, 12],                 # 豆粕
    'Y':  [1, 3, 5, 7, 8, 9, 11, 12],                 # 豆油
    'A':  [1, 3, 5, 7, 9, 11],                         # 豆一：奇数月
    'B':  [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],    # 豆二：每月
    'C':  [1, 3, 5, 7, 9, 11],                         # 玉米：奇数月
    'CS': [1, 3, 5, 7, 9, 11],                         # 淀粉：奇数月
    'I':  [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],    # 铁矿：每月
    'J':  [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],    # 焦炭：每月
    'JM': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],    # 焦煤：每月
    'L':  [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],    # 塑料：每月
    'PP': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],    # 聚丙烯：每月
    'V':  [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],    # PVC：每月
    'EG': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],    # 乙二醇：每月
    'EB': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],    # 苯乙烯：每月
    'PG': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],    # LPG：每月
    'P':  [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],    # 棕榈油：每月
    'FB': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],    # 纤维板：每月
    'BB': [1, 3, 5, 7, 9, 11],                         # 胶合板：奇数月
    'JD': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],    # 鸡蛋：每月
    'RR': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],    # 粳米：每月
    'LH': [1, 3, 5, 7, 9, 11],                         # 生猪：奇数月
    'BZ': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],    # 苯乙烯：每月
    'LG': [1, 3, 5, 7, 9, 11],                         # 铁合金：奇数月

    # ── 郑州商品 (market_type='future_zj') ──────────────────────
    # 注：TDX代码表中郑州市场代码为28，V7 market_type = 'future_zj'
    'CF': [1, 3, 5, 7, 9, 11],                         # 棉花：奇数月
    'SR': [1, 3, 5, 7, 9, 11],                         # 白糖：奇数月
    'TA': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],    # PTA：每月
    'MA': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],    # 甲醇：每月
    'FG': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],    # 玻璃：每月
    'SA': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],    # 纯碱：每月
    'AP': [1, 3, 5, 10, 11, 12],                       # 苹果：1,3,5,10,11,12
    'CJ': [1, 3, 5, 7, 9, 11],                         # 红枣：奇数月
    'OI': [1, 3, 5, 7, 9, 11],                         # 菜油：奇数月
    'RM': [1, 3, 5, 7, 8, 9, 11],                      # 菜粕：1,3,5,7,8,9,11
    'ZC': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],    # 动力煤：每月
    'SF': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],    # 硅铁：每月
    'SM': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],    # 锰硅：每月
    'PF': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],    # 短纤：每月
    'SH': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],    # 烧碱：每月
    'UR': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],    # 尿素：每月
    'PK': [1, 3, 4, 5, 10, 11, 12],                    # 花生：1,3,4,5,10,11,12
    'CY': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],    # 棉纱：每月
    'WH': [1, 3, 5, 7, 9, 11],                         # 强麦：奇数月
    'PM': [1, 3, 5, 7, 9, 11],                         # 普麦：奇数月
    'RI': [1, 3, 5, 7, 9, 11],                         # 早籼稻：奇数月
    'JR': [1, 3, 5, 7, 9, 11],                         # 粳稻：奇数月
    'RS': [7, 8, 9, 11],                                # 菜籽：7,8,9,11
    'PR': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],    # 瓶片：每月
    'PX': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],    # 对二甲苯：每月
    'PL': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],    # 油脂：每月

    # ── 广州期货 (market_type='future_gz') ──────────────────────
    'LC': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],    # 碳酸锂：每月
    'SI': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],    # 工业硅：每月
    'PS': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],    # 碳酸锂：每月
    'PD': [6, 8, 10, 12],                               # 铂：双月(6月起)
    'PT': [6, 8, 10, 12],                               # 钯：双月(6月起)
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
    'AO': 30, 'BR': 30, 'EC': 30, 'AD': 30, 'OP': 30, 'SC': 30,
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

#: 品种 → V7 market_type 字符串（与 TDXAdapter MARKET_MAP 对齐）
VARIETY_MARKET_TYPE: Dict[str, str] = {
    # 上海期货
    'CU': 'future_sh', 'AL': 'future_sh', 'ZN': 'future_sh',
    'PB': 'future_sh', 'NI': 'future_sh', 'SN': 'future_sh',
    'AU': 'future_sh', 'AG': 'future_sh', 'RB': 'future_sh',
    'HC': 'future_sh', 'SS': 'future_sh', 'BU': 'future_sh',
    'RU': 'future_sh', 'NR': 'future_sh', 'FU': 'future_sh',
    'LU': 'future_sh', 'SP': 'future_sh', 'BC': 'future_sh',
    'AO': 'future_sh', 'BR': 'future_sh', 'EC': 'future_sh',
    'AD': 'future_sh', 'OP': 'future_sh', 'SC': 'future_sh',
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
    'IF': 'future_zz', 'IH': 'future_zz', 'IC': 'future_zz', 'IM': 'future_zz',
    'T': 'future_zz', 'TF': 'future_zz', 'TL': 'future_zz', 'TS': 'future_zz',
}

#: 品种 → 中文名称
VARIETY_NAMES: Dict[str, str] = {
    'CU': '沪铜', 'AL': '沪铝', 'ZN': '沪锌', 'PB': '沪铅', 'NI': '沪镍',
    'SN': '沪锡', 'AU': '黄金', 'AG': '白银', 'RB': '螺纹钢', 'HC': '热卷',
    'SS': '不锈钢', 'BU': '沥青', 'RU': '橡胶', 'NR': '20号胶', 'FU': '燃油',
    'LU': '低硫燃油', 'SP': '纸浆', 'BC': '国际铜', 'AO': '氧化铝',
    'BR': '丁二烯橡胶', 'EC': '集运指数', 'AD': '铝合金', 'OP': '石油沥青',
    'SC': '原油',
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

#: 系统监控的商品品种（英文键 → TDX品种代码）
MONITORED_COMMODITIES: Dict[str, str] = {
    'copper':    'CU',
    'aluminum':  'AL',
    'lithium':   'LC',
    'silicon':   'SI',
    'crude':     'SC',
    'rebar':     'RB',
    'gold':      'AU',
    'soybean':   'M',
}

#: 股指期货配置
INDEX_FUTURES_CONFIG: Dict[str, Dict[str, str]] = {
    'if': {
        'variety': 'IF',
        'spot_code': '000300',
        'spot_name': '沪深300',
        'market_type': 'future_zz',
    },
    'ih': {
        'variety': 'IH',
        'spot_code': '000016',
        'spot_name': '上证50',
        'market_type': 'future_zz',
    },
    'ic': {
        'variety': 'IC',
        'spot_code': '000905',
        'spot_name': '中证500',
        'market_type': 'future_zz',
    },
    'im': {
        'variety': 'IM',
        'spot_code': '000852',
        'spot_name': '中证1000',
        'market_type': 'future_zz',
    },
}

#: 期权标的配置（含 market_type 字符串，与 TDXAdapter 对齐）
OPTION_UNDERLYING_CONFIG: Dict[str, Dict] = {
    'IO': {
        'spot_code': '000300',
        'market_code': 7,
        'market_type': 'option_zj',
        'name': '沪深300指数期权',
    },
    'HO': {
        'spot_code': '000016',
        'market_code': 7,
        'market_type': 'option_zj',
        'name': '上证50指数期权',
    },
    'MO': {
        'spot_code': '000852',
        'market_code': 7,
        'market_type': 'option_zj',
        'name': '中证1000指数期权',
    },
    '510300': {
        'spot_code': '510300',
        'market_code': 8,
        'market_type': 'option_sh',
        'name': '沪深300ETF期权',
    },
    '510500': {
        'spot_code': '510500',
        'market_code': 8,
        'market_type': 'option_sh',
        'name': '中证500ETF期权',
    },
    '588000': {
        'spot_code': '588000',
        'market_code': 8,
        'market_type': 'option_sh',
        'name': '科创50ETF期权',
    },
    '159915': {
        'spot_code': '159915',
        'market_code': 9,
        'market_type': 'option_sz',
        'name': '创业板ETF期权',
    },
}

#: 合约到期提醒天数（交割月前 N 天视为即将到期）
EXPIRY_WARNING_DAYS: int = 5

#: 合约滚动判断日（每月第 15 日后视为需切换下月合约）
ROLLOVER_DAY: int = 15


# ═══════════════════════════════════════════════════════════════════════
#  ContractManager
# ═══════════════════════════════════════════════════════════════════════

class ContractManager:
    """V7 合约管理器：基于日期动态推导合约代码。

    核心设计原则：
    - **零硬编码**：所有合约代码由日期 + 品种规则动态生成
    - **自动滚动**：合约到期后自动切换到下月
    - **精确匹配**：不同品种交割月份规则精确编码
    - **容错回退**：代码表中无匹配时按规则推算
    - **market_type 驱动**：V7 新增，与 TDXAdapter MARKET_MAP 无缝衔接

    公共接口：
    - :meth:`get_commodity_contracts`   — 获取商品期货近月/远月合约对
    - :meth:`get_index_futures_contracts` — 获取股指期货当月/下季月合约
    - :meth:`get_option_contracts`       — 获取期权近月合约组
    - :meth:`get_option_near_month`      — 获取期权近月交割月份
    - :meth:`generate_full_config_updates` — 生成动态配置更新
    - :meth:`check_expiry_warnings`      — 检查即将到期合约
    - :meth:`get_contract_summary`       — 获取合约推导摘要
    """

    def __init__(
        self,
        code_table_path: Optional[str] = None,
        reference_date: Optional[datetime] = None,
        rollover_day: int = ROLLOVER_DAY,
        expiry_warning_days: int = EXPIRY_WARNING_DAYS,
    ) -> None:
        """初始化合约管理器。

        Args:
            code_table_path:   TDX 代码表 Excel 路径（可选）
            reference_date:    参考日期，默认今天
            rollover_day:      每月第 N 天后视为需切换下月合约
            expiry_warning_days: 到期提醒天数
        """
        self.reference_date = reference_date or datetime.now()
        self.code_table_path = code_table_path
        self.rollover_day = rollover_day
        self.expiry_warning_days = expiry_warning_days
        self._logger = logger

        # TDX 代码表数据
        self._code_table: Dict[str, ContractInfo] = {}
        self._variety_codes: Dict[str, List[ContractInfo]] = defaultdict(list)
        self._option_by_underlying: Dict[str, List[ContractInfo]] = defaultdict(list)

        # 加载代码表（如果路径有效）
        if code_table_path and os.path.exists(code_table_path):
            self._load_code_table(code_table_path)

        self._logger.info(
            f"ContractManager V7 初始化完成 | "
            f"参考日期: {self.reference_date.strftime('%Y-%m-%d')} | "
            f"已加载 {len(self._code_table)} 个合约"
        )

    # ──────────────────────────────────────────────────────────────
    #  代码表加载
    # ──────────────────────────────────────────────────────────────

    def _load_code_table(self, path: str) -> None:
        """从 Excel 加载 TDX 代码表。

        Args:
            path: xlsx 文件路径
        """
        try:
            import openpyxl

            wb = openpyxl.load_workbook(path, read_only=True)
            ws = wb.active

            for row in ws.iter_rows(min_row=2, values_only=True):
                if row[0] is None:
                    continue
                code, code_name, market_code, market_name, category = row

                variety, delivery_year, delivery_month = self._parse_contract_code(
                    str(code), str(code_name) if code_name else '',
                    int(category) if category else 0,
                )

                market_type = self._infer_market_type(
                    variety, int(market_code) if market_code else 0,
                    int(category) if category else 0,
                )

                info = ContractInfo(
                    code=str(code),
                    name=str(code_name) if code_name else str(code),
                    market_code=int(market_code) if market_code else 0,
                    market_type=market_type,
                    market_name=str(market_name) if market_name else '',
                    category=int(category) if category else 0,
                    variety=variety,
                    delivery_year=delivery_year,
                    delivery_month=delivery_month,
                )

                self._code_table[str(code)] = info

                if category == 3 and delivery_month > 0:       # 期货（排除主连/指数）
                    self._variety_codes[variety].append(info)
                elif category == 12:                            # 期权
                    self._option_by_underlying[variety].append(info)

            wb.close()
            self._logger.info(
                f"代码表加载完成 | "
                f"期货品种: {len(self._variety_codes)} | "
                f"期权标的: {len(self._option_by_underlying)}"
            )

        except Exception as exc:
            self._logger.error(f"代码表加载失败: {exc}")

    def _infer_market_type(
        self, variety: str, market_code: int, category: int,
    ) -> str:
        """根据品种代码 / market_code / category 推断 V7 market_type。

        优先查表，查不到则按 market_code 回退。

        Args:
            variety:      品种代码
            market_code:  TDX 市场代码整数
            category:     类别 (3=期货, 12=期权)

        Returns:
            market_type 字符串
        """
        # 期货品种直接查表
        if category == 3:
            mt = VARIETY_MARKET_TYPE.get(variety)
            if mt:
                return mt

        # 期权：按 market_code 判断
        if category == 12:
            if variety in ('IO', 'HO', 'MO'):
                return 'option_zj'
            if market_code == 8:
                return 'option_sh'
            if market_code == 9:
                return 'option_sz'
            # 商品期权归属对应交易所
            mt = VARIETY_MARKET_TYPE.get(variety, '')
            if mt.startswith('future_'):
                return mt.replace('future_', 'option_')
            return 'option_sh'

        # 回退：按 market_code
        market_code_to_type = {
            30: 'future_sh', 29: 'future_dl', 28: 'future_zj',
            66: 'future_gz', 47: 'future_zz',
            7: 'option_zj', 8: 'option_sh', 9: 'option_sz',
        }
        return market_code_to_type.get(market_code, 'future_sh')

    def _parse_contract_code(
        self, code: str, name: str, category: int,
    ) -> Tuple[str, int, int]:
        """解析合约代码，提取品种 / 交割年 / 交割月。

        Returns:
            ``(variety, delivery_year, delivery_month)``
            主连/指数等特殊合约返回 ``(variety, 0, 0)``
        """
        code = code.upper().strip()

        if category == 3:  # 期货
            # 主连: CUL8, ALL8 …
            if code.endswith('L8') or code.endswith('L9'):
                return code[:-2], 0, 0

            # 普通合约: CU2606, M2603 …
            match = re.match(r'^([A-Z]+)(\d{3,4})$', code)
            if match:
                variety = match.group(1)
                num = match.group(2)
                if len(num) == 4:  # YYMM
                    return variety, 2000 + int(num[:2]), int(num[2:])
                elif len(num) == 3:  # YMM (罕见)
                    return variety, 2000 + int(num[0]) + 20, int(num[-2:])

            # 兜底：从名称提取
            if name:
                match = re.search(r'(\d{4})', name)
                if match:
                    num = match.group(1)
                    return code.rstrip('0123456789'), 2000 + int(num[:2]), int(num[2:4])

            return code, 0, 0

        elif category == 12:  # 期权
            # 中金所期权: IO2602-C-4000
            if name:
                match = re.match(r'^([A-Z]+)(\d{4})', name)
                if match:
                    return match.group(1), 2000 + int(match.group(2)[:2]), int(match.group(2)[2:4])

            # ETF期权: 510300C3A02800
            if name:
                match = re.search(r'^(\d{6})', name)
                if match:
                    return match.group(1), 0, 0

            return code, 0, 0

        return code, 0, 0

    # ──────────────────────────────────────────────────────────────
    #  核心：动态合约推导
    # ──────────────────────────────────────────────────────────────

    def _get_next_delivery_month(
        self, variety: str, ref_date: datetime, skip_months: int = 0,
    ) -> Tuple[int, int]:
        """获取品种从 ref_date 起第 skip_months+1 个交割月。

        算法：
        1. 如果当前日在 rollover_day 之前，当前月仍可被视为有效交割月
        2. 否则从下一个月开始搜索
        3. 逐月递增，最多搜索 36 个月

        Args:
            variety:      品种代码，如 ``CU``
            ref_date:     参考日期
            skip_months:  跳过月数（0=最近，1=次近，…）

        Returns:
            ``(delivery_year, delivery_month)``
        """
        delivery_months = COMMODITY_DELIVERY_MONTHS.get(
            variety, list(range(1, 13)),
        )

        current_year = ref_date.year
        current_month = ref_date.month
        current_day = ref_date.day

        # 当月在 rollover_day 之前且当月有交割 → 当月可作为候选
        is_rollover = current_day >= self.rollover_day

        found_count = 0
        search_year = current_year
        search_month = current_month

        if not is_rollover and current_month in delivery_months:
            if skip_months == 0:
                return search_year, current_month
            found_count += 1

        # 逐月搜索
        for _ in range(36):
            search_month += 1
            if search_month > 12:
                search_month = 1
                search_year += 1

            if search_month in delivery_months:
                if found_count >= skip_months:
                    return search_year, search_month
                found_count += 1

        # 兜底
        return current_year + 1, 1

    @staticmethod
    def _make_futures_code(variety: str, year: int, month: int) -> str:
        """生成期货合约代码。

        >>> ContractManager._make_futures_code('CU', 2026, 6)
        'CU2606'
        """
        yy = year % 100
        return f"{variety}{yy:02d}{month:02d}"

    @staticmethod
    def _make_main_contract_code(variety: str) -> str:
        """生成主力合约代码（TDX XL8 格式）。

        >>> ContractManager._make_main_contract_code('CU')
        'CUL8'
        """
        return f"{variety}L8"

    # ──────────────────────────────────────────────────────────────
    #  公共接口
    # ──────────────────────────────────────────────────────────────

    def get_commodity_contracts(
        self, commodity_key: Optional[str] = None,
    ) -> Dict[str, FuturesContractPair]:
        """获取商品期货近月/远月合约对（基于当前日期动态推导）。

        Args:
            commodity_key: 指定品种键名（如 ``'copper'``），``None`` = 全部

        Returns:
            ``{key: FuturesContractPair}``
        """
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

                # 尝试从代码表验证
                near_code = self._validate_code(near_code, variety, near_year, near_month)
                far_code = self._validate_code(far_code, variety, far_year, far_month)

                results[key] = FuturesContractPair(
                    variety_key=key,
                    variety_code=variety,
                    near_code=near_code,
                    far_code=far_code,
                    market_code=market_code,
                    market_type=market_type,
                    near_year=near_year,
                    near_month=near_month,
                    far_year=far_year,
                    far_month=far_month,
                )

                self._logger.debug(
                    f"  {key:10s} ({variety}): "
                    f"近月={near_code}({near_year}-{near_month:02d}) "
                    f"远月={far_code}({far_year}-{far_month:02d}) "
                    f"market_type={market_type}"
                )

            except Exception as exc:
                self._logger.warning(f"  {key} ({variety}) 合约推导失败: {exc}")
                continue

        self._logger.info(f"动态推导商品期货合约: {len(results)} 个品种")
        return results

    def get_index_futures_contracts(
        self,
    ) -> Dict[str, IndexFuturesContract]:
        """获取股指期货当月/下季月合约（基于当前日期动态推导）。

        股指期货规则：
        - 合约月份：当月、下月、随后两个季月 (3/6/9/12)
        - 主力合约通常是当月合约，临近交割切换到下月
        - 期限结构分析用当月 vs 下季月

        Returns:
            ``{key: IndexFuturesContract}``
        """
        results: Dict[str, IndexFuturesContract] = {}

        current_year = self.reference_date.year
        current_month = self.reference_date.month
        current_day = self.reference_date.day

        for key, config in INDEX_FUTURES_CONFIG.items():
            variety = config['variety']
            spot_code = config['spot_code']
            market_type = config.get('market_type', 'future_zz')

            # 1. 确定当月合约
            if current_day < self.rollover_day:
                active_month = current_month
                active_year = current_year
            else:
                active_month = current_month + 1
                active_year = current_year
                if active_month > 12:
                    active_month = 1
                    active_year += 1

            # 2. 确定下季月
            next_quarter_month: Optional[int] = None
            next_quarter_year = active_year

            for qm in INDEX_FUTURES_QUARTER_MONTHS:
                if qm > active_month:
                    next_quarter_month = qm
                    break

            if next_quarter_month is None:
                next_quarter_month = INDEX_FUTURES_QUARTER_MONTHS[0]
                next_quarter_year += 1

            # 3. 生成合约代码
            active_code = self._make_futures_code(variety, active_year, active_month)
            next_quarter_code = self._make_futures_code(
                variety, next_quarter_year, next_quarter_month,
            )

            results[key] = IndexFuturesContract(
                key=key,
                variety_code=variety,
                futures_code=active_code,
                next_quarter_code=next_quarter_code,
                spot_code=spot_code,
                market_code=47,   # 中金所
                market_type=market_type,
                delivery_year=active_year,
                delivery_month=active_month,
            )

            self._logger.debug(
                f"  {key}: 当月={active_code} 现货={spot_code} "
                f"下季月={next_quarter_code} market_type={market_type}"
            )

        self._logger.info(f"动态推导股指期货合约: {len(results)} 个品种")
        return results

    def get_index_futures_main_code(self, key: str) -> str:
        """获取股指期货主力合约代码（TDX 主连格式，用于基差分析）。

        Args:
            key: 品种键名，如 ``'if'``

        Returns:
            主力合约代码，如 ``IFL8``
        """
        config = INDEX_FUTURES_CONFIG.get(key)
        if not config:
            return f"{key.upper()}L8"
        return self._make_main_contract_code(config['variety'])

    def get_option_near_month(self, underlying: str) -> Tuple[int, int]:
        """获取期权近月交割月份。

        期权到期日规则：
        - 中金所股指期权：合约月份第三个周五
        - ETF 期权：合约月份第四个周三

        简化处理：每月 15 号后视为需看下月。

        Args:
            underlying: 标的代码，如 ``IO``、``510300``

        Returns:
            ``(delivery_year, delivery_month)``
        """
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
        """获取期权近月合约组（基于代码表筛选）。

        Args:
            underlying:  标的代码，如 ``IO``、``510300``
            market_code: TDX 市场代码（可选，从配置推断）
            market_type: V7 市场类型字符串（可选，从配置推断）

        Returns:
            :class:`OptionContractGroup` 或 ``None``
        """
        # 从配置推断 market_code / market_type
        config = OPTION_UNDERLYING_CONFIG.get(underlying, {})
        if market_code is None:
            market_code = config.get('market_code', 7)
        if market_type is None:
            market_type = config.get('market_type', 'option_zj')

        near_year, near_month = self.get_option_near_month(underlying)

        # 从代码表中筛选近月合约
        matching: List[ContractInfo] = []
        if underlying in self._option_by_underlying:
            for info in self._option_by_underlying[underlying]:
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

        # 分类看涨/看跌
        call_codes: List[str] = []
        put_codes: List[str] = []
        for info in matching:
            name = info.name
            if '-C-' in name or name.endswith('C') or 'C3' in name:
                call_codes.append(info.code)
            elif '-P-' in name or name.endswith('P') or 'P3' in name:
                put_codes.append(info.code)
            else:
                # 无法直接判断，归入看涨
                call_codes.append(info.code)

        return OptionContractGroup(
            underlying=underlying,
            market_code=market_code,
            market_type=market_type,
            delivery_year=near_year,
            delivery_month=near_month,
            contracts=matching,
            call_codes=call_codes,
            put_codes=put_codes,
        )

    # ──────────────────────────────────────────────────────────────
    #  动态配置生成
    # ──────────────────────────────────────────────────────────────

    def generate_commodity_contracts_config(self) -> Dict:
        """生成商品期货合约配置（替代 YAML 中硬编码的 commodity_contracts）。

        Returns:
            ``{key: {near_code, far_code, market_code, market_type, ...}}``
        """
        pairs = self.get_commodity_contracts()
        config: Dict = {}
        for key, pair in pairs.items():
            config[key] = {
                'near_code': pair.near_code,
                'far_code': pair.far_code,
                'market_code': pair.market_code,
                'market_type': pair.market_type,
                'near_year': pair.near_year,
                'near_month': pair.near_month,
                'far_year': pair.far_year,
                'far_month': pair.far_month,
            }
        return config

    def generate_index_futures_config(self) -> Dict:
        """生成股指期货合约配置（替代 YAML 中硬编码的 index_futures_contracts）。

        Returns:
            ``{key: {futures_code, spot_code, market_code, market_type, ...}}``
        """
        contracts = self.get_index_futures_contracts()
        config: Dict = {}
        for key, contract in contracts.items():
            main_code = self.get_index_futures_main_code(key)
            config[key] = {
                'main_code': main_code,
                'futures_code': contract.futures_code,
                'next_quarter_code': contract.next_quarter_code,
                'spot_code': contract.spot_code,
                'market_code': contract.market_code,
                'market_type': contract.market_type,
                'delivery_year': contract.delivery_year,
                'delivery_month': contract.delivery_month,
            }
        return config

    def generate_commodity_strategy_map(self) -> Dict:
        """生成商品策略映射（动态合约代码版本）。

        Returns:
            ``{main_code: {name, market_code, market_type, near_contract, far_contract}}``
        """
        pairs = self.get_commodity_contracts()
        strategy_map: Dict = {}

        for key, pair in pairs.items():
            main_code = self._make_main_contract_code(pair.variety_code)
            strategy_map[main_code] = {
                'name': VARIETY_NAMES.get(pair.variety_code, pair.variety_code),
                'variety_key': pair.variety_key,
                'market_code': pair.market_code,
                'market_type': pair.market_type,
                'near_contract': pair.near_code,
                'far_contract': pair.far_code,
                'near_year': pair.near_year,
                'near_month': pair.near_month,
                'far_year': pair.far_year,
                'far_month': pair.far_month,
            }

        return strategy_map

    def generate_full_config_updates(self) -> Dict:
        """生成完整的配置更新（用于热更新 YAML 配置）。

        Returns:
            包含所有动态推导结果的字典
        """
        return {
            'commodity_contracts': self.generate_commodity_contracts_config(),
            'index_futures_contracts': self.generate_index_futures_config(),
            'commodity_strategy_map_dynamic': self.generate_commodity_strategy_map(),
            'reference_date': self.reference_date.strftime('%Y-%m-%d'),
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }

    # ──────────────────────────────────────────────────────────────
    #  辅助方法
    # ──────────────────────────────────────────────────────────────

    def _validate_code(
        self, generated_code: str, variety: str, year: int, month: int,
    ) -> str:
        """验证生成的合约代码是否在代码表中存在；不存在则回退。

        Args:
            generated_code: 生成的合约代码
            variety:        品种代码
            year:           交割年
            month:          交割月

        Returns:
            验证后的合约代码
        """
        if not self._variety_codes:
            return generated_code

        for info in self._variety_codes.get(variety, []):
            if info.delivery_year == year and info.delivery_month == month:
                return info.code

        self._logger.debug(
            f"合约 {generated_code} 未在代码表中找到，使用生成代码"
        )
        return generated_code

    def get_contract_summary(self) -> pd.DataFrame:
        """获取合约推导结果摘要（用于报告 / 调试）。

        Returns:
            DataFrame，包含类别 / 品种 / 合约代码 / 市场信息等列
        """
        rows: List[Dict] = []

        # 商品期货
        pairs = self.get_commodity_contracts()
        for key, pair in pairs.items():
            rows.append({
                '类别': '商品期货',
                '品种': key,
                '品种代码': pair.variety_code,
                '近月合约': pair.near_code,
                '远月合约': pair.far_code,
                '市场代码': pair.market_code,
                '市场类型': pair.market_type,
                '近月交割年月': f"{pair.near_year}-{pair.near_month:02d}",
                '远月交割年月': f"{pair.far_year}-{pair.far_month:02d}",
            })

        # 股指期货
        idx_contracts = self.get_index_futures_contracts()
        for key, contract in idx_contracts.items():
            rows.append({
                '类别': '股指期货',
                '品种': key,
                '品种代码': contract.variety_code,
                '近月合约': contract.futures_code,
                '远月合约': contract.next_quarter_code,
                '市场代码': contract.market_code,
                '市场类型': contract.market_type,
                '近月交割年月': f"{contract.delivery_year}-{contract.delivery_month:02d}",
                '远月交割年月': '-',
            })

        return pd.DataFrame(rows)

    def check_expiry_warnings(self) -> List[Dict]:
        """检查即将到期的合约。

        V7 修复：使用 ``pair.near_year`` 字段计算到期日，解决 V6.1
        中 ``hasattr(pair, 'near_year')`` 回退导致的年份错误。

        Returns:
            ``[{variety_key, variety_code, contract, days_to_expiry, warning}]``
        """
        warnings: List[Dict] = []

        pairs = self.get_commodity_contracts()
        for key, pair in pairs.items():
            # V7: 直接使用 pair.near_year（V6.1 此字段缺失导致 bug）
            expiry_date = datetime(pair.near_year, pair.near_month, 15)
            days_to_expiry = (expiry_date - self.reference_date).days

            if 0 <= days_to_expiry <= self.expiry_warning_days:
                warnings.append({
                    'variety_key': key,
                    'variety_code': pair.variety_code,
                    'contract': pair.near_code,
                    'market_type': pair.market_type,
                    'days_to_expiry': days_to_expiry,
                    'warning': (
                        f"{pair.near_code} 将在 {days_to_expiry} 天后到期 "
                        f"(market_type={pair.market_type})"
                    ),
                })

        return warnings

    def get_variety_info(self, variety: str) -> Optional[Dict]:
        """获取品种的综合信息（便捷查询）。

        Args:
            variety: 品种代码，如 ``CU``

        Returns:
            包含 name / market_code / market_type / delivery_months 的字典，
            或 ``None``
        """
        if variety not in COMMODITY_DELIVERY_MONTHS:
            return None

        return {
            'variety': variety,
            'name': VARIETY_NAMES.get(variety, variety),
            'market_code': VARIETY_MARKET_CODE.get(variety, 0),
            'market_type': VARIETY_MARKET_TYPE.get(variety, 'unknown'),
            'delivery_months': COMMODITY_DELIVERY_MONTHS[variety],
        }


# ═══════════════════════════════════════════════════════════════════════
#  便捷工厂函数
# ═══════════════════════════════════════════════════════════════════════

def create_contract_manager(
    code_table_path: str = './data/tdx_code_table.xlsx',
    reference_date: Optional[datetime] = None,
    rollover_day: int = ROLLOVER_DAY,
    expiry_warning_days: int = EXPIRY_WARNING_DAYS,
) -> ContractManager:
    """创建 ContractManager 实例（便捷函数）。

    Args:
        code_table_path:    TDX 代码表路径
        reference_date:     参考日期
        rollover_day:       滚动切换日
        expiry_warning_days: 到期提醒天数

    Returns:
        :class:`ContractManager` 实例
    """
    return ContractManager(
        code_table_path=code_table_path,
        reference_date=reference_date,
        rollover_day=rollover_day,
        expiry_warning_days=expiry_warning_days,
    )


# ═══════════════════════════════════════════════════════════════════════
#  测试入口
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
    )

    # 查找代码表
    code_table: Optional[str] = None
    search_paths = [
        './tdx基金期货期权代码表.xlsx',
        './data/tdx_code_table.xlsx',
        './config/tdx基金期货期权代码表.xlsx',
        '../upload/tdx基金期货期权代码表.xlsx',
    ]
    for p in search_paths:
        if os.path.exists(p):
            code_table = p
            break

    print("=" * 80)
    print("ContractManager V7 动态合约推导测试")
    print("=" * 80)

    mgr = ContractManager(
        code_table_path=code_table,
        reference_date=datetime.now(),
    )

    # 1. 商品期货合约
    print("\n1. 商品期货合约（动态推导）:")
    pairs = mgr.get_commodity_contracts()
    for key, pair in pairs.items():
        print(
            f"  {key:10s}: 近月={pair.near_code}({pair.near_year}-{pair.near_month:02d}) "
            f"远月={pair.far_code}({pair.far_year}-{pair.far_month:02d}) "
            f"market_type={pair.market_type}"
        )

    # 2. 股指期货合约
    print("\n2. 股指期货合约（动态推导）:")
    idx = mgr.get_index_futures_contracts()
    for key, contract in idx.items():
        main = mgr.get_index_futures_main_code(key)
        print(
            f"  {key:4s}: 当月={contract.futures_code} 主连={main} "
            f"下季月={contract.next_quarter_code} 现货={contract.spot_code} "
            f"market_type={contract.market_type}"
        )

    # 3. 动态配置
    print("\n3. 生成的动态配置:")
    config = mgr.generate_full_config_updates()
    for k, v in config.items():
        if isinstance(v, dict):
            print(f"  {k}:")
            for kk, vv in list(v.items())[:3]:
                print(f"    {kk}: {vv}")
            if len(v) > 3:
                print(f"    ... ({len(v)} items)")
        else:
            print(f"  {k}: {v}")

    # 4. 合约摘要
    print("\n4. 合约推导摘要:")
    summary = mgr.get_contract_summary()
    print(summary.to_string(index=False))

    # 5. 到期检查
    print("\n5. 到期预警:")
    expiry_warnings = mgr.check_expiry_warnings()
    if expiry_warnings:
        for w in expiry_warnings:
            print(f"  WARNING: {w['warning']}")
    else:
        print("  无即将到期的合约")

    # 6. 品种信息查询
    print("\n6. 品种信息查询（示例）:")
    for v in ['CU', 'AU', 'LC', 'M', 'IF']:
        info = mgr.get_variety_info(v)
        if info:
            print(
                f"  {v}: {info['name']} | market_type={info['market_type']} | "
                f"delivery_months={info['delivery_months']}"
            )

    print("\n" + "=" * 80)
    print("测试完成")
