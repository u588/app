#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TechnicalConfidence：技术面置信度评估模块
功能：
  - 量化技术指标的信号质量 (0.98~1.02)
  - 支持配置化权重 + 阈值
  - 输出可解释的诊断信息
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict
import logging
import yaml

logger = logging.getLogger(__name__)


@dataclass
class ConfidenceConfig:
    """置信度计算配置"""
    # 权重配置 (总和=1.0)
    data_quality_weight: float = 0.40
    consistency_weight: float = 0.35
    strength_weight: float = 0.25
    
    # 阈值配置
    min_data_days: int = 60
    ideal_data_days: int = 250
    volume_spike_threshold: float = 1.2
    volume_drop_threshold: float = 0.8
    ma_separation_threshold: float = 0.02  # 均线分离 2%
    atr_ratio_min: float = 0.01  # ATR/价格 1%
    atr_ratio_max: float = 0.08  # ATR/价格 8%
    breakout_threshold: float = 0.03  # 突破 3%
    
    # 输出范围
    factor_min: float = 0.98
    factor_max: float = 1.02
    neutral_score: float = 0.5  # 得分 0.5→因子 1.0
    
    @classmethod
    def from_dict(cls, config: Dict) -> 'ConfidenceConfig':
        """从字典创建配置（支持部分覆盖）"""
        return cls(**{k: v for k, v in config.items() if k in cls.__dataclass_fields__})


@dataclass
class ConfidenceResult:
    """置信度计算结果"""
    factor: float  # 最终置信度因子 (0.98~1.02)
    score: float   # 原始得分 (0~1)
    level: str     # 'high'/'normal'/'low'
    
    # 分项得分
    data_quality_score: float
    consistency_score: float
    strength_score: float
    
    # 诊断信息
    diagnostics: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """转换为字典（便于日志/输出）"""
        return asdict(self)


