#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TechnicalCalculator：技术面指标计算与价格生成模块
功能：
  - 计算 MA/ATR/RSI/MACD/波动率/布林带
  - 根据 stock_params 生成动态入场/止损/目标价
  - 数据不足时自动降级或返回安全默认值
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TechnicalCalculator:
    """技术指标计算器"""
    
    def __init__(self, df: pd.DataFrame, params: Optional[Dict] = None):
        """
        初始化
        :param df: 日线数据 DataFrame（包含 open/high/low/close/vol）
        """
        self.df = df.copy().sort_index()
        self.params = params or {}
        
        # 参数默认值
        self.ma_period = self.params.get('entry_ma_period', 20)
        self.atr_period = self.params.get('atr_period', 14)
        self.rsi_period = self.params.get('rsi_period', 14)
        self.volatility_window = self.params.get('volatility_lookback', 20)
        self.stop_loss_atr_mult = self.params.get('stop_loss_atr_mult', 3.0)
        self.target_multiplier = self.params.get('target_multiplier', 1.20)

        self._calculate_all_indicators()

    
    def _calculate_all_indicators(self):
        """计算所有技术指标"""
        self._calculate_ma()
        self._calculate_atr()
        self._calculate_rsi()
        self._calculate_macd()
        self._calculate_boll()
        self._calulate_volatility()
    
    def _calculate_ma(self):
        """计算均线"""
        self.df['ma_short'] = self.df['close'].rolling(self.ma_period, min_periods=1).mean()
        self.df['ma_long'] = self.df['close'].rolling(self.ma_period * 3, min_periods=1).mean()
    
    def _calculate_atr(self, period=14):
        """计算 ATR（平均真实波幅）"""
        high = self.df['high']
        low = self.df['low']
        close = self.df['close'].shift(1)
        
        tr1 = high - low
        tr2 = abs(high - close)
        tr3 = abs(low - close)
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        self.df['atr14'] = tr.rolling(period).mean()
    
    def _calculate_rsi(self, period=14):
        """计算 RSI"""
        delta = self.df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        
        rs = gain / loss
        self.df['rsi14'] = 100 - (100 / (1 + rs))
    
    def _calculate_macd(self):
        """计算 MACD"""
        exp1 = self.df['close'].ewm(span=12, adjust=False).mean()
        exp2 = self.df['close'].ewm(span=26, adjust=False).mean()
        
        self.df['macd_dif'] = exp1 - exp2
        self.df['macd_dea'] = self.df['macd_dif'].ewm(span=9, adjust=False).mean()
        self.df['macd_hist'] = self.df['macd_dif'] - self.df['macd_dea']
    
    def _calculate_boll(self, period=20, width=2):
        """计算布林带"""
        self.df['boll_mid'] = self.df['close'].rolling(period).mean()
        std = self.df['close'].rolling(period).std()
        self.df['boll_upper'] = self.df['boll_mid'] + width * std
        self.df['boll_lower'] = self.df['boll_mid'] - width * std
    
    def _calulate_volatility(self, period=20):
        """计算波动率（20 日标准差）"""
        returns = self.df['close'].pct_change()
        self.df['volatility'] = returns.rolling(period).std() * np.sqrt(250)
    
    def get_latest_indicators(self):
        """获取最新技术指标"""
        if self.df.empty:
            return None
        
        latest = self.df.iloc[-1]
        return {
            'close': latest['close'],
            'ma5': latest.get('ma5', None),
            'ma20': latest.get('ma20', None),
            'ma60': latest.get('ma60', None),
            'atr14': latest.get('atr14', None),
            'rsi14': latest.get('rsi14', None),
            'macd_dif': latest.get('macd_dif', None),
            'macd_dea': latest.get('macd_dea', None),
            'macd_hist': latest.get('macd_hist', None),
            'boll_upper': latest.get('boll_upper', None),
            'boll_lower': latest.get('boll_lower', None),
            'volatility_20': latest.get('volatility_20', None),
        }
    
    def get_technical_entry_price(self):
        """计算技术面入场价"""
        indicators = self.get_latest_indicators()
        if indicators is None:
            return None
        
        close = indicators['close']
        ma20 = indicators['ma20']
        ma60 = indicators['ma60']
        atr = indicators['atr14']
        rsi = indicators['rsi14']
        volatility = indicators['volatility']
        
        # 基础入场价（均线支撑）
        if close > ma20:  # 上升趋势
            base_entry = ma20 * 0.98
        else:
            base_entry = ma60 * 0.95 if ma60 else close * 0.95
        

        # ATR 波动调整
        atr_adjustment = atr * 1.5 if atr else close * 0.03
        
        # RSI 调整
        if rsi and rsi < 30:
            rsi_factor = 0.97
        elif rsi and rsi > 70:
            rsi_factor = 1.03
        else:
            rsi_factor = 1.00
        
        technical_entry = (base_entry - atr_adjustment) * rsi_factor
        
        return round(technical_entry, 2)
    
    def get_technical_stop_loss(self):
        """计算技术面止损价"""
        indicators = self.get_latest_indicators()
        if indicators is None:
            return None
        
        close = indicators['close']
        ma60 = indicators['ma60']
        atr = indicators['atr14']
        
        # 均线止损
        ma_stop = ma60 * 0.97 if ma60 else close * 0.95
        
        # ATR 止损
        atr_stop = close - (atr * 3) if atr else close * 0.90
        
        # 取较高者（更严格）
        technical_stop = max(ma_stop, atr_stop)
        
        return round(technical_stop, 2)
    
    def get_technical_target(self):
        """计算技术面目标价"""
        indicators = self.get_latest_indicators()
        if indicators is None:
            return None
        
        close = indicators['close']
        atr = indicators['atr14']
        
        # 前高（简化为近期最高）
        recent_high = self.df['high'].rolling(20).max().iloc[-1]
        high_target = recent_high * 1.05
        
        # 通道目标
        channel_target = close + (atr * 8) if atr else close * 1.20
        
        # 取较低者（更保守）
        technical_target = min(high_target, channel_target)
        
        return round(technical_target, 2)

