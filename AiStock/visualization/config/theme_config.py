#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
可视化主题配置
===============
定义全局配色方案、字体、布局参数等可视化主题。
所有图表组件共享同一套主题，确保视觉一致性。
支持自定义主题覆盖。
"""

from typing import Dict, Any


class ThemeConfig:
    """可视化主题配置

    提供统一的配色方案、字体和布局参数，
    所有图表组件应通过此配置获取样式参数。

    Usage:
        theme = ThemeConfig()
        primary_color = theme.get_color('primary')
        fig = theme.apply_to(fig, title='GDP趋势')
    """

    # 默认配色方案
    DEFAULT_COLORS = {
        'primary': '#1a5276',
        'secondary': '#2980b9',
        'accent': '#e74c3c',
        'success': '#27ae60',
        'warning': '#f39c12',
        'danger': '#c0392b',
        'info': '#3498db',
        'bg': '#f8f9fa',
        'grid': '#ecf0f1',
        'text': '#2c3e50',
    }

    DEFAULT_PALETTE = [
        '#2980b9', '#e74c3c', '#27ae60', '#f39c12',
        '#8e44ad', '#1abc9c', '#d35400', '#2c3e50',
    ]

    # 默认字体
    DEFAULT_FONT_FAMILY = 'Noto Sans SC, sans-serif'

    # 默认布局参数
    DEFAULT_LAYOUT = {
        'margin': dict(l=60, r=30, t=80, b=50),
        'hovermode': 'x unified',
    }

    def __init__(self, colors: Dict[str, str] = None,
                 palette: list = None,
                 font_family: str = None):
        """初始化主题配置

        Args:
            colors: 自定义颜色映射（覆盖默认值）
            palette: 自定义调色板
            font_family: 自定义字体
        """
        self.colors = {**self.DEFAULT_COLORS, **(colors or {})}
        self.palette = palette or self.DEFAULT_PALETTE[:]
        self.font_family = font_family or self.DEFAULT_FONT_FAMILY
        self.layout_params = {**self.DEFAULT_LAYOUT}

    def get_color(self, name: str) -> str:
        """获取指定颜色"""
        return self.colors.get(name, '#333333')

    def get_palette_color(self, index: int) -> str:
        """获取调色板中指定索引的颜色"""
        return self.palette[index % len(self.palette)]

    def apply_to(self, fig, title: str, height: int = 600):
        """将主题应用到 Plotly Figure

        Args:
            fig: Plotly Figure 对象
            title: 图表标题
            height: 图表高度

        Returns:
            应用主题后的 Figure
        """
        fig.update_layout(
            title=dict(
                text=title,
                font=dict(size=20, color=self.colors['text']),
                x=0.5,
            ),
            template='plotly_white',
            height=height,
            font=dict(family=self.font_family, color=self.colors['text']),
            paper_bgcolor='white',
            plot_bgcolor=self.colors['bg'],
            hovermode=self.layout_params['hovermode'],
            legend=dict(
                orientation='h',
                yanchor='bottom', y=1.02,
                xanchor='right', x=1,
            ),
            margin=self.layout_params['margin'],
        )
        fig.update_xaxes(gridcolor=self.colors['grid'], showgrid=True)
        fig.update_yaxes(gridcolor=self.colors['grid'], showgrid=True)
        return fig

    def get_indicator_colors(self, values: list, threshold: float = 50) -> list:
        """根据阈值生成条件配色列表

        Args:
            values: 数值列表
            threshold: 阈值，>=threshold 为 success 色，<threshold 为 accent 色

        Returns:
            颜色列表
        """
        return [
            self.colors['success'] if v >= threshold else self.colors['accent']
            for v in values
        ]

    def get_score_color(self, score: float) -> str:
        """根据评分获取对应颜色

        Args:
            score: 评分值（0-100）

        Returns:
            颜色值
        """
        if score >= 60:
            return self.colors['success']
        elif score >= 45:
            return self.colors['warning']
        return self.colors['accent']


# 模块级默认主题
_default_theme: ThemeConfig = None


def get_default_theme() -> ThemeConfig:
    """获取默认主题单例"""
    global _default_theme
    if _default_theme is None:
        _default_theme = ThemeConfig()
    return _default_theme