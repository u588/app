#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
报告生成服务
==============
将图表和分析结果组合为完整的 HTML 报告。
支持自定义模板、多图表布局和交互式图表嵌入。
"""

import os
from typing import Dict, List, Optional, Tuple
from datetime import datetime

import plotly.graph_objects as go
from plotly.io import to_html

from visualization.config.theme_config import ThemeConfig, get_default_theme
from macro_analysis_system.visualization.macro_chart_engine import MacroChartEngine
from macro_analysis_system.analysis.summary_generator import SummaryGenerator
from base_services.logger_service import LoggerService
# from base_services.logger_service import LoggerService, get_global_logger_service


class ReportService:
    """报告生成服务

    将 MacroChartEngine 生成的图表与 SummaryGenerator 生成的分析文本
    组合为完整的交互式 HTML 报告。

    Usage:
        service = ReportService(chart_engine, summary_generator)
        service.save_html('/path/to/report.html', outlook, figures)
    """

    def __init__(self, chart_engine: Optional[MacroChartEngine] = None,
                 summary_generator: Optional[SummaryGenerator] = None,
                 theme: Optional[ThemeConfig] = None,
                 logger: Optional[LoggerService] = None):
        """初始化报告服务

        Args:
            chart_engine: 图表引擎实例
            summary_generator: 汇总生成器实例
            theme: 主题配置
            logger: 日志服务实例
        """
        self.chart_engine = chart_engine
        self.summary_generator = summary_generator or SummaryGenerator()
        self.theme = theme or get_default_theme()
        self._logger = logger.get_logger('report_service')
        # self._logger = (logger or get_global_logger_service()).get_logger('report_service')

    def generate_html(self, outlook: Dict, analysis: Dict,
                      figures: List[Tuple[str, go.Figure, str]]) -> str:
        """生成完整的 HTML 报告内容

        Args:
            outlook: 综合展望字典
            analysis: 各维度分析结果
            figures: (key, figure, name) 元组列表

        Returns:
            HTML 字符串
        """
        html_parts = []

        # HTML 头部和样式
        html_parts.append(self._get_html_header())

        # 报告头部
        now = datetime.now().strftime('%Y年%m月%d日')
        html_parts.append(f"""
    <div class="header">
        <h1>中国宏观经济分析报告</h1>
        <p>数据更新至 {now} | 综合评分: {outlook['total_score']:.0f} | 经济状态: {outlook['status']}</p>
    </div>
""")

        # 导航栏
        html_parts.append(self._get_navigation(figures))

        # 主内容区
        html_parts.append('    <div class="container">')

        # 图表与分析
        analysis_map = {
            'economic_growth': 'economic_growth',
            'pmi_prosperity': 'prosperity',
            'monetary': 'monetary',
            'trade_fx': 'trade_fx',
            'energy_industry': 'energy_industry',
            'capital_market': 'capital_market',
            'international': 'international',
        }

        for key, fig, name in figures:
            html_parts.append(f'        <div class="chart-section" id="{key}">')
            html_parts.append(f'            <h2>{name}</h2>')

            # 添加分析文本
            if key in analysis_map:
                a_key = analysis_map[key]
                if a_key in analysis:
                    html_parts.append(
                        self._generate_analysis_html(analysis[a_key])
                    )

            chart_html = to_html(fig, full_html=False, include_plotlyjs=False)
            html_parts.append(f'            {chart_html}')
            html_parts.append(f'        </div>')

        # 展望部分
        html_parts.append(self._generate_outlook_html(outlook))

        # HTML 尾部
        html_parts.append(self._get_html_footer())

        return '\n'.join(html_parts)

    def save_html(self, filepath: str, outlook: Dict, analysis: Dict,
                  figures: List[Tuple[str, go.Figure, str]]):
        """生成并保存 HTML 报告

        Args:
            filepath: 输出文件路径
            outlook: 综合展望字典
            analysis: 各维度分析结果
            figures: 图表列表
        """
        html_content = self.generate_html(outlook, analysis, figures)

        os.makedirs(os.path.dirname(filepath) or '.', exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)

        self._logger.info(f"HTML报告已保存: {filepath}")

    def _generate_analysis_html(self, dim_result: Dict) -> str:
        """生成单个维度的分析 HTML 片段"""
        score = dim_result['score']
        score_class = 'score-high' if score >= 60 else ('score-mid' if score >= 45 else 'score-low')

        parts = [f'            <div class="analysis-box">']
        parts.append(f'                <span class="score-badge {score_class}">评分: {score:.0f}</span>')
        parts.append(f'                <div style="margin-top: 10px;">')
        for signal in dim_result.get('signals', []):
            parts.append(f'                <div class="signal">{signal}</div>')
        parts.append(f'                </div>')
        parts.append(f'            </div>')

        return '\n'.join(parts)

    def _generate_outlook_html(self, outlook: Dict) -> str:
        """生成经济展望 HTML 片段"""
        total = outlook['total_score']
        score_class = 'score-high' if total >= 60 else ('score-mid' if total >= 45 else 'score-low')

        category_labels = {
            'economic_growth': '经济增长', 'prosperity': '景气度',
            'monetary': '货币金融', 'trade_fx': '贸易外汇',
            'energy_industry': '能源工业', 'capital_market': '资本市场',
            'international': '国际环境',
        }

        score_cards = []
        for key, label in category_labels.items():
            if key in outlook.get('category_scores', {}):
                s = outlook['category_scores'][key]
                sc = 'score-high' if s >= 60 else ('score-mid' if s >= 45 else 'score-low')
                score_cards.append(f'                        <div><span class="score-badge {sc}">{label}: {s:.0f}</span></div>')

        cards_html = '\n'.join(score_cards)

        return f"""
        <div class="chart-section" id="outlook">
            <h2>经济展望与预期</h2>
            <div class="analysis-box">
                <span class="score-badge {score_class}">
                    综合评分: {total:.0f}
                </span>
                <div style="margin-top: 15px; font-size: 16px; line-height: 2;">
                    {outlook['outlook']}
                </div>
                <div style="margin-top: 15px;">
                    <strong>各维度评分：</strong>
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; margin-top: 10px;">
{cards_html}
                    </div>
                </div>
            </div>
        </div>
