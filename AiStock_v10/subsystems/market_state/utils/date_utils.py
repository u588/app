#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AiStock V10 — 交易日历与日期工具 (DateUtils)

V10: 从 V9 直接移植, 无配置依赖。

提供中国市场交易日判断、期权交割月推导、股指期货季月推导等功能。

核心方法:
  get_trading_date(offset=0)        — 获取第N个前交易日 (跳过周末)
  is_trading_day(date)              — 判断是否为交易日
  get_near_month_delivery(date)     — 期权近月交割月
  get_next_quarter_month(date)      — 股指期货下个季月
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import List, Optional


# ═══════════════════════════════════════════════════════════════════════════════
# 2026年中国A股市场休市日 (根据国务院公告)
# ═══════════════════════════════════════════════════════════════════════════════

cn_holidays_2026: List[date] = [
    # ─── 元旦 ──────────────────────────────────────────────
    date(2026, 1, 1),
    date(2026, 1, 2),
    date(2026, 1, 3),
    date(2026, 1, 4),

    # ─── 春节 ──────────────────────────────────────────────
    date(2026, 2, 16),
    date(2026, 2, 17),
    date(2026, 2, 18),
    date(2026, 2, 19),
    date(2026, 2, 20),
    date(2026, 2, 21),
    date(2026, 2, 22),

    # ─── 清明节 ────────────────────────────────────────────
    date(2026, 4, 4),
    date(2026, 4, 5),
    date(2026, 4, 6),

    # ─── 劳动节 ────────────────────────────────────────────
    date(2026, 5, 1),
    date(2026, 5, 2),
    date(2026, 5, 3),
    date(2026, 5, 4),
    date(2026, 5, 5),

    # ─── 端午节 ────────────────────────────────────────────
    date(2026, 6, 19),
    date(2026, 6, 20),
    date(2026, 6, 21),

    # ─── 中秋节 ────────────────────────────────────────────
    date(2026, 9, 25),
    date(2026, 9, 26),
    date(2026, 9, 27),

    # ─── 国庆节 ────────────────────────────────────────────
    date(2026, 10, 1),
    date(2026, 10, 2),
    date(2026, 10, 3),
    date(2026, 10, 4),
    date(2026, 10, 5),
    date(2026, 10, 6),
    date(2026, 10, 7),
]

_CN_HOLIDAYS_BY_YEAR: dict[int, set[date]] = {
    2026: set(cn_holidays_2026),
}

_QUARTER_MONTHS: tuple[int, ...] = (3, 6, 9, 12)


class DateUtils:
    """日期工具类 — 交易日判断与期货/期权交割月推导

    所有方法均为静态方法, 无需实例化即可使用。

    使用方式:
        >>> DateUtils.is_trading_day(date(2026, 3, 16))
        True
        >>> DateUtils.get_trading_date(offset=0)
        datetime.date(2026, 3, 16)
        >>> DateUtils.get_near_month_delivery(date(2026, 3, 16))
        3
        >>> DateUtils.get_next_quarter_month(date(2026, 3, 16))
        6
    """

    @staticmethod
    def is_trading_day(d: date) -> bool:
        """判断指定日期是否为交易日

        简易判断逻辑:
          1. 周六和周日 → 非交易日
          2. 在中国A股休市假期列表中 → 非交易日
          3. 其余 → 交易日
        """
        if d.weekday() >= 5:
            return False
        holidays = _CN_HOLIDAYS_BY_YEAR.get(d.year)
        if holidays and d in holidays:
            return False
        return True

    @staticmethod
    def get_trading_date(offset: int = 0) -> date:
        """获取第N个前交易日

        Args:
            offset: 偏移量
                     0 = 最近一个交易日
                     1 = 前1个交易日
                     2 = 前2个交易日
        """
        current = date.today()
        found = 0

        while True:
            if DateUtils.is_trading_day(current):
                if found == offset:
                    return current
                found += 1
            current -= timedelta(days=1)
            if current.year < 2020:
                raise ValueError(f"无法找到偏移 {offset} 的交易日, 搜索已回溯至 {current}")

    @staticmethod
    def get_near_month_delivery(
        d: date,
        rollover_day: int = 15,
    ) -> int:
        """获取期权近月交割月

        Args:
            d:           参考日期
            rollover_day: 展仓日 (默认15日)

        Returns:
            交割月份 (1-12)
        """
        if d.day < rollover_day:
            return d.month
        else:
            if d.month == 12:
                return 1
            return d.month + 1

    @staticmethod
    def get_next_quarter_month(d: date) -> int:
        """获取股指期货下一个季月

        Args:
            d: 参考日期

        Returns:
            下一个季月 (3/6/9/12)
        """
        current_month = d.month
        for qm in _QUARTER_MONTHS:
            if qm > current_month:
                return qm
        return _QUARTER_MONTHS[0]

    @staticmethod
    def get_far_month_delivery(
        d: date,
        rollover_day: int = 15,
    ) -> int:
        """获取期权远月交割月

        远月 = 近月之后的第二个自然月。
        """
        near = DateUtils.get_near_month_delivery(d, rollover_day)
        far = near + 2
        if far > 12:
            far -= 12
        return far

    @staticmethod
    def get_index_futures_contracts(d: date) -> dict[str, int]:
        """获取股指期货当前4个合约月份

        当月、下月和随后的两个季月。
        """
        current_month = d.month
        next_month = current_month + 1 if current_month < 12 else 1

        quarter_months: list[int] = []
        check_month = next_month
        for _ in range(12):
            if check_month in _QUARTER_MONTHS:
                quarter_months.append(check_month)
                if len(quarter_months) == 2:
                    break
            check_month = check_month + 1 if check_month < 12 else 1

        if len(quarter_months) < 2:
            quarter_months.append(_QUARTER_MONTHS[0])

        return {
            "current": current_month,
            "next": next_month,
            "quarter_1": quarter_months[0],
            "quarter_2": quarter_months[1],
        }

    @staticmethod
    def trading_days_between(
        start: date,
        end: date,
    ) -> int:
        """计算两个日期之间的交易日数"""
        if start >= end:
            return 0

        count = 0
        current = start + timedelta(days=1)
        while current <= end:
            if DateUtils.is_trading_day(current):
                count += 1
            current += timedelta(days=1)
        return count

    @staticmethod
    def format_date(d: date, fmt: str = "%Y-%m-%d") -> str:
        """格式化日期"""
        return d.strftime(fmt)

    @staticmethod
    def add_holidays(year: int, holidays: list[date]) -> None:
        """为指定年份添加假期"""
        if year in _CN_HOLIDAYS_BY_YEAR:
            _CN_HOLIDAYS_BY_YEAR[year].update(holidays)
        else:
            _CN_HOLIDAYS_BY_YEAR[year] = set(holidays)

    @staticmethod
    def get_holiday_list(year: int) -> set[date]:
        """获取指定年份的假期集合"""
        return _CN_HOLIDAYS_BY_YEAR.get(year, set())
