#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ColorScales：置信度相关颜色方案
"""

# 置信度因子颜色（连续）
CONFIDENCE_COLORSCALE = [
    [0.0, '#d62728'],  # 0.98: 红色 (低置信)
    [0.25, '#ff7f0e'], # 0.985: 橙色
    [0.5, '#f7b731'],  # 0.99: 黄色 (中性)
    [0.75, '#2ca02c'], # 1.01: 绿色
    [1.0, '#1f77b4']   # 1.02: 蓝色 (高置信)
]

# 置信度等级颜色（离散）
CONFIDENCE_LEVEL_COLORS = {
    'low': '#d62728',      # 红色
    'normal': '#1f77b4',   # 蓝色
    'high': '#2ca02c'      # 绿色
}

# 分项得分颜色
DIMENSION_COLORS = {
    'data_quality': '#1f77b4',    # 蓝色
    'consistency': '#ff7f0e',     # 橙色
    'strength': '#2ca02c'         # 绿色
}

# 诊断状态颜色
DIAGNOSTIC_STATUS_COLORS = {
    '✅': '#2ca02c',   # 通过
    '⚠️': '#ff7f0e',   # 警告
    '❌': '#d62728'    # 失败
}

def get_confidence_color(factor: float) -> str:
    """根据置信度因子获取颜色"""
    if factor <= 0.99:
        return CONFIDENCE_LEVEL_COLORS['low']
    elif factor >= 1.01:
        return CONFIDENCE_LEVEL_COLORS['high']
    else:
        return CONFIDENCE_LEVEL_COLORS['normal']

def get_dimension_color(dimension: str) -> str:
    """根据维度名称获取颜色"""
    return DIMENSION_COLORS.get(dimension, '#7f7f7f')