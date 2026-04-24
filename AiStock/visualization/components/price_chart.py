#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PriceChart：价格区间可视化组件
功能：
  - 展示当前价/入场价/止损价/目标价
  - 支持区间色带/悬停提示/动态缩放
  - 业务无关：仅依赖标准结果字典
"""

import plotly.graph_objects as go
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


def create_price_interval_chart(
    result: Dict[str, Any],
    config: Optional[Dict] = None
) -> go.Figure:
    """
    创建价格区间可视化图表
    
    参数:
        result: DynamicPriceEngine 计算结果（标准结构）
        config: 图表配置（可选，覆盖全局配置）
    
    返回:
        Plotly Figure 对象
    """
    config = config or {}
    p = result.get('prices', {})
    
    if not p:
        logger.warning("⚠️ 价格数据为空，无法生成价格区间图")
        return go.Figure()
    
    # 动态计算 Y 轴范围（避免硬编码截断）
    all_p = [v for v in p.values() if isinstance(v, (int, float))]
    if not all_p:
        return go.Figure()
    
    y_min, y_max = min(all_p), max(all_p)
    padding = (y_max - y_min) * config.get('y_padding', 0.3)
    
    fig = go.Figure()
    
    # 1. 当前价（基准点）
    fig.add_trace(go.Scatter(
        x=['当前价'], y=[p['current']],
        mode='markers',
        marker=dict(
            size=config.get('current_marker_size', 16),
            color=config.get('current_color', 'blue'),
            symbol=config.get('current_symbol', 'star'),
            line=dict(width=2, color='white')
        ),
        name='当前价',
        hovertemplate='<b>当前价</b><br>¥%{y:.2f}<extra></extra>'
    ))
    
    # 2. 入场区间（绿色虚线 + 悬停提示）
    entry_range = config.get('entry_range', 0.98)
    entry_low = p['entry'] * entry_range
    entry_high = p['entry'] * (2 - entry_range)  # 对称区间
    
    fig.add_trace(go.Scatter(
        x=['入场区间', '入场区间'], y=[entry_low, entry_high],
        mode='lines',
        line=dict(
            color=config.get('entry_color', 'green'),
            width=config.get('entry_line_width', 4),
            dash=config.get('entry_line_dash', 'dash')
        ),
        name='入场区间',
        hovertemplate='<b>入场区间</b><br>¥' + f'{entry_low:.2f} - {entry_high:.2f}<extra></extra>'
    ))
    
    # 3. 止损价（红色叉号）
    fig.add_trace(go.Scatter(
        x=['止损价'], y=[p['stop_loss']],
        mode='markers+text',
        marker=dict(
            size=config.get('stop_marker_size', 14),
            color=config.get('stop_color', 'red'),
            symbol=config.get('stop_symbol', 'x'),
            line=dict(width=2)
        ),
        text=[config.get('stop_text', '止损')],
        textposition=config.get('stop_text_position', 'bottom center'),
        name='止损价',
        hovertemplate='<b>止损价</b><br>¥%{y:.2f}<extra></extra>'
    ))
    
    # 4. 目标价（蓝色菱形 + 盈亏比标注）✅ 修复 f-string 引号冲突
    pl_ratio = result.get('scores', {}).get('pl_ratio', 0)
    target_text = f"目标 (盈亏比:{pl_ratio:.1f}x)"
    
    fig.add_trace(go.Scatter(
        x=['目标价'], y=[p['target']],
        mode='markers+text',
        marker=dict(
            size=config.get('target_marker_size', 14),
            color=config.get('target_color', 'darkblue'),
            symbol=config.get('target_symbol', 'diamond'),
            line=dict(width=2)
        ),
        text=[target_text],
        textposition=config.get('target_text_position', 'top center'),
        name='目标价',
        hovertemplate=f"<b>目标价</b><br>¥{p['target']:.2f}<br>盈亏比：{pl_ratio:.1f}x<extra></extra>"
    ))
    
    # 5. 潜在盈利区间（背景色带）✅ 使用 add_shape 替代 fill='toself'
    fig.add_shape(
        type="rect", xref="x", yref="y",
        x0=config.get('profit_zone_x0', 0.6), 
        x1=config.get('profit_zone_x1', 1.4),  # 覆盖"入场区间"类别
        y0=entry_low, y1=p['target'],
        fillcolor=config.get('profit_zone_color', 'rgba(0, 128, 0, 0.1)'),
        line_width=0, layer="below"
    )
    
    # 布局配置
    fig.update_layout(
        title=config.get('title', f"🎯 动态价格区间 ({result.get('code', '')} : {result.get('name', '')})"),
        xaxis=dict(
            title=config.get('xaxis_title', '价格类型'),
            showgrid=False,
            categoryorder='array',
            categoryarray=config.get('x_order', ['当前价', '入场区间', '止损价', '目标价'])
        ),
        yaxis=dict(
            title=config.get('yaxis_title', '价格 (元)'),
            range=[y_min - padding, y_max + padding]
        ),
        height=config.get('height', 450),
        hovermode=config.get('hovermode', 'closest'),
        template=config.get('template', 'plotly_white')
    )
    
    # 添加顶部注释（板块/趋势/建议）
    if config.get('show_annotation', True):
        annotation_text = (
            f"板块:{result.get('sector', '未知')} | "
            f"趋势:{result.get('signals', {}).get('trend', 'unknown')} | "
            f"建议:{result.get('recommendation', '未知')}"
        )
        fig.add_annotation(
            x=0.5, y=1.02,
            text=annotation_text,
            showarrow=False,
            bgcolor=config.get('annotation_bgcolor', 'lightgray'),
            font=dict(size=config.get('annotation_font_size', 10)),
            xref='paper', yref='paper'
        )
    
    return fig