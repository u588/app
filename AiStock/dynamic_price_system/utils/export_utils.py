#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ExportUtils：数据导出工具模块
职责：
1. Excel 报表导出
2. PDF 报告生成
3. CSV 数据导出
4. 图表生成
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path
import pandas as pd

logger = logging.getLogger(__name__)


class ExportUtils:
    """数据导出工具"""
    
    def __init__(self, output_dir: Optional[Path] = None):
        """
        初始化工具
        
        参数:
            output_dir: 输出目录
        """
        self.output_dir = output_dir or Path('./output')
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"✅ ExportUtils 初始化成功 | 输出目录={self.output_dir}")
    
    def export_dynamic_prices(
        self,
        results: List[Dict],
        filename: Optional[str] = None
    ) -> str:
        """
        导出动态价格表
        
        参数:
            results: 动态价格结果列表
            filename: 文件名（可选）
        
        返回:
            文件路径
        """
        if not results:
            logger.warning("⚠️ 无数据可导出")
            return ""
        
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"dynamic_price_{timestamp}.xlsx"
        
        filepath = self.output_dir / filename
        
        try:
            # 转换为 DataFrame
            df = pd.DataFrame(results)
            
            # 选择需要的列
            columns = [
                'code', 'sector', 'current_price', 'entry_price',
                'stop_loss', 'target_price', 'profit_loss_ratio',
                'fundamental_score', 'macro_factor', 'recommendation'
            ]
            df = df[[col for col in columns if col in df.columns]]
            
            # 导出 Excel
            df.to_excel(filepath, index=False, sheet_name='动态价格')
            
            logger.info(f"✅ 导出动态价格表：{filepath}")
            return str(filepath)
        except Exception as e:
            logger.error(f"❌ 导出动态价格表失败：{e}")
            return ""
    
    def export_portfolio_summary(
        self,
        summary: Dict[str, Any],
        filename: Optional[str] = None
    ) -> str:
        """
        导出组合摘要
        
        参数:
            summary: 组合摘要字典
            filename: 文件名（可选）
        
        返回:
            文件路径
        """
        if not summary:
            logger.warning("⚠️ 无数据可导出")
            return ""
        
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"portfolio_summary_{timestamp}.xlsx"
        
        filepath = self.output_dir / filename
        
        try:
            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                # 基本信息
                info_df = pd.DataFrame([
                    ['组合总市值', f"¥{summary.get('total_value', 0):,.2f}"],
                    ['现金', f"¥{summary.get('cash', 0):,.2f}"],
                    ['总收益率', summary.get('total_return', '0%')],
                    ['交易次数', summary.get('transaction_count', 0)],
                    ['更新时间', summary.get('update_time', '')],
                ], columns=['指标', '数值'])
                info_df.to_excel(writer, sheet_name='基本信息', index=False)
                
                # 持仓明细
                if 'positions' in summary and summary['positions']:
                    pos_df = pd.DataFrame(summary['positions'])
                    pos_df.to_excel(writer, sheet_name='持仓明细', index=False)
            
            logger.info(f"✅ 导出组合摘要：{filepath}")
            return str(filepath)
        except Exception as e:
            logger.error(f"❌ 导出组合摘要失败：{e}")
            return ""
    
    def export_risk_report(
        self,
        report: Dict[str, Any],
        filename: Optional[str] = None
    ) -> str:
        """
        导出风险报告
        
        参数:
            report: 风险报告字典
            filename: 文件名（可选）
        
        返回:
            文件路径
        """
        if not report:
            logger.warning("⚠️ 无数据可导出")
            return ""
        
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"risk_report_{timestamp}.xlsx"
        
        filepath = self.output_dir / filename
        
        try:
            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                # 风险摘要
                summary_df = pd.DataFrame([
                    ['报告时间', report.get('timestamp', '')],
                    ['总预警数', report.get('total_alerts', 0)],
                    ['高危预警', report.get('high_priority', 0)],
                    ['中危预警', report.get('medium_priority', 0)],
                    ['风险等级', report.get('risk_level', '正常')],
                ], columns=['指标', '数值'])
                summary_df.to_excel(writer, sheet_name='风险摘要', index=False)
                
                # 预警明细
                if 'alerts' in report and report['alerts']:
                    alerts_df = pd.DataFrame(report['alerts'])
                    alerts_df.to_excel(writer, sheet_name='预警明细', index=False)
            
            logger.info(f"✅ 导出风险报告：{filepath}")
            return str(filepath)
        except Exception as e:
            logger.error(f"❌ 导出风险报告失败：{e}")
            return ""
    
    def export_rebalance_report(
        self,
        report: Dict[str, Any],
        filename: Optional[str] = None
    ) -> str:
        """
        导出再平衡报告
        
        参数:
            report: 再平衡报告字典
            filename: 文件名（可选）
        
        返回:
            文件路径
        """
        if not report:
            logger.warning("⚠️ 无数据可导出")
            return ""
        
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"rebalance_report_{timestamp}.xlsx"
        
        filepath = self.output_dir / filename
        
        try:
            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                # 报告摘要
                summary_df = pd.DataFrame([
                    ['报告时间', report.get('timestamp', '')],
                    ['总动作数', report.get('total_actions', 0)],
                    ['买入动作', report.get('buy_actions', 0)],
                    ['卖出动作', report.get('sell_actions', 0)],
                    ['买入总额', f"¥{report.get('total_buy_value', 0):,.0f}"],
                    ['卖出总额', f"¥{report.get('total_sell_value', 0):,.0f}"],
                    ['净现金流', f"¥{report.get('net_cash_flow', 0):,.0f}"],
                    ['交易成本', f"¥{report.get('total_transaction_cost', 0):,.0f}"],
                ], columns=['指标', '数值'])
                summary_df.to_excel(writer, sheet_name='报告摘要', index=False)
                
                # 调仓动作
                if 'actions' in report and report['actions']:
                    actions_df = pd.DataFrame(report['actions'])
                    actions_df.to_excel(writer, sheet_name='调仓动作', index=False)
            
            logger.info(f"✅ 导出再平衡报告：{filepath}")
            return str(filepath)
        except Exception as e:
            logger.error(f"❌ 导出再平衡报告失败：{e}")
            return ""
    
    def export_to_csv(
        self,
        data: List[Dict],
        filename: str
    ) -> str:
        """
        导出 CSV 文件
        
        参数:
            data: 数据列表
            filename: 文件名
        
        返回:
            文件路径
        """
        if not data:
            logger.warning("⚠️ 无数据可导出")
            return ""
        
        filepath = self.output_dir / filename
        
        try:
            df = pd.DataFrame(data)
            df.to_csv(filepath, index=False, encoding='utf-8-sig')
            
            logger.info(f"✅ 导出 CSV：{filepath}")
            return str(filepath)
        except Exception as e:
            logger.error(f"❌ 导出 CSV 失败：{e}")
            return ""
    
    def export_daily_report(
        self,
        dynamic_prices: List[Dict],
        portfolio_summary: Dict,
        risk_report: Dict,
        date: Optional[str] = None
    ) -> str:
        """
        导出每日综合报告
        
        参数:
            dynamic_prices: 动态价格结果
            portfolio_summary: 组合摘要
            risk_report: 风险报告
            date: 日期（可选）
        
        返回:
            文件路径
        """
        if date is None:
            date = datetime.now().strftime('%Y%m%d')
        
        filename = f"daily_report_{date}.xlsx"
        filepath = self.output_dir / filename
        
        try:
            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                # 动态价格
                if dynamic_prices:
                    df_prices = pd.DataFrame(dynamic_prices)
                    df_prices.to_excel(writer, sheet_name='动态价格', index=False)
                
                # 组合摘要
                if portfolio_summary:
                    df_summary = pd.DataFrame([
                        ['总市值', f"¥{portfolio_summary.get('total_value', 0):,.2f}"],
                        ['收益率', portfolio_summary.get('total_return', '0%')],
                    ], columns=['指标', '数值'])
                    df_summary.to_excel(writer, sheet_name='组合摘要', index=False)
                
                # 风险报告
                if risk_report:
                    df_risk = pd.DataFrame([
                        ['预警总数', risk_report.get('total_alerts', 0)],
                        ['风险等级', risk_report.get('risk_level', '正常')],
                    ], columns=['指标', '数值'])
                    df_risk.to_excel(writer, sheet_name='风险报告', index=False)
            
            logger.info(f"✅ 导出每日综合报告：{filepath}")
            return str(filepath)
        except Exception as e:
            logger.error(f"❌ 导出每日综合报告失败：{e}")
            return ""


