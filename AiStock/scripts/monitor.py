#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实时监测脚本：组合表现跟踪 + 风控预警
输出：
  - 命令行摘要
  - HTML 仪表板（Plotly）
  - 预警日志/消息
"""

import sys
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from base_services.config_service import ConfigService
from dynamic_price_system.portfolio.tracker import PortfolioTracker
from dynamic_price_system.portfolio.risk_manager import RiskManager

class MonitorDashboard:
    """监测仪表板"""
    
    def __init__(self, config: ConfigService):
        self.config = config
        self.tracker = PortfolioTracker(
            initial_capital=config.get('portfolio.initial_capital', 1_000_000),
            config=config
        )
        self.risk_manager = RiskManager(config=config, portfolio=self.tracker)
    
    def update_prices(self, current_prices: Dict[str, float]):
        """更新持仓价格"""
        self.tracker.update_prices(current_prices)
    
    def generate_summary(self) -> Dict:
        """生成监测摘要"""
        portfolio_value = self.tracker.get_portfolio_value()
        positions = self.tracker.get_positions()
        
        # 计算关键指标
        daily_return = self.tracker.calculate_daily_return()
        drawdown = self.tracker.calculate_drawdown()
        
        # 风控检查
        alerts = self.risk_manager.check_alerts(positions)
        
        return {
            'portfolio_value': portfolio_value,
            'cash': self.tracker.cash,
            'daily_return': daily_return,
            'drawdown': drawdown,
            'position_count': len(positions),
            'alerts': alerts,
            'top_positions': sorted(
                [(code, pos['quantity'] * pos['current_price']) 
                 for code, pos in positions.items()],
                key=lambda x: -x[1]
            )[:5]
        }
    
    def plot_dashboard(self, summary: Dict) -> go.Figure:
        """生成监测仪表板图表"""
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=['组合净值', '持仓分布', '风险指标', '预警信息'],
            specs=[[{'type': 'scatter'}, {'type': 'pie'}],
                   [{'type': 'indicator'}, {'type': 'table'}]]
        )
        
        # 1. 净值曲线（简化：用模拟数据）
        dates = pd.date_range(end=pd.Timestamp.now(), periods=30)
        nav = 1_000_000 * np.cumprod(1 + np.random.normal(0.0005, 0.01, 30))
        fig.add_trace(go.Scatter(x=dates, y=nav, name='组合净值'), row=1, col=1)
        
        # 2. 持仓分布饼图
        if summary['top_positions']:
            labels, values = zip(*summary['top_positions'])
            fig.add_trace(go.Pie(labels=labels, values=values, hole=0.4), row=1, col=2)
        
        # 3. 风险指标仪表
        fig.add_trace(go.Indicator(
            mode='gauge+number+delta',
            value=summary['drawdown'],
            title={'text': '当前回撤'},
            gauge={'axis': {'range': [-0.3, 0]}, 'bar': {'color': 'red' if summary['drawdown'] < -0.1 else 'green'}}
        ), row=2, col=1)
        
        # 4. 预警信息表格
        if summary['alerts']:
            alert_rows = [[a['code'], a['type'], a['message']] for a in summary['alerts']]
        else:
            alert_rows = [['- 无预警 -', '', '']]
        
        fig.add_trace(go.Table(
            header=dict(values=['标的', '类型', '消息']),
            cells=dict(values=list(zip(*alert_rows)))
        ), row=2, col=2)
        
        fig.update_layout(height=600, title_text='📡 AiStock 实时监测仪表板')
        return fig

def main():
    """主函数：执行监测"""
    # 1. 初始化
    config = ConfigService(system_name='dynamic_price')
    monitor = MonitorDashboard(config)
    
    # 2. 获取最新价格（实际应从行情接口获取）
    # 简化：用动态价格引擎最新结果
    from dynamic_price_system.core.dynamic_price_engine import DynamicPriceEngine
    engine = DynamicPriceEngine(config_service=config)
    
    # 此处应加载最新数据并计算，简化为模拟
    current_prices = {
        '600938': 42.24, '601899': 32.40, '300750': 400.50, '600406': 30.70
    }
    monitor.update_prices(current_prices)
    
    # 3. 生成摘要
    summary = monitor.generate_summary()
    
    # 4. 命令行输出
    print("\n" + "="*60)
    print("📡 AiStock 实时监测摘要")
    print("="*60)
    print(f"组合市值: ¥{summary['portfolio_value']:,.0f}")
    print(f"可用现金: ¥{summary['cash']:,.0f}")
    print(f"今日收益: {summary['daily_return']:+.2%}")
    print(f"当前回撤: {summary['drawdown']:+.2%}")
    print(f"持仓数量: {summary['position_count']} 只")
    
    if summary['alerts']:
        print(f"\n⚠️ 风控预警 ({len(summary['alerts'])} 条):")
        for alert in summary['alerts']:
            print(f"  • {alert['code']}: {alert['type']} - {alert['message']}")
    else:
        print("\n✅ 无风控预警")
    
    # 5. 生成并保存仪表板
    fig = monitor.plot_dashboard(summary)
    output_path = PROJECT_ROOT / 'output' / 'monitor_dashboard.html'
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(output_path), include_plotlyjs='cdn')
    print(f"\n📊 仪表板已保存: {output_path}")
    
    # 6. 预警推送（可选：集成钉钉/企业微信）
    if summary['alerts']:
        send_alert_notification(summary['alerts'])  # 需实现推送逻辑

def send_alert_notification(alerts: List[Dict]):
    """发送预警通知（示例）"""
    # 实际可集成：
    # - 钉钉 webhook
    # - 企业微信机器人
    # - 邮件/短信
    print("🔔 预警通知已触发（需配置推送渠道）")

if __name__ == '__main__':
    main()