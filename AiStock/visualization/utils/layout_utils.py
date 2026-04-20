#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LayoutUtils：布局适配工具
"""
def responsive_layout(width: int = 1200, height: int = 600) -> dict:
    return {
        'width': width, 'height': height,
        'margin': dict(l=40, r=40, t=60, b=40),
        'autosize': True
    }