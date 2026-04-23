#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DrillDown：交互式钻取组件
功能：
  - 支持点击图表元素下钻至明细
  - 面包屑导航 + 历史回溯
  - 支持多级别钻取（板块→标的→指标→明细）
"""

import plotly.graph_objects as go
from typing import Dict, List, Optional, Any, Callable
import logging

logger = logging.getLogger(__name__)


class DrillDownManager:
    """钻取管理器"""
    
    def __init__(self, config: Optional[Dict] = None):
        """
        初始化钻取管理器
        
        参数:
            config: 钻取配置
        """
        self.config = config or {}
        self.history: List[Dict] = []  # 钻取历史
        self.callbacks: Dict[str, Callable] = {}  # 钻取回调
        
        logger.info("✅ DrillDownManager 初始化完成")
    
    def register_callback(self, level: str, callback: Callable):
        """注册钻取回调"""
        self.callbacks[level] = callback
        logger.debug(f"📝 注册钻取回调: {level}")
    
    def create_drillable_chart(
        self,
        base_fig: go.Figure,
        drill_config: Dict,
        on_drill: Optional[Callable] = None
    ) -> go.Figure:
        """
        创建可钻取图表
        
        参数:
            base_fig: 基础图表
            drill_config: 钻取配置 {level: {drill_data, drill_handler}}
            on_drill: 全局钻取回调
        
        返回:
            增强后的 Plotly Figure
        """
        fig = base_fig
        
        # 添加钻取事件处理器（通过 customdata + hovertemplate）
        for trace in fig.data:
            if 'customdata' in trace and drill_config:
                # 添加钻取提示
                if 'hovertemplate' in trace:
                    trace.hovertemplate += '<br>💡 点击钻取详情<extra></extra>'
                else:
                    trace.hovertemplate = '💡 点击钻取详情<extra></extra>'
        
        # 添加面包屑导航占位
        fig.add_annotation(
            x=0.02, y=0.98,
            text="🏠 首页",
            showarrow=False,
            bgcolor='lightgray',
            font=dict(size=10),
            xref='paper', yref='paper',
            clickhandler='reset_drill'  # 自定义事件
        )
        
        # 存储钻取配置
        fig._drill_config = drill_config
        fig._on_drill = on_drill
        
        return fig
    
    def handle_drill_event(self, fig: go.Figure, click_ Dict) -> Optional[go.Figure]:
        """
        处理钻取事件
        
        参数:
            fig: 当前图表
            click_ 点击事件数据 {curveNumber, pointNumber, customdata}
        
        返回:
            钻取后的新图表，或 None
        """
        drill_config = getattr(fig, '_drill_config', {})
        on_drill = getattr(fig, '_on_drill', None)
        
        if not drill_config:
            return None
        
        # 解析点击数据
        curve_num = click_data.get('curveNumber')
        point_num = click_data.get('pointNumber')
        customdata = click_data.get('customdata')
        
        if customdata is None:
            return None
        
        # 记录历史
        self.history.append({
            'level': 'current',
            'data': customdata,
            'timestamp': datetime.now()
        })
        
        # 调用回调
        if on_drill:
            try:
                new_fig = on_drill(customdata, self.history)
                if new_fig:
                    return new_fig
            except Exception as e:
                logger.warning(f"⚠️ 钻取回调执行失败: {e}")
        
        # 默认行为：显示明细表格
        return self._create_detail_table(customdata)
    
    def _create_detail_table(self,  Dict) -> go.Figure:
        """创建明细表格"""
        # 展平嵌套数据
        rows = []
        for key, value in data.items():
            if isinstance(value, dict):
                for k, v in value.items():
                    rows.append([f"{key}.{k}", str(v)])
            else:
                rows.append([key, str(value)])
        
        fig = go.Figure(data=[go.Table(
            header=dict(values=['字段', '值'], fill_color='royalblue', font=dict(color='white')),
            cells=dict(values=list(zip(*rows)))
        )])
        
        fig.update_layout(
            title="📋 钻取明细",
            height=400,
            margin=dict(l=20, r=20, t=40, b=20)
        )
        
        return fig
    
    def reset_drill(self) -> Optional[go.Figure]:
        """重置钻取（返回根图表）"""
        if self.history:
            self.history.clear()
            logger.debug("🔄 钻取历史已重置")
        return None
    
    def get_history(self) -> List[Dict]:
        """获取钻取历史"""
        return self.history.copy()
    
    def create_breadcrumb_nav(self, history: List[Dict]) -> str:
        """生成面包屑导航 HTML"""
        if not history:
            return '<span>🏠 首页</span>'
        
        crumbs = ['<a href="#" onclick="reset_drill()">🏠 首页</a>']
        for i, item in enumerate(history):
            label = item.get('label', f"级别 {i+1}")
            crumbs.append(f'<span> &gt; {label}</span>')
        
        return ' '.join(crumbs)