#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BaseRenderer：图表渲染器抽象基类
职责：
  - 定义统一渲染接口
  - 支持主题/布局/导出等通用配置
  - 为多后端（Plotly/Matplotlib）提供扩展点
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Union
from pathlib import Path
import pandas as pd
import logging

logger = logging.getLogger(__name__)


class BaseRenderer(ABC):
    """图表渲染器基类（抽象）"""
    
    SUPPORTED_FORMATS = ['html', 'png', 'pdf', 'svg']
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化渲染器
        
        参数:
            config: 渲染配置（主题/尺寸/字体等）
        """
        self.config = config
        self.theme = config.get('theme', 'plotly_white')
        self.width = config.get('width', 1200)
        self.height = config.get('height', 600)
        self.scale = config.get('scale', 2)  # 导出图片分辨率
        
        logger.debug(f"✅ {self.__class__.__name__} 初始化: theme={self.theme}")
    
    @abstractmethod
    def render(self, data: Union[pd.DataFrame, Dict], **kwargs) -> Any:
        """
        渲染图表
        
        参数:
            data: 输入数据（DataFrame 或 Dict）
            **kwargs: 图表特定参数（x/y 轴/颜色/标题等）
        
        返回:
            图表对象（Plotly Figure / Matplotlib Axes 等）
        """
        pass
    
    @abstractmethod
    def export(self, fig: Any, output_path: Union[str, Path], format: str = 'html') -> str:
        """
        导出图表
        
        参数:
            fig: 图表对象
            output_path: 输出路径
            format: 输出格式（html/png/pdf/svg）
        
        返回:
            实际输出路径
        """
        if format not in self.SUPPORTED_FORMATS:
            raise ValueError(f"不支持的格式: {format}，支持: {self.SUPPORTED_FORMATS}")
        
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        return str(output_path)
    
    def _apply_common_config(self, fig: Any, **kwargs) -> Any:
        """应用通用配置（标题/图例/网格等）"""
        # 子类可重写以适配具体图表库
        if hasattr(fig, 'update_layout'):
            fig.update_layout(
                title=kwargs.get('title'),
                height=self.height,
                width=self.width,
                template=self.theme,
                hovermode=kwargs.get('hovermode', 'closest'),
                legend=dict(
                    orientation=kwargs.get('legend_orientation', 'h'),
                    yanchor='bottom', y=-0.15,
                    xanchor='center', x=0.5
                )
            )
        return fig