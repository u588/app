#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AiStock V8 — 交易日历与日期工具 (DateUtils)

提供中国市场交易日判断、期权交割月推导、股指期货季月推导等功能。

核心方法:
  get_trading_date(offset=0)        — 获取第N个前交易日 (跳过周末)
  is_trading_day(date)              — 判断是否为交易日 (非周末 + 非假期)
  get_near_month_delivery(date, rollover_day=15) — 期权近月交割月
  get_next_quarter_month(date)      — 股指期货下个季月

常量:
  cn_holidays_2026 — 2026年A股市场休市日列表
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import List, Optional


# ═══════════════════════════════════════════════════════════════════════════════
# 2026年中国A股市场休市日 (根据国务院公告)
# ═══════════════════════════════════════════════════════════════════════════════

cn_holidays_2026: List[date] = [
    # ─── 元旦 ──────────────────────────────────────────────
    date(2026, 1, 1),   # 周四 元旦
    date(2026, 1, 2),   # 周五 调休
    date(2026, 1, 3),   # 周六 (含在假期中)
    date(2026, 1, 4),   # 周日 (含在假期中)

    # ─── 春节 ──────────────────────────────────────────────
    date(2026, 2, 16),  # 周一 除夕
    date(2026, 2, 17),  # 周二 初一
    date(2026, 2, 18),  # 周三 初二
    date(2026, 2, 19),  # 周四 初三
    date(2026, 2, 20),  # 周五 初四
    date(2026, 2, 21),  # 周六 初五
    date(2026, 2, 22),  # 周日 初六

    # ─── 清明节 ────────────────────────────────────────────
    date(2026, 4, 4),   # 周六 清明
    date(2026, 4, 5),   # 周日
    date(2026, 4, 6),   # 周一 调休

    # ─── 劳动节 ────────────────────────────────────────────
    date(2026, 5, 1),   # 周五 劳动节
    date(2026, 5, 2),   # 周六
    date(2026, 5, 3),   # 周日
    date(2026, 5, 4),   # 周一 调休
    date(2026, 5, 5),   # 周二 调休

    # ─── 端午节 ────────────────────────────────────────────
    date(2026, 6, 19),  # 周五 端午
    date(2026, 6, 20),  # 周六
    date(2026, 6, 21),  # 周日

    # ─── 中秋节 ────────────────────────────────────────────
    date(2026, 9, 25),  # 周五 中秋
    date(2026, 9, 26),  # 周六
    date(2026, 9, 27),  # 周日

    # ─── 国庆节 ────────────────────────────────────────────
    date(2026, 10, 1),  # 周四 国庆
    date(2026, 10, 2),  # 周五
    date(2026, 10, 3),  # 周六
    date(2026, 10, 4),  # 周日
    date(2026, 10, 5),  # 周一 调休
    date(2026, 10, 6),  # 周二 调休
    date(2026, 10, 7),  # 周三 调休
]

# 按年份组织的假期查找表
_CN_HOLIDAYS_BY_YEAR: dict[int, set[date]] = {
    2026: set(cn_holidays_2026),
}

# 股指期货季月 (3/6/9/12)
_QUARTER_MONTHS: tuple[int, ...] = (3, 6, 9, 12)


