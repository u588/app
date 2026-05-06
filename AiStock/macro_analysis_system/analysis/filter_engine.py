#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
信号过滤引擎
=============
对分析结果中的信号进行过滤、排序和权重标注。
可用于提取关键信号、去除噪声信号、按重要性排序输出。
"""

from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class FilteredSignal:
    """过滤后的信号

    Attributes:
        dimension: 所属维度
        text: 信号文本
        score_impact: 对评分的影响值
        priority: 优先级 (1=高, 2=中, 3=低)
        category: 信号类别 (positive/negative/neutral)
    """
    dimension: str
    text: str
    score_impact: int
    priority: int
    category: str


class FilterEngine:
    """信号过滤引擎

    从分析结果中提取、过滤和排序信号。

    Usage:
        engine = FilterEngine()
        signals = engine.extract_signals(analyzer.analysis)
        key_signals = engine.filter_by_priority(signals, priority=1)
    """

    # 关键词权重映射
    KEYWORD_PRIORITY = {
        '强劲': 1, '活跃': 1, '充裕': 1, '扩张': 1, '积极': 1,
        '疲软': 1, '收缩': 1, '承压': 1, '下行': 1, '不足': 1,
        '平稳': 2, '适度': 2, '温和': 2, '稳定': 2,
        '偏弱': 2, '放缓': 2, '偏紧': 2,
        '企稳': 3, '持平': 3, '一般': 3,
    }

    def extract_signals(self, analysis: Dict[str, Dict]) -> List[FilteredSignal]:
        """从分析结果中提取所有信号

        Args:
            analysis: 各维度分析结果字典

        Returns:
            过滤后的信号列表
        """
        signals = []
        for dim_key, dim_result in analysis.items():
            base_score = dim_result.get('score', 50)
            for signal_text in dim_result.get('signals', []):
                # 推断评分影响
                score_impact = self._infer_score_impact(signal_text)

                # 判断信号类别
                category = self._classify_signal(signal_text)

                # 推断优先级
                priority = self._infer_priority(signal_text)

                signals.append(FilteredSignal(
                    dimension=dim_key,
                    text=signal_text,
                    score_impact=score_impact,
                    priority=priority,
                    category=category,
                ))

        return signals

    def filter_by_priority(self, signals: List[FilteredSignal],
                           priority: int = 1) -> List[FilteredSignal]:
        """按优先级过滤信号

        Args:
            signals: 信号列表
            priority: 最低优先级（1=仅高优先级）

        Returns:
            过滤后的信号列表
        """
        return [s for s in signals if s.priority <= priority]

    def filter_by_category(self, signals: List[FilteredSignal],
                           category: str = 'positive') -> List[FilteredSignal]:
        """按信号类别过滤

        Args:
            signals: 信号列表
            category: 信号类别 (positive/negative/neutral)

        Returns:
            过滤后的信号列表
        """
        return [s for s in signals if s.category == category]

    def sort_by_impact(self, signals: List[FilteredSignal],
                       descending: bool = True) -> List[FilteredSignal]:
        """按评分影响排序信号

        Args:
            signals: 信号列表
            descending: 是否降序排列

        Returns:
            排序后的信号列表
        """
        return sorted(signals, key=lambda s: abs(s.score_impact), reverse=descending)

    def get_summary(self, signals: List[FilteredSignal]) -> Dict:
        """获取信号汇总统计

        Args:
            signals: 信号列表

        Returns:
            汇总统计字典
        """
        positive = [s for s in signals if s.category == 'positive']
        negative = [s for s in signals if s.category == 'negative']
        neutral = [s for s in signals if s.category == 'neutral']

        return {
            'total': len(signals),
            'positive': len(positive),
            'negative': len(negative),
            'neutral': len(neutral),
            'high_priority': len([s for s in signals if s.priority == 1]),
            'top_positive': [s.text for s in self.sort_by_impact(positive)[:3]],
            'top_negative': [s.text for s in self.sort_by_impact(negative)[:3]],
        }

    def _classify_signal(self, text: str) -> str:
        """判断信号类别"""
        positive_keywords = ['强劲', '活跃', '充裕', '扩张', '积极', '向好', '充足',
                             '复苏', '改善', '看好', '升温', '宽松']
        negative_keywords = ['疲软', '收缩', '承压', '下行', '不足', '偏弱', '放缓',
                             '退潮', '撤离', '贬值', '偏紧', '倒挂', '走弱', '外流']

        pos_count = sum(1 for kw in positive_keywords if kw in text)
        neg_count = sum(1 for kw in negative_keywords if kw in text)

        if pos_count > neg_count:
            return 'positive'
        elif neg_count > pos_count:
            return 'negative'
        return 'neutral'

    def _infer_score_impact(self, text: str) -> int:
        """推断信号的评分影响方向和量级"""
        if any(kw in text for kw in ['强劲', '充裕', '积极', '看好']):
            return 10
        elif any(kw in text for kw in ['活跃', '扩张', '复苏', '改善']):
            return 8
        elif any(kw in text for kw in ['疲软', '收缩', '下行', '退潮']):
            return -8
        elif any(kw in text for kw in ['不足', '偏弱', '承压', '贬值']):
            return -5
        elif any(kw in text for kw in ['平稳', '适度', '稳定']):
            return 3
        return 0

    def _infer_priority(self, text: str) -> int:
        """推断信号优先级"""
        for keyword, priority in self.KEYWORD_PRIORITY.items():
            if keyword in text:
                return priority
        return 3