#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RendererFactory：渲染器工厂
"""
from typing import Dict, Any
from .base_renderer import BaseRenderer
from .plotly_renderer import PlotlyRenderer
import logging

logger = logging.getLogger(__name__)

class RendererFactory:
    @staticmethod
    def create(config: Dict[str, Any]) -> BaseRenderer:
        renderer_type = config.get('type', 'plotly').lower()
        if renderer_type == 'plotly':
            return PlotlyRenderer(config)
        else:
            logger.warning(f"⚠️ 未知渲染器类型: {renderer_type}，回退到 Plotly")
            return PlotlyRenderer(config)