#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
宏观面联动计算模块
"""

import logging
from config import SECTOR_MACRO_LINK

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MacroCalculator:
    """宏观面计算器"""
    
    def __init__(self, macro_data):
        """
        初始化
        :param macro_data: 宏观数据字典
        """
        self.data = macro_data
    
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