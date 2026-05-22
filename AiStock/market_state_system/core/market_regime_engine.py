#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
V7.0 MarketRegimeEngine：市场体制识别引擎（3D市场状态模型第3维度）

4种市场体制: Bull(牛市) / Bear(熊市) / Volatile(震荡) / Recovery(复苏)
识别维度: 波动率体制 + 动量体制 + 市场广度 → softmax综合概率 → 滞后确认

架构:
  ┌──────────────────────────────────────────────────┐
  │              MarketRegimeEngine                    │
  ├──────────────────────────────────────────────────┤
  │  1. VolatilityRegime  ← 20d/60d 滚动波动率        │
  │  2. MomentumRegime    ← 20d/60d 收益率            │
  │  3. BreadthRegime     ← 均线上方个股占比           │
  │  4. CompositeProb     ← softmax 综合概率           │
  │  5. Hysteresis        ← 3日确认机制                │
  └──────────────────────────────────────────────────┘
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional
from collections import deque
import logging

logger = logging.getLogger(__name__)

# CSI 300 基准指数
BENCHMARK_CODE = "000300"

# 体制标签
REGIME_BULL = "bull"
REGIME_BEAR = "bear"
REGIME_VOLATILE = "volatile"
REGIME_RECOVERY = "recovery"
ALL_REGIMES = [REGIME_BULL, REGIME_BEAR, REGIME_VOLATILE, REGIME_RECOVERY]


