#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FundamentalCalculator：基本面评分与调整系数模块
功能：
  - 将财务指标标准化为 0-100 分
  - 根据权重计算综合评分
  - 映射为价格调整系数 (0.90 ~ 1.10)
  - 支持缺失值降级与行业代理
"""

import logging
from typing import Dict, Optional, List
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FundamentalCalculator:
    """基本面计算器"""
    
    # 指标标准化参考区间 (行业经验值)
    REFERENCE_RANGES = {
        'revenue_growth': (0.0, 0.50),      # 营收增速 0%~50%
        'profit_growth': (0.0, 0.60),       # 利润增速 0%~60%
        'roe': (0.0, 0.30),                 # ROE 0%~30%
        'gross_margin': (0.0, 0.50),        # 毛利率 0%~50%
        'debt_ratio': (0.80, 0.0)           # 负债率 (反向：80%~0%)
    }
    
    DEFAULT_WEIGHTS = {
        'revenue_growth': 0.25,
        'profit_growth': 0.25,
        'roe': 0.20,
        'gross_margin': 0.15,
        'debt_ratio': 0.15
    }
 
    # def __init__(self, financial_data):
    #     """
    #     初始化
    #     :param financial_data: 财务数据字典
    #     """
    #     self.data = financial_data
    
    def __init__(self, financial_data: Dict, params: Optional[Dict] = None):
        self.data = financial_data or {}
        self.params = params or {}
        self.logger = logger
        self.weights = self._resolve_weights()    
    
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

## ========= 进阶版本：支持动态权重与详细分解 ==========
    def _resolve_weights(self) -> Dict:
        """解析权重配置"""
        weights = self.DEFAULT_WEIGHTS.copy()
        for k, v in self.params.items():
            if k.endswith('_weight') and k.replace('_weight', '') in weights:
                metric = k.replace('_weight', '')
                weights[metric] = float(v)
        
        # 归一化权重
        total = sum(weights.values())
        if total > 0:
            weights = {k: v/total for k, v in weights.items()}
        return weights
    
    def _normalize(self, metric: str, value: float) -> float:
        """将原始值标准化到 0-100 区间"""
        if value is None or np.isnan(value):
            return 50.0  # 缺失值默认中性分
        
        ref_min, ref_max = self.REFERENCE_RANGES.get(metric, (0, 1))
        
        # 负债率为反向指标
        if metric == 'debt_ratio':
            ref_min, ref_max = ref_max, ref_min
        
        if ref_max == ref_min:
            return 50.0
            
        normalized = ((value - ref_min) / (ref_max - ref_min)) * 100
        return np.clip(normalized, 0, 100)
    
    def get_score(self) -> float:
        """计算综合基本面评分 (0-100)"""
        if not self.data:
            self.logger.warning("⚠️ 财务数据为空，返回默认评分 50")
            return 50.0
        
        total_score = 0.0
        valid_count = 0
        
        for metric, weight in self.weights.items():
            raw_value = self.data.get(metric)
            score = self._normalize(metric, raw_value)
            total_score += score * weight
            valid_count += 1
        
        if valid_count == 0:
            return 50.0
            
        return round(total_score, 1)
    
    def get_adjustment_factor(self, score: Optional[float] = None) -> float:
        """
        将评分映射为价格调整系数
        映射规则:
          80-100 -> 1.05 ~ 1.10
          60-79  -> 1.00 ~ 1.05
          40-59  -> 0.95 ~ 1.00
          0-39   -> 0.90 ~ 0.95
        """
        if score is None:
            score = self.get_score()
            
        min_fund_score = self.params.get('min_fundamental_score', 50)
        if score < min_fund_score:
            self.logger.info(f"📉 基本面评分 {score} < 阈值 {min_fund_score}，启用降权因子")
        
        # 分段线性映射
        if score >= 80:
            factor = 1.05 + (score - 80) * 0.0025  # max 1.10
        elif score >= 60:
            factor = 1.00 + (score - 60) * 0.0025  # 1.00 ~ 1.05
        elif score >= 40:
            factor = 0.95 + (score - 40) * 0.0025  # 0.95 ~ 1.00
        else:
            factor = 0.90 + score * 0.00125        # 0.90 ~ 0.95
            
        return round(np.clip(factor, 0.85, 1.15), 3)
    
    def get_detailed_breakdown(self) -> Dict:
        """获取各指标详细得分与系数"""
        breakdown = {}
        for metric in self.weights:
            raw = self.data.get(metric)
            norm_score = self._normalize(metric, raw)
            breakdown[metric] = {
                'raw_value': raw,
                'normalized_score': round(norm_score, 1),
                'weight': round(self.weights[metric], 2),
                'weighted_score': round(norm_score * self.weights[metric], 2)
            }
            
        return {
            'total_score': self.get_score(),
            'adjustment_factor': self.get_adjustment_factor(),
            'components': breakdown
        }

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