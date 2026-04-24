#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BatchDashboard：批量对比仪表板组件
包含: create_batch_dashboard, create_risk_return_scatter
"""

import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
from collections import Counter
from typing import List, Dict, Optional, Union, Any
from ..utils.color_scales import RECOMMENDATION_COLORS

def _ensure_df(results: Union[List[Dict], pd.DataFrame]) -> pd.DataFrame:
    """统一转为 DataFrame，兼容字典列表"""
    if isinstance(results, pd.DataFrame):
        return results
    if not results:
        return pd.DataFrame()
    return pd.DataFrame(results)


def create_batch_dashboard(results: Union[List[Dict], pd.DataFrame], config: Optional[Dict] = None) -> go.Figure:
    """创建批量对比仪表板（安全兼容饼图+直方图）"""
    config = config or {}
    df = _ensure_df(results)
    if df.empty:
        return go.Figure().add_annotation(text="无数据", showarrow=False)
    
    # 兼容中英文字段
    sectors = df.get('sector') or df.get('板块')
    recs = df.get('recommendation') or df.get('建议')
    pls = df.get('pl_ratio') or df.get('盈亏比')
    confs = df.get('confidence_factor') or df.get('置信度')
    
    sector_counts = Counter(sectors.dropna()) if isinstance(sectors, pd.Series) else Counter()
    rec_counts = Counter(recs.dropna()) if isinstance(recs, pd.Series) else Counter()
    
    # 严格声明子图类型
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=['板块分布', '建议分布', '盈亏比分布', '置信度分布'],
        specs=[
            [{'type': 'pie'}, {'type': 'pie'}],
            [{'type': 'histogram'}, {'type': 'histogram'}]
        ],
        vertical_spacing=0.12,
        horizontal_spacing=0.1
    )
    
    # 饼图 (Row 1)
    if sector_counts:
        fig.add_trace(go.Pie(
            labels=list(sector_counts.keys()), values=list(sector_counts.values()),
            textinfo='label+percent', textposition='auto', insidetextfont=dict(size=9),
            hovertemplate='<b>%{label}</b><br>数量：%{value}<extra></extra>'
        ), row=1, col=1)
        
    if rec_counts:
        rec_colors = [RECOMMENDATION_COLORS.get(k, '#7f7f7f') for k in rec_counts.keys()]
        fig.add_trace(go.Pie(
            labels=list(rec_counts.keys()), values=list(rec_counts.values()),
            marker_colors=rec_colors, textinfo='label+percent', insidetextfont=dict(size=9),
            hovertemplate='<b>%{label}</b><br>数量：%{value}<extra></extra>'
        ), row=1, col=2)
        
    # 直方图 (Row 2) -> 显式绑定 row/col
    if isinstance(pls, pd.Series) and len(pls) > 0:
        fig.add_trace(go.Histogram(
            x=pls, name='盈亏比', marker_color='#1f77b4', nbinsx=20,
            hovertemplate='<b>盈亏比</b><br>%{x:.1f}x<extra></extra>'
        ), row=2, col=1)
        fig.update_xaxes(title_text='盈亏比 (x)', row=2, col=1)
        fig.update_yaxes(title_text='标的数量', row=2, col=1)
        fig.add_vline(x=2.0, line_dash='dash', line_color='blue', row=2, col=1,
                      annotation_text='阈值', annotation_position='top right')
                  
    if isinstance(confs, pd.Series) and len(confs) > 0:
        fig.add_trace(go.Histogram(
            x=confs, name='置信度', marker_color='#2ca02c', nbinsx=20,
            hovertemplate='<b>置信度</b><br>%{x:.3f}<extra></extra>'
        ), row=2, col=2)
        fig.update_xaxes(title_text='置信度因子', row=2, col=2)
        fig.update_yaxes(title_text='标的数量', row=2, col=2)
        fig.add_vline(x=1.0, line_dash='dash', line_color='gray', row=2, col=2,
                      annotation_text='中性', annotation_position='top right')
                  
    # 全局布局（严格避开 xaxis/yaxis 键）
    fig.update_layout(
        title=config.get('title', f"📊 批量标的对比分析 ({len(results)} 只)"),
        height=config.get('height', 800), width=config.get('width', 1400),
        template=config.get('template', 'plotly_white'),
        hovermode='closest', showlegend=False, margin=dict(l=40, r=40, t=60, b=50)
    )
    
    # 底部指标卡片
    avg_pl = pls.mean() if isinstance(pls, pd.Series) and len(pls) > 0 else 0
    high_conf = sum(1 for c in confs if c >= 1.01) if isinstance(confs, pd.Series) else 0
    strong_rec = rec_counts.get('强烈推荐', 0)
    
    fig.add_annotation(
        x=0.5, y=-0.04,
        text=f"平均盈亏比: {avg_pl:.2f}x | 高置信度: {high_conf} 只 | 强烈推荐: {strong_rec} 只",
        showarrow=False, bgcolor='rgba(240,240,240,0.9)', font=dict(size=11),
        xref='paper', yref='paper'
    )
    return fig


def create_risk_return_scatter(results: Union[List[Dict], pd.DataFrame], config: Optional[Dict] = None) -> go.Figure:
    """创建风险-收益散点图（盈亏比 vs 波动/回撤）"""
    config = config or {}
    df = _ensure_df(results)
    if df.empty:
        return go.Figure().add_annotation(text="无数据", showarrow=False)
    
    # 计算风险(止损空间)与收益(目标空间)
    entry = pd.to_numeric(df.get('entry_price') or df.get('prices', pd.Series()).apply(lambda x: x.get('entry') if isinstance(x, dict) else None), errors='coerce')
    stop = pd.to_numeric(df.get('stop_loss') or df.get('prices', pd.Series()).apply(lambda x: x.get('stop_loss') if isinstance(x, dict) else None), errors='coerce')
    target = pd.to_numeric(df.get('target_price') or df.get('prices', pd.Series()).apply(lambda x: x.get('target') if isinstance(x, dict) else None), errors='coerce')
    
    risk = (entry - stop).clip(lower=0.1)  # 避免除零
    reward = (target - entry).clip(lower=0)
    pl_ratio = reward / risk
    rec = df.get('recommendation') or df.get('建议')
    name = df.get('name') or df.get('名称')
    
    plot_df = pd.DataFrame({
        '风险(止损距离)': risk,
        '预期收益': reward,
        '盈亏比': pl_ratio,
        '建议': rec,
        '名称': name
    }).dropna()
    
    if plot_df.empty:
        return go.Figure().add_annotation(text="数据不足以绘制散点图", showarrow=False)
    
    fig = px.scatter(
        plot_df,
        x='风险(止损距离)', y='预期收益',
        color='建议',
        color_discrete_map=RECOMMENDATION_COLORS,
        size='盈亏比', size_max=30,
        hover_name='名称',
        hover_data={'盈亏比': ':.1f', '风险(止损距离)': ':.2f', '预期收益': ':.2f'},
        title=config.get('title', '🎯 风险-收益分布'),
        labels={'风险(止损距离)': '风险空间 (元)', '预期收益': '目标空间 (元)'}
    )
    
    # 参考线
    fig.add_hline(y=0, line_dash='dot', line_color='gray', opacity=0.3)
    fig.add_vline(x=0, line_dash='dot', line_color='gray', opacity=0.3)
    
    # 盈亏比等值线 (y = k*x)
    for k in [1.5, 2.0, 3.0]:
        max_x = plot_df['风险(止损距离)'].max() * 1.1
        fig.add_trace(go.Scatter(
            x=[0, max_x], y=[0, max_x * k],
            mode='lines', line=dict(dash='dash', color='rgba(0,0,0,0.3)', width=1),
            name=f'{k}x', showlegend=False, hoverinfo='skip'
        ))
    
    fig.update_layout(
        height=config.get('height', 500), width=config.get('width', 900),
        template=config.get('template', 'plotly_white'),
        hovermode='closest',
        legend=dict(orientation='h', yanchor='bottom', y=-0.15, xanchor='center', x=0.5)
    )
    return fig