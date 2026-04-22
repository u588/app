#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DiagnosticsTree：置信度诊断树状图组件
功能：
  - 将嵌套诊断信息展平为 Treemap
  - 颜色编码反映健康度（得分/状态）
  - 支持点击钻取至明细
"""

import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from typing import Dict, List, Any
from ..utils.color_scales import DIAGNOSTIC_STATUS_COLORS

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
    # 尝试从值中提取数值评分，否则标记为文本状态
    def parse_score(val):
        if isinstance(val, (int, float)):
            return val
        # 尝试从字符串提取 "得分: 0.85" 或类似模式
        import re
        match = re.search(r'(\d+\.?\d*)', str(val))
        return float(match.group(1)) if match else 0.5  # 默认中性
    
    df['score'] = df['value'].apply(parse_score)
    df['status_color'] = df['value'].apply(lambda v: '#2ca02c' if v == '✅' else ('#ff7f0e' if '⚠️' in str(v) else '#7f7f7f'))
    
    # 为 Treemap 构造层级路径
    # 使用 px.treemap 的 path 参数自动处理层级
    # 需要将数据转换为 path 列表: [[根, 维度, 指标, 值], ...]
    tree_records = []
    for _, row in df.iterrows():
        parts = row['path'].split(' > ')
        if len(parts) == 1:
            path = ['根诊断', parts[0]]
            val = row['score']
        elif len(parts) == 2:
            path = ['根诊断', parts[0], parts[1]]
            val = row['score']
        elif len(parts) == 3:
            path = ['根诊断', parts[0], parts[1], parts[2]]
            val = row['score']
        else:
            continue
        tree_records.append({'path': tuple(path), 'value': val, 'display': str(row['value'])})
    
    tree_df = pd.DataFrame(tree_records)
    if tree_df.empty:
        return go.Figure()
        
    # 3. 创建 Treemap
    fig = px.treemap(
        tree_df,
        path=[px.Constant('诊断'), tree_df['path'].apply(lambda x: x[1] if len(x)>1 else ''), 
              tree_df['path'].apply(lambda x: x[2] if len(x)>2 else ''),
              tree_df['path'].apply(lambda x: x[3] if len(x)>3 else '')],
        values='value',
        hover_data={'display': True, 'value': ':.3f'},
        title='技术面诊断树状图',
        color='value',
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