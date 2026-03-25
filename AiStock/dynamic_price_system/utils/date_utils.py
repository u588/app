#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DateUtils：日期处理工具模块
职责：
1. 交易日历查询
2. 日期格式转换
3. 时间周期计算
4. 节假日判断
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Tuple

logger = logging.getLogger(__name__)


class DateUtils:
    """日期处理工具"""
    
    # A 股交易时间
    TRADING_HOURS = {
        'morning_start': '09:30',
        'morning_end': '11:30',
        'afternoon_start': '13:00',
        'afternoon_end': '15:00',
    }
    
    def __init__(self):
        """初始化工具"""
        logger.info("✅ DateUtils 初始化成功")
    
    def is_trading_day(self, date: Optional[datetime] = None) -> bool:
        """
        判断是否为交易日
        
        参数:
            date: 日期（默认今天）
        
        返回:
            是否为交易日
        """
        if date is None:
            date = datetime.now()
        
        # 周末不是交易日
        if date.weekday() >= 5:
            return False
        
        # TODO: 添加中国节假日判断
        # 这里简化处理，实际应接入节假日 API
        
        return True
    
    def get_previous_trading_day(
        self,
        date: Optional[datetime] = None,
        days: int = 1
    ) -> datetime:
        """
        获取前 N 个交易日
        
        参数:
            date: 基准日期（默认今天）
            days: 向前推几天
        
        返回:
            前 N 个交易日日期
        """
        if date is None:
            date = datetime.now()
        
        count = 0
        current = date
        
        while count < days:
            current -= timedelta(days=1)
            if self.is_trading_day(current):
                count += 1
        
        return current
    
    def get_next_trading_day(
        self,
        date: Optional[datetime] = None,
        days: int = 1
    ) -> datetime:
        """
        获取后 N 个交易日
        
        参数:
            date: 基准日期（默认今天）
            days: 向后推几天
        
        返回:
            后 N 个交易日日期
        """
        if date is None:
            date = datetime.now()
        
        count = 0
        current = date
        
        while count < days:
            current += timedelta(days=1)
            if self.is_trading_day(current):
                count += 1
        
        return current
    
    def get_trading_days_in_range(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[datetime]:
        """
        获取日期范围内的交易日列表
        
        参数:
            start_date: 开始日期
            end_date: 结束日期
        
        返回:
            交易日列表
        """
        trading_days = []
        current = start_date
        
        while current <= end_date:
            if self.is_trading_day(current):
                trading_days.append(current)
            current += timedelta(days=1)
        
        return trading_days
    
    def format_date(
        self,
        date: Optional[datetime] = None,
        format_str: str = '%Y-%m-%d'
    ) -> str:
        """
        格式化日期
        
        参数:
            date: 日期（默认今天）
            format_str: 格式字符串
        
        返回:
            格式化后的日期字符串
        """
        if date is None:
            date = datetime.now()
        
        return date.strftime(format_str)
    
    def parse_date(
        self,
        date_str: str,
        format_str: str = '%Y-%m-%d'
    ) -> Optional[datetime]:
        """
        解析日期字符串
        
        参数:
            date_str: 日期字符串
            format_str: 格式字符串
        
        返回:
            日期对象或 None
        """
        try:
            return datetime.strptime(date_str, format_str)
        except Exception as e:
            logger.error(f"❌ 解析日期失败：{date_str}, {e}")
            return None
    
    def get_current_trading_period(self) -> str:
        """
        获取当前交易时段
        
        返回:
            交易时段描述
        """
        now = datetime.now()
        current_time = now.strftime('%H:%M')
        
        if not self.is_trading_day(now):
            return '非交易日'
        
        if current_time < self.TRADING_HOURS['morning_start']:
            return '盘前'
        elif current_time < self.TRADING_HOURS['morning_end']:
            return '早盘'
        elif current_time < self.TRADING_HOURS['afternoon_start']:
            return '午间休市'
        elif current_time < self.TRADING_HOURS['afternoon_end']:
            return '午盘'
        else:
            return '收盘后'
    
    def calculate_holding_days(
        self,
        buy_date: datetime,
        sell_date: Optional[datetime] = None
    ) -> int:
        """
        计算持仓天数（交易日）
        
        参数:
            buy_date: 买入日期
            sell_date: 卖出日期（默认今天）
        
        返回:
            持仓交易日天数
        """
        if sell_date is None:
            sell_date = datetime.now()
        
        trading_days = self.get_trading_days_in_range(buy_date, sell_date)
        return len(trading_days)
    
    def get_quarter_dates(self, year: Optional[int] = None) -> List[Tuple[datetime, datetime]]:
        """
        获取年度季度日期范围
        
        参数:
            year: 年份（默认今年）
        
        返回:
            季度日期范围列表 [(Q1_start, Q1_end), ...]
        """
        if year is None:
            year = datetime.now().year
        
        quarters = [
            (datetime(year, 1, 1), datetime(year, 3, 31)),
            (datetime(year, 4, 1), datetime(year, 6, 30)),
            (datetime(year, 7, 1), datetime(year, 9, 30)),
            (datetime(year, 10, 1), datetime(year, 12, 31)),
        ]
        
        return quarters
    
    def is_report_period(self, date: Optional[datetime] = None) -> bool:
        """
        判断是否为财报披露期
        
        参数:
            date: 日期（默认今天）
        
        返回:
            是否为财报期
        """
        if date is None:
            date = datetime.now()
        
        month = date.month
        
        # A 股财报披露期：1-4 月（年报）、7-8 月（中报）、10 月（三季报）
        report_months = [1, 2, 3, 4, 7, 8, 10]
        
        return month in report_months


# ==================== 使用示例 ====================
def example_date_utils():
    """日期工具使用示例"""
    
    print("=" * 80)
    print("🧪 DateUtils 使用示例")
    print("=" * 80)
    
    utils = DateUtils()
    
    # 判断交易日
    print("\n1️⃣ 判断交易日...")
    today = datetime.now()
    print(f"   • 今天 {today.strftime('%Y-%m-%d')} 是交易日：{utils.is_trading_day(today)}")
    
    # 获取前/后交易日
    print("\n2️⃣ 获取前/后交易日...")
    prev_day = utils.get_previous_trading_day(today, days=1)
    next_day = utils.get_next_trading_day(today, days=1)
    print(f"   • 前 1 个交易日：{prev_day.strftime('%Y-%m-%d')}")
    print(f"   • 后 1 个交易日：{next_day.strftime('%Y-%m-%d')}")
    
    # 获取交易时段
    print("\n3️⃣ 获取当前交易时段...")
    period = utils.get_current_trading_period()
    print(f"   • 当前时段：{period}")
    
    # 日期格式化
    print("\n4️⃣ 日期格式化...")
    formatted = utils.format_date(today, '%Y年%m月%d日')
    print(f"   • 格式化：{formatted}")
    
    # 判断财报期
    print("\n5️⃣ 判断财报披露期...")
    is_report = utils.is_report_period(today)
    print(f"   • 当前是否为财报期：{is_report}")
    
    print("\n" + "=" * 80)
    print("✅ DateUtils 示例运行完成")
    print("=" * 80)


if __name__ == "__main__":
    example_date_utils()