#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ComparisonTool：多标的对比分析工具
功能：
  - 标的 vs 板块均值对比
  - 标的 vs 推荐列表对比
  - 多维度雷达图 + 差异高亮
"""

import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any

def create_comparison_chart(
    target_result: Dict,
    sector_results: Optional[List[Dict]] = None,
    recommended_results: Optional[List[Dict]] = None,
    config: Optional[Dict] = None
) -> go.Figure:
    """
    创建对比分析图表
    
    参数:
        target_result: 目标标的结果
        sector_results: 同板块其他标的（用于板块对比）
        recommended_results: 推荐列表（用于推荐对比）
        config: 图表配置
    
    返回:
        Plotly Figure
    """
    config = config or {}
    
    # 1. 准备对比数据
    target = {
        'name': target_result['name'],
        'pl_ratio': target_result['scores']['pl_ratio'],
        'confidence': target_result.get('technical_quality', {}).get('factor', 1.0),
        'fundamental': target_result['scores']['fundamental'],
        'entry': target_result['prices']['entry']
    }
    
    # 板块均值
    sector_avg = None
    if sector_results:
        sector_avg = {
            'name': f"{target_result['sector']} 均值",
            'pl_ratio': np.mean([r['scores']['pl_ratio'] for r in sector_results]),
            'confidence': np.mean([r.get('technical_quality', {}).get('factor', 1.0) for r in sector_results]),
            'fundamental': np.mean([r['scores']['fundamental'] for r in sector_results])
        }
    
    # 推荐列表均值
    rec_avg = None
    if recommended_results:
        rec_avg = {
            'name': '推荐列表均值',
            'pl_ratio': np.mean([r['scores']['pl_ratio'] for r in recommended_results]),
            'confidence': np.mean([r.get('technical_quality', {}).get('factor', 1.0) for r in recommended_results]),
            'fundamental': np.mean([r['scores']['fundamental'] for r in recommended_results])
        }
    
    # 2. 创建雷达图
    fig = go.Figure()
    
    # 目标标的
    fig.add_trace(go.Scatterpolar(
        r=[target['pl_ratio']/3, target['confidence'], target['fundamental']/100],
        theta=['盈亏比', '置信度', '基本面'],
        fill='toself',
        name=target['name'],
        line_color='#1f77b4',
        fillcolor='rgba(31, 119, 180, 0.2)'
    ))
    
    # 板块均值（可选）
    if sector_avg:
        fig.add_trace(go.Scatterpolar(
            r=[sector_avg['pl_ratio']/3, sector_avg['confidence'], sector_avg['fundamental']/100],
            theta=['盈亏比', '置信度', '基本面'],
            fill='toself',
            name=sector_avg['name'],
            line_color='#ff7f0e',
            fillcolor='rgba(255, 127, 14, 0.1)',
            line=dict(dash='dash')
        ))
    
    # 推荐均值（可选）
    if rec_avg:
        fig.add_trace(go.Scatterpolar(
            r=[rec_avg['pl_ratio']/3, rec_avg['confidence'], rec_avg['fundamental']/100],
            theta=['盈亏比', '置信度', '基本面'],
            fill='toself',
            name=rec_avg['name'],
            line_color='#2ca02c',
            fillcolor='rgba(44, 160, 44, 0.1)',
            line=dict(dash='dot')
        ))
    
    # 3. 布局优化
    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 1])
        ),
        title=config.get('title', f"📊 {target['name']} 对比分析"),
        height=config.get('height', 500),
        width=config.get('width', 700),
        template=config.get('template', 'plotly_white'),
        showlegend=True,
        legend=dict(orientation='h', yanchor='bottom', y=-0.1, xanchor='center', x=0.5)
    )
    
    # 4. 添加差异标注
    if sector_avg:
        # 标注目标与板块的差异
        for i, (metric, target_val, sector_val) in enumerate([
            ('盈亏比', target['pl_ratio'], sector_avg['pl_ratio']),
            ('置信度', target['confidence'], sector_avg['confidence']),
            ('基本面', target['fundamental'], sector_avg['fundamental'])
        ]):
            diff = target_val - sector_val
            if abs(diff) > 0.1:  # 显著差异
                symbol = '📈' if diff > 0 else '📉'
                fig.add_annotation(
                    x=0.5 + i*0.2, y=1.05,
                    text=f"{symbol}{metric} {diff:+.1f}",
                    showarrow=False,
                    font=dict(size=9, color='#2ca02c' if diff>0 else '#d62728'),
                    xref='paper', yref='paper'
                )
    
    return fig


def create_price_comparison_table(
    target_result: Dict,
    comparison_results: List[Dict],
    config: Optional[Dict] = None
) -> go.Figure:
    """
    创建价格对比表格
    
    参数:
        target_result: 目标标的
        comparison_results: 对比标的列表
        config: 配置
    
    返回:
        Plotly Figure (Table)
    """
    # 准备表格数据
    rows = {
        '标的': [target_result['name']] + [r['name'] for r in comparison_results[:5]],
        '代码': [target_result['code']] + [r['code'] for r in comparison_results[:5]],
        '入场价': [f"¥{target_result['prices']['entry']}"] + [f"¥{r['prices']['entry']}" for r in comparison_results[:5]],
        '止损价': [f"¥{target_result['prices']['stop_loss']}"] + [f"¥{r['prices']['stop_loss']}" for r in comparison_results[:5]],
        '目标价': [f"¥{target_result['prices']['target']}"] + [f"¥{r['prices']['target']}" for r in comparison_results[:5]],
        '盈亏比': [f"{target_result['scores']['pl_ratio']:.1f}x"] + [f"{r['scores']['pl_ratio']:.1f}x" for r in comparison_results[:5]],
        '建议': [target_result['recommendation']] + [r['recommendation'] for r in comparison_results[:5]]
    }
    
    # 创建表格
    fig = go.Figure(data=[go.Table(
        header=dict(
            values=[f'<b>{k}</b>' for k in rows.keys()],
            fill_color='royalblue',
            font=dict(color='white', size=11)
        ),
        cells=dict(
            values=list(rows.values()),
            fill_color=[
                ['white'] * len(rows['标的']),  # 标的
                ['white'] * len(rows['标的']),  # 代码
                ['rgba(31,119,180,0.1)'] * len(rows['标的']),  # 入场价
                ['rgba(214,39,40,0.1)'] * len(rows['标的']),  # 止损价
                ['rgba(44,160,44,0.1)'] * len(rows['标的']),  # 目标价
                ['white'] * len(rows['标的']),  # 盈亏比
                ['white'] * len(rows['标的'])   # 建议
            ],
            align='center',
            font=dict(size=10)
        )
    )])
    
    fig.update_layout(
        title=config.get('title', '💰 价格对比'),
        height=config.get('height', 300),
        margin=dict(l=20, r=20, t=40, b=20)
    )
    
    return fig