#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
动态价格计算核心模块
"""

import logging
from config import STOCKS_CONFIG, WEIGHTS
from AiStock.dynamic_price_system.core.technical_calculator import TechnicalCalculator
from AiStock.dynamic_price_system.core.fundamental_calculator import FundamentalCalculator
from AiStock.dynamic_price_system.core.macro_calculator import MacroCalculator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DynamicPriceCalculator:
    """动态价格计算器"""
    
    def __init__(self, stocks_data, financial_data, macro_data):
        """
        初始化
        :param stocks_data: 股票日线数据字典 {code: df}
        :param financial_data: 财务数据字典 {code: data}
        :param macro_data: 宏观数据字典
        """
        self.stocks_data = stocks_data
        self.financial_data = financial_data
        self.macro_data = macro_data
    
    def calculate_all(self):
        """计算所有标的动态价格"""
        results = []
        
        for stock in STOCKS_CONFIG:
            code = stock['code']
            sector = stock['sector']
            
            result = self.calculate_single(code, sector)
            if result:
                results.append(result)
        
        logger.info(f"✅ 动态价格计算完成：{len(results)}只标的")
        return results
    
    def calculate_single(self, code, sector):
        """计算单只标的动态价格"""
        try:
            # 技术面计算
            df = self.stocks_data.get(code)
            if df is None or df.empty:
                logger.warning(f"⚠️ {code} 无日线数据")
                return None
            
            tech_calc = TechnicalCalculator(df)
            tech_entry = tech_calc.get_technical_entry_price()
            tech_stop = tech_calc.get_technical_stop_loss()
            tech_target = tech_calc.get_technical_target()
            
            if not all([tech_entry, tech_stop, tech_target]):
                return None
            
            # 基本面计算
            fin_data = self.financial_data.get(code, {})
            fin_calc = FundamentalCalculator(fin_data)
            fin_factor = fin_calc.get_fundamental_factor()
            fin_score = fin_calc.calculate_score()
            fin_rec = fin_calc.get_recommendation()
            
            # 宏观面计算
            macro_calc = MacroCalculator(self.macro_data)
            macro_factor = macro_calc.get_sector_factor(sector)
            
            # 三维加权综合
            final_entry = self._comprehensive_price(tech_entry, fin_factor, macro_factor)
            final_stop = self._comprehensive_price(tech_stop, fin_factor, macro_factor)
            final_target = self._comprehensive_price(tech_target, fin_factor, macro_factor)
            
            # 盈亏比计算
            profit_loss_ratio = (final_target - final_entry) / (final_entry - final_stop) \
                if (final_entry - final_stop) > 0 else 0
            
            # 投资建议
            recommendation = self._get_recommendation(profit_loss_ratio, fin_score)
            
            result = {
                'code': code,
                'sector': sector,
                'current_price': tech_calc.get_latest_indicators()['close'],
                'entry_price': round(final_entry, 2),
                'stop_loss': round(final_stop, 2),
                'target_price': round(final_target, 2),
                'profit_loss_ratio': round(profit_loss_ratio, 2),
                'fundamental_score': fin_score,
                'fundamental_rec': fin_rec,
                'macro_factor': macro_factor,
                'recommendation': recommendation,
            }
            
            logger.info(f"✅ {code} 动态价格计算完成")
            return result
            
        except Exception as e:
            logger.error(f"❌ {code} 动态价格计算失败：{e}")
            return None
    
    def _comprehensive_price(self, tech_price, fin_factor, macro_factor):
        """三维加权综合价格计算"""
        w_tech = WEIGHTS['technical']
        w_fin = WEIGHTS['fundamental']
        w_macro = WEIGHTS['macro']
        
        comprehensive = (
            tech_price * w_tech +
            tech_price * fin_factor * w_fin +
            tech_price * macro_factor * w_macro
        )
        
        return comprehensive
    
    def _get_recommendation(self, pl_ratio, fin_score):
        """生成投资建议"""
        if pl_ratio >= 3 and fin_score >= 70:
            return "强烈推荐"
        elif pl_ratio >= 2 and fin_score >= 60:
            return "推荐"
        elif pl_ratio >= 1.5 and fin_score >= 50:
            return "观望"
        else:
            return "谨慎"


# 测试
if __name__ == '__main__':
    import pandas as pd
    import numpy as np
    
    # 模拟数据
    dates = pd.date_range('2025-01-01', periods=100, freq='D')
    df = pd.DataFrame({
        'open': np.random.uniform(100, 110, 100),
        'high': np.random.uniform(110, 115, 100),
        'low': np.random.uniform(95, 105, 100),
        'close': np.random.uniform(100, 112, 100),
        'vol': np.random.uniform(1000000, 5000000, 100),
    }, index=dates)
    
    stocks_data = {'600938': df}
    financial_data = {'600938': {'revenue_growth': 15, 'profit_growth': 20, 'roe': 18, 'gross_margin': 30, 'debt_ratio': 40}}
    macro_data = {'brent_crude': 104.66, 'pmi': 51.2}
    
    calc = DynamicPriceCalculator(stocks_data, financial_data, macro_data)
    results = calc.calculate_all()
    
    print("\n" + "="*60)
    print("动态价格计算结果")
    print("="*60)
    for r in results:
        print(f"{r['code']}: 入场{r['entry_price']} 止损{r['stop_loss']} 目标{r['target_price']} 盈亏比{r['profit_loss_ratio']} 建议{r['recommendation']}")