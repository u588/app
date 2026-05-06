#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Plotly 辅助工具函数
====================
提供创建子图、添加参考线等通用可视化辅助函数，
供各图表组件复用，避免重复代码。
"""

from typing import List, Optional

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from visualization.config.theme_config import ThemeConfig, get_default_theme


def create_subplots(rows: int, cols: int, titles: List[str],
                    specs: Optional[list] = None,
                    theme: Optional[ThemeConfig] = None,
                    **kwargs) -> go.Figure:
    """创建带统一主题的子图布局

    Args:
        rows: 行数
        cols: 列数
        titles: 子图标题列表
        specs: 子图规格（支持 secondary_y 等）
        theme: 主题配置

    Returns:
        Plotly Figure 对象
    """
    fig = make_subplots(
        rows=rows, cols=cols,
        subplot_titles=titles,
        vertical_spacing=kwargs.pop('vertical_spacing', 0.08),
        horizontal_spacing=kwargs.pop('horizontal_spacing', 0.08),
        specs=specs,
        **kwargs,
    )
    return fig


def add_reference_line(fig, y: float, text: str = '',
                       row: Optional[int] = None, col: Optional[int] = None,
                       color: str = 'gray', dash: str = 'dash'):
    """添加水平参考线

    Args:
        fig: Plotly Figure
        y: Y 值
        text: 标注文字
        row: 子图行号
        col: 子图列号
        color: 线条颜色
        dash: 线条样式

    Returns:
        修改后的 Figure
    """
    kwargs = dict(line_dash=dash, line_color=color)
    if text:
        kwargs['annotation_text'] = text
    if row is not None:
        kwargs['row'] = row
    if col is not None:
        kwargs['col'] = col
    fig.add_hline(y=y, **kwargs)
    return fig


def add_bar_trace(fig, x, y, name: str, color: str,
                  row: int = 1, col: int = 1,
                  opacity: float = 0.8, showlegend: bool = True,
                  **kwargs):
    """添加柱状图轨迹

    Args:
        fig: Plotly Figure
        x: X 轴数据
        y: Y 轴数据
        name: 轨迹名称
        color: 柱状颜色
        row: 子图行号
        col: 子图列号
        opacity: 透明度
        showlegend: 是否显示图例

    Returns:
        修改后的 Figure
    """
    fig.add_trace(go.Bar(
        x=x, y=y,
        name=name,
        marker_color=color,
        marker_line_width=0,
        opacity=opacity,
        showlegend=showlegend,
        **kwargs,
    ), row=row, col=col)
    return fig


def add_line_trace(fig, x, y, name: str, color: str,
                   row: int = 1, col: int = 1,
                   width: float = 2, dash: str = None,
                   mode: str = 'lines', marker_size: int = 4,
                   fill: Optional[str] = None,
                   showlegend: bool = True,
                   secondary_y: bool = False,
                   **kwargs):
    """添加折线图轨迹

    Args:
        fig: Plotly Figure
        x: X 轴数据
        y: Y 轴数据
        name: 轨迹名称
        color: 线条颜色
        row: 子图行号
        col: 子图列号
        width: 线条宽度
        dash: 线条样式（None/solid/dash/dot）
        mode: 显示模式（lines/lines+markers）
        fill: 填充方式（None/tozeroy/tonexty）
        secondary_y: 是否使用副Y轴

    Returns:
        修改后的 Figure
    """
    line_dict = dict(color=color, width=width)
    if dash:
        line_dict['dash'] = dash

    marker_dict = dict(size=marker_size) if 'markers' in mode else None

    trace_kwargs = dict(
        x=x, y=y,
        name=name,
        mode=mode,
        line=line_dict,
        showlegend=showlegend,
    )
    if marker_dict:
        trace_kwargs['marker'] = marker_dict
    if fill:
        trace_kwargs['fill'] = fill

    fig.add_trace(go.Scatter(**trace_kwargs), row=row, col=col, secondary_y=secondary_y)
    return fig


def compute_yoy_series(dates, values, period: int = 12):
    """计算同比变化序列

    Args:
        dates: 日期序列
        values: 数值序列
        period: 同比周期（月数）

    Returns:
        (dates, yoy_values) 同比变化序列
    """
    yoy_values = []
    yoy_dates = []
    for i in range(period, len(values)):
        prev = values[i - period]
        if prev != 0:
            yoy = (values[i] - prev) / abs(prev) * 100
            yoy_values.append(yoy)
            yoy_dates.append(dates[i])
    return yoy_dates, yoy_values