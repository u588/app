# #!/usr/bin/env python3
# # -*- coding: utf-8 -*-
# """
# PortfolioChart：组合对比可视化组件
# """
# import plotly.express as px
# import pandas as pd
# from typing import List, Dict, Any, Optional
# import logging

# logger = logging.getLogger(__name__)

# def create_portfolio_comparison_chart(results: List[Dict[str, Any]], config: Optional[Dict] = None) -> px.scatter:
#     config = config or {}
#     if not results:
#         logger.warning("⚠️ 批量结果为空")
#         return px.scatter()
    
#     df = pd.DataFrame([{
#         '代码': r['code'], '名称': r.get('name', '未知'), '板块': r['sector'],
#         '盈亏比': float(r['scores']['pl_ratio']), '综合因子': float(r['factors']['composite']),
#         '建议': r['recommendation'], '入场价': float(r['prices']['entry']),
#         '目标价': float(r['prices']['target'])
#     } for r in results])
    
#     color_map = {'强烈推荐': '#2ca02c', '推荐': '#1f77b4', '观望': '#ff7f0e', '谨慎': '#d62728'}
    
#     fig = px.scatter(df, x=config.get('x_axis', '综合因子'), y=config.get('y_axis', '盈亏比'),
#                      color=config.get('color_by', '建议'), color_discrete_map=color_map,
#                      size=config.get('size_by', '目标价'), hover_name='名称',
#                      title=config.get('title', '🎯 批量标的对比'),
#                      labels={'综合因子': '综合调整因子', '盈亏比': '盈亏比 (x)'},
#                      size_range=config.get('size_range', [10, 30]), opacity=0.85)
    
#     fig.add_vline(x=1.0, line_dash='dash', line_color='gray', annotation_text='中性因子')
#     fig.add_hline(y=2.0, line_dash='dash', line_color='blue', annotation_text='盈亏比阈值')
#     fig.update_layout(height=500, hovermode='closest', template=config.get('template', 'plotly_white'))
#     return fig

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PortfolioChart：组合对比可视化组件（已修复 size_range 报错）
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
    
    # 1. 数据清洗与转换（确保原生类型）
    df = pd.DataFrame([{
        '代码': r['code'], 
        '名称': r.get('name', '未知'), 
        '板块': r['sector'],
        '盈亏比': float(r['scores']['pl_ratio']), 
        '综合因子': float(r['factors']['composite']),
        '建议': r['recommendation'], 
        '入场价': float(r['prices']['entry']),
        '目标价': float(r['prices']['target'])
    } for r in results])
    
    # 2. 颜色映射
    color_map = {'强烈推荐': '#2ca02c', '推荐': '#1f77b4', '观望': '#ff7f0e', '谨慎': '#d62728'}
    
    # 3. 安全提取 size 列名（防止配置列不存在）
    size_col = config.get('size_by', '目标价')
    if size_col not in df.columns:
        size_col = None
    
    # 4. 绘制散点图（移除非法的 size_range 参数）
    fig = px.scatter(
        df, 
        x=config.get('x_axis', '综合因子'), 
        y=config.get('y_axis', '盈亏比'),
        color=config.get('color_by', '建议'), 
        color_discrete_map=color_map,
        size=size_col, 
        hover_name='名称',
        title=config.get('title', '🎯 批量标的对比'),
        labels={'综合因子': '综合调整因子', '盈亏比': '盈亏比 (x)'},
        opacity=0.85
    )
    
    # 5. 可选：手动控制气泡大小范围（替代原 size_range）
    if size_col:
        # Plotly 官方推荐的气泡面积控制公式：sizeref = 2. * max_size / (desired_max_radius ** 2)
        max_val = df[size_col].max()
        fig.update_traces(
            marker=dict(
                sizeref=2.0 * max_val / (30 ** 2),  # 30 为期望的最大像素半径
                sizemode='area'
            )
        )
    
    # 6. 添加参考线
    fig.add_vline(x=1.0, line_dash='dash', line_color='gray', annotation_text='中性因子')
    fig.add_hline(y=2.0, line_dash='dash', line_color='blue', annotation_text='盈亏比阈值')
    
    fig.update_layout(height=500, hovermode='closest', template=config.get('template', 'plotly_white'))
    return fig