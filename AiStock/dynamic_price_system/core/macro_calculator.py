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
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

config = ConfigService(system_name='dynamic_price')
SECTOR_MACRO_LINK = config.get('sector_macro_link', {})
class MacroCalculator:
    """宏观面计算器"""
    
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
    
    # def __init__(self, macro_data, sector):
    #     """
    #     初始化
    #     :param macro_data: 宏观数据字典
    #     """
    #     self.data = macro_data
    #     self.sector = sector

    def __init__(self, macro_data: Dict, sector: str, params: Optional[Dict] = None, 
                 config_macros: Optional[Dict] = None):
        self.macro_data = macro_data or {}
        self.sector = sector
        self.params = params or {}
        self.config_macros = config_macros or {}
        self.logger = logger
        
        self.sensitivity = self.params.get('macro_sensitivity', 1.0)
        self.correlation_window = self.params.get('correlation_window', 60)
        self.lag_tolerance = self.params.get('lag_tolerance_days', 3)
    
    def get_sector_factor(self, sector):
        """获取板块宏观调整系数"""
        if sector not in SECTOR_MACRO_LINK:
            return 1.00
        
        indicators = SECTOR_MACRO_LINK[sector]
        factors = []
        
        for indicator in indicators:
            value = self.data.get(indicator)
            if value is None:
                continue
            
            factor = self._calculate_indicator_factor(indicator, value)
            factors.append(factor)
        
        if not factors:
            return 1.00
        
        macro_factor = sum(factors) / len(factors)
        logger.info(f"{sector} 宏观系数：{macro_factor:.3f}")
        return round(macro_factor, 3)
    
    def _calculate_indicator_factor(self, indicator, value):
        """计算单个宏观指标的调整系数"""
        
        # 原油价格
        if indicator == 'brent_crude':
            if value > 90:
                return 1.05
            elif value > 80:
                return 1.02
            elif value > 70:
                return 1.00
            elif value > 60:
                return 0.98
            else:
                return 0.95
        
        # 黄金价格
        elif indicator == 'comex_gold':
            if value > 4500:
                return 1.05
            elif value > 4000:
                return 1.02
            elif value > 3500:
                return 1.00
            else:
                return 0.98
        
        # 铜价
        elif indicator == 'lme_copper':
            if value > 10000:
                return 1.03
            elif value > 9000:
                return 1.01
            elif value > 8000:
                return 1.00
            else:
                return 0.98
        
        # 天然气
        elif indicator == 'nymex_gas':
            if value > 3.5:
                return 1.03
            elif value > 2.5:
                return 1.01
            else:
                return 0.98
        
        # PMI
        elif indicator == 'pmi':
            if value > 52:
                return 1.03
            elif value > 50:
                return 1.01
            elif value > 48:
                return 1.00
            else:
                return 0.97
        
        # M2 增速
        elif indicator == 'm2_growth':
            if value > 10:
                return 1.03
            elif value > 8:
                return 1.01
            else:
                return 0.98
        
        # 国债收益率
        elif indicator == 'china_10y_bond':
            if value > 3.0:
                return 0.98
            elif value > 2.5:
                return 1.00
            else:
                return 1.02
        
        # CPI/PPI
        elif indicator in ['cpi', 'ppi']:
            if value > 3:
                return 1.02
            elif value > 1:
                return 1.00
            else:
                return 0.98
        
        # 汇率
        elif indicator == 'usd_cny':
            if value > 7.3:
                return 1.02  # 人民币贬值，出口受益
            elif value > 7.0:
                return 1.00
            else:
                return 0.99
        
        return 1.00
    
    def get_macro_environment_score(self):
        """获取宏观环境综合评分"""
        scores = []
        
        # PMI 评分
        pmi = self.data.get('pmi')
        if pmi:
            scores.append(min(100, max(0, (pmi - 45) * 20)))
        
        # M2 评分
        m2 = self.data.get('m2_growth')
        if m2:
            scores.append(min(100, max(0, (m2 - 5) * 10)))
        
        # 油价评分
        oil = self.data.get('brent_crude')
        if oil:
            if 70 <= oil <= 90:
                scores.append(80)
            elif 60 <= oil < 70 or 90 < oil <= 100:
                scores.append(60)
            else:
                scores.append(40)
        
        if not scores:
            return 50
        
        return round(sum(scores) / len(scores), 1)

## ============== new method ==============
    def get_adjustment_factor(self) -> float:
        """计算宏观联动调整系数"""
        if not self.macro_data:
            self.logger.warning("⚠️ 宏观数据为空，返回中性系数 1.0")
            return 1.0
        
        # 获取板块关联指标 (优先从 params 取，其次 config，最后默认)
        linked_indicators = self.params.get('macro_link', [])
        if not linked_indicators:
            # 默认板块映射
            default_map = {
                '油气开采': ['brent_crude', 'pmi'],
                'LNG': ['nymex_gas', 'usd_cny'],
                '黄金': ['comex_gold', 'china_10y_bond'],
                '新能源': ['lme_copper', 'm2_growth'],
                '军工': ['pmi', 'm2_growth']
            }
            linked_indicators = default_map.get(self.sector, ['pmi'])
        
        impacts = []
        valid_count = 0
        
        for indicator in linked_indicators:
            impact = self._calculate_indicator_impact(indicator)
            if impact is not None:
                impacts.append(impact)
                valid_count += 1
            else:
                self.logger.debug(f"🔍 指标 {indicator} 数据不足或过期，跳过")
        
        if valid_count == 0:
            return 1.0
            
        # 综合影响：算术平均后乘以敏感度
        avg_impact = np.mean(impacts)
        factor = 1.0 + avg_impact * self.sensitivity
        
        # 限制在中性区间内，防止极端行情导致因子失真
        neutral_range = self.params.get('neutral_range', [0.92, 1.08])
        factor = np.clip(factor, neutral_range[0], neutral_range[1])
        
        return round(float(factor), 3)
    
    def _calculate_indicator_impact(self, indicator: str) -> Optional[float]:
        """计算单个宏观指标的影响值 (-0.1 ~ 0.1)"""
        # 获取当前值
        current = self.macro_data.get(indicator)
        if current is None:
            return None
            
        # 获取元数据
        meta = self.INDICATOR_META.get(indicator, {})
        neutral = meta.get('neutral', 0)
        range_width = meta.get('range', 1)
        
        # 计算标准化偏差
        deviation = (current - neutral) / range_width
        
        # PMI 特殊处理：>50 利好，<50 利空
        if indicator == 'pmi':
            impact = deviation * 0.15
        # 国债收益率：上行利空成长/高估值，下行利好
        elif indicator in ['china_10y_bond', 'usd_cny']:
            impact = -deviation * 0.10
        # 大宗商品：上行利好资源/通胀受益板块
        elif indicator in ['brent_crude', 'comex_gold', 'lme_copper', 'nymex_gas']:
            impact = deviation * 0.12
        # 货币/流动性：M2上行利好
        elif indicator == 'm2_growth':
            impact = deviation * 0.08
        else:
            impact = deviation * 0.10
            
        return float(np.clip(impact, -0.15, 0.15))
    
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
            val = self.macro_data.get(ind)
            meta = self.INDICATOR_META.get(ind, {})
            report['indicators'][ind] = {
                'current_value': val,
                'neutral': meta.get('neutral'),
                'unit': meta.get('unit'),
                'impact': self._calculate_indicator_impact(ind)
            }
            
        return report
    

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