#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PortfolioChart：组合对比可视化组件
"""
import plotly.express as px
import pandas as pd
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

def create_portfolio_comparison_chart(results: List[Dict[str, Any]], config: Optional[Dict] = None) -> px.scatter:
    config = config or {}
    if not results:
        logger.warning("⚠️ 批量结果为空")
        return px.scatter()
    
    df = pd.DataFrame([{
        '代码': r['code'], '名称': r.get('name', '未知'), '板块': r['sector'],
        '盈亏比': float(r['scores']['pl_ratio']), '综合因子': float(r['factors']['composite']),
        '建议': r['recommendation'], '入场价': float(r['prices']['entry']),
        '目标价': float(r['prices']['target'])
    } for r in results])
    
    color_map = {'强烈推荐': '#2ca02c', '推荐': '#1f77b4', '观望': '#ff7f0e', '谨慎': '#d62728'}
    
    fig = px.scatter(df, x=config.get('x_axis', '综合因子'), y=config.get('y_axis', '盈亏比'),
                     color=config.get('color_by', '建议'), color_discrete_map=color_map,
                     size=config.get('size_by', '目标价'), hover_name='名称',
                     title=config.get('title', '🎯 批量标的对比'),
                     labels={'综合因子': '综合调整因子', '盈亏比': '盈亏比 (x)'},
                     size_range=config.get('size_range', [10, 30]), opacity=0.85)
    
    fig.add_vline(x=1.0, line_dash='dash', line_color='gray', annotation_text='中性因子')
    fig.add_hline(y=2.0, line_dash='dash', line_color='blue', annotation_text='盈亏比阈值')
    fig.update_layout(height=500, hovermode='closest', template=config.get('template', 'plotly_white'))
    return fig