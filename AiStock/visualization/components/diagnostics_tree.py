#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DiagnosticsTree：诊断树状图组件
功能：
  - 将嵌套诊断信息展平为 Treemap
  - 颜色编码反映健康度（得分/状态）
  - 支持点击钻取至明细
"""

import plotly.express as px
import pandas as pd
from typing import Dict, List, Any

def _flatten_diagnostics(diagnostics: Dict, parent: str = '', records: List[Dict] = None) -> List[Dict]:
    """递归展平嵌套诊断字典"""
    if records is None:
        records = []
        
    for key, value in diagnostics.items():
        current_path = f"{parent} > {key}" if parent else key
        if isinstance(value, dict):
            # 如果是字典，继续递归
            _flatten_diagnostics(value, current_path, records)
        else:
            # 叶子节点：记录名称、父节点、值、类型
            records.append({
                'name': key.replace('_', ' ').title(),
                'parent': parent.replace(' > ', '/') if parent else '根诊断',
                'value': value,
                'path': current_path
            })
    return records

def create_diagnostics_tree(diagnostics: Dict) -> go.Figure:
    """
    创建诊断树状图
    
    参数:
        diagnostics: ConfidenceResult.diagnostics 字典
    
    返回:
        Plotly Figure (Treemap)
    """
    # 1. 展平数据
    flat_data = _flatten_diagnostics(diagnostics)
    df = pd.DataFrame(flat_data)
    
    if df.empty:
        return go.Figure().add_annotation(text="无诊断数据", showarrow=False)
    
    # 2. 提取评分与状态
    def parse_score(val):
        if isinstance(val, (int, float)):
            return val
        import re
        match = re.search(r'(\d+\.?\d*)', str(val))
        return float(match.group(1)) if match else 0.5
    
    df['score'] = df['value'].apply(parse_score)
    
    # 3. 创建 Treemap
    fig = px.treemap(
        df,
        path=[px.Constant('诊断'), df['parent'], df['name']],
        values='score',
        hover_data={'value': True, 'score': ':.2f'},
        title='技术面诊断树状图',
        color='score',
        color_continuous_scale=[[0, '#d62728'], [0.5, '#f7b731'], [1, '#2ca02c']],
        range_color=(0, 1)
    )
    
    # 优化显示
    fig.update_traces(
        hovertemplate='<b>%{label}</b><br>值: %{customdata[0]}<br>得分: %{value:.2f}<extra></extra>',
        textposition='middle center',
        textfont=dict(size=11)
    )
    
    fig.update_layout(
        height=400,
        margin=dict(l=20, r=20, t=50, b=20),
        coloraxis_showscale=True,
        coloraxis_colorbar=dict(title='健康得分', tickformat='.0%')
    )
    
    # 添加说明注释
    fig.add_annotation(
        x=0.02, y=-0.05,
        text="💡 点击节点可向上/向下钻取 | 颜色越绿表示指标越健康",
        showarrow=False, font=dict(size=9), bgcolor='rgba(240,240,240,0.8)',
        xref='paper', yref='paper'
    )
    
    return fig