## ====new====

    def get_entry_price(self) -> Optional[float]:
        """生成动态入场价"""
        try:
            close = self.indicators.get('close')
            ma_short = self.indicators.get('ma_short')
            rsi = self.indicators.get('rsi')
            volatility = self.indicators.get('volatility', 0.2)
            
            if close is None or ma_short is None:
                self.logger.warning("⚠️ 价格或均线数据缺失，使用当前价 * 0.98 作为保守入场")
                return close * 0.98 if close else None
            
            # 基础入场逻辑：均线附近 + 波动率缓冲
            base_entry = ma_short * (1 - volatility * 0.5)
            
            # RSI 超卖修正（<30 时进一步下移入场价）
            if rsi and rsi < 30:
                base_entry *= 0.995
            
            return round(base_entry, 2)
        except Exception as e:
            self.logger.error(f"❌ 入场价生成失败: {e}")
            return self.indicators.get('close')
    
    def get_stop_loss(self, entry_price: float) -> float:
        """生成动态止损价"""
        try:
            atr = self.indicators.get('atr', 0)
            if atr > 0:
                return round(entry_price - atr * self.stop_loss_atr_mult, 2)
            # 降级：固定比例止损
            return round(entry_price * 0.92, 2)
        except Exception as e:
            self.logger.error(f"❌ 止损价生成失败: {e}")
            return round(entry_price * 0.92, 2)
    
    def get_target_price(self, entry_price: float) -> float:
        """生成动态目标价"""
        try:
            # 基础目标：入场价 × 乘数
            base_target = entry_price * self.target_multiplier
            
            # 布林带上轨约束（避免过度乐观）
            bb_upper = self.indicators.get('bb_upper')
            if bb_upper and base_target > bb_upper:
                base_target = bb_upper * 1.02  # 略突破上轨
            
            return round(base_target, 2)
        except Exception as e:
            self.logger.error(f"❌ 目标价生成失败: {e}")
            return round(entry_price * self.target_multiplier, 2)
    
    def get_all_signals(self) -> Dict:
        """获取完整技术信号字典"""
        entry = self.get_entry_price()
        if entry is None:
            return {'status': 'insufficient_data', 'indicators': self.indicators}
        
        return {
            'status': 'valid',
            'indicators': self.indicators,
            'entry_price': entry,
            'stop_loss': self.get_stop_loss(entry),
            'target_price': self.get_target_price(entry),
            'trend': 'bullish' if self.indicators.get('ma_short', 0) > self.indicators.get('ma_long', 0) else 'bearish',
            'rsi_zone': 'oversold' if self.indicators.get('rsi', 50) < 30 else ('overbought' if self.indicators.get('rsi', 50) > 70 else 'neutral')
        }
        

# 测试
if __name__ == '__main__':
    # 模拟数据测试
    dates = pd.date_range('2025-01-01', periods=100, freq='D')
    df = pd.DataFrame({
        'open': np.random.uniform(100, 110, 100),
        'high': np.random.uniform(110, 115, 100),
        'low': np.random.uniform(95, 105, 100),
        'close': np.random.uniform(100, 112, 100),
        'vol': np.random.uniform(1000000, 5000000, 100),
    }, index=dates)
    
    calc = TechnicalCalculator(df)
    
    print("\n" + "="*60)
    print("技术指标测试结果")
    print("="*60)
    print(f"最新收盘价：{calc.get_latest_indicators()['close']}")
    print(f"技术入场价：{calc.get_technical_entry_price()}")
    print(f"技术止损价：{calc.get_technical_stop_loss()}")
    print(f"技术目标价：{calc.get_technical_target()}")