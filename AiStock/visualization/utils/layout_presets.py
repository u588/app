#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LayoutPresets：仪表板布局预设
"""

DASHBOARD_LAYOUT = {
    'font': {'family': 'Microsoft YaHei, SimHei, sans-serif', 'size': 12},
    'plot_bgcolor': 'white',
    'paper_bgcolor': 'white',
    'hoverlabel': {'bgcolor': 'white', 'font_size': 11, 'font_family': 'Microsoft YaHei'},
    'legend': {'orientation': 'h', 'yanchor': 'bottom', 'y': -0.15, 'xanchor': 'center', 'x': 0.5},
    'margin': {'l': 40, 'r': 40, 't': 60, 'b': 40},
    'dragmode': 'pan',  # 默认拖拽模式为平移
    'modebar': {
        'add': ['drawline', 'drawopenpath', 'drawclosedpath', 'drawcircle', 'drawrect'],
        'remove': ['select2d', 'lasso2d']
    }
}

MOBILE_LAYOUT = {
    **DASHBOARD_LAYOUT,
    'width': 400,
    'height': 800,
    'font': {'size': 10},
    'margin': {'l': 20, 'r': 20, 't': 40, 'b': 20}
}

PRINT_LAYOUT = {
    **DASHBOARD_LAYOUT,
    'width': 1200,
    'height': 1600,
    'font': {'size': 14},
    'hovermode': False,  # 打印时禁用悬停
    'modebar': {'remove': ['*']}  # 隐藏工具栏
}