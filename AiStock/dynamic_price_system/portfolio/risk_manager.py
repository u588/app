#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RiskManager：风险管理模块
职责：
1. 止损/止盈检测
2. 组合回撤监控
3. 风险预警生成
4. 仓位控制建议
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from base_services.config_service import ConfigService

logger = logging.getLogger(__name__)


class RiskManager:
    """风险管理引擎"""
    
    def __init__(self, config: Optional[ConfigService] = None, portfolio=None):
        """
        初始化风险管理器
        
        参数:
            config: 配置服务实例
            portfolio: 组合跟踪器实例
        """
        self.config = config
        self.portfolio = portfolio
        
        # 默认风控阈值
        self.stop_loss_threshold = -0.15  # 止损阈值 -15%
        self.take_profit_threshold = 0.30  # 止盈阈值 30%
        self.max_drawdown_threshold = -0.20  # 最大回撤 -20%
        self.single_position_limit = 0.15  # 单标的上限 15%
        self.sector_position_limit = 0.30  # 单板块上限 30%
        
        # 从配置加载
        if config:
            self._load_config()
        
        logger.info("✅ RiskManager 初始化成功")
    
    def _load_config(self):
        """从配置加载风控参数"""
        try:
            risk_control = self.config.get('risk_control', {})
            if risk_control:
                self.stop_loss_threshold = risk_control.get('stop_loss_fixed', -0.15)
                self.take_profit_threshold = risk_control.get('take_profit_fixed', 0.30)
                self.max_drawdown_threshold = risk_control.get(
                    'portfolio_drawdown_limit', -0.20
                )
                self.single_position_limit = risk_control.get(
                    'max_position_single', 0.15
                )
                self.sector_position_limit = risk_control.get(
                    'max_position_sector', 0.30
                )
        except Exception as e:
            logger.warning(f"⚠️ 加载配置失败：{e}，使用默认值")
    
    def check_alerts(
        self,
        dynamic_prices: List[Dict],
        current_prices: Dict[str, float],
        positions: Optional[Dict[str, Dict]] = None
    ) -> List[Dict]:
        """
        检查风险预警
        
        参数:
            dynamic_prices: 动态价格结果列表
            current_prices: 当前价格字典
            positions: 当前持仓（可选）
        
        返回:
            预警列表
        """
        alerts = []
        
        # 1. 检查止损/止盈
        if positions:
            stop_alerts = self._check_stop_loss_take_profit(
                positions, current_prices, dynamic_prices
            )
            alerts.extend(stop_alerts)
        
        # 2. 检查仓位限制
        position_alerts = self._check_position_limits(
            positions, current_prices, dynamic_prices
        )
        alerts.extend(position_alerts)
        
        # 3. 检查组合回撤
        if self.portfolio:
            drawdown_alerts = self._check_portfolio_drawdown()
            alerts.extend(drawdown_alerts)
        
        # 按优先级排序
        alerts = sorted(alerts, key=lambda x: self._get_alert_priority(x['type']))
        
        logger.info(f"✅ 生成 {len(alerts)} 个风险预警")
        return alerts
    
    def _check_stop_loss_take_profit(
        self,
        positions: Dict[str, Dict],
        current_prices: Dict[str, float],
        dynamic_prices: List[Dict]
    ) -> List[Dict]:
        """检查止损/止盈"""
        alerts = []
        
        # 构建动态价格查找表
        price_map = {r['code']: r for r in dynamic_prices}
        
        for code, pos in positions.items():
            current_price = current_prices.get(code, 0)
            cost = pos.get('cost', 0)
            quantity = pos.get('quantity', 0)
            
            if current_price <= 0 or cost <= 0:
                continue
            
            # 获取动态止损/目标价
            dynamic = price_map.get(code, {})
            stop_loss = dynamic.get('stop_loss', cost * (1 + self.stop_loss_threshold))
            target_price = dynamic.get('target_price', cost * (1 + self.take_profit_threshold))
            
            # 计算盈亏比例
            profit_ratio = (current_price - cost) / cost
            
            # 检查止损
            if current_price <= stop_loss:
                alerts.append({
                    'type': 'STOP_LOSS',
                    'code': code,
                    'level': 'HIGH',
                    'message': f"⚠️ {code} 触发止损！当前{current_price:.2f} <= 止损{stop_loss:.2f}",
                    'current_price': current_price,
                    'stop_loss': stop_loss,
                    'profit_ratio': f"{profit_ratio:.1%}",
                    'quantity': quantity,
                    'suggested_action': '卖出',
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
            
            # 检查止盈
            elif current_price >= target_price * 0.95:  # 达到目标价 95%
                alerts.append({
                    'type': 'TAKE_PROFIT',
                    'code': code,
                    'level': 'MEDIUM',
                    'message': f"📈 {code} 接近止盈！当前{current_price:.2f} >= 目标{target_price*0.95:.2f}",
                    'current_price': current_price,
                    'target_price': target_price,
                    'profit_ratio': f"{profit_ratio:.1%}",
                    'quantity': quantity,
                    'suggested_action': '部分止盈',
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
        
        return alerts
    
    def _check_position_limits(
        self,
        positions: Dict[str, Dict],
        current_prices: Dict[str, float],
        dynamic_prices: List[Dict]
    ) -> List[Dict]:
        """检查仓位限制"""
        alerts = []
        
        if not positions:
            return alerts
        
        # 计算总市值
        total_value = sum(
            pos['quantity'] * current_prices.get(code, 0)
            for code, pos in positions.items()
        )
        
        if total_value == 0:
            return alerts
        
        # 按板块汇总
        sector_values = {}
        for code, pos in positions.items():
            # 获取标的板块
            sector = None
            for r in dynamic_prices:
                if r['code'] == code:
                    sector = r.get('sector')
                    break
            
            if sector:
                market_value = pos['quantity'] * current_prices.get(code, 0)
                sector_values[sector] = sector_values.get(sector, 0) + market_value
        
        # 检查单标的仓位
        for code, pos in positions.items():
            market_value = pos['quantity'] * current_prices.get(code, 0)
            weight = market_value / total_value
            
            if weight > self.single_position_limit:
                alerts.append({
                    'type': 'POSITION_LIMIT',
                    'code': code,
                    'level': 'MEDIUM',
                    'message': f"⚠️ {code} 仓位超限！当前{weight:.1%} > 上限{self.single_position_limit:.0%}",
                    'current_weight': f"{weight:.1%}",
                    'limit': f"{self.single_position_limit:.0%}",
                    'suggested_action': '减仓',
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
        
        # 检查板块仓位
        for sector, value in sector_values.items():
            weight = value / total_value
            
            if weight > self.sector_position_limit:
                alerts.append({
                    'type': 'SECTOR_LIMIT',
                    'sector': sector,
                    'level': 'MEDIUM',
                    'message': f"⚠️ {sector}板块仓位超限！当前{weight:.1%} > 上限{self.sector_position_limit:.0%}",
                    'current_weight': f"{weight:.1%}",
                    'limit': f"{self.sector_position_limit:.0%}",
                    'suggested_action': '调整板块配置',
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
        
        return alerts
    
    def _check_portfolio_drawdown(self) -> List[Dict]:
        """检查组合回撤"""
        alerts = []
        
        if not self.portfolio:
            return alerts
        
        try:
            # 获取组合收益率
            # 这里简化处理，实际应从组合跟踪器获取
            # current_return = self.portfolio.get_portfolio_return()
            
            # 模拟回撤检查
            # if current_return < self.max_drawdown_threshold:
            #     alerts.append({
            #         'type': 'MAX_DRAWDOWN',
            #         'level': 'HIGH',
            #         'message': f"🔴 组合回撤过大！当前{current_return:.1%} <= 阈值{self.max_drawdown_threshold:.0%}",
            #         'current_drawdown': f"{current_return:.1%}",
            #         'limit': f"{self.max_drawdown_threshold:.0%}",
            #         'suggested_action': '降低仓位',
            #         'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            #     })
            pass
        except Exception as e:
            logger.error(f"❌ 检查组合回撤失败：{e}")
        
        return alerts
    
    def _get_alert_priority(self, alert_type: str) -> int:
        """获取预警优先级（数字越小优先级越高）"""
        priority_map = {
            'STOP_LOSS': 1,
            'MAX_DRAWDOWN': 2,
            'POSITION_LIMIT': 3,
            'SECTOR_LIMIT': 4,
            'TAKE_PROFIT': 5,
        }
        return priority_map.get(alert_type, 99)
    
    def generate_risk_report(
        self,
        alerts: List[Dict],
        portfolio_summary: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        生成风险报告
        
        参数:
            alerts: 预警列表
            portfolio_summary: 组合摘要
        
        返回:
            风险报告字典
        """
        high_count = sum(1 for a in alerts if a.get('level') == 'HIGH')
        medium_count = sum(1 for a in alerts if a.get('level') == 'MEDIUM')
        low_count = sum(1 for a in alerts if a.get('level') == 'LOW')
        
        report = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_alerts': len(alerts),
            'high_priority': high_count,
            'medium_priority': medium_count,
            'low_priority': low_count,
            'alerts_by_type': self._group_alerts_by_type(alerts),
            'alerts': alerts,
            'portfolio_summary': portfolio_summary,
            'risk_level': self._calculate_risk_level(alerts),
        }
        
        logger.info(f"✅ 生成风险报告：{len(alerts)}个预警，风险等级{report['risk_level']}")
        return report
    
    def _group_alerts_by_type(self, alerts: List[Dict]) -> Dict[str, int]:
        """按类型分组预警"""
        groups = {}
        for alert in alerts:
            alert_type = alert.get('type', 'UNKNOWN')
            groups[alert_type] = groups.get(alert_type, 0) + 1
        return groups
    
    def _calculate_risk_level(self, alerts: List[Dict]) -> str:
        """计算风险等级"""
        high_count = sum(1 for a in alerts if a.get('level') == 'HIGH')
        
        if high_count >= 3:
            return '高危'
        elif high_count >= 1:
            return '中危'
        elif len(alerts) >= 5:
            return '低危'
        else:
            return '正常'
    
    def get_position_suggestion(
        self,
        code: str,
        current_price: float,
        entry_price: float,
        stop_loss: float,
        target_price: float
    ) -> Dict[str, Any]:
        """
        获取仓位建议
        
        参数:
            code: 股票代码
            current_price: 当前价
            entry_price: 入场价
            stop_loss: 止损价
            target_price: 目标价
        
        返回:
            仓位建议字典
        """
        profit_ratio = (current_price - entry_price) / entry_price if entry_price > 0 else 0
        
        # 判断建议
        if current_price <= stop_loss:
            suggestion = '止损卖出'
            action = 'sell'
            ratio = 1.0
        elif current_price >= target_price * 0.95:
            suggestion = '部分止盈'
            action = 'sell'
            ratio = 0.5
        elif profit_ratio > 0.10:
            suggestion = '持有观望'
            action = 'hold'
            ratio = 1.0
        elif profit_ratio < -0.10:
            suggestion = '谨慎持有'
            action = 'hold'
            ratio = 0.8
        else:
            suggestion = '正常持有'
            action = 'hold'
            ratio = 1.0
        
        return {
            'code': code,
            'suggestion': suggestion,
            'action': action,
            'position_ratio': ratio,
            'profit_ratio': f"{profit_ratio:.1%}",
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }


# ==================== 使用示例 ====================
def example_risk_manager():
    """风险管理器使用示例"""
    
    print("=" * 80)
    print("🧪 RiskManager 使用示例")
    print("=" * 80)
    
    risk_manager = RiskManager()
    
    # 模拟动态价格结果
    dynamic_prices = [
        {
            'code': '600938',
            'sector': '油气开采',
            'current_price': 42.24,
            'stop_loss': 39.20,
            'target_price': 48.50,
        },
        {
            'code': '601899',
            'sector': '黄金',
            'current_price': 32.40,
            'stop_loss': 30.15,
            'target_price': 41.00,
        },
    ]
    
    # 模拟当前价格
    current_prices = {
        '600938': 42.24,
        '601899': 32.40,
    }
    
    # 模拟持仓
    positions = {
        '600938': {'quantity': 5000, 'cost': 40.00},
        '601899': {'quantity': 8000, 'cost': 32.00},
    }
    
    # 检查预警
    print("\n1️⃣ 检查风险预警...")
    alerts = risk_manager.check_alerts(
        dynamic_prices=dynamic_prices,
        current_prices=current_prices,
        positions=positions
    )
    
    for alert in alerts:
        print(f"   • [{alert['level']}] {alert['message']}")
    
    # 生成风险报告
    print("\n2️⃣ 生成风险报告...")
    report = risk_manager.generate_risk_report(alerts)
    print(f"   • 总预警数：{report['total_alerts']}")
    print(f"   • 高危：{report['high_priority']}")
    print(f"   • 中危：{report['medium_priority']}")
    print(f"   • 风险等级：{report['risk_level']}")
    
    # 获取仓位建议
    print("\n3️⃣ 获取仓位建议...")
    suggestion = risk_manager.get_position_suggestion(
        code='600938',
        current_price=42.24,
        entry_price=40.00,
        stop_loss=39.20,
        target_price=48.50
    )
    print(f"   • {suggestion['code']}: {suggestion['suggestion']} "
          f"(盈利{suggestion['profit_ratio']})")
    
    print("\n" + "=" * 80)
    print("✅ RiskManager 示例运行完成")
    print("=" * 80)


if __name__ == "__main__":
    example_risk_manager()