#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
date_utils：日期工具函数
提供期权/期货交割日计算、季度月判断、交易日判断等
"""

from datetime import date, datetime, timedelta
from typing import Tuple

# ── 中国主要节假日（硬编码，覆盖 2024–2026） ────────────────────────────────
_MAJOR_HOLIDAYS: set = {
    # 2024
    date(2024, 1, 1),   # 元旦
    date(2024, 2, 9),   # 除夕
    date(2024, 2, 10),  # 春节
    date(2024, 2, 11), date(2024, 2, 12), date(2024, 2, 13),
    date(2024, 2, 14), date(2024, 2, 15), date(2024, 2, 16), date(2024, 2, 17),
    date(2024, 4, 4), date(2024, 4, 5), date(2024, 4, 6),    # 清明
    date(2024, 5, 1), date(2024, 5, 2), date(2024, 5, 3),
    date(2024, 5, 4), date(2024, 5, 5),                        # 劳动节
    date(2024, 6, 8), date(2024, 6, 9), date(2024, 6, 10),    # 端午
    date(2024, 9, 15), date(2024, 9, 16), date(2024, 9, 17),  # 中秋
    date(2024, 10, 1), date(2024, 10, 2), date(2024, 10, 3),
    date(2024, 10, 4), date(2024, 10, 5), date(2024, 10, 6),
    date(2024, 10, 7),                                         # 国庆
    # 2025
    date(2025, 1, 1),                                          # 元旦
    date(2025, 1, 28), date(2025, 1, 29), date(2025, 1, 30),
    date(2025, 1, 31), date(2025, 2, 1), date(2025, 2, 2),
    date(2025, 2, 3), date(2025, 2, 4),                        # 春节
    date(2025, 4, 4), date(2025, 4, 5), date(2025, 4, 6),     # 清明
    date(2025, 5, 1), date(2025, 5, 2), date(2025, 5, 3),
    date(2025, 5, 4), date(2025, 5, 5),                        # 劳动节
    date(2025, 5, 31), date(2025, 6, 1), date(2025, 6, 2),    # 端午
    date(2025, 10, 1), date(2025, 10, 2), date(2025, 10, 3),
    date(2025, 10, 4), date(2025, 10, 5), date(2025, 10, 6),
    date(2025, 10, 7), date(2025, 10, 8),                      # 国庆+中秋
    # 2026
    date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 3),     # 元旦
    date(2026, 2, 16), date(2026, 2, 17), date(2026, 2, 18),
    date(2026, 2, 19), date(2026, 2, 20), date(2026, 2, 21),
    date(2026, 2, 22),                                         # 春节
    date(2026, 4, 4), date(2026, 4, 5), date(2026, 4, 6),     # 清明
    date(2026, 5, 1), date(2026, 5, 2), date(2026, 5, 3),
    date(2026, 5, 4), date(2026, 5, 5),                        # 劳动节
    date(2026, 6, 19), date(2026, 6, 20), date(2026, 6, 21),  # 端午
    date(2026, 9, 25), date(2026, 9, 26), date(2026, 9, 27),  # 中秋
    date(2026, 10, 1), date(2026, 10, 2), date(2026, 10, 3),
    date(2026, 10, 4), date(2026, 10, 5), date(2026, 10, 6),
    date(2026, 10, 7),                                         # 国庆
}

_QUARTER_MONTHS = (3, 6, 9, 12)


def get_third_friday(year: int, month: int) -> date:
    """
    计算给定年月的第三个星期五（期权/期货交割日）

    Parameters
    ----------
    year : int
        年份
    month : int
        月份（1-12）

    Returns
    -------
    date
        该月第三个星期五的日期
    """
    first_day = date(year, month, 1)
    # 星期一=0 … 星期日=6 → 星期五=4
    first_friday_offset = (4 - first_day.weekday()) % 7
    first_friday = first_day + timedelta(days=first_friday_offset)
    third_friday = first_friday + timedelta(days=14)
    return third_friday


def get_next_quarter_month(current_month: int) -> int:
    """
    根据当前月份，返回下一个季度月（3/6/9/12）

    Parameters
    ----------
    current_month : int
        当前月份（1-12）

    Returns
    -------
    int
        下一个季度月
    """
    for qm in _QUARTER_MONTHS:
        if qm > current_month:
            return qm
    # 跨年 → 回到第一个季度月
    return _QUARTER_MONTHS[0]


def is_trading_day(target_date: date) -> bool:
    """
    判断给定日期是否为交易日（简单版：排除周末和中国主要节假日）

    Parameters
    ----------
    target_date : date
        待判断的日期

    Returns
    -------
    bool
        True 表示交易日
    """
    # 周末排除
    if target_date.weekday() >= 5:
        return False
    # 节假日排除
    if target_date in _MAJOR_HOLIDAYS:
        return False
    return True


def get_near_month(reference_date: date,
                   delivery_months: Tuple[int, ...] = _QUARTER_MONTHS) -> Tuple[int, int]:
    """
    获取距离参考日最近（含当月）的交割月

    Parameters
    ----------
    reference_date : date
        参考日期
    delivery_months : tuple of int
        品种的交割月列表，默认为季度月

    Returns
    -------
    tuple[int, int]
        (年份, 月份)
    """
    year = reference_date.year
    month = reference_date.month
    for dm in sorted(delivery_months):
        if dm >= month:
            # 如果当月交割日已过，则取下一个
            expiry = get_third_friday(year, dm)
            if reference_date <= expiry:
                return year, dm
    # 跨年
    return year + 1, sorted(delivery_months)[0]