# ==================== 使用示例 ====================
def example_export_utils():
    """导出工具使用示例"""
    
    print("=" * 80)
    print("🧪 ExportUtils 使用示例")
    print("=" * 80)
    
    from pathlib import Path
    exporter = ExportUtils(output_dir=Path('./output'))
    
    # 模拟动态价格结果
    dynamic_prices = [
        {
            'code': '600938',
            'sector': '油气开采',
            'current_price': 42.24,
            'entry_price': 40.13,
            'stop_loss': 39.20,
            'target_price': 48.50,
            'profit_loss_ratio': 3.21,
            'recommendation': '推荐',
        },
    ]
    
    # 模拟组合摘要
    portfolio_summary = {
        'total_value': 500000,
        'cash': 50000,
        'total_return': '8.5%',
        'transaction_count': 15,
        'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'positions': [
            {'code': '600938', 'quantity': 5000, 'market_value': 211200},
        ],
    }
    
    # 导出动态价格表
    print("\n1️⃣ 导出动态价格表...")
    filepath = exporter.export_dynamic_prices(dynamic_prices)
    print(f"   ✅ {filepath}")
    
    # 导出组合摘要
    print("\n2️⃣ 导出组合摘要...")
    filepath = exporter.export_portfolio_summary(portfolio_summary)
    print(f"   ✅ {filepath}")
    
    # 导出每日综合报告
    print("\n3️⃣ 导出每日综合报告...")
    filepath = exporter.export_daily_report(
        dynamic_prices=dynamic_prices,
        portfolio_summary=portfolio_summary,
        risk_report={'total_alerts': 0, 'risk_level': '正常'}
    )
    print(f"   ✅ {filepath}")
    
    print("\n" + "=" * 80)
    print("✅ ExportUtils 示例运行完成")
    print("=" * 80)


if __name__ == "__main__":
    example_export_utils()