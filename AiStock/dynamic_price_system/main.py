#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主程序入口：三维动态价格调整系统
"""

import logging
from datetime import datetime
from config import STOCKS_CONFIG
from data_fetcher import DataFetcher
from dynamic_price import DynamicPriceCalculator
from portfolio_tracker import PortfolioTracker
from alert_system import AlertSystem
from excel_export import ExcelExporter

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/system.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class DynamicPriceSystem:
    """三维动态价格调整系统"""
    
    def __init__(self, initial_capital=1000000):
        """初始化系统"""
        logger.info("="*60)
        logger.info("🚀 三维动态价格调整系统启动")
        logger.info("="*60)
        
        self.fetcher = DataFetcher()
        self.tracker = PortfolioTracker(initial_capital)
        self.alert_sys = AlertSystem()
        self.exporter = ExcelExporter()
    
    def run_daily(self):
        """每日运行流程"""
        logger.info("\n" + "="*60)
        logger.info("📅 开始每日运行流程")
        logger.info("="*60)
        
        # 1. 获取数据
        logger.info("\n【步骤 1】获取数据...")
        stocks_data = self.fetcher.get_all_stocks_data()
        macro_data = self.fetcher.get_all_macro_data()
        
        # 模拟财务数据（实际应从 API 获取）
        financial_data = {}
        for stock in STOCKS_CONFIG:
            financial_data[stock['code']] = {
                'revenue_growth': 15,
                'profit_growth': 20,
                'roe': 18,
                'gross_margin': 30,
                'debt_ratio': 40
            }
        
        # 2. 计算动态价格
        logger.info("\n【步骤 2】计算动态价格...")
        calc = DynamicPriceCalculator(stocks_data, financial_data, macro_data)
        results = calc.calculate_all()
        
        # 3. 检查预警
        logger.info("\n【步骤 3】检查预警...")
        for result in results:
            alerts = self.alert_sys.check_price_alerts(
                result['code'],
                result['current_price'],
                result['entry_price'],
                result['stop_loss'],
                result['target_price']
            )
            self.alert_sys.send_alerts(alerts)
        
        # 4. 组合跟踪
        logger.info("\n【步骤 4】组合跟踪...")
        current_prices = {r['code']: r['current_price'] for r in results}
        stop_prices = {r['code']: r['stop_loss'] for r in results}
        
        # 模拟持仓（实际应从数据库加载）
        if not self.tracker.positions:
            for result in results[:5]:  # 前 5 只建仓
                self.tracker.buy(
                    result['code'],
                    result['entry_price'],
                    int(100000 / result['entry_price'])
                )
        
        # 检查止损
        stop_alerts = self.tracker.check_stop_loss(current_prices, stop_prices)
        self.alert_sys.send_alerts(stop_alerts)
        
        # 检查再平衡
        rebalance_actions = self.tracker.check_rebalance(current_prices, results)
        if rebalance_actions:
            logger.info(f"📊 再平衡建议：{len(rebalance_actions)}个操作")
            for action in rebalance_actions:
                logger.info(f"  {action['code']}: {action['action']} {action['quantity']}股 ({action['reason']})")
        
        # 5. 导出 Excel
        logger.info("\n【步骤 5】导出 Excel...")
        self.exporter.export_dynamic_prices(results)
        
        # 6. 组合摘要
        summary = self.tracker.get_summary(current_prices)
        self.exporter.export_portfolio_summary(summary)
        
        # 7. 打印摘要
        logger.info("\n" + "="*60)
        logger.info("📊 系统运行摘要")
        logger.info("="*60)
        logger.info(f"计算标的数：{len(results)}")
        logger.info(f"组合总市值：¥{summary['total_value']:,.2f}")
        logger.info(f"组合收益率：{summary['total_return']}")
        logger.info(f"预警数量：{len(self.alert_sys.alerts)}")
        logger.info(self.alert_sys.get_alert_summary())
        
        # 8. 推荐标的
        logger.info("\n💡 今日推荐标的（盈亏比>2.5 且评分>70）：")
        recommended = [r for r in results if r['profit_loss_ratio'] >= 2.5 and r['fundamental_score'] >= 70]
        for r in sorted(recommended, key=lambda x: x['profit_loss_ratio'], reverse=True)[:5]:
            logger.info(f"  {r['code']} {r['recommendation']} 盈亏比{r['profit_loss_ratio']} 评分{r['fundamental_score']}")
        
        logger.info("\n" + "="*60)
        logger.info("✅ 每日运行流程完成")
        logger.info("="*60)
        
        return results, summary


# 主程序
if __name__ == '__main__':
    import os
    
    # 创建必要目录
    os.makedirs('data', exist_ok=True)
    os.makedirs('logs', exist_ok=True)
    os.makedirs('output', exist_ok=True)
    
    # 运行系统
    system = DynamicPriceSystem(initial_capital=1000000)
    results, summary = system.run_daily()
    
    print("\n" + "="*60)
    print("🎉 系统运行完成！")
    print("="*60)
    print(f"📄 Excel 报告：output/dynamic_price_*.xlsx")
    print(f"📊 组合摘要：output/dynamic_price_*_portfolio.xlsx")
    print(f"📝 系统日志：logs/system.log")
    print("="*60)