class MarketRegimeEngine:
    """
    V7 市场体制识别引擎

    通过波动率、动量、市场广度三维信号，经 softmax 综合为
    四种体制概率，再经滞后确认输出当前体制。
    """

    # 默认阈值（可被 config['market_regime'] 覆盖）
    DEFAULT_CONFIG = {
        "confirmation_days": 3,
        "volatility_window": 60,
        "momentum_window": 20,
        "regimes": {
            "bull": {
                "volatility_threshold": 0.15,
                "momentum_threshold": 0.05,
            },
            "bear": {
                "volatility_threshold": 0.30,
                "momentum_threshold": -0.05,
            },
            "volatile": {
                "volatility_threshold": 0.25,
                "momentum_range": [-0.02, 0.02],
            },
            "recovery": {
                "volatility_decreasing": True,
                "momentum_positive": True,
            },
        },
    }

    def __init__(self, data_service, config: Dict):
        """
        依赖注入初始化

        参数:
            data_service: DataLoadingService 实例，用于加载指数数据
            config: 系统配置字典，需包含 'market_regime' 节
        """
        self.data_service = data_service
        self.config = config.get("market_regime", self.DEFAULT_CONFIG)
        self.logger = logger

        # 确认天数
        self.confirmation_days = int(self.config.get("confirmation_days", 3))

        # 体制配置
        self.regime_config = self.config.get("regimes", self.DEFAULT_CONFIG["regimes"])

        # 滞后确认队列：存储最近 N 天的体制判断
        self._regime_history: deque = deque(maxlen=self.confirmation_days)

        # 上一次确认的体制（用于避免抖动）
        self._confirmed_regime: Optional[str] = None

        self.logger.info(
            f"✅ MarketRegimeEngine V7 初始化 | "
            f"确认天数={self.confirmation_days}"
        )

    # ─────────────────── 公开接口 ───────────────────

    def detect_regime(self) -> Dict:
        """
        检测当前市场体制

        返回:
            {
                'current_regime': str,
                'regime_probability': Dict[str, float],
                'volatility_20d': float,
                'volatility_60d': float,
                'momentum_20d': float,
                'momentum_60d': float,
                'confirmation_days': int,
                'confidence': float
            }
        """
        # 1. 加载基准指数数据
        index_df = self._load_benchmark_data()
        if index_df is None or len(index_df) < 60:
            self.logger.warning("⚠️ 基准指数数据不足，返回默认体制")
            return self._default_result()

        # 2. 计算波动率体制信号
        vol_20d, vol_60d = self._calc_volatility(index_df)

        # 3. 计算动量体制信号
        mom_20d, mom_60d = self._calc_momentum(index_df)

        # 4. 计算市场广度信号
        breadth_score = self._calc_breadth()

        # 5. 生成各体制原始得分
        raw_scores = self._calc_raw_regime_scores(vol_20d, vol_60d, mom_20d, mom_60d, breadth_score)

        # 6. softmax 转换为概率
        regime_prob = self._softmax_probabilities(raw_scores)

        # 7. 取概率最大的候选体制
        candidate_regime = max(regime_prob, key=regime_prob.get)

        # 8. 滞后确认
        confirmed_regime, conf_days = self._apply_hysteresis(candidate_regime)

        # 9. 置信度 = 最大概率
        confidence = regime_prob[confirmed_regime]

        result = {
            "current_regime": confirmed_regime,
            "regime_probability": regime_prob,
            "volatility_20d": round(float(vol_20d), 6),
            "volatility_60d": round(float(vol_60d), 6),
            "momentum_20d": round(float(mom_20d), 6),
            "momentum_60d": round(float(mom_60d), 6),
            "confirmation_days": conf_days,
            "confidence": round(float(confidence), 4),
        }

        self.logger.info(
            f"📊 体制检测: {confirmed_regime} | "
            f"置信度={confidence:.2%} | "
            f"vol_20d={vol_20d:.4f} mom_20d={mom_20d:.4f}"
        )
        return result

    # ─────────────────── 波动率计算 ───────────────────

    def _calc_volatility(self, df: pd.DataFrame):
        """计算 20d / 60d 年化滚动波动率"""
        returns = df["close"].pct_change().dropna()
        if len(returns) < 60:
            # 退化：用可用数据
            vol_20d = returns.tail(min(20, len(returns))).std() * np.sqrt(252)
            vol_60d = returns.std() * np.sqrt(252)
        else:
            vol_20d = returns.tail(20).std() * np.sqrt(252)
            vol_60d = returns.tail(60).std() * np.sqrt(252)
        return vol_20d, vol_60d

    # ─────────────────── 动量计算 ───────────────────

    def _calc_momentum(self, df: pd.DataFrame):
        """计算 20d / 60d 收益率"""
        close = df["close"]
        if len(close) < 60:
            mom_20d = (close.iloc[-1] / close.iloc[-min(21, len(close))] - 1) if len(close) > 1 else 0.0
            mom_60d = (close.iloc[-1] / close.iloc[0] - 1) if len(close) > 1 else 0.0
        else:
            mom_20d = close.iloc[-1] / close.iloc[-21] - 1
            mom_60d = close.iloc[-1] / close.iloc[-61] - 1
        return mom_20d, mom_60d

    # ─────────────────── 市场广度计算 ───────────────────

    def _calc_breadth(self) -> float:
        """
        计算市场广度：多指数成分股在 20d 均线上方占比的加权平均

        使用基准指数配置（大盘/中盘/小盘/微盘）作为代理，
        判断指数自身是否在 20d 均线上方，加权合成广度分数。
        """
        benchmark_config = self.data_service.config.config.get("market_benchmarks", {})
        if not benchmark_config:
            self.logger.warning("⚠️ 未找到 market_benchmarks 配置，广度分数默认 0.5")
            return 0.5

        total_weight = 0.0
        weighted_breadth = 0.0

        for name, cfg in benchmark_config.items():
            code = cfg.get("code", "")
            weight = cfg.get("weight", 0.25)
            try:
                idx_df = self.data_service.load_index_data(code, min_days=30)
                if idx_df is not None and len(idx_df) >= 20:
                    ma_20 = idx_df["close"].rolling(20).mean()
                    above_ma = 1.0 if idx_df["close"].iloc[-1] > ma_20.iloc[-1] else 0.0
                else:
                    above_ma = 0.5  # 数据不足，中性
            except Exception:
                above_ma = 0.5

            weighted_breadth += weight * above_ma
            total_weight += weight

        return weighted_breadth / total_weight if total_weight > 0 else 0.5

    # ─────────────────── 体制原始得分 ───────────────────

    def _calc_raw_regime_scores(
        self,
        vol_20d: float,
        vol_60d: float,
        mom_20d: float,
        mom_60d: float,
        breadth: float,
    ) -> Dict[str, float]:
        """
        基于三维信号计算四种体制的原始得分

        逻辑:
          - Bull:   低波动 + 正动量 + 高广度
          - Bear:   高波动 + 负动量 + 低广度
          - Volatile: 高波动 + 动量中性
          - Recovery: 波动率下降 + 动量转正
        """
        bull_cfg = self.regime_config.get("bull", {})
        bear_cfg = self.regime_config.get("bear", {})
        volatile_cfg = self.regime_config.get("volatile", {})
        recovery_cfg = self.regime_config.get("recovery", {})

        avg_vol = (vol_20d + vol_60d) / 2
        avg_mom = (mom_20d + mom_60d) / 2

        # Bull: 低波动 + 强正动量 + 高广度
        vol_th_bull = bull_cfg.get("volatility_threshold", 0.15)
        mom_th_bull = bull_cfg.get("momentum_threshold", 0.05)
        bull_score = (
            max(0, 1 - avg_vol / vol_th_bull) * 0.35
            + max(0, min(1, (avg_mom - mom_th_bull * 0.5) / mom_th_bull)) * 0.40
            + breadth * 0.25
        )

        # Bear: 高波动 + 负动量 + 低广度
        vol_th_bear = bear_cfg.get("volatility_threshold", 0.30)
        mom_th_bear = bear_cfg.get("momentum_threshold", -0.05)
        bear_score = (
            min(1, avg_vol / vol_th_bear) * 0.35
            + max(0, min(1, (-avg_mom - abs(mom_th_bear) * 0.5) / abs(mom_th_bear))) * 0.40
            + (1 - breadth) * 0.25
        )

        # Volatile: 高波动 + 动量中性
        vol_th_volatile = volatile_cfg.get("volatility_threshold", 0.25)
        mom_range = volatile_cfg.get("momentum_range", [-0.02, 0.02])
        mom_neutrality = 1 - min(1, abs(avg_mom - np.mean(mom_range)) / max(0.01, mom_range[1] - mom_range[0]))
        volatile_score = (
            min(1, avg_vol / vol_th_volatile) * 0.50
            + mom_neutrality * 0.50
        )

        # Recovery: 波动率下降趋势 + 动量转正
        vol_decreasing = 1.0 if vol_20d < vol_60d else 0.0
        mom_positive = 1.0 if avg_mom > 0 else 0.0
        recovery_score = (
            vol_decreasing * 0.40
            + mom_positive * 0.30
            + (1 - avg_vol / max(vol_th_bear, 0.01)) * 0.15
            + breadth * 0.15
        )

        return {
            REGIME_BULL: max(bull_score, 0.01),
            REGIME_BEAR: max(bear_score, 0.01),
            REGIME_VOLATILE: max(volatile_score, 0.01),
            REGIME_RECOVERY: max(recovery_score, 0.01),
        }

    # ─────────────────── Softmax 概率 ───────────────────

    @staticmethod
    def _softmax_probabilities(scores: Dict[str, float], temperature: float = 1.0) -> Dict[str, float]:
        """将原始得分通过 softmax 转换为概率分布"""
        keys = list(scores.keys())
        values = np.array([scores[k] for k in keys], dtype=np.float64)
        # 温度缩放
        scaled = values / temperature
        # 数值稳定 softmax
        shifted = scaled - np.max(scaled)
        exp_vals = np.exp(shifted)
        probs = exp_vals / np.sum(exp_vals)
        return {k: round(float(p), 4) for k, p in zip(keys, probs)}

    # ─────────────────── 滞后确认 ───────────────────

    def _apply_hysteresis(self, candidate: str) -> tuple:
        """
        滞后确认机制：连续 N 天同一体制才切换

        返回:
            (confirmed_regime, consecutive_days)
        """
        self._regime_history.append(candidate)

        # 检查队列是否全部相同
        if len(self._regime_history) >= self.confirmation_days:
            if len(set(self._regime_history)) == 1:
                # 全部一致，确认切换
                self._confirmed_regime = candidate
                return candidate, self.confirmation_days

        # 未达确认条件，维持上次确认的体制
        if self._confirmed_regime is None:
            # 首次运行，直接接受
            self._confirmed_regime = candidate
            return candidate, 1

        # 计算当前连续天数
        consecutive = 0
        for r in reversed(self._regime_history):
            if r == candidate:
                consecutive += 1
            else:
                break

        return self._confirmed_regime, consecutive

    # ─────────────────── 数据加载 ───────────────────

    def _load_benchmark_data(self) -> Optional[pd.DataFrame]:
        """加载 CSI 300 基准指数数据"""
        try:
            df = self.data_service.load_index_data(BENCHMARK_CODE, min_days=120)
            if df is not None and len(df) >= 60:
                return df
            # 退化尝试：减少最少天数
            df = self.data_service.load_index_data(BENCHMARK_CODE, min_days=60)
            return df
        except Exception as e:
            self.logger.error(f"❌ 加载基准指数数据失败: {e}")
            return None

    # ─────────────────── 默认返回 ───────────────────

    def _default_result(self) -> Dict:
        """数据不足时的默认返回"""
        default_prob = {r: 0.25 for r in ALL_REGIMES}
        return {
            "current_regime": REGIME_VOLATILE,
            "regime_probability": default_prob,
            "volatility_20d": 0.0,
            "volatility_60d": 0.0,
            "momentum_20d": 0.0,
            "momentum_60d": 0.0,
            "confirmation_days": 0,
            "confidence": 0.25,
        }
