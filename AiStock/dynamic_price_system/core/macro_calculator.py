#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MacroCalculator：宏观面联动系数模块（配置驱动优化版）
功能：
  - 从 macro_config.yaml 动态加载指标元数据与板块映射
  - 支持实时/滞后数据处理与新鲜度校验（可配置策略）
  - 敏感度可调（全局 + 板块个性化），输出价格调整系数 (0.92 ~ 1.08)
  - 增强诊断报告 + 类型安全 + 异常隔离
版本：2.0.0
"""

import logging
from typing import Dict, Optional, List, Tuple, Any, Union
from datetime import datetime, timedelta
import numpy as np
import copy

logger = logging.getLogger(__name__)


class MacroCalculator:
    """宏观面计算器（配置驱动版）"""
    
    # 默认回退配置（当 config_macros 未提供时使用）
    _DEFAULT_CONFIG = {
        'macro_indicators': {},
        'sector_macro_link': {
            '油气开采': ['brent_crude', 'pmi'],
            'LNG': ['nymex_gas', 'usd_cny'],
            '油服': ['brent_crude', 'pmi'],
            '煤炭化工': ['ppi', 'cpi', 'eua_carbon'],
            '特高压': ['lme_copper', 'china_10y_bond'],
            '新能源': ['lme_copper', 'lme_nickel', 'm2_growth'],
            '黄金': ['comex_gold', 'us_10y_bond'],
            '军工': ['pmi', 'm2_growth'],
            '政策方向': ['m2_growth', 'china_10y_bond'],
        },
        'macro_calculation': {
            'default_sensitivity': 1.0,
            'impact_clip': [-0.15, 0.15],
            'factor_range': [0.92, 1.08],
            'sector_sensitivity': {},
            'freshness_policy': {
                'stale_action': 'downgrade',
                'downgrade_factor': 0.5,
                'log_warnings': True
            },
            'missing_policy': {
                'fallback': 'neutral',
                'min_valid_indicators': 1
            }
        }
    }
    
    def __init__(
        self, 
        macro_data: Dict[str, Any], 
        sector: str, 
        params: Optional[Dict] = None,
        config_macros: Optional[Dict] = None,
        logger_instance: Optional[logging.Logger] = None,
        current_time: Optional[datetime] = None  # 用于测试时固定时间
    ):
        """
        初始化宏观计算器（配置驱动 + 依赖注入）
        
        参数:
            macro_data: 宏观指标数据 {indicator: value, indicator_update_time: datetime}
            sector: 所属板块
            params: 标的个性化参数（覆盖全局配置）
            config_macros: 全局宏观配置（来自 macro_config.yaml）
            logger_instance: 自定义日志器
            current_time: 当前时间（测试时固定，默认用 datetime.now()）
        """
        self.data = macro_data or {}
        self.sector = sector
        self.params = params or {}
        self.logger = logger_instance or logger
        self._current_time = current_time or datetime.now()
        
        # 合并配置（优先级：传入 > 默认）
        self.config = {**self._DEFAULT_CONFIG, **(config_macros or {})}
        
        # 提取配置项
        self.indicator_meta = self.config.get('macro_indicators', {})
        self.sector_link = self.config.get('sector_macro_link', {})
        calc_cfg = self.config.get('macro_calculation', {})
        self.freshness_policy = calc_cfg.get('freshness_policy', {})
        self.missing_policy = calc_cfg.get('missing_policy', {})
        
        # 参数解析（优先级：标的参数 > 板块配置 > 全局默认）
        self.sensitivity = float(
            self.params.get('macro_sensitivity') or
            calc_cfg.get('sector_sensitivity', {}).get(sector) or
            calc_cfg.get('default_sensitivity', 1.0)
        )
        self.impact_clip = tuple(self.params.get('impact_clip') or calc_cfg.get('impact_clip', [-0.15, 0.15]))
        self.factor_range = tuple(self.params.get('factor_range') or calc_cfg.get('factor_range', [0.92, 1.08]))
        
        # 缓存上次有效因子（用于 missing_policy='last_valid'）
        self._last_valid_factor: Optional[float] = None
        
        self.logger.debug(
            f"✅ MacroCalculator 初始化 | 板块={sector} | "
            f"敏感度={self.sensitivity} | 因子范围={self.factor_range}"
        )
    
    def get_adjustment_factor(self) -> float:
        """
        计算宏观联动调整系数（唯一主入口）
        
        返回:
            float: 调整系数 (0.92~1.08)
        """
        if not self.data:
            self.logger.warning("⚠️ 宏观数据为空，返回中性系数 1.0")
            return self._apply_missing_policy(1.0)
        
        # 1. 获取关联指标（优先级：标的参数 > 配置 > 默认）
        linked_indicators = (
            self.params.get('macro_link') or 
            self.sector_link.get(self.sector) or
            ['pmi']  # 最终回退
        )
        
        if not isinstance(linked_indicators, list):
            self.logger.warning(f"⚠️ 板块 {self.sector} 的宏观链接配置格式错误，使用默认 ['pmi']")
            linked_indicators = ['pmi']
        
        # 2. 逐个计算指标影响（异常隔离 + 新鲜度校验）
        impacts = []
        valid_count = 0
        
        for indicator in linked_indicators:
            try:
                result = self._calculate_indicator_impact(indicator)
                if result:
                    impact, meta, freshness = result
                    impacts.append(impact)
                    valid_count += 1
                    self.logger.debug(
                        f"🔍 {indicator}: impact={impact:.4f}, "
                        f"deviation={(self.data[indicator]-meta['neutral'])/meta['range']:.3f}, "
                        f"freshness={freshness}"
                    )
            except Exception as e:
                self.logger.warning(f"⚠️ 计算 {indicator} 影响失败: {e}，跳过")
                continue
        
        # 3. 检查有效指标数
        min_valid = self.missing_policy.get('min_valid_indicators', 1)
        if valid_count < min_valid:
            fallback = self.missing_policy.get('fallback', 'neutral')
            self.logger.info(
                f"ℹ️ {self.sector} 有效指标 {valid_count} < 最小要求 {min_valid}, "
                f"使用回退策略: {fallback}"
            )
            if fallback == 'neutral':
                return self._apply_missing_policy(1.0)
            elif fallback == 'last_valid' and self._last_valid_factor is not None:
                return self._apply_missing_policy(self._last_valid_factor)
            else:  # 'error'
                self.logger.error(f"❌ {self.sector} 宏观计算失败: 有效指标不足")
                return 1.0  # 安全兜底
        
        # 4. 综合影响：算术平均 + 敏感度调整
        avg_impact = np.mean(impacts)
        factor = 1.0 + avg_impact * self.sensitivity
        
        # 5. 截断到安全区间
        factor = np.clip(factor, self.factor_range[0], self.factor_range[1])
        
        # 6. 缓存有效因子（供下次回退使用）
        self._last_valid_factor = float(factor)
        
        self.logger.info(
            f"📊 {self.sector} 宏观系数: {factor:.3f} | "
            f"敏感度={self.sensitivity} | 有效指标={valid_count}/{len(linked_indicators)}"
        )
        return round(float(factor), 3)
    
    def _calculate_indicator_impact(
        self, 
        indicator: str
    ) -> Optional[Tuple[float, Dict, str]]:
        """
        计算单个宏观指标的影响值
        
        参数:
            indicator: 指标名称
        
        返回:
            Tuple(impact, meta, freshness) 或 None（数据无效时）
            - impact: 影响值 (-0.15~0.15)
            - meta: 指标元数据
            - freshness: 'fresh'/'stale'/'missing'
        """
        # 1. 获取当前值
        current = self.data.get(indicator)
        if current is None:
            return None
        
        # 2. 类型校验 + 转换
        try:
            current = float(current)
        except (ValueError, TypeError):
            self.logger.warning(f"⚠️ 指标 {indicator} 值非数值: {current} (type: {type(current).__name__})")
            return None
        
        # 3. 获取元数据
        meta = self.indicator_meta.get(indicator)
        if not meta:
            self.logger.warning(f"⚠️ 未知指标 {indicator}，使用默认元数据")
            meta = {
                'neutral': 0, 'range': 1, 'direction': 1, 'impact_coefficient': 0.10,
                'lag_tolerance_days': 7, 'unit': '', 'description': indicator
            }
        
        neutral = float(meta.get('neutral', 0))
        range_width = float(meta.get('range', 1))
        direction = int(meta.get('direction', 1))
        coefficient = float(meta.get('impact_coefficient', 0.10))
        lag_tolerance = int(meta.get('lag_tolerance_days', 7))
        
        # 4. 避免除零
        if range_width == 0:
            self.logger.error(f"❌ 指标 {indicator} 的 range=0，配置错误")
            return None
        
        # 5. 数据新鲜度校验
        freshness = self._check_freshness(indicator, meta)
        stale_action = self.freshness_policy.get('stale_action', 'downgrade')
        downgrade_factor = float(self.freshness_policy.get('downgrade_factor', 0.5))
        
        if freshness == 'stale' and stale_action == 'exclude':
            self.logger.warning(f"⚠️ 指标 {indicator} 数据过期，按策略排除")
            return None
        
        # 6. 计算标准化偏差
        deviation = (current - neutral) / range_width
        
        # 7. 计算影响值：偏差 × 方向 × 系数
        impact = deviation * direction * coefficient
        
        # 8. 过期数据降权（如配置）
        if freshness == 'stale' and stale_action == 'downgrade':
            impact *= downgrade_factor
            self.logger.debug(f"🔽 {indicator} 过期数据降权: ×{downgrade_factor}")
        
        # 9. 截断到安全范围
        impact = np.clip(impact, self.impact_clip[0], self.impact_clip[1])
        
        return float(impact), meta, freshness
    
    def _check_freshness(self, indicator: str, meta: Dict) -> str:
        """
        检查指标数据新鲜度
        
        返回:
            'fresh' | 'stale' | 'missing' | 'unknown'
        """
        # 检查是否有更新时间
        update_key = f'{indicator}_update_time'
        update_time = self.data.get(update_key)
        
        if update_time is None:
            # 尝试从指标值本身推断（如配置中包含）
            if 'update_time' in meta:
                update_time = meta['update_time']
            else:
                return 'unknown'  # 无时间标记，假设新鲜
        
        # 解析时间
        if isinstance(update_time, str):
            try:
                # 支持 ISO8601 格式
                update_time = datetime.fromisoformat(update_time.replace('Z', '+00:00'))
            except ValueError:
                self.logger.warning(f"⚠️ 指标 {indicator} 更新时间解析失败: {update_time}")
                return 'parse_error'
        
        if not isinstance(update_time, datetime):
            return 'unknown'
        
        # 计算滞后天数
        lag = (self._current_time - update_time).days
        tolerance = int(meta.get('lag_tolerance_days', 7))
        
        if lag <= tolerance:
            return 'fresh'
        else:
            if self.freshness_policy.get('log_warnings', True):
                self.logger.warning(
                    f"⚠️ 指标 {indicator} 数据滞后 {lag} 天 > 容忍 {tolerance} 天"
                )
            return 'stale'
    
    def _apply_missing_policy(self, factor: float) -> float:
        """应用缺失策略（记录日志 + 返回安全值）"""
        fallback = self.missing_policy.get('fallback', 'neutral')
        self.logger.debug(f"🔄 应用缺失策略: fallback={fallback}, factor={factor:.3f}")
        return factor
    
    def get_detailed_report(self) -> Dict[str, Any]:
        """
        生成详细宏观分析报告（用于调试/可视化）
        
        返回:
            Dict: 包含因子分解、指标贡献、诊断信息
        """
        linked_indicators = (
            self.params.get('macro_link') or 
            self.sector_link.get(self.sector) or
            ['pmi']
        )
        
        indicator_details = []
        valid_impacts = []
        
        for indicator in linked_indicators:
            result = self._calculate_indicator_impact(indicator)
            meta = self.indicator_meta.get(indicator, {})
            
            detail = {
                'indicator': indicator,
                'description': meta.get('description', indicator),
                'current_value': self.data.get(indicator),
                'neutral': meta.get('neutral'),
                'unit': meta.get('unit'),
                'direction': '正向' if meta.get('direction', 1) > 0 else '反向',
                'impact_coefficient': meta.get('impact_coefficient', 0.10),
                'status': 'valid' if result else 'invalid'
            }
            
            if result:
                impact, meta_used, freshness = result
                current = self.data[indicator]
                deviation = (current - meta_used['neutral']) / meta_used['range']
                detail.update({
                    'impact': round(impact, 4),
                    'deviation': round(deviation, 3),
                    'freshness': freshness,
                    'effective_impact': round(impact * (0.5 if freshness=='stale' else 1.0), 4)
                })
                valid_impacts.append(impact)
            
            indicator_details.append(detail)
        
        # 计算综合因子
        final_factor = self.get_adjustment_factor()
        avg_impact = np.mean(valid_impacts) if valid_impacts else 0
        
        return {
            'sector': self.sector,
            'adjustment_factor': round(final_factor, 3),
            'sensitivity': self.sensitivity,
            'avg_impact': round(avg_impact, 4),
            'valid_indicators': len(valid_impacts),
            'total_indicators': len(linked_indicators),
            'indicator_details': indicator_details,
            'factor_decomposition': {
                'base': 1.0,
                'avg_deviation_impact': round(avg_impact, 4),
                'sensitivity_adjusted': round(avg_impact * self.sensitivity, 4),
                'final_factor': round(final_factor, 3)
            },
            'policies': {
                'freshness': self.freshness_policy,
                'missing': self.missing_policy
            }
        }
    
    def check_data_freshness(self) -> Dict[str, str]:
        """
        检查所有关联指标的数据新鲜度
        
        返回:
            Dict[indicator -> 'fresh'/'stale'/'missing'/'unknown']
        """
        linked_indicators = (
            self.params.get('macro_link') or 
            self.sector_link.get(self.sector) or
            ['pmi']
        )
        
        freshness_report = {}
        for indicator in linked_indicators:
            meta = self.indicator_meta.get(indicator, {})
            freshness_report[indicator] = self._check_freshness(indicator, meta)
        
        return freshness_report
    
    def update_config(self, new_config: Dict):
        """
        热更新配置（用于运行时调整参数）
        
        参数:
            new_config: 新的宏观配置字典
        """
        # 深度合并配置
        def deep_merge(base: Dict, update: Dict) -> Dict:
            result = copy.deepcopy(base)
            for k, v in update.items():
                if isinstance(v, dict) and k in result and isinstance(result[k], dict):
                    result[k] = deep_merge(result[k], v)
                else:
                    result[k] = copy.deepcopy(v)
            return result
        
        old_sensitivity = self.sensitivity
        self.config = deep_merge(self.config, new_config)
        
        # 重新提取关键配置
        self.indicator_meta = self.config.get('macro_indicators', {})
        self.sector_link = self.config.get('sector_macro_link', {})
        calc_cfg = self.config.get('macro_calculation', {})
        self.freshness_policy = calc_cfg.get('freshness_policy', {})
        self.missing_policy = calc_cfg.get('missing_policy', {})
        
        # 重新解析敏感度（可能变化）
        self.sensitivity = float(
            self.params.get('macro_sensitivity') or
            calc_cfg.get('sector_sensitivity', {}).get(self.sector) or
            calc_cfg.get('default_sensitivity', 1.0)
        )
        
        self.logger.info(
            f"🔄 宏观配置已热更新 | 敏感度: {old_sensitivity} → {self.sensitivity}"
        )