"""
AiStock V8 — 市场体制检测引擎 (Market Regime Engine)

V8 升级: 海外信号调整机制 — 当外盘综合信号极端时, 调整体制概率

四种市场体制:
  1. Bull (牛市)     — 低波动 + 正动量 + 量增
  2. Bear (熊市)     — 高波动 + 负动量 + 量缩
  3. Volatile (震荡) — 中高波动 + 动量中性
  4. Recovery (复苏) — 波动下降 + 动量转正 + 量增

检测维度:
  - 波动率窗口 (60日)
  - 动量窗口 (20日)
  - PCR 水平
  - 海外信号 [V8 NEW]

V8 NEW — 海外体制调整:
  - 当海外综合信号 > 80 (极度看多) → 抑制熊市概率, 增强牛市概率
  - 当海外综合信号 < 20 (极度看空) → 放大熊市概率, 抑制牛市概率
  - 调整权重: 可配置 (默认 0.20)
  - 熊市放大因子: 1.3 (海外利空对熊市放大)
  - 牛市抑制因子: 0.9 (海外利空对牛市抑制)
"""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# ─── Type aliases ──────────────────────────────────────────────────────────────
TDXAdapter = Any
ConfigService = Any
CacheService = Any

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# 数据类定义
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class RegimeResult:
    """市场体制检测结果

    Attributes:
        current_regime:            当前体制 ('bull' / 'bear' / 'volatile' / 'recovery')
        regime_probabilities:      各体制概率 {'bull': p1, 'bear': p2, 'volatile': p3, 'recovery': p4}
        regime_duration:           当前体制持续天数估计
        transition_signals:        体制转换信号列表
        overseas_adjustment_factor: 海外调整因子 [V8 NEW]
        volatility_60d:            60日波动率
        momentum_20d:              20日动量
        pcr_level:                 PCR 水平
        overseas_signal_score:     海外综合信号分 [V8 NEW]
        confirmation_days:         确认天数
        timestamp:                 检测时间戳
    """
    current_regime: str = "volatile"
    regime_probabilities: Dict[str, float] = field(default_factory=lambda: {
        "bull": 0.25, "bear": 0.25, "volatile": 0.30, "recovery": 0.20,
    })
    regime_duration: int = 0
    transition_signals: List[str] = field(default_factory=list)
    overseas_adjustment_factor: float = 1.0
    volatility_60d: float = 0.0
    momentum_20d: float = 0.0
    pcr_level: float = 0.0
    overseas_signal_score: float = 50.0
    confirmation_days: int = 0
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    @property
    def regime_label(self) -> str:
        """体制中文标签"""
        labels = {
            "bull": "牛市", "bear": "熊市",
            "volatile": "震荡市", "recovery": "复苏期",
        }
        return labels.get(self.current_regime, self.current_regime)

    @property
    def regime_confidence(self) -> float:
        """当前体制置信度 (= 该体制概率)"""
        return self.regime_probabilities.get(self.current_regime, 0.0)

    @property
    def is_transitioning(self) -> bool:
        """是否处于体制转换中 (最高概率 < 0.40)"""
        return max(self.regime_probabilities.values()) < 0.40

    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_regime": self.current_regime,
            "regime_label": self.regime_label,
            "regime_probabilities": {k: round(v, 4) for k, v in self.regime_probabilities.items()},
            "regime_confidence": round(self.regime_confidence, 4),
            "regime_duration": self.regime_duration,
            "is_transitioning": self.is_transitioning,
            "transition_signals": self.transition_signals,
            "overseas_adjustment_factor": round(self.overseas_adjustment_factor, 4),
            "volatility_60d": round(self.volatility_60d, 6),
            "momentum_20d": round(self.momentum_20d, 6),
            "pcr_level": round(self.pcr_level, 4),
            "overseas_signal_score": round(self.overseas_signal_score, 2),
            "confirmation_days": self.confirmation_days,
            "timestamp": self.timestamp,
        }

    def __repr__(self) -> str:
        return (
            f"RegimeResult({self.current_regime} [{self.regime_label}] "
            f"p={self.regime_confidence:.2f} "
            f"vol={self.volatility_60d:.4f} mom={self.momentum_20d:.4f} "
            f"overseas_adj={self.overseas_adjustment_factor:.2f})"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 默认配置
# ═══════════════════════════════════════════════════════════════════════════════

# 体制检测阈值
REGIME_THRESHOLDS = {
    "volatility_window": 60,
    "momentum_window": 20,
    "volume_window": 20,
    "confirmation_days": 3,
}

# 体制判定阈值
BULL_VOL_THRESHOLD = 0.15       # 牛市波动率阈值 (年化)
BEAR_VOL_THRESHOLD = 0.30       # 熊市波动率阈值
VOLATILE_VOL_THRESHOLD = 0.25   # 震荡市波动率阈值
MOMENTUM_BULL_THRESHOLD = 0.05  # 牛市动量阈值
MOMENTUM_BEAR_THRESHOLD = -0.05 # 熊市动量阈值
MOMENTUM_NEUTRAL_RANGE = 0.02   # 震荡市动量范围

# PCR 阈值
PCR_BULL_THRESHOLD = 0.8    # PCR < 0.8 偏牛市
PCR_BEAR_THRESHOLD = 1.3    # PCR > 1.3 偏熊市

# 海外体制调整参数 [V8 NEW]
OVERSEAS_REGIME_PARAMS = {
    "enabled": True,
    "weight": 0.20,           # 海外信号对体制概率的调整权重
    "extreme_high": 80.0,     # 海外信号极度看多阈值
    "extreme_low": 20.0,      # 海外信号极度看空阈值
    "bear_amplification": 1.3, # 海外利空对熊市概率放大因子
    "bull_suppression": 0.9,   # 海外利空对牛市概率抑制因子
    "bull_amplification": 1.2, # 海外利多对牛市概率放大因子
    "bear_suppression": 0.85,  # 海外利多对熊市概率抑制因子
}


# ═══════════════════════════════════════════════════════════════════════════════
# 市场体制检测引擎
# ═══════════════════════════════════════════════════════════════════════════════

class MarketRegimeEngine:
    """市场体制检测引擎 (V8 增强版)

    四种体制: Bull / Bear / Volatile / Recovery

    检测基于:
      - 波动率 (60日年化波动率)
      - 动量 (20日收益率)
      - PCR 水平
      - 海外信号 [V8 NEW]

    V8 NEW — 海外体制调整:
      当外盘综合信号极端 (>80 或 <20), 调整体制概率:
        - 海外极度看空 → 放大熊市概率, 抑制牛市概率
        - 海外极度看多 → 放大牛市概率, 抑制熊市概率

    使用方式:
        >>> engine = MarketRegimeEngine(data_service=tdx, config=config)
        >>> result = engine.detect(
        ...     market_data=index_df,
        ...     derivatives_result=deriv_res,
        ...     pcr_result=pcr_res,
        ...     overseas_signal=overseas_sig,
        ... )
        >>> print(result.current_regime, result.regime_probabilities)
    """

    def __init__(
        self,
        data_service: Optional[TDXAdapter] = None,
        config: Optional[ConfigService] = None,
        cache: Optional[CacheService] = None,
        logger_instance: Optional[logging.Logger] = None,
    ) -> None:
        """初始化体制检测引擎

        Args:
            data_service: TDXAdapter 实例
            config:       配置服务
            cache:        缓存服务
            logger_instance: 自定义 logger
        """
        self._tdx = data_service
        self._config = config
        self._cache = cache
        self._logger = logger_instance or logger

        # 加载配置
        self._thresholds = self._load_thresholds()
        self._overseas_params = self._load_overseas_params()

        # 体制历史 (用于持续天数估算)
        self._regime_history: List[Dict[str, Any]] = []
        self._max_history = 60

        self._logger.info(
            "MarketRegimeEngine V8.0 初始化完成 | "
            "海外调整: %s (权重=%.2f)",
            "启用" if self._overseas_params["enabled"] else "禁用",
            self._overseas_params["weight"],
        )

    # ═══════════════════════════════════════════════════════════════════════
    # 核心检测方法
    # ═══════════════════════════════════════════════════════════════════════

    def detect(
        self,
        market_data: Optional[pd.DataFrame] = None,
        derivatives_result: Optional[Any] = None,
        pcr_result: Optional[Any] = None,
        overseas_signal: Optional[Any] = None,
    ) -> RegimeResult:
        """检测当前市场体制

        Args:
            market_data:        指数K线数据 (DataFrame, 需要 close/volume 列)
            derivatives_result: 衍生品信号结果 (DerivativesResult, 可选)
            pcr_result:         PCR 结果 (CompositePCRResult, 可选)
            overseas_signal:    海外信号 (OverseasCompositeSignal, 可选) [V8 NEW]

        Returns:
            RegimeResult
        """
        start_time = time.time()

        # 1. 计算基础指标
        volatility = self._calculate_volatility(market_data)
        momentum = self._calculate_momentum(market_data)
        pcr_level = self._extract_pcr_level(pcr_result)
        overseas_score = self._extract_overseas_score(overseas_signal)

        # 2. 基于国内指标计算体制概率
        probabilities = self._calculate_regime_probabilities(
            volatility, momentum, pcr_level,
        )

        # 3. 海外体制调整 [V8 NEW]
        overseas_adj_factor = 1.0
        if self._overseas_params["enabled"] and overseas_signal is not None:
            probabilities, overseas_adj_factor = self._apply_overseas_adjustment(
                probabilities, overseas_score,
            )

        # 4. 确定当前体制
        current_regime = max(probabilities, key=probabilities.get)

        # 5. 检测转换信号
        transition_signals = self._detect_transition_signals(
            current_regime, volatility, momentum, pcr_level, overseas_score,
        )

        # 6. 估算体制持续天数
        regime_duration = self._estimate_regime_duration(current_regime)

        # 7. 构建结果
        result = RegimeResult(
            current_regime=current_regime,
            regime_probabilities=probabilities,
            regime_duration=regime_duration,
            transition_signals=transition_signals,
            overseas_adjustment_factor=overseas_adj_factor,
            volatility_60d=volatility,
            momentum_20d=momentum,
            pcr_level=pcr_level,
            overseas_signal_score=overseas_score,
            confirmation_days=self._thresholds.get("confirmation_days", 3),
        )

        # 记录历史
        self._record_regime_history(result)

        elapsed = (time.time() - start_time) * 1000
        self._logger.info(
            "体制检测: %s [%s] p=%.2f | vol=%.4f mom=%.4f PCR=%.3f "
            "overseas=%.0f adj=%.2f | %.0fms",
            current_regime, result.regime_label, result.regime_confidence,
            volatility, momentum, pcr_level, overseas_score,
            overseas_adj_factor, elapsed,
        )

        return result

    # ═══════════════════════════════════════════════════════════════════════
    # 基础指标计算
    # ═══════════════════════════════════════════════════════════════════════

    def _calculate_volatility(self, market_data: Optional[pd.DataFrame]) -> float:
        """计算60日年化波动率

        Args:
            market_data: 指数K线数据

        Returns:
            年化波动率 (如 0.25 = 25%)
        """
        if market_data is None or market_data.empty:
            return 0.20  # 默认中等波动

        try:
            window = self._thresholds.get("volatility_window", 60)
            close = market_data["close"].values.astype(float)

            if len(close) < 5:
                return 0.20

            # 日收益率
            returns = np.diff(close) / close[:-1]
            returns = returns[np.isfinite(returns)]

            if len(returns) < 5:
                return 0.20

            # 取最近 window 日
            if len(returns) > window:
                returns = returns[-window:]

            # 年化波动率
            daily_vol = float(np.std(returns))
            annualized_vol = daily_vol * np.sqrt(252)

            return float(annualized_vol)

        except Exception as e:
            self._logger.warning("波动率计算异常: %s", e)
            return 0.20

    def _calculate_momentum(self, market_data: Optional[pd.DataFrame]) -> float:
        """计算20日动量

        Args:
            market_data: 指数K线数据

        Returns:
            动量 (如 0.05 = 5%)
        """
        if market_data is None or market_data.empty:
            return 0.0

        try:
            window = self._thresholds.get("momentum_window", 20)
            close = market_data["close"].values.astype(float)

            if len(close) < window + 1:
                window = len(close) - 1

            if window < 1 or close[-window - 1] <= 0:
                return 0.0

            momentum = (close[-1] / close[-window - 1]) - 1.0
            return float(momentum)

        except Exception as e:
            self._logger.warning("动量计算异常: %s", e)
            return 0.0

    def _extract_pcr_level(self, pcr_result: Optional[Any]) -> float:
        """从 PCR 结果中提取 PCR 水平"""
        if pcr_result is None:
            return 1.0  # 默认中性

        try:
            # CompositePCRResult
            if hasattr(pcr_result, "composite_pcr"):
                return float(pcr_result.composite_pcr)
            # Dict
            if isinstance(pcr_result, dict):
                return float(pcr_result.get("composite_pcr", 1.0))
        except (TypeError, ValueError):
            pass

        return 1.0

    def _extract_overseas_score(self, overseas_signal: Optional[Any]) -> float:
        """从海外信号中提取综合评分"""
        if overseas_signal is None:
            return 50.0  # 默认中性

        try:
            # OverseasCompositeSignal
            if hasattr(overseas_signal, "composite_score"):
                return float(overseas_signal.composite_score)
            # Dict
            if isinstance(overseas_signal, dict):
                return float(overseas_signal.get("composite_score", 50.0))
        except (TypeError, ValueError):
            pass

        return 50.0

    # ═══════════════════════════════════════════════════════════════════════
    # 体制概率计算
    # ═══════════════════════════════════════════════════════════════════════

    def _calculate_regime_probabilities(
        self,
        volatility: float,
        momentum: float,
        pcr_level: float,
    ) -> Dict[str, float]:
        """基于国内指标计算各体制概率

        使用软分类: 每个指标对每种体制贡献概率, 最终归一化.

        Args:
            volatility: 60日年化波动率
            momentum:   20日动量
            pcr_level:  PCR 水平

        Returns:
            {'bull': p1, 'bear': p2, 'volatile': p3, 'recovery': p4}
        """
        # 波动率贡献
        vol_bull = self._gaussian_score(volatility, BULL_VOL_THRESHOLD, 0.05)
        vol_bear = self._gaussian_score(volatility, BEAR_VOL_THRESHOLD, 0.08)
        vol_volatile = self._gaussian_score(volatility, VOLATILE_VOL_THRESHOLD, 0.05)
        vol_recovery = self._gaussian_score(volatility, 0.20, 0.05)  # 复苏期中等偏低波动

        # 动量贡献
        mom_bull = self._gaussian_score(momentum, MOMENTUM_BULL_THRESHOLD, 0.03)
        mom_bear = self._gaussian_score(momentum, MOMENTUM_BEAR_THRESHOLD, 0.03)
        mom_volatile = self._gaussian_score(momentum, 0.0, MOMENTUM_NEUTRAL_RANGE)
        mom_recovery = self._gaussian_score(momentum, 0.02, 0.03)  # 复苏期微正动量

        # PCR 贡献
        pcr_bull = self._gaussian_score(pcr_level, PCR_BULL_THRESHOLD, 0.15)
        pcr_bear = self._gaussian_score(pcr_level, PCR_BEAR_THRESHOLD, 0.15)
        pcr_volatile = self._gaussian_score(pcr_level, 1.0, 0.15)
        pcr_recovery = self._gaussian_score(pcr_level, 0.9, 0.15)

        # 综合各指标 (等权)
        bull_score = vol_bull + mom_bull + pcr_bull
        bear_score = vol_bear + mom_bear + pcr_bear
        volatile_score = vol_volatile + mom_volatile + pcr_volatile
        recovery_score = vol_recovery + mom_recovery + pcr_recovery

        # 归一化
        total = bull_score + bear_score + volatile_score + recovery_score
        if total <= 0:
            return {"bull": 0.25, "bear": 0.25, "volatile": 0.30, "recovery": 0.20}

        probabilities = {
            "bull": bull_score / total,
            "bear": bear_score / total,
            "volatile": volatile_score / total,
            "recovery": recovery_score / total,
        }

        return probabilities

    @staticmethod
    def _gaussian_score(value: float, center: float, sigma: float) -> float:
        """高斯核评分

        Args:
            value:  输入值
            center: 中心值
            sigma:  标准差

        Returns:
            评分 (0-1)
        """
        if sigma <= 0:
            return 1.0 if abs(value - center) < 1e-8 else 0.0
        return float(math.exp(-0.5 * ((value - center) / sigma) ** 2))

    # ═══════════════════════════════════════════════════════════════════════
    # 海外体制调整 [V8 NEW]
    # ═══════════════════════════════════════════════════════════════════════

    def _apply_overseas_adjustment(
        self,
        probabilities: Dict[str, float],
        overseas_score: float,
    ) -> Tuple[Dict[str, float], float]:
        """应用海外体制调整

        当海外信号极端时, 调整体制概率:
          - 海外极度看空 (< 20):
            - 熊市概率 × bear_amplification (1.3)
            - 牛市概率 × bull_suppression (0.9)
          - 海外极度看多 (> 80):
            - 牛市概率 × bull_amplification (1.2)
            - 熊市概率 × bear_suppression (0.85)

        Args:
            probabilities: 原始体制概率
            overseas_score: 海外综合信号 (0-100)

        Returns:
            (调整后概率, 调整因子)
        """
        params = self._overseas_params
        weight = params["weight"]
        extreme_high = params["extreme_high"]
        extreme_low = params["extreme_low"]

        adjustment_factor = 1.0

        if overseas_score < extreme_low:
            # 海外极度看空 → 放大熊市, 抑制牛市
            bear_amp = params["bear_amplification"]
            bull_supp = params["bull_suppression"]

            # 计算调整强度 (越极端, 调整越大)
            intensity = (extreme_low - overseas_score) / extreme_low
            effective_weight = weight * intensity

            # 应用调整
            adjusted = dict(probabilities)
            adjusted["bear"] = probabilities["bear"] * (1.0 + (bear_amp - 1.0) * effective_weight)
            adjusted["bull"] = probabilities["bull"] * (1.0 - (1.0 - bull_supp) * effective_weight)
            adjusted["volatile"] = probabilities["volatile"] * (
                1.0 + 0.1 * effective_weight  # 略微增加震荡概率
            )
            adjusted["recovery"] = probabilities["recovery"] * (
                1.0 - 0.1 * effective_weight  # 略微降低复苏概率
            )

            adjustment_factor = 1.0 - effective_weight * 0.3  # 标记调整因子

        elif overseas_score > extreme_high:
            # 海外极度看多 → 放大牛市, 抑制熊市
            bull_amp = params["bull_amplification"]
            bear_supp = params["bear_suppression"]

            intensity = (overseas_score - extreme_high) / (100.0 - extreme_high)
            effective_weight = weight * intensity

            adjusted = dict(probabilities)
            adjusted["bull"] = probabilities["bull"] * (1.0 + (bull_amp - 1.0) * effective_weight)
            adjusted["bear"] = probabilities["bear"] * (1.0 - (1.0 - bear_supp) * effective_weight)
            adjusted["recovery"] = probabilities["recovery"] * (
                1.0 + 0.15 * effective_weight  # 略微增加复苏概率
            )

            adjustment_factor = 1.0 + effective_weight * 0.3

        else:
            # 海外信号非极端, 不调整
            adjusted = dict(probabilities)

        # 归一化
        total = sum(adjusted.values())
        if total > 0:
            adjusted = {k: v / total for k, v in adjusted.items()}

        return adjusted, adjustment_factor

    # ═══════════════════════════════════════════════════════════════════════
    # 转换信号检测
    # ═══════════════════════════════════════════════════════════════════════

    def _detect_transition_signals(
        self,
        current_regime: str,
        volatility: float,
        momentum: float,
        pcr_level: float,
        overseas_score: float,
    ) -> List[str]:
        """检测体制转换信号

        Returns:
            转换信号列表 (如 ['动量转正', '海外信号转弱'])
        """
        signals: List[str] = []

        # 动量方向变化
        if current_regime in ("bear", "volatile") and momentum > 0.02:
            signals.append("动量转正")
        elif current_regime in ("bull", "recovery") and momentum < -0.02:
            signals.append("动量转负")

        # 波动率方向变化
        if current_regime == "bear" and volatility < BEAR_VOL_THRESHOLD * 0.8:
            signals.append("波动率回落")
        elif current_regime == "bull" and volatility > BULL_VOL_THRESHOLD * 1.5:
            signals.append("波动率上升")

        # PCR 极端
        if pcr_level > PCR_BEAR_THRESHOLD:
            signals.append("PCR偏高(看空情绪)")
        elif pcr_level < PCR_BULL_THRESHOLD:
            signals.append("PCR偏低(看多情绪)")

        # 海外信号变化 [V8 NEW]
        if overseas_score < self._overseas_params["extreme_low"]:
            signals.append("海外信号极度看空")
        elif overseas_score > self._overseas_params["extreme_high"]:
            signals.append("海外信号极度看多")

        # 检查历史趋势
        if len(self._regime_history) >= 3:
            recent_regimes = [h.get("regime", "") for h in self._regime_history[-3:]]
            if len(set(recent_regimes)) >= 3:
                signals.append("体制频繁切换")

        return signals

    # ═══════════════════════════════════════════════════════════════════════
    # 体制持续天数估算
    # ═══════════════════════════════════════════════════════════════════════

    def _estimate_regime_duration(self, current_regime: str) -> int:
        """估算当前体制持续天数

        基于历史记录中连续相同体制的天数.

        Returns:
            估计持续天数
        """
        if not self._regime_history:
            return 1

        count = 0
        for record in reversed(self._regime_history):
            if record.get("regime") == current_regime:
                count += 1
            else:
                break

        return count

    def _record_regime_history(self, result: RegimeResult) -> None:
        """记录体制历史"""
        self._regime_history.append({
            "regime": result.current_regime,
            "confidence": result.regime_confidence,
            "timestamp": result.timestamp,
        })

        # 保持历史长度
        if len(self._regime_history) > self._max_history:
            self._regime_history = self._regime_history[-self._max_history:]

    # ═══════════════════════════════════════════════════════════════════════
    # 配置加载
    # ═══════════════════════════════════════════════════════════════════════

    def _load_thresholds(self) -> Dict[str, Any]:
        """加载检测阈值"""
        if self._config is not None:
            try:
                cfg = self._config.get("market_regime", {})
                if cfg:
                    return {
                        "volatility_window": cfg.get("volatility_window", 60),
                        "momentum_window": cfg.get("momentum_window", 20),
                        "volume_window": cfg.get("volume_window", 20),
                        "confirmation_days": cfg.get("confirmation_days", 3),
                    }
            except Exception:
                pass
        return dict(REGIME_THRESHOLDS)

    def _load_overseas_params(self) -> Dict[str, Any]:
        """加载海外体制调整参数"""
        if self._config is not None:
            try:
                cfg = self._config.get("market_regime", {})
                overseas_cfg = cfg.get("overseas_regime_adjustment", {})
                if overseas_cfg:
                    return {
                        "enabled": overseas_cfg.get("enabled", True),
                        "weight": overseas_cfg.get("weight", 0.20),
                        "extreme_high": 80.0,
                        "extreme_low": 20.0,
                        "bear_amplification": overseas_cfg.get("bear_amplification", 1.3),
                        "bull_suppression": overseas_cfg.get("bull_suppression", 0.9),
                        "bull_amplification": 1.2,
                        "bear_suppression": 0.85,
                    }
            except Exception:
                pass
        return dict(OVERSEAS_REGIME_PARAMS)
