#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IndicatorScatter：技术指标关联散点图组件
功能：
  - 可视化关键指标状态（✅/⚠️）
  - 颜色编码反映健康度
  - 悬停显示理想区间
"""

import plotly.express as px
import pandas as pd
from typing import Dict, Optional
from ..utils.color_scales import DIAGNOSTIC_STATUS_COLORS

def create_indicator_scatter(
    indicators: Dict,
    prices: Dict,
    config: Optional[Dict] = None
) -> go.Figure:
    """
    创建指标关联散点图
    
    参数:
        indicators: 技术指标字典
        prices: 价格字典（用于计算衍生指标）
        config: 图表配置（可选）
    
    返回:
        Plotly Figure
    """
    config = config or {}
    
    # 提取关键指标
    data = []
    
    # RSI
    rsi = indicators.get('rsi14')
    if rsi is not None:
        status = '✅' if 30 <= rsi <= 70 else '⚠️'
        data.append({
            '指标': 'RSI(14)',
            '值': rsi,
            '理想区间': '30-70',
            '状态': status
        })
    
    # MACD
    macd_hist = indicators.get('macd_hist')
    if macd_hist is not None:
        status = '✅' if macd_hist != 0 else '⚠️'
        data.append({
            '指标': 'MACD',
            '值': macd_hist,
            '理想区间': '≠0 (有方向)',
            '状态': status
        })
    
    # ATR/Price
    atr = indicators.get('atr14')
    close = prices.get('current') or indicators.get('close')
    if atr and close:
        ratio = (atr / close) * 100
        status = '✅' if 1 <= ratio <= 8 else '⚠️'
        data.append({
            '指标': 'ATR/Price',
            '值': f'{ratio:.1f}%',
            '理想区间': '1-8%',
            '状态': status
        })
    
    # Volume Ratio
    volume = indicators.get('volume')
    vol_avg = indicators.get('vol_20d_avg')
    if volume and vol_avg:
        ratio = volume / vol_avg
        status = '✅' if ratio > 1.2 or ratio < 0.8 else '⚠️'
        data.append({
            '指标': 'Volume Ratio',
            '值': f'{ratio:.1f}x',
            '理想区间': '>1.2 (放量) / <0.8 (缩量)',
            '状态': status
        })
    
    # ADX
    adx = indicators.get('adx')
    if adx is not None:
        status = '✅' if adx >= 25 else '⚠️'
        data.append({
            '指标': 'ADX',
            '值': adx,
            '理想区间': '≥25 (强趋势)',
            '状态': status
        })
    
    if not data:
        return go.Figure().add_annotation(text="无指标数据", showarrow=False)
    
    df = pd.DataFrame(data)
    
    # 创建散点图
    fig = px.scatter(
        df,
        x='值',
        y='指标',
        color='状态',
        color_discrete_map=DIAGNOSTIC_STATUS_COLORS,
        size=[15 if s=='✅' else 10 for s in df['状态']],
        hover_data=['理想区间'],
        title='技术指标状态',
        opacity=0.9
    )
    
    # 优化布局
    fig.update_layout(
        xaxis_title='指标值',
        yaxis_title='',
        showlegend=False,
        height=300,
        hovermode='closest'
    )
    
    # 添加参考线（可选）
    if config.get('show_reference_lines', True):
        fig.add_vline(x=0, line_dash='dot', line_color='gray', opacity=0.3)
    
    return fig