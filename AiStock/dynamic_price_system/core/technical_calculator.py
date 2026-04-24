#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TechnicalCalculator：技术面指标计算与价格生成模块
功能：
  - 计算 MA/ATR/RSI/MACD/波动率/布林带
  - 根据 stock_params 生成动态入场/止损/目标价
  - 数据不足时自动降级或返回安全默认值
版本：2.1.0
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, List
import logging
import warnings

logger = logging.getLogger(__name__)


class TechnicalCalculator:
    """技术指标计算器"""
    
    # 必需的数据列
    REQUIRED_COLUMNS = ['open', 'high', 'low', 'close', 'volume']
    MIN_DATA_LENGTH = 60  # 最小数据长度（保证指标计算）
    
    def __init__(self, df: pd.DataFrame, params: Optional[Dict] = None):
        """
        初始化技术指标计算器
        
        参数:
            df: 日线数据 DataFrame（必需列：open/high/low/close/volume）
            params: 个性化参数配置（可选）
                - entry_ma_period: 入场均线周期 (default: 20)
                - atr_period: ATR 计算周期 (default: 14)
                - rsi_period: RSI 计算周期 (default: 14)
                - volatility_lookback: 波动率窗口 (default: 20)
                - stop_loss_atr_mult: 止损 ATR 倍数 (default: 3.0)
                - target_multiplier: 目标价乘数 (default: 1.20)
        """
        self.df = df.copy().sort_index()
        self.params = params or {}
        
        # 参数解析（带默认值）
        self.ma_period = int(self.params.get('entry_ma_period', 20))
        self.atr_period = int(self.params.get('atr_period', 14))
        self.rsi_period = int(self.params.get('rsi_period', 14))
        self.volatility_window = int(self.params.get('volatility_lookback', 20))
        self.stop_loss_atr_mult = float(self.params.get('stop_loss_atr_mult', 3.0))
        self.target_multiplier = float(self.params.get('target_multiplier', 1.20))
        
        # 缓存最新指标（避免重复计算）
        self._latest: Optional[Dict] = None
        
        # 数据校验 + 指标计算
        if not self._validate_data():
            logger.warning("⚠️ 数据校验失败，技术指标可能不完整")
        
        self._calculate_all_indicators()
        self._cache_latest_indicators()
    
    def _validate_data(self) -> bool:
        """校验输入数据完整性"""
        # 检查必需列
        missing_cols = set(self.REQUIRED_COLUMNS) - set(self.df.columns)
        if missing_cols:
            logger.error(f"❌ 缺失必需列: {missing_cols}")
            return False
        
        # 检查数据长度
        if len(self.df) < self.MIN_DATA_LENGTH:
            logger.warning(f"⚠️ 数据长度 {len(self.df)} < 最小要求 {self.MIN_DATA_LENGTH}，部分指标可能不准确")
            return False
        
        # 检查空值
        null_ratio = self.df[self.REQUIRED_COLUMNS].isnull().mean().max()
        if null_ratio > 0.1:  # 允许 10% 空值
            logger.warning(f"⚠️ 关键列空值比例 {null_ratio:.1%} > 10%，已自动填充")
            self.df[self.REQUIRED_COLUMNS] = self.df[self.REQUIRED_COLUMNS].fillna(method='ffill').fillna(method='bfill')
        
        return True
    
    def _calculate_all_indicators(self):
        """计算所有技术指标（异常隔离）"""
        indicators = [
            ('MA', self._calculate_ma),
            ('ATR', self._calculate_atr),
            ('RSI', self._calculate_rsi),
            ('MACD', self._calculate_macd),
            ('BOLL', self._calculate_boll),
            ('Volatility', self._calculate_volatility),  # ✅ 修复拼写
            ('ADX', self._calculate_adx),               # ✅ 新增
            ('Vol_Avg', self._calculate_vol_avg)        # ✅ 新增
        ]
        
        for name, func in indicators:
            try:
                func()
            except Exception as e:
                logger.warning(f"⚠️ {name} 指标计算失败: {e}，该指标将不可用")
    
    def _calculate_ma(self):
        """计算均线系统"""
        # 短期均线（可配置）
        self.df['ma_short'] = self.df['close'].rolling(self.ma_period, min_periods=1).mean()
        # 长期均线（3 倍短期）
        self.df['ma_long'] = self.df['close'].rolling(self.ma_period * 3, min_periods=1).mean()
    
    def _calculate_atr(self):
        """计算 ATR（平均真实波幅）"""
        high = self.df['high']
        low = self.df['low']
        close_prev = self.df['close'].shift(1)
        
        tr1 = high - low
        tr2 = (high - close_prev).abs()
        tr3 = (low - close_prev).abs()
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        # ✅ 使用实例参数
        self.df['atr14'] = tr.rolling(self.atr_period, min_periods=1).mean()
    
    def _calculate_rsi(self):
        """计算 RSI（相对强弱指标）"""
        delta = self.df['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(self.rsi_period, min_periods=1).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(self.rsi_period, min_periods=1).mean()
        
        # 避免除零
        rs = gain / loss.replace(0, np.nan)
        self.df['rsi14'] = 100 - (100 / (1 + rs))
    
    def _calculate_macd(self):
        """计算 MACD（指数平滑异同移动平均线）"""
        exp12 = self.df['close'].ewm(span=12, adjust=False).mean()
        exp26 = self.df['close'].ewm(span=26, adjust=False).mean()
        
        self.df['macd_dif'] = exp12 - exp26
        self.df['macd_dea'] = self.df['macd_dif'].ewm(span=9, adjust=False).mean()
        self.df['macd_hist'] = self.df['macd_dif'] - self.df['macd_dea']
    
    def _calculate_boll(self, period=20, width=2):
        """计算布林带"""
        self.df['boll_mid'] = self.df['close'].rolling(period, min_periods=1).mean()
        std = self.df['close'].rolling(period, min_periods=1).std()
        self.df['boll_upper'] = self.df['boll_mid'] + width * std
        self.df['boll_lower'] = self.df['boll_mid'] - width * std

    def _calculate_adx(self, period=14):
        """
        计算 ADX (平均趋向指数) 及 +DI/-DI
        逻辑: 使用 Wilder 平滑法，等效于 EMA(alpha=1/period)
        """
        high = self.df['high']
        low = self.df['low']
        close_prev = self.df['close'].shift(1)

        # 1. 计算 +DM 和 -DM
        plus_dm = high.diff()
        minus_dm = -low.diff()
        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)

        # 2. 计算 TR (True Range)
        tr = pd.concat([
            high - low,
            (high - close_prev).abs(),
            (low - close_prev).abs()
        ], axis=1).max(axis=1)

        # 3. Wilder 平滑
        alpha = 1.0 / period
        smooth_tr = tr.ewm(alpha=alpha, adjust=False).mean()
        smooth_plus_dm = plus_dm.ewm(alpha=alpha, adjust=False).mean()
        smooth_minus_dm = minus_dm.ewm(alpha=alpha, adjust=False).mean()

        # 4. 计算 DI (防除零)
        self.df['plus_di'] = 100 * smooth_plus_dm / smooth_tr.replace(0, np.nan)
        self.df['minus_di'] = 100 * smooth_minus_dm / smooth_tr.replace(0, np.nan)

        # 5. 计算 DX 和 ADX
        di_sum = self.df['plus_di'] + self.df['minus_di']
        di_diff = (self.df['plus_di'] - self.df['minus_di']).abs()
        dx = 100 * di_diff / di_sum.replace(0, np.nan)
        self.df['adx'] = dx.ewm(alpha=alpha, adjust=False).mean()

    def _calculate_vol_avg(self, period=20):
        """计算 N 日平均成交量（兼容 volume/vol 列名）"""
        vol_col = 'volume' if 'volume' in self.df.columns else 'vol'
        if vol_col in self.df.columns:
            self.df['vol_20d_avg'] = self.df[vol_col].rolling(period, min_periods=1).mean()
        else:
            self.logger.warning("⚠️ 未找到成交量列 (volume/vol)，跳过 vol_20d_avg 计算")
    
    def _calculate_volatility(self):
        """计算年化波动率（250 交易日）"""
        returns = self.df['close'].pct_change()
        # ✅ 使用实例参数 + 修复列名
        self.df['volatility'] = returns.rolling(self.volatility_window, min_periods=1).std() * np.sqrt(250)
    
    def _cache_latest_indicators(self):
        """缓存最新指标值（避免重复访问 DataFrame）"""
        if self.df.empty:
            self._latest = {}
            return
        
        latest = self.df.iloc[-1]
        self._latest = {
            'close': float(latest['close']),
            'volume': float(latest['volume']),
            'ma_short': float(latest['ma_short']) if 'ma_short' in latest else None,
            'ma_long': float(latest['ma_long']) if 'ma_long' in latest else None,
            'atr14': float(latest['atr14']) if 'atr14' in latest else None,
            'rsi14': float(latest['rsi14']) if 'rsi14' in latest else None,
            'macd_dif': float(latest['macd_dif']) if 'macd_dif' in latest else None,
            'macd_dea': float(latest['macd_dea']) if 'macd_dea' in latest else None,
            'macd_hist': float(latest['macd_hist']) if 'macd_hist' in latest else None,
            'boll_upper': float(latest['boll_upper']) if 'boll_upper' in latest else None,
            'boll_lower': float(latest['boll_lower']) if 'boll_lower' in latest else None,
            'volatility': float(latest['volatility']) if 'volatility' in latest else None,
            'adx': float(latest['adx']) if 'adx' in latest and pd.notna(latest['adx']) else None,
            'plus_di': float(latest['plus_di']) if 'plus_di' in latest and pd.notna(latest['plus_di']) else None,
            'minus_di': float(latest['minus_di']) if 'minus_di' in latest and pd.notna(latest['minus_di']) else None,
            'vol_20d_avg': float(latest['vol_20d_avg']) if 'vol_20d_avg' in latest and pd.notna(latest['vol_20d_avg']) else None
        }
    
    def get_latest_indicators(self) -> Optional[Dict[str, Optional[float]]]:
        """
        获取最新技术指标值
        
        返回:
            Dict: 指标字典，数据不足时返回 None
        """
        return self._latest.copy() if self._latest else None
    
    # ==================== 价格生成方法（新版接口） ====================
    
    def get_entry_price(self) -> Optional[float]:
        """
        生成动态入场价（基于均线 + 波动率 + RSI）
        
        逻辑:
          1. 基准价 = 短期均线 × (1 - 波动率×0.5)
          2. RSI<30 时额外折扣 0.5%
          3. 数据缺失时降级为 现价×0.98
        
        返回:
            float: 入场价格，计算失败返回 None
        """
        try:
            if not self._latest:
                return None
            
            close = self._latest.get('close')
            ma_short = self._latest.get('ma_short')
            rsi14 = self._latest.get('rsi14')  # ✅ 修复：rsi14
            volatility = self._latest.get('volatility') or 0.2
            
            if close is None or ma_short is None:
                logger.warning("⚠️ 价格或均线缺失，降级为 现价×0.98")
                return round(close * 0.98, 2) if close else None
            
            # 基础入场：均线附近 + 波动率缓冲
            base_entry = ma_short * (1 - volatility * 0.5)
            
            # RSI 超卖修正
            if rsi14 and rsi14 < 30:
                base_entry *= 0.995
            
            return round(base_entry, 2)
            
        except Exception as e:
            logger.error(f"❌ 入场价计算异常: {e}", exc_info=True)
            return None
    
    def get_stop_loss(self, entry_price: float) -> Optional[float]:
        """
        生成动态止损价（基于 ATR）
        
        逻辑:
          1. 首选: 入场价 - ATR×倍数
          2. 降级: 入场价×0.92（固定 8% 止损）
        
        参数:
            entry_price: 入场价格
        
        返回:
            float: 止损价格
        """
        try:
            if entry_price is None:
                return None
            
            atr14 = self._latest.get('atr14')  # ✅ 修复：atr14
            
            if atr14 and atr14 > 0:
                return round(entry_price - atr14 * self.stop_loss_atr_mult, 2)
            
            # 降级方案
            logger.debug("⚠️ ATR 不可用，降级为固定比例止损")
            return round(entry_price * 0.92, 2)
            
        except Exception as e:
            logger.error(f"❌ 止损价计算异常: {e}")
            return round(entry_price * 0.92, 2) if entry_price else None
    
    def get_target_price(self, entry_price: float) -> Optional[float]:
        """
        生成动态目标价（基于乘数 + 布林带上轨约束）
        
        逻辑:
          1. 基础目标: 入场价 × 乘数
          2. 布林带约束: 不超过上轨×1.02（避免过度乐观）
        
        参数:
            entry_price: 入场价格
        
        返回:
            float: 目标价格
        """
        try:
            if entry_price is None:
                return None
            
            base_target = entry_price * self.target_multiplier
            bb_upper = self._latest.get('boll_upper')
            
            # 布林带上轨约束
            if bb_upper and base_target > bb_upper:
                logger.debug(f"🎯 目标价受布林带上轨约束: {base_target:.2f} → {bb_upper*1.02:.2f}")
                base_target = bb_upper * 1.02
            
            return round(base_target, 2)
            
        except Exception as e:
            logger.error(f"❌ 目标价计算异常: {e}")
            return round(entry_price * self.target_multiplier, 2) if entry_price else None
    
    def get_all_signals(self) -> Dict:
        """
        获取完整技术信号字典
        
        返回:
            Dict: {
                'status': 'valid' | 'insufficient_data',
                'indicators': {...},
                'entry_price': float,
                'stop_loss': float,
                'target_price': float,
                'trend': 'bullish' | 'bearish',
                'rsi_zone': 'oversold' | 'overbought' | 'neutral'
            }
        """
        if not self._latest:
            return {'status': 'insufficient_data', 'indicators': {}}
        
        entry = self.get_entry_price()
        if entry is None:
            return {'status': 'insufficient_data', 'indicators': self._latest}
        
        # 趋势判断
        ma_short = self._latest.get('ma_short', 0)
        ma_long = self._latest.get('ma_long', 0)
        trend = 'bullish' if ma_short > ma_long else 'bearish'
        
        # RSI 区间
        rsi14 = self._latest.get('rsi14', 50)
        if rsi14 < 30:
            rsi_zone = 'oversold'
        elif rsi14 > 70:
            rsi_zone = 'overbought'
        else:
            rsi_zone = 'neutral'
        
        return {
            'status': 'valid',
            'indicators': self._latest.copy(),
            'entry_price': entry,
            'stop_loss': self.get_stop_loss(entry),
            'target_price': self.get_target_price(entry),
            'trend': trend,
            'rsi_zone': rsi_zone
        }
    
