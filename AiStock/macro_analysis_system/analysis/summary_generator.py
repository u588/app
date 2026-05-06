#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
汇总生成器
===========
基于分析结果和过滤信号，生成人类可读的分析汇总文本。
支持控制台文本输出和 HTML 片段输出。
"""

from typing import Dict, List, Optional
from datetime import datetime

from macro_analysis_system.analysis.filter_engine import FilterEngine, FilteredSignal


class SummaryGenerator:
    """分析汇总生成器

    从分析结果和信号列表中生成结构化的汇总文本。

    Usage:
        generator = SummaryGenerator()
        text = generator.generate_text(outlook, analysis)
        html = generator.generate_html(outlook, analysis, signals)
    """

    # 维度中文名映射
    DIMENSION_LABELS = {
        'economic_growth': '经济增长',
        'prosperity': '景气度',
        'monetary': '货币金融',
        'trade_fx': '贸易外汇',
        'energy_industry': '能源工业',
        'capital_market': '资本市场',
        'international': '国际环境',
    }

    def __init__(self):
        self.filter_engine = FilterEngine()

    def generate_text(self, outlook: Dict, analysis: Dict,
                      include_signals: bool = True) -> str:
        """生成纯文本格式的分析汇总

        Args:
            outlook: 综合展望字典
            analysis: 各维度分析结果
            include_signals: 是否包含信号详情

        Returns:
            格式化的文本字符串
        """
        lines = []
        lines.append("=" * 60)
        lines.append("    中国宏观经济分析汇总")
        lines.append("=" * 60)

        # 综合评分
        lines.append(f"\n综合评分: {outlook['total_score']:.0f}")
        lines.append(f"经济状态: {outlook['status']}")
        lines.append(f"经济展望: {outlook['outlook']}")

        # 各维度评分
        lines.append("\n各维度评分:")
        for key, score in outlook.get('category_scores', {}).items():
            label = self.DIMENSION_LABELS.get(key, key)
            bar = '█' * int(score / 5) + '░' * (20 - int(score / 5))
            lines.append(f"  {label:8s} [{bar}] {score:.0f}")

        # 信号汇总
        if include_signals:
            signals = self.filter_engine.extract_signals(analysis)
            summary = self.filter_engine.get_summary(signals)

            lines.append(f"\n信号统计: 正面{summary['positive']} / "
                         f"负面{summary['negative']} / 中性{summary['neutral']}")

            # 关键正面信号
            if summary['top_positive']:
                lines.append("\n关键正面信号:")
                for s in summary['top_positive']:
                    lines.append(f"  + {s}")

            # 关键负面信号
            if summary['top_negative']:
                lines.append("\n关键负面信号:")
                for s in summary['top_negative']:
                    lines.append(f"  - {s}")

        lines.append("\n" + "=" * 60)
        return '\n'.join(lines)

    def generate_html(self, outlook: Dict, analysis: Dict,
                      signals: Optional[List[FilteredSignal]] = None) -> str:
        """生成 HTML 片段格式的分析汇总

        Args:
            outlook: 综合展望字典
            analysis: 各维度分析结果
            signals: 过滤后的信号列表（可选，None 则自动提取）

        Returns:
            HTML 片段字符串
        """
        if signals is None:
            signals = self.filter_engine.extract_signals(analysis)

        html_parts = []

        # 各维度评分卡片
        for key, score in outlook.get('category_scores', {}).items():
            label = self.DIMENSION_LABELS.get(key, key)
            score_class = 'score-high' if score >= 60 else ('score-mid' if score >= 45 else 'score-low')
            html_parts.append(
                f'<div class="score-card">'
                f'<span class="score-badge {score_class}">{label}: {score:.0f}</span>'
                f'</div>'
            )

        # 信号列表
        dim_signals = {}
        for sig in signals:
            if sig.dimension not in dim_signals:
                dim_signals[sig.dimension] = []
            dim_signals[sig.dimension].append(sig)

        for dim_key, dim_sigs in dim_signals.items():
            label = self.DIMENSION_LABELS.get(dim_key, dim_key)
            html_parts.append(f'<div class="analysis-box">')
            html_parts.append(f'<h3>{label}</h3>')
            for sig in dim_sigs:
                icon = '🟢' if sig.category == 'positive' else ('🔴' if sig.category == 'negative' else '⚪')
                html_parts.append(f'<div class="signal">{icon} {sig.text}</div>')
            html_parts.append(f'</div>')

        return '\n'.join(html_parts)

    def generate_dimension_analysis_html(self, analysis: Dict) -> str:
        """生成各维度分析详情的 HTML 片段

        Args:
            analysis: 各维度分析结果

        Returns:
            HTML 片段
        """
        html_parts = []
        analysis_map = {
            'economic_growth': 'economic_growth',
            'pmi_prosperity': 'prosperity',
            'monetary': 'monetary',
            'trade_fx': 'trade_fx',
            'energy_industry': 'energy_industry',
            'capital_market': 'capital_market',
            'international': 'international',
        }

        for chart_key, dim_key in analysis_map.items():
            if dim_key not in analysis:
                continue
            dim = analysis[dim_key]
            score = dim['score']
            score_class = 'score-high' if score >= 60 else ('score-mid' if score >= 45 else 'score-low')

            html_parts.append(f'<div class="analysis-box">')
            html_parts.append(f'<span class="score-badge {score_class}">评分: {score:.0f}</span>')
            html_parts.append(f'<div style="margin-top: 10px;">')
            for signal in dim.get('signals', []):
                html_parts.append(f'<div class="signal">{signal}</div>')
            html_parts.append(f'</div>')
            html_parts.append(f'</div>')

        return '\n'.join(html_parts)