"""

    def _get_html_header(self) -> str:
        """获取 HTML 头部和样式"""
        return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>中国宏观经济分析报告</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Noto Sans SC', 'Microsoft YaHei', sans-serif; background: #f0f2f5; color: #2c3e50; }
        .header { background: linear-gradient(135deg, #1a5276 0%, #2980b9 100%); color: white; padding: 40px 20px; text-align: center; }
        .header h1 { font-size: 32px; margin-bottom: 10px; }
        .header p { font-size: 16px; opacity: 0.9; }
        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
        .chart-section { background: white; border-radius: 12px; margin: 20px 0; padding: 20px; box-shadow: 0 2px 12px rgba(0,0,0,0.08); }
        .chart-section h2 { font-size: 20px; color: #1a5276; margin-bottom: 15px; padding-bottom: 10px; border-bottom: 2px solid #ecf0f1; }
        .analysis-box { background: #f8f9fa; border-left: 4px solid #2980b9; padding: 15px 20px; margin: 15px 0; border-radius: 0 8px 8px 0; line-height: 1.8; }
        .analysis-box .signal { margin: 5px 0; padding-left: 15px; position: relative; }
        .analysis-box .signal::before { content: '\\2022'; position: absolute; left: 0; color: #2980b9; font-weight: bold; }
        .score-badge { display: inline-block; padding: 5px 15px; border-radius: 20px; color: white; font-weight: bold; font-size: 14px; }
        .score-high { background: #27ae60; }
        .score-mid { background: #f39c12; }
        .score-low { background: #e74c3c; }
        .nav { position: sticky; top: 0; background: white; z-index: 100; padding: 10px 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); display: flex; justify-content: center; gap: 15px; flex-wrap: wrap; }
        .nav a { color: #2980b9; text-decoration: none; padding: 5px 12px; border-radius: 4px; font-size: 13px; transition: all 0.2s; }
        .nav a:hover { background: #2980b9; color: white; }
        .footer { text-align: center; padding: 30px; color: #95a5a6; font-size: 13px; }
    </style>
</head>
<body>
"""

    def _get_navigation(self, figures: List[Tuple[str, go.Figure, str]]) -> str:
        """生成导航栏 HTML"""
        parts = ['    <div class="nav">']
        for key, _, name in figures:
            parts.append(f'        <a href="#{key}">{name}</a>')
        parts.append('    </div>')
        return '\n'.join(parts)

    def _get_html_footer(self) -> str:
        """获取 HTML 尾部"""
        return """
    <div class="footer">
        本报告由宏观经济分析系统自动生成，数据来源：通达信扩展市场API，仅供参考，不构成投资建议。
    </div>
    <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
</body>
</html>
"""