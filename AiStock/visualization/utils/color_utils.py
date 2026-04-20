#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ColorUtils：颜色方案管理
"""
from typing import Dict, List

BRAND_COLORS = {
    'primary': '#1f77b4', 'success': '#2ca02c', 'warning': '#ff7f0e',
    'danger': '#d62728', 'info': '#17becf', 'neutral': '#7f7f7f'
}

CATEGORICAL_MAP = {
    '强烈推荐': '#2ca02c', '推荐': '#1f77b4', '观望': '#ff7f0e', '谨慎': '#d62728'
}

def get_color_map(category: str, custom_map: Dict[str, str] = None) -> str:
    base = custom_map or CATEGORICAL_MAP
    return base.get(category, BRAND_COLORS['neutral'])

def get_brand_colors() -> Dict[str, str]:
    return BRAND_COLORS.copy()