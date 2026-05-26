"""
AiStock V8 — 市场状态分类器 (Market State Classifier)

V8 升级: 3D → 4D 模型

V7 (3D):
  - 估值 (40%)
  - 动量 (35%)
  - 体制 (25%)

V8 (4D):
  - 估值 (30%) — DatabaseReader PE/PB 百分位 → 股权风险溢价/股债比
  - 动量 (25%) — 指数价格趋势 (MA/ROC/广度)
  - 体制 (25%) — MarketRegimeEngine 体制概率
  - 海外 (20%) — OverseasFuturesSignalEngine 综合信号 [V8 NEW]

四维评分 → 综合评分 (0-100) → 状态标签

状态标签 (5级):
  strategic_offense (战略进攻)  — 综合评分 ≥ 80
  active_allocation (积极配置)  — 综合评分 65-80
  balanced_hold (均衡持有)     — 综合评分 50-65
  defensive_watch (防御观望)    — 综合评分 35-50
  strategic_defense (战略防御)  — 综合评分 < 35
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
DatabaseReader = Any
ConfigService = Any
CacheService = Any

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# 数据类定义
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class DimensionScore:
    """单维度评分

    Attributes:
        name:            维度名称
        score:           评分 (0-100)
        weight:          权重 (0-1)
        weighted_score:  加权评分 (score × weight)
        sub_scores:      子维度评分
        direction:       方向 'bullish' / 'bearish' / 'neutral'
    """
    name: str
    score: float = 50.0
    weight: float = 0.25
    weighted_score: float = 0.0
    sub_scores: Dict[str, float] = field(default_factory=dict)
    direction: str = "neutral"

    def __post_init__(self) -> None:
        self.weighted_score = self.score * self.weight
        if self.score >= 65:
            self.direction = "bullish"
        elif self.score <= 35:
            self.direction = "bearish"
        else:
            self.direction = "neutral"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "score": round(self.score, 2),
            "weight": round(self.weight, 4),
            "weighted_score": round(self.weighted_score, 2),
            "sub_scores": {k: round(v, 2) for k, v in self.sub_scores.items()},
            "direction": self.direction,
        }


@dataclass
class ClassificationResult:
    """市场状态分类结果

    Attributes:
        overall_state:   总体状态标签
        scores:          各维度评分
        composite_score: 综合评分 (0-100)
        state_label:     中文状态标签
        state_level:     状态级别 (1-5, 1=最强进攻, 5=最强防御)
        confidence:      置信度 (0-1)
        timestamp:       分类时间戳
    """
    overall_state: str = "balanced_hold"
    scores: Dict[str, DimensionScore] = field(default_factory=dict)
    composite_score: float = 50.0
    state_label: str = "均衡持有"
    state_level: int = 3
    confidence: float = 0.0
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    @property
    def is_offensive(self) -> bool:
        """是否为进攻状态"""
        return self.composite_score >= 65

    @property
    def is_defensive(self) -> bool:
        """是否为防御状态"""
        return self.composite_score < 50

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_state": self.overall_state,
            "state_label": self.state_label,
            "state_level": self.state_level,
            "composite_score": round(self.composite_score, 2),
            "confidence": round(self.confidence, 4),
            "is_offensive": self.is_offensive,
            "is_defensive": self.is_defensive,
            "scores": {k: v.to_dict() for k, v in self.scores.items()},
            "timestamp": self.timestamp,
        }

    def __repr__(self) -> str:
        return (
            f"ClassificationResult({self.overall_state} [{self.state_label}] "
            f"score={self.composite_score:.1f} level={self.state_level})"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 状态标签定义
# ═══════════════════════════════════════════════════════════════════════════════

STATE_LABELS: Dict[str, Tuple[str, int, str]] = {
    "strategic_offense":  ("战略进攻", 1, "strong_bullish"),
    "active_allocation":  ("积极配置", 2, "moderate_bullish"),
    "balanced_hold":      ("均衡持有", 3, "neutral"),
    "defensive_watch":    ("防御观望", 4, "moderate_bearish"),
    "strategic_defense":  ("战略防御", 5, "strong_bearish"),
}

# 评分阈值
SCORE_THRESHOLDS = {
    "strategic_offense": 80.0,
    "active_allocation": 65.0,
    "balanced_hold": 50.0,
    "defensive_watch": 35.0,
    # < 35 → strategic_defense
}

# V8 四维权重
DEFAULT_DIMENSION_WEIGHTS = {
    "valuation": 0.30,
    "momentum": 0.25,
    "regime": 0.25,
    "overseas": 0.20,
}

# 估值子维度权重
VALUATION_SUB_WEIGHTS = {
    "pe_percentile": 0.40,
    "pb_percentile": 0.25,
    "equity_risk_premium": 0.20,
    "equity_bond_ratio": 0.15,
}

# 动量子维度权重
MOMENTUM_SUB_WEIGHTS = {
    "trend_strength": 0.35,
    "breadth_ratio": 0.30,
    "volume_price_divergence": 0.20,
    "sector_rotation": 0.15,
}

# 体制子维度权重
REGIME_SUB_WEIGHTS = {
    "volatility_regime": 0.35,
    "trend_regime": 0.30,
    "liquidity_regime": 0.20,
    "sentiment_regime": 0.15,
}

# 海外子维度权重
OVERSEAS_SUB_WEIGHTS = {
    "price_signal": 0.40,
    "position_signal": 0.25,
    "macro_signal": 0.20,
    "sentiment_signal": 0.15,
}


# ═══════════════════════════════════════════════════════════════════════════════
# 市场状态分类器
# ═══════════════════════════════════════════════════════════════════════════════

class MarketStateClassifier:
    """市场状态分类器 (V8 四维模型)

    4D 模型:
      1. 估值 (30%) — PE/PB 百分位 + 股权风险溢价 + 股债比
      2. 动量 (25%) — 趋势强度 + 广度 + 量价背离 + 板块轮动
      3. 体制 (25%) — 波动率体制 + 趋势体制 + 流动性体制 + 情绪体制
      4. 海外 (20%) — 价格信号 + 持仓信号 + 宏观信号 + 情绪信号 [V8 NEW]

    综合评分 → 5级状态标签

    使用方式:
        >>> classifier = MarketStateClassifier(
        ...     data_service=tdx, db_reader=db, config=config,
        ... )
        >>> result = classifier.classify(
        ...     market_data=index_df,
        ...     regime_result=regime_res,
        ...     derivatives_result=deriv_res,
        ...     pcr_result=pcr_res,
        ...     overseas_signal=overseas_sig,
        ... )
        >>> print(result.overall_state, result.composite_score)
    """

    def __init__(
        self,
        data_service: Optional[TDXAdapter] = None,
        db_reader: Optional[DatabaseReader] = None,
        config: Optional[ConfigService] = None,
        cache: Optional[CacheService] = None,
        logger_instance: Optional[logging.Logger] = None,
    ) -> None:
        """初始化分类器

        Args:
            data_service: TDXAdapter 实例
            db_reader:    DatabaseReader 实例 (估值数据)
            config:       配置服务
            cache:        缓存服务
            logger_instance: 自定义 logger
        """
        self._tdx = data_service
        self._db = db_reader
        self._config = config
        self._cache = cache
        self._logger = logger_instance or logger

        # 加载配置
        self._dimension_weights = self._load_dimension_weights()
        self._valuation_sub_weights = self._load_valuation_sub_weights()
        self._momentum_sub_weights = self._load_momentum_sub_weights()
        self._regime_sub_weights = self._load_regime_sub_weights()
        self._overseas_sub_weights = self._load_overseas_sub_weights()

        self._logger.info(
            "MarketStateClassifier V8.0 初始化完成 | "
            "4D权重: 估值=%.0f%% 动量=%.0f%% 体制=%.0f%% 海外=%.0f%%",
            self._dimension_weights["valuation"] * 100,
            self._dimension_weights["momentum"] * 100,
            self._dimension_weights["regime"] * 100,
            self._dimension_weights["overseas"] * 100,
        )

    # ═══════════════════════════════════════════════════════════════════════
    # 核心分类方法
    # ═══════════════════════════════════════════════════════════════════════

    def classify(
        self,
        market_data: Optional[pd.DataFrame] = None,
        regime_result: Optional[Any] = None,
        derivatives_result: Optional[Any] = None,
        pcr_result: Optional[Any] = None,
        overseas_signal: Optional[Any] = None,
    ) -> ClassificationResult:
        """执行4D市场状态分类

        Args:
            market_data:        指数K线数据
            regime_result:      体制检测结果 (RegimeResult)
            derivatives_result: 衍生品信号结果 (DerivativesResult)
            pcr_result:         PCR 结果 (CompositePCRResult)
            overseas_signal:    海外信号 (OverseasCompositeSignal) [V8 NEW]

        Returns:
            ClassificationResult
        """
        start_time = time.time()

        # 1. 估值维度评分
        valuation_score = self._calculate_valuation_score(market_data)

        # 2. 动量维度评分
        momentum_score = self._calculate_momentum_score(
            market_data, derivatives_result,
        )

        # 3. 体制维度评分
        regime_score = self._calculate_regime_score(regime_result)

        # 4. 海外维度评分 [V8 NEW]
        overseas_score = self._calculate_overseas_score(overseas_signal)

        # 5. 构建维度评分对象
        scores = {
            "valuation": DimensionScore(
                name="估值",
                score=valuation_score,
                weight=self._dimension_weights["valuation"],
                sub_scores=self._last_valuation_subs,
            ),
            "momentum": DimensionScore(
                name="动量",
                score=momentum_score,
                weight=self._dimension_weights["momentum"],
                sub_scores=self._last_momentum_subs,
            ),
            "regime": DimensionScore(
                name="体制",
                score=regime_score,
                weight=self._dimension_weights["regime"],
                sub_scores=self._last_regime_subs,
            ),
            "overseas": DimensionScore(
                name="海外",
                score=overseas_score,
                weight=self._dimension_weights["overseas"],
                sub_scores=self._last_overseas_subs,
            ),
        }

        # 6. 计算综合评分
        composite = sum(s.weighted_score for s in scores.values())

        # 7. 确定状态标签
        overall_state, state_label, state_level = self._determine_state(composite)

        # 8. 计算置信度
        confidence = self._calculate_confidence(scores, composite)

        result = ClassificationResult(
            overall_state=overall_state,
            scores=scores,
            composite_score=composite,
            state_label=state_label,
            state_level=state_level,
            confidence=confidence,
        )

        elapsed = (time.time() - start_time) * 1000
        self._logger.info(
            "4D分类: %s [%s] score=%.1f | 估值=%.1f 动量=%.1f 体制=%.1f 海外=%.1f | conf=%.2f | %.0fms",
            overall_state, state_label, composite,
            valuation_score, momentum_score, regime_score, overseas_score,
            confidence, elapsed,
        )

        return result

    # ═══════════════════════════════════════════════════════════════════════
    # D1: 估值维度
    # ═══════════════════════════════════════════════════════════════════════

    # 保存最近一次子维度评分 (用于 DimensionScore)
    _last_valuation_subs: Dict[str, float] = {}
    _last_momentum_subs: Dict[str, float] = {}
    _last_regime_subs: Dict[str, float] = {}
    _last_overseas_subs: Dict[str, float] = {}

    def _calculate_valuation_score(self, market_data: Optional[pd.DataFrame]) -> float:
        """计算估值维度评分 (0-100)

        子维度:
          - PE 百分位 (40%): 越低越便宜 → 评分越高
          - PB 百分位 (25%): 越低越便宜 → 评分越高
          - 股权风险溢价 (20%): 越高越好
          - 股债比 (15%): 股票相对债券吸引力

        评分逻辑: PE/PB 百分位反转 (低百分位 = 高评分)
        """
        subs: Dict[str, float] = {}

        # PE 百分位
        pe_percentile = self._get_latest_pe_percentile()
        subs["pe_percentile"] = 100.0 - pe_percentile  # 反转: 低百分位 → 高评分

        # PB 百分位
        pb_percentile = self._get_latest_pb_percentile()
        subs["pb_percentile"] = 100.0 - pb_percentile

        # 股权风险溢价 (简化: 使用 1/PE - 债券收益率)
        erp_score = self._estimate_equity_risk_premium(pe_percentile)
        subs["equity_risk_premium"] = erp_score

        # 股债比 (简化: PE倒数 vs 债券收益率)
        ebr_score = self._estimate_equity_bond_ratio(pe_percentile)
        subs["equity_bond_ratio"] = ebr_score

        # 保存子维度
        self._last_valuation_subs = subs

        # 加权评分
        score = sum(
            subs.get(k, 50.0) * self._valuation_sub_weights.get(k, 0.25)
            for k in self._valuation_sub_weights
        )

        return max(0.0, min(100.0, score))

    def _get_latest_pe_percentile(self) -> float:
        """获取最新 PE 百分位"""
        if self._db is None:
            return 50.0  # 默认中位数

        try:
            df = self._db.get_latest_pe()
            if df is not None and not df.empty:
                # 取沪深300的 PE 百分位
                hs300 = df[df["index_code"] == "000300"]
                if not hs300.empty:
                    val = float(hs300.iloc[0].get("pe_percentile", 50.0))
                    return max(0.0, min(100.0, val))
        except Exception as e:
            self._logger.debug("PE百分位获取失败: %s", e)

        return 50.0

    def _get_latest_pb_percentile(self) -> float:
        """获取最新 PB 百分位"""
        if self._db is None:
            return 50.0

        try:
            df = self._db.get_latest_pe()
            if df is not None and not df.empty:
                hs300 = df[df["index_code"] == "000300"]
                if not hs300.empty:
                    val = float(hs300.iloc[0].get("pb_percentile", 50.0))
                    return max(0.0, min(100.0, val))
        except Exception as e:
            self._logger.debug("PB百分位获取失败: %s", e)

        return 50.0

    @staticmethod
    def _estimate_equity_risk_premium(pe_percentile: float) -> float:
        """估算股权风险溢价评分

        PE 百分位低 → ERP 高 → 评分高
        """
        if pe_percentile < 20:
            return 85.0  # 极度低估
        elif pe_percentile < 35:
            return 70.0  # 低估
        elif pe_percentile < 50:
            return 55.0  # 略低
        elif pe_percentile < 65:
            return 45.0  # 略高
        elif pe_percentile < 80:
            return 30.0  # 高估
        else:
            return 15.0  # 极度高估

    @staticmethod
    def _estimate_equity_bond_ratio(pe_percentile: float) -> float:
        """估算股债比评分

        PE 百分位低 → 股票吸引力高 → 评分高
        """
        if pe_percentile < 25:
            return 80.0
        elif pe_percentile < 45:
            return 60.0
        elif pe_percentile < 55:
            return 50.0
        elif pe_percentile < 75:
            return 35.0
        else:
            return 20.0

    # ═══════════════════════════════════════════════════════════════════════
    # D2: 动量维度
    # ═══════════════════════════════════════════════════════════════════════

    def _calculate_momentum_score(
        self,
        market_data: Optional[pd.DataFrame],
        derivatives_result: Optional[Any],
    ) -> float:
        """计算动量维度评分 (0-100)

        子维度:
          - 趋势强度 (35%): MA 位置关系
          - 广度比率 (30%): 上涨家数占比
          - 量价背离 (20%): 价格与成交量方向一致性
          - 板块轮动 (15%): 从衍生品行业情绪推算
        """
        subs: Dict[str, float] = {}

        # 趋势强度
        subs["trend_strength"] = self._calculate_trend_strength(market_data)

        # 广度比率 (简化: 使用价格vs均线比例近似)
        subs["breadth_ratio"] = self._estimate_breadth(market_data)

        # 量价背离
        subs["volume_price_divergence"] = self._detect_volume_price_divergence(market_data)

        # 板块轮动 (从衍生品结果提取)
        subs["sector_rotation"] = self._extract_sector_rotation(derivatives_result)

        self._last_momentum_subs = subs

        score = sum(
            subs.get(k, 50.0) * self._momentum_sub_weights.get(k, 0.25)
            for k in self._momentum_sub_weights
        )

        return max(0.0, min(100.0, score))

    def _calculate_trend_strength(self, market_data: Optional[pd.DataFrame]) -> float:
        """计算趋势强度"""
        if market_data is None or market_data.empty:
            return 50.0

        try:
            close = market_data["close"].values.astype(float)
            if len(close) < 20:
                return 50.0

            current = close[-1]
            ma5 = float(np.mean(close[-5:]))
            ma10 = float(np.mean(close[-10:]))
            ma20 = float(np.mean(close[-20:]))

            # 均线多头排列
            if current > ma5 > ma10 > ma20:
                return 85.0
            elif current > ma5 > ma10:
                return 70.0
            elif current > ma5:
                return 58.0
            elif current < ma5 < ma10 < ma20:
                return 15.0
            elif current < ma5 < ma10:
                return 30.0
            elif current < ma5:
                return 42.0
            else:
                return 50.0

        except Exception:
            return 50.0

    def _estimate_breadth(self, market_data: Optional[pd.DataFrame]) -> float:
        """估算广度比率 (简化版)

        使用指数自身涨幅家数占比近似:
          - 指数上涨天数占比作为广度代理
        """
        if market_data is None or market_data.empty:
            return 50.0

        try:
            close = market_data["close"].values.astype(float)
            if len(close) < 10:
                return 50.0

            # 最近10天上涨天数占比
            changes = np.diff(close[-11:])
            up_days = np.sum(changes > 0)
            breadth_ratio = float(up_days) / len(changes)

            # 映射到 0-100
            return breadth_ratio * 100.0

        except Exception:
            return 50.0

    def _detect_volume_price_divergence(
        self, market_data: Optional[pd.DataFrame],
    ) -> float:
        """检测量价背离

        量价同向 → 中性偏多
        价涨量缩 → 背离 (偏空)
        价跌量增 → 背离 (偏多, 可能见底)
        """
        if market_data is None or market_data.empty:
            return 50.0

        try:
            close = market_data["close"].values.astype(float)
            volume = market_data.get("volume")
            if volume is None:
                return 50.0
            volume = volume.values.astype(float) if hasattr(volume, 'values') else np.array(volume)

            if len(close) < 5 or len(volume) < 5:
                return 50.0

            # 最近5日价格变化方向
            price_change = close[-1] - close[-5]
            # 最近5日成交量变化方向
            vol_recent = float(np.mean(volume[-5:]))
            vol_prev = float(np.mean(volume[-10:-5])) if len(volume) >= 10 else vol_recent

            if price_change > 0 and vol_recent > vol_prev:
                return 65.0  # 价涨量增 → 多头
            elif price_change > 0 and vol_recent < vol_prev:
                return 35.0  # 价涨量缩 → 背离偏空
            elif price_change < 0 and vol_recent > vol_prev:
                return 60.0  # 价跌量增 → 可能见底
            elif price_change < 0 and vol_recent < vol_prev:
                return 30.0  # 价跌量缩 → 空头
            else:
                return 50.0

        except Exception:
            return 50.0

    def _extract_sector_rotation(self, derivatives_result: Optional[Any]) -> float:
        """从衍生品结果中提取板块轮动信号"""
        if derivatives_result is None:
            return 50.0

        try:
            # DerivativesResult.industry_sentiment
            if hasattr(derivatives_result, "industry_sentiment"):
                sentiments = derivatives_result.industry_sentiment
                if sentiments:
                    avg_signal = float(np.mean([
                        s.composite_signal for s in sentiments.values()
                    ]))
                    # -100~+100 → 0~100
                    return max(0.0, min(100.0, 50.0 + avg_signal * 0.5))
        except Exception:
            pass

        return 50.0

    # ═══════════════════════════════════════════════════════════════════════
    # D3: 体制维度
    # ═══════════════════════════════════════════════════════════════════════

    def _calculate_regime_score(self, regime_result: Optional[Any]) -> float:
        """计算体制维度评分 (0-100)

        子维度:
          - 波动率体制 (35%): 低波动→高分, 高波动→低分
          - 趋势体制 (30%): 牛市→高分, 熊市→低分
          - 流动性体制 (20%): 量增→高分
          - 情绪体制 (15%): PCR中性→高分
        """
        subs: Dict[str, float] = {}

        if regime_result is not None and hasattr(regime_result, "current_regime"):
            # 波动率体制
            vol = getattr(regime_result, "volatility_60d", 0.20)
            if vol < 0.15:
                subs["volatility_regime"] = 80.0
            elif vol < 0.25:
                subs["volatility_regime"] = 55.0
            elif vol < 0.35:
                subs["volatility_regime"] = 35.0
            else:
                subs["volatility_regime"] = 20.0

            # 趋势体制
            regime = regime_result.current_regime
            regime_score_map = {
                "bull": 85.0, "recovery": 65.0,
                "volatile": 45.0, "bear": 20.0,
            }
            subs["trend_regime"] = regime_score_map.get(regime, 50.0)

            # 流动性体制 (简化: 使用体制概率)
            probs = getattr(regime_result, "regime_probabilities", {})
            bull_prob = probs.get("bull", 0.0) + probs.get("recovery", 0.0)
            subs["liquidity_regime"] = 30.0 + bull_prob * 70.0

            # 情绪体制 (PCR水平)
            pcr = getattr(regime_result, "pcr_level", 1.0)
            if 0.8 <= pcr <= 1.2:
                subs["sentiment_regime"] = 60.0  # PCR中性偏多
            elif pcr < 0.8:
                subs["sentiment_regime"] = 75.0  # PCR偏低, 看多
            elif pcr > 1.3:
                subs["sentiment_regime"] = 25.0  # PCR偏高, 看空
            else:
                subs["sentiment_regime"] = 45.0

        else:
            # 无体制结果, 使用默认值
            subs = {
                "volatility_regime": 50.0,
                "trend_regime": 50.0,
                "liquidity_regime": 50.0,
                "sentiment_regime": 50.0,
            }

        self._last_regime_subs = subs

        score = sum(
            subs.get(k, 50.0) * self._regime_sub_weights.get(k, 0.25)
            for k in self._regime_sub_weights
        )

        return max(0.0, min(100.0, score))

    # ═══════════════════════════════════════════════════════════════════════
    # D4: 海外维度 [V8 NEW]
    # ═══════════════════════════════════════════════════════════════════════

    def _calculate_overseas_score(self, overseas_signal: Optional[Any]) -> float:
        """计算海外维度评分 (0-100) [V8 NEW]

        子维度:
          - 价格信号 (40%): 海外期货价格方向
          - 持仓信号 (25%): CFTC 持仓方向
          - 宏观信号 (20%): 中美利差/PMI等
          - 情绪信号 (15%): QVIX/BTC波动率等

        海外综合信号本身就是 0-100 评分, 直接使用.
        """
        subs: Dict[str, float] = {}

        if overseas_signal is not None:
            # OverseasCompositeSignal
            if hasattr(overseas_signal, "price_score"):
                subs["price_signal"] = float(overseas_signal.price_score)
            if hasattr(overseas_signal, "position_score"):
                subs["position_signal"] = float(overseas_signal.position_score)
            if hasattr(overseas_signal, "macro_score"):
                subs["macro_signal"] = float(overseas_signal.macro_score)
            if hasattr(overseas_signal, "sentiment_score"):
                subs["sentiment_signal"] = float(overseas_signal.sentiment_score)

            # 如果没有子维度但有综合评分, 直接使用
            if not subs and hasattr(overseas_signal, "composite_score"):
                return max(0.0, min(100.0, float(overseas_signal.composite_score)))

        # 填充缺失子维度
        default_subs = {
            "price_signal": 50.0,
            "position_signal": 50.0,
            "macro_signal": 50.0,
            "sentiment_signal": 50.0,
        }
        for k, v in default_subs.items():
            if k not in subs:
                subs[k] = v

        self._last_overseas_subs = subs

        score = sum(
            subs.get(k, 50.0) * self._overseas_sub_weights.get(k, 0.25)
            for k in self._overseas_sub_weights
        )

        return max(0.0, min(100.0, score))

    # ═══════════════════════════════════════════════════════════════════════
    # 综合评判
    # ═══════════════════════════════════════════════════════════════════════

    @staticmethod
    def _determine_state(
        composite_score: float,
    ) -> Tuple[str, str, int]:
        """根据综合评分确定状态标签

        Args:
            composite_score: 综合评分 (0-100)

        Returns:
            (overall_state, state_label, state_level)
        """
        if composite_score >= SCORE_THRESHOLDS["strategic_offense"]:
            state = "strategic_offense"
        elif composite_score >= SCORE_THRESHOLDS["active_allocation"]:
            state = "active_allocation"
        elif composite_score >= SCORE_THRESHOLDS["balanced_hold"]:
            state = "balanced_hold"
        elif composite_score >= SCORE_THRESHOLDS["defensive_watch"]:
            state = "defensive_watch"
        else:
            state = "strategic_defense"

        label, level, _ = STATE_LABELS[state]
        return state, label, level

    @staticmethod
    def _calculate_confidence(
        scores: Dict[str, DimensionScore],
        composite_score: float,
    ) -> float:
        """计算分类置信度

        置信度基于:
          1. 评分偏离50的程度 (越偏离中性, 越自信)
          2. 各维度方向一致性 (越一致, 越自信)
        """
        # 评分偏离度
        deviation = abs(composite_score - 50.0) / 50.0

        # 方向一致性
        directions = [s.direction for s in scores.values()]
        bullish_count = sum(1 for d in directions if d == "bullish")
        bearish_count = sum(1 for d in directions if d == "bearish")

        if bullish_count + bearish_count == 0:
            consistency = 0.3  # 全中性, 低置信度
        else:
            consistency = max(bullish_count, bearish_count) / len(directions)

        # 综合置信度
        confidence = deviation * 0.6 + consistency * 0.4
        return max(0.0, min(1.0, confidence))

    # ═══════════════════════════════════════════════════════════════════════
    # 配置加载
    # ═══════════════════════════════════════════════════════════════════════

    def _load_dimension_weights(self) -> Dict[str, float]:
        """加载四维权重"""
        if self._config is not None:
            try:
                cfg = self._config.get("market_state_classifier", {})
                thresholds = cfg.get("thresholds", {})
                if thresholds:
                    return {
                        "valuation": thresholds.get("valuation_weight", 0.30),
                        "momentum": thresholds.get("momentum_weight", 0.25),
                        "regime": thresholds.get("regime_weight", 0.25),
                        "overseas": thresholds.get("overseas_weight", 0.20),
                    }
            except Exception:
                pass
        return dict(DEFAULT_DIMENSION_WEIGHTS)

    def _load_valuation_sub_weights(self) -> Dict[str, float]:
        """加载估值子维度权重"""
        if self._config is not None:
            try:
                cfg = self._config.get("market_state_classifier", {})
                sub = cfg.get("valuation_sub_dimensions", {})
                if sub:
                    return {k: float(v) for k, v in sub.items()}
            except Exception:
                pass
        return dict(VALUATION_SUB_WEIGHTS)

    def _load_momentum_sub_weights(self) -> Dict[str, float]:
        """加载动量子维度权重"""
        if self._config is not None:
            try:
                cfg = self._config.get("market_state_classifier", {})
                sub = cfg.get("momentum_sub_dimensions", {})
                if sub:
                    return {k: float(v) for k, v in sub.items()}
            except Exception:
                pass
        return dict(MOMENTUM_SUB_WEIGHTS)

    def _load_regime_sub_weights(self) -> Dict[str, float]:
        """加载体制子维度权重"""
        if self._config is not None:
            try:
                cfg = self._config.get("market_state_classifier", {})
                sub = cfg.get("regime_sub_dimensions", {})
                if sub:
                    return {k: float(v) for k, v in sub.items()}
            except Exception:
                pass
        return dict(REGIME_SUB_WEIGHTS)

    def _load_overseas_sub_weights(self) -> Dict[str, float]:
        """加载海外子维度权重"""
        if self._config is not None:
            try:
                cfg = self._config.get("market_state_classifier", {})
                sub = cfg.get("overseas_sub_dimensions", {})
                if sub:
                    return {k: float(v) for k, v in sub.items()}
            except Exception:
                pass
        return dict(OVERSEAS_SUB_WEIGHTS)
