#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MacroCalculator：宏观面联动系数模块
功能：
  - 根据板块关联的宏观指标计算联动系数
  - 支持实时/滞后数据处理与新鲜度校验
  - 敏感度可调，输出价格调整系数 (0.92 ~ 1.08)
"""

import logging
# from config import SECTOR_MACRO_LINK
import logging
from typing import Dict, Optional, List
from datetime import datetime, timedelta
import numpy as np
from base_services.config_service import ConfigService
# logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 移除模块级初始化
# config = ConfigService(system_name='dynamic_price')
# SECTOR_MACRO_LINK = config.get('sector_macro_link', {})
class MacroCalculator:
    """宏观面计算器"""
    # ========== 新增：默认板块 - 指标映射（类属性） ==========
    DEFAULT_SECTOR_LINK = {
        '油气开采': ['brent_crude', 'pmi'],
        'LNG': ['nymex_gas', 'usd_cny'],
        '油服': ['brent_crude', 'pmi'],
        '煤炭化工': ['ppi', 'cpi', "eua_carbon"],
        '特高压': ['lme_copper', 'china_10y_bond'],
        '新能源': ["lme_copper", "lme_nickel", "m2_growth"],
        '黄金': ['comex_gold', 'china_10y_bond'],
        '军工': ['pmi', 'm2_growth'],
        '政策方向': ['m2_growth', 'china_10y_bond'],
    }    
    # 指标类型元数据 (用于偏差计算)
    INDICATOR_META = {
        'brent_crude': {'unit': 'USD/bbl', 'neutral': 80, 'range': 40, 'lag_tolerance_days': 2},
        'comex_gold': {'unit': 'USD/oz', 'neutral': 2300, 'range': 600, 'lag_tolerance_days': 1},
        'lme_copper': {'unit': 'USD/t', 'neutral': 9000, 'range': 3000, 'lag_tolerance_days': 2},
        'nymex_gas': {'unit': 'USD/mmbtu', 'neutral': 2.8, 'range': 2.0, 'lag_tolerance_days': 1},
        'pmi': {'unit': 'index', 'neutral': 50.0, 'range': 10.0, 'lag_tolerance_days': 30},
        'usd_cny': {'unit': 'ratio', 'neutral': 7.15, 'range': 0.6, 'lag_tolerance_days': 1},
        'china_10y_bond': {'unit': '%', 'neutral': 2.5, 'range': 1.5, 'lag_tolerance_days': 1},
        'm2_growth': {'unit': '%', 'neutral': 9.0, 'range': 4.0, 'lag_tolerance_days': 15},
        'cpi': {'unit': '%', 'neutral': 2.0, 'range': 3.0, 'lag_tolerance_days': 30},
        'ppi': {'unit': '%', 'neutral': 1.0, 'range': 5.0, 'lag_tolerance_days': 30}
    }
    
    def __init__(
        self, 
        macro_data: Dict[str, Any], 
        sector: str, 
        params: Optional[Dict] = None,
        config_macros: Optional[Dict] = None,  # ✅ 新增：全局宏观配置
        indicator_meta: Optional[Dict] = None,  # ✅ 新增：元数据覆盖（测试用）
        sector_link: Optional[Dict] = None,     # ✅ 新增：板块映射覆盖
        logger_instance: Optional[logging.Logger] = None
    ):
        """
        初始化宏观计算器（依赖注入版）
        
        参数:
            macro_data 宏观指标数据 {indicator: value}
            sector: 所属板块
            params: 标的个性化参数
            config_macros 全局宏观配置（含 sector_macro_link 等）
            indicator_meta 指标元数据覆盖（用于测试/热更新）
            sector 板块 - 指标映射覆盖
            logger_instance: 自定义日志器
        """
        self.data = macro_data or {}
        self.sector = sector
        self.params = params or {}
        self.config_macros = config_macros or {}
        self.logger = logger_instance or logger

        # 合并元数据（支持测试时覆盖）
        self.indicator_meta = {**self.INDICATOR_META, **(indicator_meta or {})}
        # 合并板块映射（优先级：参数 > 配置 > 默认）
        self.sector_link = {
            **self.DEFAULT_SECTOR_LINK, 
            **(config_macros.get('sector_macro_link', {}) if config_macros else {}),
            **(sector_link or {})
        }        

        # 参数解析（带默认值）
        self.sensitivity = float(self.params.get('macro_sensitivity', 1.0))
        self.correlation_window = int(self.params.get('correlation_window', 60))
        self.lag_tolerance = int(self.params.get('lag_tolerance_days', 3))
        self.impact_clip = tuple(self.params.get('impact_clip', (-0.15, 0.15)))
        self.factor_range = tuple(self.params.get('neutral_range', (0.92, 1.08)))
        
        self.logger.debug(f"✅ MacroCalculator 初始化 | 板块={sector} | 敏感度={self.sensitivity}")

    def get_adjustment_factor(self) -> float:
        """计算宏观联动调整系数（唯一主入口）"""
        if not self.data:
            self.logger.warning("⚠️ 宏观数据为空，返回中性系数 1.0")
            return 1.0
        
        # 1. 获取关联指标（优先级：params > config > 默认）
        linked_indicators = (
            self.params.get('macro_link') or 
            self.config_macros.get('sector_macro_link', {}).get(self.sector) or
            self.sector_link.get(self.sector, ['pmi'])
        )
        
        if not isinstance(linked_indicators, list):
            self.logger.warning(f"⚠️ 板块 {self.sector} 的宏观链接配置格式错误，使用默认")
            linked_indicators = ['pmi']
        
        impacts = []
        
        # 2. 逐个计算指标影响（异常隔离）
        for indicator in linked_indicators:
            try:
                result = self._calculate_indicator_impact(indicator)
                if result:
                    impact, _ = result
                    impacts.append(impact)
                    self.logger.debug(f"🔍 {indicator}: impact={impact:.3f}")
            except Exception as e:
                self.logger.warning(f"⚠️ 计算 {indicator} 影响失败: {e}，跳过")
                continue
        
        # 3. 无有效指标时返回中性
        if not impacts:
            self.logger.info(f"ℹ️ {self.sector} 无有效宏观指标，返回中性系数 1.0")
            return 1.0
        
        # 4. 综合影响：算术平均 + 敏感度调整
        avg_impact = np.mean(impacts)
        factor = 1.0 + avg_impact * self.sensitivity
        
        # 5. 截断到安全区间
        factor = np.clip(factor, self.factor_range[0], self.factor_range[1])
        
        self.logger.info(f"📊 {self.sector} 宏观系数: {factor:.3f} (基于 {len(impacts)} 个指标)")
        return round(float(factor), 3)
    
    def _calculate_indicator_impact(
        self, 
        indicator: str
    ) -> Optional[Tuple[float, Dict]]:
        """
        计算单个宏观指标的影响值
        
        参数:
            indicator: 指标名称
        
        返回:
            Tuple(impact, meta) 或 None（数据无效时）
            impact: 影响值 (-0.15~0.15)
            meta: 指标元数据（用于诊断）
        """
        # 1. 获取当前值
        current = self.data.get(indicator)
        if current is None:
            return None
        
        # 2. 类型校验 + 转换
        try:
            current = float(current)
        except (ValueError, TypeError):
            self.logger.warning(f"⚠️ 指标 {indicator} 值非数值: {current}")
            return None
        
        # 3. 获取元数据
        meta = self.indicator_meta.get(indicator)
        if not meta:
            self.logger.warning(f"⚠️ 未知指标 {indicator}，使用默认元数据")
            meta = {'neutral': 0, 'range': 1, 'direction': 1, 'impact_coefficient': 0.10}
        
        neutral = meta.get('neutral', 0)
        range_width = meta.get('range', 1)
        direction = meta.get('direction', 1)
        coefficient = meta.get('impact_coefficient', 0.10)
        
        # 4. 避免除零
        if range_width == 0:
            self.logger.warning(f"⚠️ 指标 {indicator} 的 range=0，跳过")
            return None
        
        # 5. 数据新鲜度校验（可选）
        if 'update_time' in self.data:
            update_time = self.data['update_time']
            if isinstance(update_time, str):
                try:
                    update_time = datetime.fromisoformat(update_time.replace('Z', '+00:00'))
                except:
                    update_time = None
            
            if update_time:
                lag_days = (datetime.now() - update_time).days
                tolerance = meta.get('lag_tolerance_days', self.lag_tolerance)
                if lag_days > tolerance:
                    self.logger.warning(f"⚠️ 指标 {indicator} 数据滞后 {lag_days} 天 > 容忍 {tolerance} 天")
                    # 可选：降级使用或返回 None
                    # return None
        
        # 6. 计算标准化偏差
        deviation = (current - neutral) / range_width
        
        # 7. 计算影响值：偏差 × 方向 × 系数
        impact = deviation * direction * coefficient
        
        # 8. 截断到安全范围
        impact = np.clip(impact, self.impact_clip[0], self.impact_clip[1])
        
        return float(impact), meta
    
    def get_macro_report(self) -> Dict:
        """生成宏观分析简报"""
        report = {
            'sector': self.sector,
            'sensitivity': self.sensitivity,
            'adjustment_factor': self.get_adjustment_factor(),
            'indicators': {}
        }
        
        linked = self.params.get('macro_link', [])
        for ind in linked:
            val = self.data.get(ind)
            meta = self.INDICATOR_META.get(ind, {})
            report['indicators'][ind] = {
                'current_value': val,
                'neutral': meta.get('neutral'),
                'unit': meta.get('unit'),
                'impact': self._calculate_indicator_impact(ind)
            }
            
        return report
    
    def get_detailed_report(self) -> Dict[str, Any]:
        """
        生成详细宏观分析报告（用于调试/可视化）
        
        返回:
            Dict: 包含因子分解、指标贡献、诊断信息
        """
        linked_indicators = (
            self.params.get('macro_link') or 
            self.config_macros.get('sector_macro_link', {}).get(self.sector) or
            self.sector_link.get(self.sector, ['pmi'])
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
                'status': 'valid' if result else 'invalid'
            }
            
            if result:
                impact, _ = result
                deviation = (self.data[indicator] - meta.get('neutral', 0)) / meta.get('range', 1)
                detail['impact'] = round(impact, 4)
                detail['deviation'] = round(deviation, 3)
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
            }
        }

    def check_data_freshness(self) -> Dict[str, str]:
        """
        检查宏观数据新鲜度
        
        返回:
            Dict[indicator -> 'fresh'/'stale'/'missing']
        """
        freshness = {}
        now = datetime.now()
        
        for indicator, meta in self.indicator_meta.items():
            if indicator not in self.data:
                freshness[indicator] = 'missing'
                continue
            
            # 检查是否有更新时间
            update_key = f'{indicator}_update_time'
            update_time = self.data.get(update_key)
            
            if update_time is None:
                freshness[indicator] = 'unknown'  # 无时间标记，假设新鲜
                continue
            
            if isinstance(update_time, str):
                try:
                    update_time = datetime.fromisoformat(update_time.replace('Z', '+00:00'))
                except:
                    freshness[indicator] = 'parse_error'
                    continue
            
            lag_days = (now - update_time).days
            tolerance = meta.get('lag_tolerance_days', self.lag_tolerance)
            
            if lag_days <= tolerance:
                freshness[indicator] = 'fresh'
            else:
                freshness[indicator] = f'stale({lag_days}d>{tolerance}d)'
        
        return freshness
# 测试
if __name__ == '__main__':
    # 模拟宏观数据
    macro_data = {
        'brent_crude': 104.66,
        'comex_gold': 4693.38,
        'lme_copper': 9500,
        'pmi': 51.2,
        'm2_growth': 9.5,
        'usd_cny': 7.22,
    }
    
    calc = MacroCalculator(macro_data)
    
    print("\n" + "="*60)
    print("宏观面计算测试结果")
    print("="*60)
    print(f"油气开采宏观系数：{calc.get_sector_factor('油气开采')}")
    print(f"黄金宏观系数：{calc.get_sector_factor('黄金')}")
    print(f"新能源宏观系数：{calc.get_sector_factor('新能源')}")
    print(f"宏观环境评分：{calc.get_macro_environment_score()}分")