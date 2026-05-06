#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
宏观经济指标定义模块
====================
从 YAML 配置文件加载指标定义，提供 MacroIndicator 数据类和全局指标注册表。
支持动态加载、指标查询、按类别分组等操作，便于各子系统复用。
"""

import os
from dataclasses import dataclass, field
from typing import Optional, Dict, List

import yaml


@dataclass
class MacroIndicator:
    """宏观经济指标定义

    Attributes:
        code: 通达信代码
        name: 中文名称
        category: 分析类别
        unit: 单位
        freq: 数据频率 (M=月度, Q=季度, D=日度, Y=年度)
        scale: 数据缩放因子（如亿元->万亿）
        compare_codes: 关联对比指标
        transform: 数据转换方式 (none/index_minus_100/pct_change12)
    """
    code: str
    name: str
    category: str
    unit: str
    freq: str
    scale: float = 1.0
    compare_codes: List[str] = field(default_factory=list)
    transform: str = 'none'


def load_indicators(config_path: Optional[str] = None) -> Dict[str, MacroIndicator]:
    """从YAML配置文件加载指标定义

    Args:
        config_path: 配置文件路径，默认为 AiStock/config/macro/indicators.yaml

    Returns:
        指标键名到 MacroIndicator 的映射字典
    """
    if config_path is None:
        # 定位到 AiStock 项目根目录下的 config/macro/indicators.yaml
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        config_path = os.path.join(base_dir, 'config', 'macro', 'indicators.yaml')

    with open(config_path, 'r', encoding='utf-8') as f:
        raw = yaml.safe_load(f)

    indicators = {}
    for key, props in raw.items():
        indicators[key] = MacroIndicator(
            code=props['code'],
            name=props['name'],
            category=props['category'],
            unit=props['unit'],
            freq=props['freq'],
            scale=props.get('scale', 1.0),
            compare_codes=props.get('compare_codes', []),
            transform=props.get('transform', 'none'),
        )

    return indicators


def get_indicators_by_category(indicators: Dict[str, MacroIndicator]) -> Dict[str, List[str]]:
    """按类别分组指标

    Args:
        indicators: 指标字典

    Returns:
        类别名称到指标键名列表的映射
    """
    categories = {}
    for key, ind in indicators.items():
        if ind.category not in categories:
            categories[ind.category] = []
        categories[ind.category].append(key)
    return categories


def get_indicator_names(indicators: Dict[str, MacroIndicator]) -> Dict[str, str]:
    """获取指标键名到中文名称的映射

    Args:
        indicators: 指标字典

    Returns:
        指标键名到中文名称的映射
    """
    return {key: ind.name for key, ind in indicators.items()}


# 模块级默认指标注册表（懒加载）
_INDICATORS: Optional[Dict[str, MacroIndicator]] = None


def get_default_indicators() -> Dict[str, MacroIndicator]:
    """获取默认指标注册表（单例模式，懒加载）"""
    global _INDICATORS
    if _INDICATORS is None:
        _INDICATORS = load_indicators()
    return _INDICATORS