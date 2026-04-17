#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PlotlyRenderer：Plotly 图表渲染器
功能：
  - 支持散点/折线/柱状/蜡烛图/热力图等
  - 交互式悬停/缩放/筛选
  - HTML/PNG/PDF 多格式导出
"""

import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from .base_renderer import BaseRenderer
from typing import Dict, Any, Union
import pandas as pd
import logging

logger = logging.getLogger(__name__)


class PlotlyRenderer(BaseRenderer):
    """Plotly 图表渲染器"""
    
    def render(self, data: Union[pd.DataFrame, Dict], **kwargs) -> go.Figure:
        """渲染 Plotly 图表"""
        chart_type = kwargs.get('chart_type', 'scatter')
        
        try:
            if chart_type == 'scatter':
                return self._render_scatter(data, **kwargs)
            elif chart_type == 'line':
                return self._render_line(data, **kwargs)
            elif chart_type == 'bar':
                return self._render_bar(data, **kwargs)
            elif chart_type == 'candlestick':
                return self._render_candlestick(data, **kwargs)
            elif chart_type == 'heatmap':
                return self._render_heatmap(data, **kwargs)
            elif chart_type == 'subplots':
                return self._render_subplots(data, **kwargs)
            else:
                raise ValueError(f"不支持的图表类型: {chart_type}")
                
        except Exception as e:
            logger.error(f"❌ Plotly 渲染失败: {e}")
            raise
    
    def _render_scatter(self, data: pd.DataFrame, **kwargs) -> go.Figure:
        """渲染散点图"""
        x = kwargs.get('x', data.columns[0])
        y = kwargs.get('y', data.columns[1])
        color = kwargs.get('color')
        
        fig = px.scatter(
            data, x=x, y=y, color=color,
            title=kwargs.get('title', ''),
            hover_data=kwargs.get('hover_data'),
            color_discrete_map=kwargs.get('color_map'),
            size=kwargs.get('size'),
            opacity=kwargs.get('opacity', 0.8)
        )
        
        # 添加参考线
        if kwargs.get('add_reference_lines'):
            for line in kwargs['add_reference_lines']:
                if line.get('type') == 'hline':
                    fig.add_hline(
                        y=line['y'], line_dash='dash',
                        line_color=line.get('color', 'gray'),
                        annotation_text=line.get('text'),
                        annotation_position=line.get('position', 'top right')
                    )
                elif line.get('type') == 'vline':
                    fig.add_vline(
                        x=line['x'], line_dash='dash',
                        line_color=line.get('color', 'gray'),
                        annotation_text=line.get('text')
                    )
        
        return self._apply_common_config(fig, **kwargs)
    
    def export(self, fig: go.Figure, output_path: str, format: str = 'html') -> str:
        """导出 Plotly 图表"""
        output_path = super().export(fig, output_path, format)
        
        try:
            if format == 'html':
                include_js = self.config.get('include_plotlyjs', 'cdn')
                fig.write_html(output_path, include_plotlyjs=include_js)
            elif format in ['png', 'pdf', 'svg']:
                # 需要安装 kaleido: pip install kaleido
                fig.write_image(
                    output_path, 
                    width=self.width, 
                    height=self.height, 
                    scale=self.scale,
                    format=format
                )
            logger.info(f"✅ 导出成功: {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"❌ 导出失败 {format}: {e}")
            # 降级：保存为 JSON 数据
            json_path = output_path.rsplit('.', 1)[0] + '.json'
            fig.write_json(json_path)
            logger.warning(f"⚠️ 降级保存为 JSON: {json_path}")
            return json_path