class DateUtils:
    """日期工具类 — 交易日判断与期货/期权交割月推导

    所有方法均为静态方法, 无需实例化即可使用。

    使用方式:
        >>> DateUtils.is_trading_day(date(2026, 3, 16))  # 周一
        True
        >>> DateUtils.is_trading_day(date(2026, 1, 1))    # 元旦
        False
        >>> DateUtils.get_trading_date(offset=0)
        datetime.date(2026, 3, 16)
        >>> DateUtils.get_near_month_delivery(date(2026, 3, 16))
        3
        >>> DateUtils.get_next_quarter_month(date(2026, 3, 16))
        6
    """

    # ─── 交易日判断 ──────────────────────────────────────────

    @staticmethod
    def is_trading_day(d: date) -> bool:
        """判断指定日期是否为交易日

        简易判断逻辑:
          1. 周六 (weekday=5) 和 周日 (weekday=6) → 非交易日
          2. 在中国A股休市假期列表中 → 非交易日
          3. 其余 → 交易日

        注意: 此方法不含周末补班日 (如国庆前的周六上班),
              实际使用中可通过配置补充调休工作日。

        Args:
            d: 待判断日期

        Returns:
            True=交易日, False=非交易日
        """
        # 周末一定非交易日
        if d.weekday() >= 5:
            return False

        # 检查假期
        holidays = _CN_HOLIDAYS_BY_YEAR.get(d.year)
        if holidays and d in holidays:
            return False

        return True

    @staticmethod
    def get_trading_date(offset: int = 0) -> date:
        """获取第N个前交易日

        从今天开始, 向前寻找第 offset 个交易日 (跳过周末和假期)。

        Args:
            offset: 偏移量
                     0 = 最近一个交易日 (若今天是交易日则返回今天)
                     1 = 前1个交易日
                     2 = 前2个交易日
                     ...以此类推

        Returns:
            目标交易日

        Example:
            >>> # 假设今天是2026-03-16 (周一)
            >>> DateUtils.get_trading_date(0)   # 2026-03-16
            >>> DateUtils.get_trading_date(1)   # 2026-03-13 (上周五)
            >>> DateUtils.get_trading_date(5)   # 2026-03-09
        """
        current = date.today()
        found = 0

        while True:
            if DateUtils.is_trading_day(current):
                if found == offset:
                    return current
                found += 1

            current -= timedelta(days=1)

            # 安全阀: 防止无限循环
            if current.year < 2020:
                raise ValueError(f"无法找到偏移 {offset} 的交易日, 搜索已回溯至 {current}")

    # ─── 期权交割月推导 ─────────────────────────────────────

    @staticmethod
    def get_near_month_delivery(
        d: date,
        rollover_day: int = 15,
    ) -> int:
        """获取期权近月交割月

        50ETF/300ETF等期权每月都有到期日 (通常为第四个周三),
        本方法简化为: 若当月尚未到 rollover_day, 则近月为当月,
        否则近月为下月。

        Args:
            d:           参考日期
            rollover_day: 展仓日 (默认15日), 超过此日后近月切换到下月

        Returns:
            交割月份 (1-12)

        Example:
            >>> DateUtils.get_near_month_delivery(date(2026, 3, 10))  # 3
            >>> DateUtils.get_near_month_delivery(date(2026, 3, 16))  # 4
        """
        if d.day < rollover_day:
            return d.month
        else:
            # 下月
            if d.month == 12:
                return 1
            return d.month + 1

    # ─── 股指期货季月推导 ───────────────────────────────────

    @staticmethod
    def get_next_quarter_month(d: date) -> int:
        """获取股指期货下一个季月

        股指期货 (IF/IH/IC/IM) 的合约月份为当月、下月和随后的两个季月。
        季月定义: 3月、6月、9月、12月。

        本方法返回从指定日期之后最近的季月。

        Args:
            d: 参考日期

        Returns:
            下一个季月 (3/6/9/12)

        Example:
            >>> DateUtils.get_next_quarter_month(date(2026, 1, 15))  # 3
            >>> DateUtils.get_next_quarter_month(date(2026, 3, 15))  # 6
            >>> DateUtils.get_next_quarter_month(date(2026, 10, 1))  # 12
        """
        current_month = d.month

        for qm in _QUARTER_MONTHS:
            if qm > current_month:
                return qm

        # 当前月已过最后一个季月, 返回下一年的第一个季月
        return _QUARTER_MONTHS[0]

    # ─── 辅助方法 ────────────────────────────────────────────

    @staticmethod
    def get_far_month_delivery(
        d: date,
        rollover_day: int = 15,
    ) -> int:
        """获取期权远月交割月

        远月 = 近月之后的第二个自然月。
        例如: 近月=3月, 则远月=5月。

        Args:
            d:           参考日期
            rollover_day: 展仓日

        Returns:
            远月交割月份 (1-12)
        """
        near = DateUtils.get_near_month_delivery(d, rollover_day)

        # 远月 = 近月 + 2
        far = near + 2
        if far > 12:
            far -= 12
        return far

    @staticmethod
    def get_index_futures_contracts(d: date) -> dict[str, int]:
        """获取股指期货当前4个合约月份

        当月、下月和随后的两个季月。

        Args:
            d: 参考日期

        Returns:
            {'current': 当月, 'next': 下月, 'quarter_1': 季月1, 'quarter_2': 季月2}
        """
        current_month = d.month
        next_month = current_month + 1 if current_month < 12 else 1

        # 找到两个最近的季月 (从下月开始算)
        quarter_months: list[int] = []
        check_month = next_month
        for _ in range(12):
            if check_month in _QUARTER_MONTHS:
                quarter_months.append(check_month)
                if len(quarter_months) == 2:
                    break
            check_month = check_month + 1 if check_month < 12 else 1

        # 如果只找到一个季月 (极端情况), 补上下一个季月
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
        """计算两个日期之间的交易日数

        Args:
            start: 起始日期
            end:   结束日期

        Returns:
            交易日数 (不含 start, 含 end)
        """
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
        """格式化日期

        Args:
            d:   日期
            fmt: 格式字符串

        Returns:
            格式化后的日期字符串
        """
        return d.strftime(fmt)

    @staticmethod
    def add_holidays(year: int, holidays: list[date]) -> None:
        """为指定年份添加假期

        允许运行时动态添加假期数据。

        Args:
            year:     年份
            holidays: 假期日期列表
        """
        if year in _CN_HOLIDAYS_BY_YEAR:
            _CN_HOLIDAYS_BY_YEAR[year].update(holidays)
        else:
            _CN_HOLIDAYS_BY_YEAR[year] = set(holidays)

    @staticmethod
    def get_holiday_list(year: int) -> set[date]:
        """获取指定年份的假期集合

        Args:
            year: 年份

        Returns:
            假期日期集合
        """
        return _CN_HOLIDAYS_BY_YEAR.get(year, set())