# ==================== 测试工具函数（可独立导入） ====================

def generate_mock_ohlcv(
    periods: int = 200,
    start_price: float = 100.0,
    volatility: float = 0.02,
    seed: Optional[int] = None
) -> pd.DataFrame:
    """
    生成模拟 OHLCV 数据（用于测试）
    
    参数:
        periods: 数据长度
        start_price: 起始价格
        volatility: 日波动率
        seed: 随机种子
    
    返回:
        pd.DataFrame: 包含 open/high/low/close/volume 的模拟数据
    """
    if seed is not None:
        np.random.seed(seed)
    
    dates = pd.date_range(end=pd.Timestamp.now(), periods=periods, freq='D')
    
    # 生成随机游走价格
    returns = np.random.normal(0.0005, volatility, periods)
    close = start_price * np.cumprod(1 + returns)
    
    # 生成 OHLC（简化模型）
    open_ = close * (1 + np.random.randn(periods) * 0.005)
    high = np.maximum(open_, close) * (1 + np.abs(np.random.randn(periods) * 0.01))
    low = np.minimum(open_, close) * (1 - np.abs(np.random.randn(periods) * 0.01))
    volume = np.random.randint(1_000_000, 10_000_000, periods)
    
    return pd.DataFrame({
        'open': open_,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume
    }, index=dates)


