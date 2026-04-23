#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SingleStockDashboard：单标六宫格深度分析面板
功能：
  - 价格区间 + 因子分解 + 置信度 + 诊断 + 指标 + 汇总
  - 交互式钻取 + 多维度联动
  - 支持响应式布局
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots
from typing import Dict, Optional, Any
from ..components.price_chart import create_price_interval_chart
from ..components.factor_breakdown import create_factor_breakdown
from ..components.confidence_gauge import create_confidence_gauge
from ..components.diagnostics_tree import create_diagnostics_tree
from ..components.indicator_scatter import create_indicator_scatter

def create_single_stock_dashboard(
    result: Dict[str, Any],
    config: Optional[Dict] = None
) -> go.Figure:
    """
    创建单标六宫格深度分析面板
    
    参数:
        result: 单标的计算结果（含 technical_quality）
        config: 图表配置
    
    返回:
        Plotly Figure
    """
    config = config or {}
    
    if not result or 'prices' not in result:
        return go.Figure().add_annotation(text="无有效数据", showarrow=False)
    
    code = result.get('code', 'unknown')
    name = result.get('name', '未知')
    
    # 1. 创建 3×2 子图布局
    fig = make_subplots(
        rows=3, cols=2,
        subplot_titles=[
            f"{name}({code}) 价格区间",
            "因子分解",
            "置信度评估",
            "诊断详情",
            "指标状态",
            "操作建议"
        ],
        specs=[
            [{'type': 'scatter'}, {'type': 'bar'}],
            [{'type': 'indicator'}, {'type': 'treemap'}],
            [{'type': 'scatter'}, {'type': 'indicator'}]
        ],
        vertical_spacing=0.08,
        horizontal_spacing=0.08,
        row_heights=[0.35, 0.35, 0.30]
    )
    
    # 2. 填充各子图
    
    # 2.1 价格区间图 (1,1)
    price_fig = create_price_interval_chart(result, config.get('price_chart', {}))
    for trace in price_fig.data:
        fig.add_trace(trace, row=1, col=1)
    
    # 2.2 因子分解图 (1,2)
    factors = result.get('factors', {})
    breakdown_fig = create_factor_breakdown(
        technical=factors.get('technical', 1.0),
        fundamental=factors.get('fundamental', 1.0),
        macro=factors.get('macro', 1.0),
        weights=config.get('weights', {'technical': 0.4, 'fundamental': 0.35, 'macro': 0.25}),
        composite=factors.get('composite', 1.0)
    )
    for trace in breakdown_fig.data:
        fig.add_trace(trace, row=1, col=2)
    
    # 2.3 置信度仪表盘 (2,1)
    if 'technical_quality' in result:
        conf_fig = create_confidence_gauge(
            factor=result['technical_quality']['factor'],
            score=result['technical_quality']['score'],
            level=result['technical_quality']['level'],
            breakdown=result['technical_quality'].get('breakdown')
        )
        for trace in conf_fig.data:
            fig.add_trace(trace, row=2, col=1)
    
    # 2.4 诊断树状图 (2,2)
    if 'technical_quality' in result and 'diagnostics' in result['technical_quality']:
        diag_fig = create_diagnostics_tree(result['technical_quality']['diagnostics'])
        for trace in diag_fig.data:
            fig.add_trace(trace, row=2, col=2)
    
    # 2.5 指标关联散点图 (3,1)
    indicator_fig = create_indicator_scatter(
        result.get('signals', {}),
        result.get('prices', {}),
        config.get('indicator_chart', {})
    )
    for trace in indicator_fig.data:
        fig.add_trace(trace, row=3, col=1)
    
    # 2.6 操作建议仪表盘 (3,2)
    suggestion_fig = _create_suggestion_gauge(result)
    for trace in suggestion_fig.data:
        fig.add_trace(trace, row=3, col=2)
    
    # 3. 统一布局
    fig.update_layout(
        title=config.get('title', f"🎯 {name}({code}) 深度分析"),
        height=config.get('height', 1000),
        width=config.get('width', 1400),
        template=config.get('template', 'plotly_white'),
        hovermode='closest',
        showlegend=False,
        margin=dict(l=40, r=40, t=60, b=40)
    )
    
    # 4. 添加交互说明
    fig.add_annotation(
        x=0.5, y=-0.03,
        text="💡 提示：点击图表元素可钻取详情 | 双击图例可隐藏/显示",
        showarrow=False,
        bgcolor='rgba(240,240,240,0.8)',
        font=dict(size=10),
        xref='paper', yref='paper'
    )
    
    return fig


def _create_suggestion_gauge(result: Dict) -> go.Figure:
    """创建操作建议仪表盘"""
    pl_ratio = result.get('scores', {}).get('pl_ratio', 0)
    confidence = result.get('technical_quality', {}).get('factor', 1.0)
    recommendation = result.get('recommendation', '观望')
    
    # 综合评分
    composite = (pl_ratio / 3.0) * 0.6 + ((confidence - 0.98) / 0.04) * 0.4
    composite = max(0, min(1, composite))
    
    # 确定颜色
    if recommendation == '强烈推荐' and pl_ratio >= 2.5:
        color = '#2ca02c'
        text = "✅ 重点关注"
    elif recommendation == '谨慎' or pl_ratio < 1.5:
        color = '#d62728'
        text = "⚠️ 谨慎对待"
    else:
        color = '#1f77b4'
        text = "🔍 正常跟踪"
    
    fig = go.Figure(go.Indicator(
        mode='gauge+number+delta',
        value=composite,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': f"操作建议: {text}"},
        number={'font': {'size': 24}},
        gauge={
            'axis': {'range': [0, 1]},
            'bar': {'color': color},
            'steps': [
                {'range': [0, 0.4], 'color': 'lightcoral'},
                {'range': [0.4, 0.7], 'color': 'lightyellow'},
                {'range': [0.7, 1.0], 'color': 'lightgreen'}
            ],
            'threshold': {
                'line': {'color': 'red', 'width': 4},
                'thickness': 0.75,
                'value': 0.6
            }
        }
    ))
    
    fig.update_layout(height=300, margin=dict(l=20, r=20, t=40, b=20))
    return fig