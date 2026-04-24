#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PlotlyRenderer：Plotly 图表渲染与导出实现
"""
import plotly.graph_objects as go
import plotly.express as px
from .base_renderer import BaseRenderer
from typing import Dict, Any, Union
import logging
import pandas as pd

logger = logging.getLogger(__name__)

class PlotlyRenderer(BaseRenderer):
    def render(self, data: Any, **kwargs) -> go.Figure:
        chart_type = kwargs.get('chart_type', 'scatter')
        try:
            if chart_type == 'scatter':
                return self._render_scatter(data, **kwargs)
            elif chart_type == 'line':
                return self._render_line(data, **kwargs)
            elif chart_type == 'bar':
                return self._render_bar(data, **kwargs)
            elif chart_type == 'subplots':
                return self._render_subplots(data, **kwargs)
            else:
                raise ValueError(f"不支持的图表类型: {chart_type}")
        except Exception as e:
            logger.error(f"❌ Plotly 渲染失败: {e}")
            raise
    
    def _render_scatter(self,  data: Any, **kwargs) -> go.Figure:
        x = kwargs.get('x', data.columns[0])
        y = kwargs.get('y', data.columns[1])
        color = kwargs.get('color')
        fig = px.scatter(data, x=x, y=y, color=color, title=kwargs.get('title', ''),
                         hover_data=kwargs.get('hover_data'),
                         color_discrete_map=kwargs.get('color_map'),
                         size=kwargs.get('size'), opacity=kwargs.get('opacity', 0.8))
        return self._apply_common_config(fig, **kwargs)
    
    def _render_line(self, data: Any, **kwargs) -> go.Figure:
        x = kwargs.get('x', data.columns[0])
        y = kwargs.get('y', data.columns[1])
        fig = px.line(data, x=x, y=y, title=kwargs.get('title', ''), markers=True)
        return self._apply_common_config(fig, **kwargs)
    
    def _render_bar(self,  data: Any, **kwargs) -> go.Figure:
        x = kwargs.get('x', data.columns[0])
        y = kwargs.get('y', data.columns[1])
        color = kwargs.get('color')
        fig = px.bar(data, x=x, y=y, color=color, title=kwargs.get('title', ''),
                     text_auto=kwargs.get('show_values', False),
                     color_discrete_map=kwargs.get('color_map'))
        return self._apply_common_config(fig, **kwargs)
    
    def _render_subplots(self,  data: Any, **kwargs) -> go.Figure:
        return self._apply_common_config(data, **kwargs)
    
    def export(self, fig: go.Figure, output_path: str, format: str = 'html') -> str:
        output_path = super().export(fig, output_path, format)
        try:
            if format == 'html':
                fig.write_html(output_path, include_plotlyjs=self.config.get('include_plotlyjs', 'cdn'))
            elif format in ['png', 'pdf', 'svg']:
                fig.write_image(output_path, width=self.width, height=self.height, scale=self.scale, format=format)
            logger.info(f"✅ 导出成功: {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"❌ 导出失败 {format}: {e}")
            json_path = output_path.rsplit('.', 1)[0] + '.json'
            fig.write_json(json_path)
            logger.warning(f"⚠️ 降级保存为 JSON: {json_path}")
            return json_path