#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DashboardChart：综合仪表盘组件
"""
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

def create_dashboard_chart(results: List[Dict[str, Any]], config: Optional[Dict] = None) -> go.Figure:
    config = config or {}
    if not results:
        return go.Figure()
    
    # 简化版：上下布局，上部价格/因子，下部组合散点
    fig = make_subplots(rows=2, cols=1, subplot_titles=["单标分析示例", "组合分布"],
                        vertical_spacing=0.15, row_heights=[0.4, 0.6])
    
    # 这里仅做框架示例，实际可循环注入组件图
    # 实际项目中建议将组件图提取 data 后合并到 subplot
    fig.update_layout(height=800, title="📈 AiStock 动态价格仪表盘",
                      hovermode='closest', template=config.get('template', 'plotly_white'))
    return fig