# ==================== 主程序（测试入口） ====================

if __name__ == '__main__':
    # 生成测试数据
    print("🧪 生成模拟数据...")
    test_df = generate_mock_ohlcv(periods=200, start_price=100, seed=42)
    
    # 初始化计算器
    print("🔧 初始化 TechnicalCalculator...")
    calc = TechnicalCalculator(
        test_df,
        params={
            'entry_ma_period': 20,
            'stop_loss_atr_mult': 3.0,
            'target_multiplier': 1.20
        }
    )
    
    # 测试各方法
    print("\n" + "="*60)
    print("📊 技术指标计算结果")
    print("="*60)
    
    indicators = calc.get_latest_indicators()
    if indicators:
        print(f"📈 最新收盘价: ¥{indicators['close']:.2f}")
        print(f"📊 MA20: ¥{indicators['ma_short']:.2f} | MA60: ¥{indicators['ma_long']:.2f}")
        print(f"📉 ATR(14): ¥{indicators['atr14']:.2f} | RSI(14): {indicators['rsi14']:.1f}")
        print(f"📦 波动率: {indicators['volatility']:.1%} (年化)")
    
    print("\n🎯 动态价格信号")
    signals = calc.get_all_signals()
    if signals['status'] == 'valid':
        print(f"✅ 状态: 有效")
        print(f"📍 入场价: ¥{signals['entry_price']:.2f}")
        print(f"🛑 止损价: ¥{signals['stop_loss']:.2f}")
        print(f"🎯 目标价: ¥{signals['target_price']:.2f}")
        print(f"📈 趋势: {signals['trend']} | RSI 区间: {signals['rsi_zone']}")
        
        # 计算盈亏比
        risk = signals['entry_price'] - signals['stop_loss']
        reward = signals['target_price'] - signals['entry_price']
        pl_ratio = reward / risk if risk > 0 else 0
        print(f"⚖️ 盈亏比: {pl_ratio:.2f}x")
    else:
        print(f"❌ 状态: 数据不足，无法生成信号")
    
    print("\n" + "="*60)