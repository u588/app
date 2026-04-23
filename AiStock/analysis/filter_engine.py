#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FilterEngine：智能筛选引擎
功能：
  - 支持多维条件组合筛选（盈亏比/置信度/板块/建议等）
  - 支持权重评分排序
  - 支持动态规则加载（YAML 配置）
"""

import logging
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
import pandas as pd

logger = logging.getLogger(__name__)


class FilterEngine:
    """智能筛选引擎"""
    
    # 内置筛选函数
    FILTER_FUNCTIONS = {
        'pl_ratio': lambda r, v: r['scores']['pl_ratio'] >= v,
        'fundamental_score': lambda r, v: r['scores']['fundamental'] >= v,
        'confidence_factor': lambda r, v: r.get('technical_quality', {}).get('factor', 1.0) >= v,
        'recommendation': lambda r, v: r['recommendation'] in (v if isinstance(v, list) else [v]),
        'sector': lambda r, v: r['sector'] in (v if isinstance(v, list) else [v]),
        'entry_price_range': lambda r, v: v[0] <= r['prices']['entry'] <= v[1],
    }
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化筛选引擎
        
        参数:
            config_path: 筛选规则配置文件路径
        """
        self.rules = self._load_rules(config_path) if config_path else {}
        logger.info(f"✅ FilterEngine 初始化 | 规则数: {len(self.rules)}")
    
    def _load_rules(self, path: str) -> Dict:
        """加载 YAML 筛选规则"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.warning(f"⚠️ 加载筛选规则失败 {path}: {e}，使用默认规则")
            return self._default_rules()
    
    def _default_rules(self) -> Dict:
        """默认筛选规则"""
        return {
            'default': {
                'conditions': {
                    'pl_ratio': {'>=': 2.0},
                    'confidence_factor': {'>=': 0.99},
                    'recommendation': {'in': ['强烈推荐', '推荐']}
                },
                'order_by': 'pl_ratio',
                'limit': 10
            },
            'conservative': {
                'conditions': {
                    'pl_ratio': {'>=': 2.5},
                    'fundamental_score': {'>=': 65},
                    'confidence_factor': {'>=': 1.01},
                    'recommendation': {'==': '强烈推荐'}
                },
                'order_by': 'confidence_factor',
                'limit': 5
            },
            'aggressive': {
                'conditions': {
                    'pl_ratio': {'>=': 1.5},
                    'recommendation': {'in': ['强烈推荐', '推荐', '观望']}
                },
                'order_by': 'pl_ratio',
                'limit': 20
            }
        }
    
    def filter_results(
        self,
        results: List[Dict],
        rule_name: str = 'default',
        custom_conditions: Optional[Dict] = None
    ) -> List[Dict]:
        """
        执行筛选
        
        参数:
            results: 待筛选结果列表
            rule_name: 规则名称（来自配置）
            custom_conditions: 自定义条件（覆盖规则）
        
        返回:
            List[Dict]: 筛选后的结果
        """
        # 1. 获取规则
        rule = self.rules.get(rule_name, self.rules['default'])
        conditions = custom_conditions or rule.get('conditions', {})
        
        # 2. 执行筛选
        filtered = results
        for field, ops in conditions.items():
            if field not in self.FILTER_FUNCTIONS:
                logger.warning(f"⚠️ 未知筛选字段: {field}，跳过")
                continue
            
            filter_func = self.FILTER_FUNCTIONS[field]
            for op, value in ops.items():
                # 简化：只支持单操作符，实际可扩展
                filtered = [r for r in filtered if filter_func(r, value)]
        
        # 3. 排序
        order_by = rule.get('order_by', 'pl_ratio')
        reverse = rule.get('reverse', True)
        filtered.sort(key=lambda r: r.get('scores', {}).get(order_by, 0) if order_by in ['pl_ratio', 'fundamental'] 
                     else r.get('technical_quality', {}).get('factor', 1.0) if order_by == 'confidence_factor'
                     else r.get(order_by, 0), reverse=reverse)
        
        # 4. 限制数量
        limit = rule.get('limit')
        if limit:
            filtered = filtered[:limit]
        
        logger.info(f"🔍 筛选完成: {len(results)} → {len(filtered)} 只 | 规则: {rule_name}")
        return filtered
    
    def score_and_rank(
        self,
        results: List[Dict],
        weights: Optional[Dict] = None
    ) -> List[Dict]:
        """
        综合评分排序（加权打分）
        
        参数:
            results: 结果列表
            weights: 权重配置 {pl_ratio: 0.4, confidence: 0.35, fundamental: 0.25}
        
        返回:
            List[Dict]: 带综合评分的排序结果
        """
        weights = weights or {'pl_ratio': 0.4, 'confidence': 0.35, 'fundamental': 0.25}
        
        for r in results:
            # 标准化各指标到 0-1 区间
            pl_norm = min(r['scores']['pl_ratio'] / 5.0, 1.0)  # 5.0 为满分基准
            conf_norm = (r.get('technical_quality', {}).get('factor', 1.0) - 0.98) / 0.04  # 0.98~1.02 → 0~1
            fin_norm = r['scores']['fundamental'] / 100
            
            # 加权综合评分
            r['_composite_score'] = (
                pl_norm * weights['pl_ratio'] +
                conf_norm * weights['confidence'] +
                fin_norm * weights['fundamental']
            )
        
        # 按综合评分排序
        results.sort(key=lambda r: r['_composite_score'], reverse=True)
        
        logger.debug(f"📊 综合评分完成 | 权重: {weights}")
        return results