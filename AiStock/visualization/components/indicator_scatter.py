#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IndicatorScatter：技术指标关联散点图组件
功能：
  - 可视化关键指标状态（✅/⚠️）
  - 数值型坐标 + 格式化文本显示
  - 颜色编码反映健康度
"""

import plotly.graph_objects as go
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
    创建指标关联散点图（修复数值/文本分离问题）
    
    参数:
        indicators: 技术指标字典（需包含 rsi14, macd_hist, atr14, volume, vol_20d_avg, adx 等）
        prices: 价格字典（用于计算衍生指标）
        config: 图表配置（可选）
    
    返回:
        Plotly Figure
    """
    config = config or {}
    
    # 1. 准备数据（数值列 + 显示列分离）
    data = []
    
    # RSI(14)
    rsi = indicators.get('rsi14')
    if rsi is not None:
        status = '✅' if 30 <= rsi <= 70 else '⚠️'
        data.append({
            '指标': 'RSI(14)',
            'x_value': rsi,              # ✅ 数值列：用于绘图坐标
            'x_display': f'{rsi:.1f}',   # ✅ 显示列：用于悬停/标签
            '理想区间': '30-70',
            '状态': status
        })
    
    # MACD
    macd_hist = indicators.get('macd_hist')
    if macd_hist is not None:
        status = '✅' if macd_hist != 0 else '⚠️'
        data.append({
            '指标': 'MACD',
            'x_value': macd_hist,
            'x_display': f'{macd_hist:.3f}',
            '理想区间': '≠0 (有方向)',
            '状态': status
        })
    
    # ATR/Price (%)
    atr = indicators.get('atr14')
    close = prices.get('current') or indicators.get('close')
    if atr and close and close > 0:
        ratio_pct = (atr / close) * 100
        status = '✅' if 1 <= ratio_pct <= 8 else '⚠️'
        data.append({
            '指标': 'ATR/Price',
            'x_value': ratio_pct,
            'x_display': f'{ratio_pct:.1f}%',
            '理想区间': '1-8%',
            '状态': status
        })
    
    # Volume Ratio ✅ 核心修复：数值/文本分离
    volume = indicators.get('volume')
    vol_avg = indicators.get('vol_20d_avg')
    if volume and vol_avg and vol_avg > 0:
        ratio = volume / vol_avg
        status = '✅' if ratio > 1.2 or ratio < 0.8 else '⚠️'
        data.append({
            '指标': 'Volume Ratio',
            'x_value': ratio,            # ✅ 数值：1.5 → 可绘图
            'x_display': f'{ratio:.1f}x', # ✅ 文本：1.5x → 可显示
            '理想区间': '>1.2 (放量) / <0.8 (缩量)',
            '状态': status
        })
    
    # ADX
    adx = indicators.get('adx')
    if adx is not None:
        status = '✅' if adx >= 25 else '⚠️'
        data.append({
            '指标': 'ADX',
            'x_value': adx,
            'x_display': f'{adx:.1f}',
            '理想区间': '≥25 (强趋势)',
            '状态': status
        })
    
    if not data:
        return go.Figure().add_annotation(text="无指标数据", showarrow=False)
    
    df = pd.DataFrame(data)
    
    # 2. 创建散点图（使用 x_value 绘图，x_display 显示）
    fig = px.scatter(
        df,
        x='x_value',        # ✅ 数值列：确保坐标可计算
        y='指标',
        color='状态',
        color_discrete_map=DIAGNOSTIC_STATUS_COLORS,
        size=[15 if s=='✅' else 10 for s in df['状态']],
        text='x_display',   # ✅ 格式化文本：显示在点上
        hover_data={
            'x_value': False,  # 隐藏原始数值
            'x_display': True, # 显示格式化值
            '理想区间': True,
            '状态': True
        },
        title='技术指标状态',
        opacity=0.9
    )
    
    # 3. 优化文本显示
    fig.update_traces(
        textposition='middle right',
        textfont=dict(size=10, color='#333'),
        hovertemplate='<b>%{y}</b><br>值：%{customdata[0]}<br>区间：%{customdata[1]}<br>状态：%{customdata[2]}<extra></extra>'
    )
    
    # 4. 布局优化
    fig.update_layout(
        xaxis_title='指标值',
        yaxis_title='',
        showlegend=False,
        height=300,
        hovermode='closest',
        margin=dict(l=40, r=100, t=30, b=20)  # ✅ 右侧留白给文本
    )
    
    # 5. 添加参考线（可选）
    if config.get('show_reference_lines', True):
        # RSI 参考线
        fig.add_vrect(x0=30, x1=70, fillcolor="rgba(44,160,44,0.1)", line_width=0, layer='below')
        # ATR/Price 参考线
        fig.add_vrect(x0=1, x1=8, fillcolor="rgba(44,160,44,0.1)", line_width=0, layer='below', y0=0.4, y1=0.6)
    
    return fig