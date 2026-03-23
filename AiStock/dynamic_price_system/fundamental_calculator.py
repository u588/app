#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基本面评分模块
"""

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FundamentalCalculator:
    """基本面评分器"""
    
    def __init__(self, financial_data):
        """
        初始化
        :param financial_data: 财务数据字典
        """
        self.data = financial_data
    
    def calculate_score(self):
        """计算基本面综合评分（0-100 分）"""
        if not self.data:
            return 50  # 默认中等评分
        
        scores = {
            'revenue_growth': self._score_revenue_growth(),
            'profit_growth': self._score_profit_growth(),
            'roe': self._score_roe(),
            'gross_margin': self._score_gross_margin(),
            'debt_ratio': self._score_debt_ratio(),
        }
        
        weights = {
            'revenue_growth': 0.25,
            'profit_growth': 0.30,
            'roe': 0.20,
            'gross_margin': 0.15,
            'debt_ratio': 0.10,
        }
        
        total_score = sum(scores[k] * weights[k] for k in scores)
        
        logger.info(f"基本面评分：{total_score:.1f}分")
        return round(total_score, 1)
    
    def _score_revenue_growth(self):
        """营收增速评分"""
        try:
            growth = self.data.get('revenue_growth', 0)
            if growth > 20:
                return 100
            elif growth > 10:
                return 80
            elif growth > 0:
                return 60
            else:
                return 40
        except:
            return 50
    
    def _score_profit_growth(self):
        """净利润增速评分"""
        try:
            growth = self.data.get('profit_growth', 0)
            if growth > 25:
                return 100
            elif growth > 15:
                return 80
            elif growth > 5:
                return 60
            else:
                return 40
        except:
            return 50
    
    def _score_roe(self):
        """ROE 评分"""
        try:
            roe = self.data.get('roe', 0)
            if roe > 15:
                return 100
            elif roe > 10:
                return 80
            elif roe > 5:
                return 60
            else:
                return 40
        except:
            return 50
    
    def _score_gross_margin(self):
        """毛利率评分"""
        try:
            margin = self.data.get('gross_margin', 0)
            if margin > 30:
                return 100
            elif margin > 20:
                return 80
            elif margin > 10:
                return 60
            else:
                return 40
        except:
            return 50
    
    def _score_debt_ratio(self):
        """负债率评分（越低越好）"""
        try:
            ratio = self.data.get('debt_ratio', 50)
            if ratio < 40:
                return 100
            elif ratio < 60:
                return 80
            elif ratio < 70:
                return 60
            else:
                return 40
        except:
            return 50
    
    def get_fundamental_factor(self):
        """获取基本面价格调整系数"""
        score = self.calculate_score()
        
        if score >= 80:
            return 1.05 + (score - 80) * 0.0025  # 最高 1.10
        elif score >= 60:
            return 0.95 + (score - 60) * 0.005  # 0.95-1.05
        elif score >= 40:
            return 0.85 + (score - 40) * 0.005  # 0.85-0.95
        else:
            return 0.75 + score * 0.0025  # 最低 0.75
    
    def get_recommendation(self):
        """获取基本面建议"""
        score = self.calculate_score()
        
        if score >= 80:
            return "优秀"
        elif score >= 60:
            return "良好"
        elif score >= 40:
            return "一般"
        else:
            return "警惕"


# 测试
if __name__ == '__main__':
    # 模拟财务数据
    financial_data = {
        'revenue_growth': 15.5,
        'profit_growth': 22.3,
        'roe': 18.5,
        'gross_margin': 28.5,
        'debt_ratio': 45.0,
    }
    
    calc = FundamentalCalculator(financial_data)
    
    print("\n" + "="*60)
    print("基本面评分测试结果")
    print("="*60)
    print(f"综合评分：{calc.calculate_score()}分")
    print(f"价格调整系数：{calc.get_fundamental_factor():.3f}")
    print(f"基本面建议：{calc.get_recommendation()}")