class TechnicalConfidence:
    """技术面置信度评估器"""
    
    def __init__(self, config: Optional[ConfidenceConfig] = None):
        """
        初始化置信度评估器
        
        参数:
            config: 置信度配置（可选，使用默认值）
        """
        self.config = config or ConfidenceConfig()
        self.logger = logger
        
    def calculate(
        self,
        indicators: Dict[str, Any],
        stock_ pd.DataFrame,
        params: Optional[Dict] = None
    ) -> ConfidenceResult:
        """
        计算技术面置信度
        
        参数:
            indicators: 技术指标字典（来自 TechnicalCalculator）
            stock_ OHLCV 数据 DataFrame
            params: 标的个性化参数（可选，用于覆盖默认阈值）
        
        返回:
            ConfidenceResult: 置信度因子 + 诊断信息
        """
        # 应用参数覆盖（如有）
        if params:
            self._apply_param_overrides(params)
        
        # 1. 计算各分项得分
        dq_score = self._calculate_data_quality(stock_data)
        cs_score = self._calculate_consistency(indicators, stock_data)
        st_score = self._calculate_strength(indicators, stock_data)
        
        # 2. 加权融合
        total_score = (
            dq_score * self.config.data_quality_weight +
            cs_score * self.config.consistency_weight +
            st_score * self.config.strength_weight
        )
        total_score = np.clip(total_score, 0.0, 1.0)
        
        # 3. 映射到因子区间 [factor_min, factor_max]
        # 线性映射: score=neutral_score → factor=1.0
        factor = self._score_to_factor(total_score)
        factor = np.clip(factor, self.config.factor_min, self.config.factor_max)
        
        # 4. 确定等级
        if factor >= 1.01:
            level = 'high'
        elif factor <= 0.99:
            level = 'low'
        else:
            level = 'normal'
        
        # 5. 生成诊断信息
        diagnostics = self._generate_diagnostics(
            indicators, stock_data, dq_score, cs_score, st_score
        )
        
        return ConfidenceResult(
            factor=round(factor, 3),
            score=round(total_score, 3),
            level=level,
            data_quality_score=round(dq_score, 3),
            consistency_score=round(cs_score, 3),
            strength_score=round(st_score, 3),
            diagnostics=diagnostics
        )
    
    def _apply_param_overrides(self, params: Dict):
        """应用标的个性化参数覆盖"""
        # 示例：支持通过 stock_params 覆盖阈值
        if 'confidence_volume_spike' in params:
            self.config.volume_spike_threshold = params['confidence_volume_spike']
        if 'confidence_breakout' in params:
            self.config.breakout_threshold = params['confidence_breakout']
        # 可扩展其他参数...
    
    def _calculate_data_quality(self,  pd.DataFrame) -> float:
        """
        计算数据质量得分 (0~1)
        
        评估维度:
          • 数据长度 (50%)
          • 缺失值比例 (30%)
          • 数据新鲜度 (20%)
        """
        score = 0.0
        
        # 1. 数据长度评分 (50%)
        n_days = len(stock_data)
        if n_days >= self.config.ideal_data_days:
            score += 0.50
        elif n_days >= self.config.min_data_days:
            # 线性插值: 60 天→0.2, 250 天→0.5
            ratio = (n_days - self.config.min_data_days) / \
                   (self.config.ideal_data_days - self.config.min_data_days)
            score += 0.20 + ratio * 0.30
        else:
            score += 0.20 * (n_days / self.config.min_data_days)  # <60 天按比例
        
        # 2. 缺失值评分 (30%)
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        if all(col in stock_data.columns for col in required_cols):
            null_ratio = stock_data[required_cols].isnull().mean().mean()
            # null_ratio=0→1.0, null_ratio=0.1→0.5, null_ratio≥0.2→0.0
            missing_score = max(0, 1.0 - null_ratio * 5)  # 线性衰减
            score += 0.30 * missing_score
        
        # 3. 数据新鲜度 (20%)
        if not stock_data.empty and 'datetime' in stock_data.columns:
            last_date = stock_data['datetime'].iloc[-1]
            days_ago = (pd.Timestamp.now() - last_date).days
            # 1 天内→1.0, 3 天内→0.8, 7 天内→0.5, >7 天→0.2
            if days_ago <= 1:
                freshness_score = 1.0
            elif days_ago <= 3:
                freshness_score = 0.8
            elif days_ago <= 7:
                freshness_score = 0.5
            else:
                freshness_score = 0.2
            score += 0.20 * freshness_score
        
        return np.clip(score, 0.0, 1.0)
    
    def _calculate_consistency(
        self, 
        indicators: Dict[str, Any], 
        stock_ pd.DataFrame
    ) -> float:
        """
        计算指标一致性得分 (0~1)
        
        评估维度:
          • 均线排列 (40%)
          • 量价配合 (35%)
          • 指标共振 (25%)
        """
        checks = []
        
        # 1. 均线排列评分 (40%)
        ma_short = indicators.get('ma_short')
        ma_long = indicators.get('ma_long')
        close = indicators.get('close')
        
        if ma_short and ma_long and close:
            # 多头: close>ma_short>ma_long; 空头: close<ma_short<ma_long
            if ma_short > ma_long * (1 + self.config.ma_separation_threshold):
                if close > ma_short:
                    checks.append(1.0)  # 多头排列 + 价格在均线上
                elif close < ma_long:
                    checks.append(0.9)  # 多头排列但价格在下方（回调）
                else:
                    checks.append(0.7)  # 多头排列但价格在中间
            elif ma_short < ma_long * (1 - self.config.ma_separation_threshold):
                if close < ma_short:
                    checks.append(1.0)  # 空头排列 + 价格在均线下
                elif close > ma_long:
                    checks.append(0.9)  # 空头排列但价格在上方（反弹）
                else:
                    checks.append(0.7)
            else:
                checks.append(0.5)  # 均线粘合=方向不明
        else:
            checks.append(0.5)  # 数据缺失=中性
        
        # 2. 量价配合评分 (35%)
        volume = indicators.get('volume')
        vol_avg = indicators.get('vol_20d_avg')
        
        if volume and vol_avg and vol_avg > 0:
            volume_ratio = volume / vol_avg
            price_change = (close - stock_data['close'].iloc[-2]) / stock_data['close'].iloc[-2] if len(stock_data) >= 2 else 0
            
            # 量价同向=一致
            if (volume_ratio > self.config.volume_spike_threshold and price_change > 0) or \
               (volume_ratio < self.config.volume_drop_threshold and price_change < 0):
                checks.append(1.0)  # 放量上涨/缩量下跌=健康
            elif (volume_ratio > self.config.volume_spike_threshold and price_change < 0) or \
                 (volume_ratio < self.config.volume_drop_threshold and price_change > 0):
                checks.append(0.4)  # 放量下跌/缩量上涨=背离
            else:
                checks.append(0.7)  # 量能平淡=中性
        else:
            checks.append(0.7)  # 无量能数据=略保守
        
        # 3. 指标共振评分 (25%)
        rsi = indicators.get('rsi14')
        macd_hist = indicators.get('macd_hist')
        
        if rsi is not None and macd_hist is not None:
            # RSI 与 MACD 同向=共振
            rsi_signal = 1 if rsi > 50 else (-1 if rsi < 50 else 0)
            macd_signal = 1 if macd_hist > 0 else (-1 if macd_hist < 0 else 0)
            
            if rsi_signal == macd_signal and rsi_signal != 0:
                checks.append(1.0)  # 指标共振
            elif rsi_signal == 0 or macd_signal == 0:
                checks.append(0.7)  # 一个中性
            else:
                checks.append(0.4)  # 指标背离
        else:
            checks.append(0.7)  # 指标缺失=略保守
        
        # 加权平均
        weights = [0.40, 0.35, 0.25]
        score = sum(c * w for c, w in zip(checks, weights))
        
        return np.clip(score, 0.0, 1.0)
    
    def _calculate_strength(
        self,
        indicators: Dict[str, Any],
        stock_ pd.DataFrame
    ) -> float:
        """
        计算信号强度得分 (0~1)
        
        评估维度:
          • 突破强度 (50%)
          • 波动率适中 (30%)
          • 趋势强度 (20%)
        """
        score = 0.0
        close = indicators.get('close', 0)
        
        # 1. 突破强度 (50%)
        ma_short = indicators.get('ma_short')
        if ma_short and close:
            breakout = abs(close - ma_short) / ma_short
            # 突破 3%=满分，1.5%=半分，<0.5%=0 分
            if breakout >= self.config.breakout_threshold:
                score += 0.50
            elif breakout >= self.config.breakout_threshold * 0.5:
                score += 0.25
            # else: 0
        
        # 2. 波动率适中 (30%)
        atr = indicators.get('atr14')
        if atr and close:
            atr_ratio = atr / close
            # ATR/价格在 2-5% 为理想区间
            if self.config.atr_ratio_min <= atr_ratio <= self.config.atr_ratio_max * 0.6:
                score += 0.30  # 理想波动
            elif self.config.atr_ratio_min * 0.5 <= atr_ratio < self.config.atr_ratio_min or \
                 self.config.atr_ratio_max * 0.6 < atr_ratio <= self.config.atr_ratio_max * 1.2:
                score += 0.15  # 边缘波动
            # else: 0 (波动过小或过大)
        
        # 3. 趋势强度 (20%) - 使用 ADX 或均线斜率
        adx = indicators.get('adx')
        if adx is not None:
            # ADX>25=强趋势，15-25=中等，<15=无趋势
            if adx >= 25:
                score += 0.20
            elif adx >= 15:
                score += 0.10
        else:
            # 无 ADX 时用均线斜率近似
            if len(stock_data) >= 10 and ma_short:
                ma_prev = stock_data['close'].rolling(20).mean().iloc[-11] if len(stock_data) >= 11 else ma_short
                ma_slope = (ma_short - ma_prev) / ma_prev if ma_prev else 0
                if abs(ma_slope) >= 0.01:  # 10 日变化≥1%
                    score += 0.20
                elif abs(ma_slope) >= 0.005:
                    score += 0.10
        
        return np.clip(score, 0.0, 1.0)
    
    def _score_to_factor(self, score: float) -> float:
        """
        将原始得分 (0~1) 映射到因子区间 [factor_min, factor_max]
        
        映射规则:
          • score = neutral_score → factor = 1.0
          • score = 1.0 → factor = factor_max
          • score = 0.0 → factor = factor_min
        """
        if score >= self.config.neutral_score:
            # 上半段: neutral_score→1.0, 1.0→factor_max
            ratio = (score - self.config.neutral_score) / (1.0 - self.config.neutral_score)
            factor = 1.0 + ratio * (self.config.factor_max - 1.0)
        else:
            # 下半段: 0.0→factor_min, neutral_score→1.0
            ratio = score / self.config.neutral_score
            factor = self.config.factor_min + ratio * (1.0 - self.config.factor_min)
        
        return factor
    
    def _generate_diagnostics(
        self,
        indicators: Dict,
        stock_ pd.DataFrame,
        dq_score: float,
        cs_score: float,
        st_score: float
    ) -> Dict[str, Any]:
        """生成可解释的诊断信息"""
        return {
            'data_quality': {
                'score': dq_score,
                'days': len(stock_data),
                'missing_ratio': stock_data[['open','high','low','close','volume']].isnull().mean().mean() if not stock_data.empty else 1.0,
                'freshness_days': (pd.Timestamp.now() - stock_data['datetime'].iloc[-1]).days if 'datetime' in stock_data.columns and not stock_data.empty else 999
            },
            'consistency': {
                'score': cs_score,
                'ma_alignment': self._describe_ma_alignment(indicators),
                'volume_price': self._describe_volume_price(indicators, stock_data),
                'indicator_resonance': self._describe_indicator_resonance(indicators)
            },
            'strength': {
                'score': st_score,
                'breakout': self._describe_breakout(indicators),
                'volatility': self._describe_volatility(indicators),
                'trend': self._describe_trend(indicators, stock_data)
            }
        }
    
    def _describe_ma_alignment(self, indicators: Dict) -> str:
        """描述均线排列状态"""
        ma_s = indicators.get('ma_short')
        ma_l = indicators.get('ma_long')
        close = indicators.get('close')
        
        if not all([ma_s, ma_l, close]):
            return "数据不足"
        
        if ma_s > ma_l * (1 + self.config.ma_separation_threshold):
            if close > ma_s:
                return "多头排列 + 价格在上方"
            elif close < ma_l:
                return "多头排列 + 价格在下方(回调)"
            else:
                return "多头排列 + 价格在中间"
        elif ma_s < ma_l * (1 - self.config.ma_separation_threshold):
            if close < ma_s:
                return "空头排列 + 价格在下方"
            elif close > ma_l:
                return "空头排列 + 价格在上方(反弹)"
            else:
                return "空头排列 + 价格在中间"
        else:
            return "均线粘合(方向不明)"
    
    def _describe_volume_price(self, indicators: Dict,  pd.DataFrame) -> str:
        """描述量价配合状态"""
        volume = indicators.get('volume')
        vol_avg = indicators.get('vol_20d_avg')
        close = indicators.get('close')
        
        if not all([volume, vol_avg, close]) or vol_avg <= 0:
            return "量能数据不足"
        
        volume_ratio = volume / vol_avg
        price_change = (close - stock_data['close'].iloc[-2]) / stock_data['close'].iloc[-2] if len(stock_data) >= 2 else 0
        
        if volume_ratio > self.config.volume_spike_threshold and price_change > 0:
            return "放量上涨✅"
        elif volume_ratio < self.config.volume_drop_threshold and price_change < 0:
            return "缩量下跌✅"
        elif volume_ratio > self.config.volume_spike_threshold and price_change < 0:
            return "放量下跌⚠️"
        elif volume_ratio < self.config.volume_drop_threshold and price_change > 0:
            return "缩量上涨⚠️"
        else:
            return "量能平淡"
    
    def _describe_indicator_resonance(self, indicators: Dict) -> str:
        """描述指标共振状态"""
        rsi = indicators.get('rsi14')
        macd = indicators.get('macd_hist')
        
        if rsi is None or macd is None:
            return "指标数据不足"
        
        rsi_sig = "多" if rsi > 50 else ("空" if rsi < 50 else "中")
        macd_sig = "多" if macd > 0 else ("空" if macd < 0 else "中")
        
        if rsi_sig == macd_sig and rsi_sig != "中":
            return f"RSI({rsi_sig})+MACD({macd_sig}) 共振✅"
        elif rsi_sig == "中" or macd_sig == "中":
            return f"RSI({rsi_sig})/MACD({macd_sig}) 一中一强"
        else:
            return f"RSI({rsi_sig})+MACD({macd_sig}) 背离⚠️"
    
    def _describe_breakout(self, indicators: Dict) -> str:
        """描述突破强度"""
        close = indicators.get('close')
        ma = indicators.get('ma_short')
        
        if not all([close, ma]) or ma == 0:
            return "数据不足"
        
        breakout = abs(close - ma) / ma
        if breakout >= self.config.breakout_threshold:
            direction = "上破" if close > ma else "下破"
            return f"{direction}{breakout*100:.1f}%✅"
        elif breakout >= self.config.breakout_threshold * 0.5:
            direction = "微上破" if close > ma else "微下破"
            return f"{direction}{breakout*100:.1f}%"
        else:
            return f"盘整(距均线{breakout*100:.1f}%)"
    
    def _describe_volatility(self, indicators: Dict) -> str:
        """描述波动率状态"""
        atr = indicators.get('atr14')
        close = indicators.get('close')
        
        if not all([atr, close]) or close == 0:
            return "数据不足"
        
        ratio = atr / close * 100  # 转换为百分比
        if self.config.atr_ratio_min*100 <= ratio <= self.config.atr_ratio_max*100*0.6:
            return f"波动适中({ratio:.1f}%)✅"
        elif ratio < self.config.atr_ratio_min*100:
            return f"波动过低({ratio:.1f}%)⚠️"
        elif ratio > self.config.atr_ratio_max*100*1.2:
            return f"波动过高({ratio:.1f}%)⚠️"
        else:
            return f"波动边缘({ratio:.1f}%)"
    
    def _describe_trend(self, indicators: Dict,  pd.DataFrame) -> str:
        """描述趋势强度"""
        adx = indicators.get('adx')
        
        if adx is not None:
            if adx >= 25:
                return f"强趋势(ADX={adx:.0f})✅"
            elif adx >= 15:
                return f"中趋势(ADX={adx:.0f})"
            else:
                return f"无趋势(ADX={adx:.0f})⚠️"
        
        # 无 ADX 时用均线斜率
        if len(stock_data) >= 10:
            ma_curr = stock_data['close'].rolling(20).mean().iloc[-1]
            ma_prev = stock_data['close'].rolling(20).mean().iloc[-11] if len(stock_data) >= 11 else ma_curr
            slope = (ma_curr - ma_prev) / ma_prev * 100 if ma_prev else 0
            
            if abs(slope) >= 1.0:
                direction = "↑" if slope > 0 else "↓"
                return f"均线{direction}{abs(slope):.1f}%✅"
            elif abs(slope) >= 0.5:
                direction = "↑" if slope > 0 else "↓"
                return f"均线{direction}{abs(slope):.1f}%"
            else:
                return "均线走平⚠️"
        
        return "趋势数据不足"