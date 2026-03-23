#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
预警系统模块
"""

import logging
from datetime import datetime
from config import ALERT_THRESHOLDS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AlertSystem:
    """预警系统"""
    
    def __init__(self):
        self.alerts = []
    
    def check_price_alerts(self, code, current_price, entry_price, stop_price, target_price):
        """检查价格预警"""
        alerts = []
        
        # 止损预警
        if current_price <= stop_price:
            alerts.append({
                'type': 'STOP_LOSS',
                'code': code,
                'message': f"⚠️ 触发止损！当前{current_price} <= 止损{stop_price}",
                'level': 'HIGH'
            })
        
        # 止盈预警
        if current_price >= target_price * 0.95:
            alerts.append({
                'type': 'TAKE_PROFIT',
                'code': code,
                'message': f"📈 接近目标价！当前{current_price} >= 目标{target_price*0.95:.2f}",
                'level': 'MEDIUM'
            })
        
        # 入场机会
        if current_price <= entry_price * 1.02:
            alerts.append({
                'type': 'BUY_OPPORTUNITY',
                'code': code,
                'message': f"💰 入场机会！当前{current_price} <= 入场{entry_price*1.02:.2f}",
                'level': 'MEDIUM'
            })
        
        return alerts
    
    def check_portfolio_alerts(self, portfolio_return, drawdown):
        """检查组合预警"""
        alerts = []
        
        # 组合回撤预警
        if drawdown <= ALERT_THRESHOLDS['portfolio_drawdown']:
            alerts.append({
                'type': 'PORTFOLIO_DRAWDOWN',
                'message': f"🔴 组合回撤过大！当前{drawdown:.1%} <= 阈值{ALERT_THRESHOLDS['portfolio_drawdown']:.0%}",
                'level': 'HIGH'
            })
        
        # 组合收益预警
        if portfolio_return >= 0.25:
            alerts.append({
                'type': 'PORTFOLIO_PROFIT',
                'message': f"📈 组合收益良好！当前{portfolio_return:.1%} >= 25%",
                'level': 'LOW'
            })
        
        return alerts
    
    def send_alerts(self, alerts):
        """发送预警（可扩展为邮件/微信/短信）"""
        if not alerts:
            logger.info("✅ 无预警信息")
            return
        
        for alert in alerts:
            self.alerts.append({
                'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                **alert
            })
            
            # 日志输出
            if alert['level'] == 'HIGH':
                logger.error(f"{alert['message']}")
            elif alert['level'] == 'MEDIUM':
                logger.warning(f"{alert['message']}")
            else:
                logger.info(f"{alert['message']}")
        
        # 可扩展：发送邮件/微信
        # self._send_email(alerts)
        # self._send_wechat(alerts)
    
    def get_alert_summary(self):
        """获取预警摘要"""
        if not self.alerts:
            return "无预警"
        
        high_count = sum(1 for a in self.alerts if a['level'] == 'HIGH')
        medium_count = sum(1 for a in self.alerts if a['level'] == 'MEDIUM')
        low_count = sum(1 for a in self.alerts if a['level'] == 'LOW')
        
        return f"预警摘要：高{high_count} 中{medium_count} 低{low_count}"
    
    def clear_alerts(self):
        """清空预警"""
        self.alerts = []


# 测试
if __name__ == '__main__':
    alert_sys = AlertSystem()
    
    # 模拟价格预警
    alerts1 = alert_sys.check_price_alerts('600938', 39.50, 40.00, 39.00, 48.00)
    alert_sys.send_alerts(alerts1)
    
    # 模拟组合预警
    alerts2 = alert_sys.check_portfolio_alerts(0.15, -0.12)
    alert_sys.send_alerts(alerts2)
    
    print("\n" + "="*60)
    print("预警系统测试结果")
    print("="*60)
    print(alert_sys.get_alert_summary())