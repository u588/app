#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
宏观经济分析引擎
=================
基于 YAML 评分规则对宏观经济数据进行多维度分析。
各维度的评分规则从配置文件加载，支持灵活调整阈值和权重。
"""

from typing import Dict, Optional, List
import re

import pandas as pd

from macro_analysis_system.config.macro_indicators import MacroIndicator, get_default_indicators
from base_services.config_service import ConfigService
from base_services.logger_service import LoggerService
# from base_services.config_service import ConfigService, get_global_config
# from base_services.logger_service import LoggerService, get_global_logger_service
# from macro_analysis_system.data_service.data_loader_service import DataLoaderService


class MacroAnalyzer:
    """宏观经济分析引擎

    从 YAML 配置加载评分规则，对各维度指标进行自动评分和信号生成。

    Usage:
        loader = DataLoaderService()
        analyzer = MacroAnalyzer(loader)
        outlook = analyzer.run_full_analysis()
    """

    def __init__(self, data_loader: DataLoaderService,
                 config: Optional[ConfigService] = None,
                 logger: Optional[LoggerService] = None):
        self.data_loader = data_loader
        self._config = config 
        self._logger = logger.get_logger('macro_analyzer') if logger else None
        # self._config = config or get_global_config()
        # self._logger = (logger or get_global_logger_service()).get_logger('macro_analyzer')
        self._indicators = data_loader.indicators
        self.data: Dict[str, pd.DataFrame] = {}
        self.analysis: Dict[str, Dict] = {}
        self._scoring_config = self._config.get_namespace('scoring')

    def load_data(self):
        """加载所有核心指标数据"""
        self._logger.info("正在加载宏观数据...")
        self.data = self.data_loader.fetch_all(count=120)
        self._logger.info(f"成功加载 {len(self.data)}/{len(self._indicators)} 个指标")

    def get_latest_snapshot(self) -> Dict:
        """获取最新宏观指标快照"""
        return self.data_loader.get_latest_snapshot(self.data)

    def _evaluate_conditions(self, value: float, conditions: List[Dict]) -> Dict:
        """根据条件列表评估得分和信号"""
        for cond in conditions:
            threshold = cond['threshold']
            operator = cond['operator']
            score = cond['score']
            signal_template = cond['signal']

            matched = False
            if operator == '>=':
                matched = value >= threshold
            elif operator == '>':
                matched = value > threshold
            elif operator == '<=':
                matched = value <= threshold
            elif operator == '<':
                matched = value < threshold

            if matched:
                try:
                    signal = signal_template.format(value=value, abs_value=abs(value))
                except (KeyError, IndexError):
                    signal = signal_template
                return {'score': score, 'signal': signal}

        return {'score': 0, 'signal': None}

    def _get_indicator_value(self, indicator_key: str,
                              transform: str = 'none',
                              min_length: int = 0) -> Optional[float]:
        """获取指标当前值（支持数据转换）"""
        if indicator_key not in self.data:
            return None

        df = self.data[indicator_key]
        if len(df) < min_length:
            return None

        if transform in ('none', 'index_minus_100'):
            return df.iloc[-1]['value'] if len(df) > 0 else None
        elif transform == 'yoy':
            if len(df) >= 13:
                current = df.iloc[-1]['value']
                year_ago = df.iloc[-13]['value']
                if year_ago != 0:
                    return (current - year_ago) / abs(year_ago) * 100
            return None
        elif transform == 'trend_6m':
            if len(df) >= 6:
                recent = df.tail(6)
                return recent.iloc[-1]['value'] - recent.iloc[0]['value']
            return None
        elif transform == 'qoq':
            if len(df) >= 2:
                current = df.iloc[-1]['value']
                prev = df.iloc[-2]['value']
                if prev != 0:
                    return (current - prev) / abs(prev) * 100
            return None
        elif transform == 'period_diff':
            if len(df) >= 2:
                return df.iloc[-1]['value'] - df.iloc[-2]['value']
            return None
        elif transform == 'pct_change12':
            if len(df) >= 13:
                current = df.iloc[-1]['value']
                year_ago = df.iloc[-13]['value']
                if year_ago != 0:
                    return (current - year_ago) / abs(year_ago) * 100
            return None

        return df.iloc[-1]['value'] if len(df) > 0 else None

    def _analyze_dimension(self, dimension_key: str) -> Dict:
        """分析单个维度"""
        dim_config = self._scoring_config.get('scoring_rules', {}).get(dimension_key, {})
        if not dim_config:
            return {'title': dimension_key, 'score': 50, 'signals': []}

        base_score = dim_config.get('base_score', 50)
        result = {
            'title': self._get_dimension_title(dimension_key),
            'content': '',
            'score': base_score,
            'signals': [],
        }

        intermediate_values: Dict[str, float] = {}

        for rule_key, rule_config in dim_config.get('rules', {}).items():
            rule_type = rule_config.get('type', 'simple')

            if rule_type == 'derived':
                value = self._compute_derived_value(
                    rule_config.get('formula', ''), intermediate_values
                )
            else:
                indicator_key = rule_config.get('indicator', '')
                transform = rule_config.get('transform', 'none')
                min_length = rule_config.get('min_length', 0)
                value = self._get_indicator_value(indicator_key, transform, min_length)

            if value is None:
                continue

            intermediate_values[rule_key] = value

            conditions = rule_config.get('conditions', [])
            eval_result = self._evaluate_conditions(value, conditions)

            if eval_result['signal']:
                result['signals'].append(eval_result['signal'])
            result['score'] += eval_result['score']
            result[rule_key] = value

        result['score'] = max(0, min(100, result['score']))
        self.analysis[dimension_key] = result
        return result

    def _compute_derived_value(self, formula: str,
                                intermediate_values: Dict[str, float]) -> Optional[float]:
        """计算派生指标值"""
        try:
            expr = formula
            for k, v in intermediate_values.items():
                expr = expr.replace(k, str(v))

            remaining_keys = re.findall(r'[A-Za-z_]\w*', expr)
            for rk in remaining_keys:
                if rk in self.data and len(self.data[rk]) > 0:
                    val = self.data[rk].iloc[-1]['value']
                    expr = expr.replace(rk, str(val))

            return eval(expr)
        except Exception:
            return None

    def _get_dimension_title(self, key: str) -> str:
        """获取维度中文名称"""
        titles = {
            'economic_growth': '经济增长分析',
            'prosperity': '景气度分析',
            'monetary': '货币金融分析',
            'trade_fx': '贸易与外汇分析',
            'energy_industry': '能源与工业分析',
            'capital_market': '资本市场分析',
            'international': '国际环境分析',
        }
        return titles.get(key, key)

    def analyze_economic_growth(self) -> Dict:
        return self._analyze_dimension('economic_growth')

    def analyze_prosperity(self) -> Dict:
        return self._analyze_dimension('prosperity')

    def analyze_monetary(self) -> Dict:
        return self._analyze_dimension('monetary')

    def analyze_trade_fx(self) -> Dict:
        return self._analyze_dimension('trade_fx')

    def analyze_energy_industry(self) -> Dict:
        return self._analyze_dimension('energy_industry')

    def analyze_capital_market(self) -> Dict:
        return self._analyze_dimension('capital_market')

    def analyze_international(self) -> Dict:
        return self._analyze_dimension('international')

    def generate_outlook(self) -> Dict:
        """生成综合经济展望"""
        weights = self._scoring_config.get('weights', {
            'economic_growth': 0.25, 'prosperity': 0.20, 'monetary': 0.20,
            'trade_fx': 0.12, 'energy_industry': 0.10,
            'capital_market': 0.08, 'international': 0.05,
        })

        total_score = 0
        for key, weight in weights.items():
            if key in self.analysis:
                total_score += self.analysis[key]['score'] * weight

        thresholds = self._scoring_config.get('status_thresholds', {})
        status = "未知"
        outlook = ""

        for _, cfg in sorted(thresholds.items(), key=lambda x: x[1].get('min_score', 0), reverse=True):
            if total_score >= cfg.get('min_score', 0):
                status = cfg.get('label', '未知')
                outlook = cfg.get('outlook', '')
                break

        return {
            'total_score': total_score,
            'status': status,
            'outlook': outlook,
            'category_scores': {k: v['score'] for k, v in self.analysis.items()},
            'weights': weights,
        }

    def run_full_analysis(self) -> Dict:
        """执行完整分析"""
        self.load_data()
        dimensions = [
            'economic_growth', 'prosperity', 'monetary',
            'trade_fx', 'energy_industry', 'capital_market', 'international',
        ]
        for dim in dimensions:
            self._analyze_dimension(dim)
        return self.generate_outlook()