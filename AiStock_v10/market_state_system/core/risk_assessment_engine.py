"""
AiStock V8 — 风险评估引擎 (Risk Assessment Engine)

V8 升级: 海外传导风险 + 期权情绪风险

7 维度风险因子:
  1. 估值风险 — PE/PB 极度高估
  2. 流动性风险 — 成交量萎缩/融资余额下降
  3. 波动率风险 — 波动率急剧放大
  4. 杠杆风险 — 融资融券余额异常
  5. 集中度风险 — 行业/板块集中度过高
  6. 海外传导风险 [V8 NEW] — 外盘极端信号传导
  7. 期权情绪风险 [V8 NEW] — PCR 极端/波动率偏斜

风险指标:
  - VaR_95:  95% 置信度 Value-at-Risk
  - CVaR_95: 95% 置信度 Conditional VaR (Expected Shortfall)
  - max_drawdown: 最大回撤
  - volatility: 波动率
  - sharpe: 夏普比率

风险级别: low / medium / high / extreme
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
class RiskFactor:
    """风险因子

    Attributes:
        name:        因子名称
        category:    因子类别
        score:       风险评分 (0-100, 0=无风险, 100=极高风险)
        level:       风险级别 'low' / 'medium' / 'high' / 'extreme'
        description: 风险描述
        value:       原始值
        threshold:   阈值
    """
    name: str
    category: str = ""
    score: float = 0.0
    level: str = "low"
    description: str = ""
    value: float = 0.0
    threshold: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "score": round(self.score, 2),
            "level": self.level,
            "description": self.description,
            "value": round(self.value, 4),
            "threshold": round(self.threshold, 4),
        }


@dataclass
class RiskMetrics:
    """风险指标

    Attributes:
        var_95:        95% VaR (日度)
        cvar_95:       95% CVaR (日度)
        max_drawdown:  最大回撤
        volatility:    年化波动率
        sharpe:        夏普比率 (年化)
    """
    var_95: float = 0.0
    cvar_95: float = 0.0
    max_drawdown: float = 0.0
    volatility: float = 0.0
    sharpe: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "VaR_95": round(self.var_95, 6),
            "CVaR_95": round(self.cvar_95, 6),
            "max_drawdown": round(self.max_drawdown, 6),
            "volatility": round(self.volatility, 6),
            "sharpe": round(self.sharpe, 4),
        }


@dataclass
class RiskResult:
    """风险评估结果

    Attributes:
        overall_risk_score: 总风险评分 (0-100)
        risk_level:         总风险级别
        risk_factors:       各维度风险因子
        risk_metrics:       风险指标
        warnings:           风险预警列表
        timestamp:          评估时间戳
    """
    overall_risk_score: float = 0.0
    risk_level: str = "low"
    risk_factors: Dict[str, RiskFactor] = field(default_factory=dict)
    risk_metrics: Optional[RiskMetrics] = None
    warnings: List[str] = field(default_factory=list)
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    @property
    def is_high_risk(self) -> bool:
        return self.overall_risk_score >= 60.0

    @property
    def is_extreme_risk(self) -> bool:
        return self.overall_risk_score >= 80.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_risk_score": round(self.overall_risk_score, 2),
            "risk_level": self.risk_level,
            "is_high_risk": self.is_high_risk,
            "is_extreme_risk": self.is_extreme_risk,
            "risk_factors": {k: v.to_dict() for k, v in self.risk_factors.items()},
            "risk_metrics": self.risk_metrics.to_dict() if self.risk_metrics else None,
            "warnings": self.warnings,
            "timestamp": self.timestamp,
        }

    def __repr__(self) -> str:
        return (
            f"RiskResult(score={self.overall_risk_score:.1f} [{self.risk_level}] "
            f"factors={len(self.risk_factors)} warnings={len(self.warnings)})"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 默认配置
# ═══════════════════════════════════════════════════════════════════════════════

# 风险因子类别权重
RISK_CATEGORY_WEIGHTS = {
    "valuation": 0.15,
    "liquidity": 0.15,
    "volatility": 0.18,
    "leverage": 0.12,
    "concentration": 0.10,
    "overseas": 0.15,
    "pcr_sentiment": 0.15,
}

# 风险级别阈值
RISK_LEVEL_THRESHOLDS = {
    "low": 25.0,
    "medium": 50.0,
    "high": 70.0,
    "extreme": 100.0,
}

# 估值风险阈值
VALUATION_RISK_THRESHOLDS = {
    "pe_overvalued": 75.0,      # PE百分位 75%+ → 高估风险
    "pe_extreme": 90.0,         # PE百分位 90%+ → 极度高估
    "pb_overvalued": 75.0,
    "pb_extreme": 90.0,
}

# 波动率风险阈值
VOLATILITY_RISK_THRESHOLDS = {
    "warning_expansion": 1.8,   # 波动率扩张倍数
    "extreme_expansion": 2.5,
}

# 流动性风险阈值
LIQUIDITY_RISK_THRESHOLDS = {
    "warning_shrink": 0.6,      # 成交量萎缩比率
    "extreme_shrink": 0.4,
}

# 海外风险阈值 [V8 NEW]
OVERSEAS_RISK_THRESHOLDS = {
    "extreme_bearish": 20.0,    # 海外信号极度看空阈值
    "cftc_extreme_position": True,
    "dollar_breakout": 105.0,
    "bond_yield_inversion": True,
    "vix_spike": 30.0,
}

# PCR 风险阈值 [V8 NEW]
PCR_RISK_THRESHOLDS = {
    "extreme_high": 1.5,        # PCR 极端高位 (恐慌)
    "warning_high": 1.3,
    "extreme_low": 0.5,         # PCR 极端低位 (贪婪)
    "warning_low": 0.7,
    "volatility_skew_extreme": 2.0,
}


# ═══════════════════════════════════════════════════════════════════════════════
# 风险评估引擎
# ═══════════════════════════════════════════════════════════════════════════════

class RiskAssessmentEngine:
    """风险评估引擎 (V8 增强版)

    7 维度风险因子:
      1. 估值风险 — PE/PB 极度高估
      2. 流动性风险 — 成交量萎缩
      3. 波动率风险 — 波动率急剧放大
      4. 杠杆风险 — 融资融券异常
      5. 集中度风险 — 行业集中度过高
      6. 海外传导风险 [V8 NEW] — 外盘极端信号
      7. 期权情绪风险 [V8 NEW] — PCR 极端

    使用方式:
        >>> engine = RiskAssessmentEngine(config=config)
        >>> result = engine.assess(
        ...     classification_result=cls_res,
        ...     regime_result=regime_res,
        ...     derivatives_result=deriv_res,
        ...     pcr_result=pcr_res,
        ...     overseas_signal=overseas_sig,
        ... )
        >>> print(result.overall_risk_score, result.risk_level)
    """

    def __init__(
        self,
        data_service: Optional[TDXAdapter] = None,
        db_reader: Optional[DatabaseReader] = None,
        config: Optional[ConfigService] = None,
        cache: Optional[CacheService] = None,
        logger_instance: Optional[logging.Logger] = None,
    ) -> None:
        """初始化风险评估引擎

        Args:
            data_service: TDXAdapter 实例
            db_reader:    DatabaseReader 实例
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
        self._category_weights = self._load_category_weights()
        self._valuation_thresholds = self._load_valuation_thresholds()
        self._volatility_thresholds = self._load_volatility_thresholds()
        self._liquidity_thresholds = self._load_liquidity_thresholds()
        self._overseas_thresholds = self._load_overseas_thresholds()
        self._pcr_thresholds = self._load_pcr_thresholds()

        self._logger.info(
            "RiskAssessmentEngine V8.0 初始化完成 | 7维度风险因子 (含海外+PCR)"
        )

    # ═══════════════════════════════════════════════════════════════════════
    # 核心评估方法
    # ═══════════════════════════════════════════════════════════════════════

    def assess(
        self,
        classification_result: Optional[Any] = None,
        regime_result: Optional[Any] = None,
        derivatives_result: Optional[Any] = None,
        pcr_result: Optional[Any] = None,
        overseas_signal: Optional[Any] = None,
        market_data: Optional[pd.DataFrame] = None,
    ) -> RiskResult:
        """执行综合风险评估

        Args:
            classification_result: 分类结果 (ClassificationResult)
            regime_result:         体制结果 (RegimeResult)
            derivatives_result:    衍生品结果 (DerivativesResult)
            pcr_result:            PCR 结果 (CompositePCRResult)
            overseas_signal:       海外信号 (OverseasCompositeSignal) [V8 NEW]
            market_data:           指数K线数据

        Returns:
            RiskResult
        """
        start_time = time.time()

        risk_factors: Dict[str, RiskFactor] = {}
        warnings: List[str] = []

        # 1. 估值风险
        val_risk = self._assess_valuation_risk(classification_result)
        risk_factors["valuation"] = val_risk
        if val_risk.level in ("high", "extreme"):
            warnings.append(f"估值风险: {val_risk.description}")

        # 2. 流动性风险
        liq_risk = self._assess_liquidity_risk(market_data, derivatives_result)
        risk_factors["liquidity"] = liq_risk
        if liq_risk.level in ("high", "extreme"):
            warnings.append(f"流动性风险: {liq_risk.description}")

        # 3. 波动率风险
        vol_risk = self._assess_volatility_risk(regime_result, market_data)
        risk_factors["volatility"] = vol_risk
        if vol_risk.level in ("high", "extreme"):
            warnings.append(f"波动率风险: {vol_risk.description}")

        # 4. 杠杆风险
        lev_risk = self._assess_leverage_risk()
        risk_factors["leverage"] = lev_risk
        if lev_risk.level in ("high", "extreme"):
            warnings.append(f"杠杆风险: {lev_risk.description}")

        # 5. 集中度风险
        con_risk = self._assess_concentration_risk(derivatives_result)
        risk_factors["concentration"] = con_risk
        if con_risk.level in ("high", "extreme"):
            warnings.append(f"集中度风险: {con_risk.description}")

        # 6. 海外传导风险 [V8 NEW]
        os_risk = self._assess_overseas_risk(overseas_signal)
        risk_factors["overseas"] = os_risk
        if os_risk.level in ("high", "extreme"):
            warnings.append(f"海外传导风险: {os_risk.description}")

        # 7. 期权情绪风险 [V8 NEW]
        pcr_risk = self._assess_pcr_risk(pcr_result)
        risk_factors["pcr_sentiment"] = pcr_risk
        if pcr_risk.level in ("high", "extreme"):
            warnings.append(f"期权情绪风险: {pcr_risk.description}")

        # 综合风险评分
        overall_score = self._calculate_overall_risk(risk_factors)
        risk_level = self._determine_risk_level(overall_score)

        # 风险指标
        risk_metrics = self._calculate_risk_metrics(market_data)

        result = RiskResult(
            overall_risk_score=overall_score,
            risk_level=risk_level,
            risk_factors=risk_factors,
            risk_metrics=risk_metrics,
            warnings=warnings,
        )

        elapsed = (time.time() - start_time) * 1000
        self._logger.info(
            "风险评估: score=%.1f [%s] | 估值=%.0f 流动性=%.0f 波动率=%.0f "
            "杠杆=%.0f 集中度=%.0f 海外=%.0f PCR=%.0f | warnings=%d | %.0fms",
            overall_score, risk_level,
            val_risk.score, liq_risk.score, vol_risk.score,
            lev_risk.score, con_risk.score, os_risk.score, pcr_risk.score,
            len(warnings), elapsed,
        )

        return result

    # ═══════════════════════════════════════════════════════════════════════
    # 1. 估值风险
    # ═══════════════════════════════════════════════════════════════════════

    def _assess_valuation_risk(self, classification_result: Optional[Any]) -> RiskFactor:
        """评估估值风险"""
        # 从分类结果中提取估值评分
        valuation_score = 50.0
        if classification_result is not None:
            try:
                if hasattr(classification_result, "scores"):
                    val = classification_result.scores.get("valuation")
                    if val is not None:
                        valuation_score = val.score
            except Exception:
                pass

        # 估值评分低 → 估值风险高 (PE/PB 高估)
        # 反转: 估值评分 0 → 风险 100, 估值评分 100 → 风险 0
        risk_score = 100.0 - valuation_score

        if risk_score >= 80:
            level = "extreme"
            desc = f"极度高估 (估值评分={valuation_score:.0f})"
        elif risk_score >= 60:
            level = "high"
            desc = f"偏高估 (估值评分={valuation_score:.0f})"
        elif risk_score >= 35:
            level = "medium"
            desc = f"估值适中 (估值评分={valuation_score:.0f})"
        else:
            level = "low"
            desc = f"估值偏低 (估值评分={valuation_score:.0f})"

        return RiskFactor(
            name="估值风险", category="valuation",
            score=risk_score, level=level,
            description=desc, value=valuation_score,
            threshold=self._valuation_thresholds.get("pe_overvalued", 75.0),
        )

    # ═══════════════════════════════════════════════════════════════════════
    # 2. 流动性风险
    # ═══════════════════════════════════════════════════════════════════════

    def _assess_liquidity_risk(
        self,
        market_data: Optional[pd.DataFrame],
        derivatives_result: Optional[Any],
    ) -> RiskFactor:
        """评估流动性风险"""
        risk_score = 20.0  # 默认低风险
        shrink_ratio = 1.0

        if market_data is not None and not market_data.empty:
            try:
                volume = market_data["volume"].values.astype(float)
                if len(volume) >= 20:
                    vol_recent = float(np.mean(volume[-5:]))
                    vol_20d = float(np.mean(volume[-20:]))
                    if vol_20d > 0:
                        shrink_ratio = vol_recent / vol_20d

                    # 成交量萎缩 → 流动性风险上升
                    warning_shrink = self._liquidity_thresholds.get("warning_shrink", 0.6)
                    extreme_shrink = self._liquidity_thresholds.get("extreme_shrink", 0.4)

                    if shrink_ratio < extreme_shrink:
                        risk_score = 80.0
                    elif shrink_ratio < warning_shrink:
                        risk_score = 55.0
                    elif shrink_ratio < 0.8:
                        risk_score = 35.0
                    else:
                        risk_score = 15.0
            except Exception:
                pass

        level = self._score_to_level(risk_score)
        desc = f"成交量比率={shrink_ratio:.2f}"

        return RiskFactor(
            name="流动性风险", category="liquidity",
            score=risk_score, level=level,
            description=desc, value=shrink_ratio,
            threshold=self._liquidity_thresholds.get("warning_shrink", 0.6),
        )

    # ═══════════════════════════════════════════════════════════════════════
    # 3. 波动率风险
    # ═══════════════════════════════════════════════════════════════════════

    def _assess_volatility_risk(
        self,
        regime_result: Optional[Any],
        market_data: Optional[pd.DataFrame],
    ) -> RiskFactor:
        """评估波动率风险"""
        vol_60d = 0.0
        risk_score = 20.0

        # 从体制结果提取
        if regime_result is not None:
            try:
                vol_60d = getattr(regime_result, "volatility_60d", 0.0)
            except Exception:
                pass

        # 如果没有体制结果, 从市场数据计算
        if vol_60d <= 0 and market_data is not None and not market_data.empty:
            try:
                close = market_data["close"].values.astype(float)
                if len(close) >= 20:
                    returns = np.diff(close[-61:]) / close[-61:-1]
                    returns = returns[np.isfinite(returns)]
                    if len(returns) > 0:
                        vol_60d = float(np.std(returns) * np.sqrt(252))
            except Exception:
                pass

        # 波动率风险评估
        if vol_60d > 0.40:
            risk_score = 85.0
        elif vol_60d > 0.30:
            risk_score = 65.0
        elif vol_60d > 0.25:
            risk_score = 45.0
        elif vol_60d > 0.20:
            risk_score = 30.0
        else:
            risk_score = 15.0

        level = self._score_to_level(risk_score)
        desc = f"60日年化波动率={vol_60d:.2%}"

        return RiskFactor(
            name="波动率风险", category="volatility",
            score=risk_score, level=level,
            description=desc, value=vol_60d,
            threshold=0.30,
        )

    # ═══════════════════════════════════════════════════════════════════════
    # 4. 杠杆风险
    # ═══════════════════════════════════════════════════════════════════════

    def _assess_leverage_risk(self) -> RiskFactor:
        """评估杠杆风险 (融资融券)

        简化版: 使用配置中的阈值, 实际数据需从 TDX 或 akshare 获取.
        """
        # 默认中等风险 (无数据时)
        risk_score = 30.0
        margin_ratio = 0.0

        # TODO: 从 TDX 或 akshare 获取融资融券数据
        # margin_data = self._fetch_margin_data()
        # if margin_data:
        #     margin_ratio = margin_data.get("ratio", 0.09)
        #     warning = self._config.get("risk_thresholds.liquidity.margin_trading_warning", 0.7)
        #     extreme = self._config.get("risk_thresholds.liquidity.margin_trading_extreme", 0.5)
        #     ...

        level = self._score_to_level(risk_score)
        desc = f"融资余额比率={margin_ratio:.2%}"

        return RiskFactor(
            name="杠杆风险", category="leverage",
            score=risk_score, level=level,
            description=desc, value=margin_ratio,
            threshold=0.07,
        )

    # ═══════════════════════════════════════════════════════════════════════
    # 5. 集中度风险
    # ═══════════════════════════════════════════════════════════════════════

    def _assess_concentration_risk(self, derivatives_result: Optional[Any]) -> RiskFactor:
        """评估集中度风险

        行业情绪集中度: 如果多数行业信号方向一致, 集中度高.
        """
        risk_score = 25.0
        concentration = 0.0

        if derivatives_result is not None:
            try:
                if hasattr(derivatives_result, "industry_sentiment"):
                    sentiments = derivatives_result.industry_sentiment
                    if sentiments:
                        directions = [s.direction for s in sentiments.values()]
                        total = len(directions)
                        if total > 0:
                            bullish = sum(1 for d in directions if d == "bullish")
                            bearish = sum(1 for d in directions if d == "bearish")
                            concentration = max(bullish, bearish) / total

                            # 集中度过高 → 风险 (方向可能反转)
                            if concentration > 0.80:
                                risk_score = 70.0
                            elif concentration > 0.65:
                                risk_score = 50.0
                            elif concentration > 0.50:
                                risk_score = 35.0
                            else:
                                risk_score = 20.0
            except Exception:
                pass

        level = self._score_to_level(risk_score)
        desc = f"行业方向集中度={concentration:.1%}"

        return RiskFactor(
            name="集中度风险", category="concentration",
            score=risk_score, level=level,
            description=desc, value=concentration,
            threshold=0.65,
        )

    # ═══════════════════════════════════════════════════════════════════════
    # 6. 海外传导风险 [V8 NEW]
    # ═══════════════════════════════════════════════════════════════════════

    def _assess_overseas_risk(self, overseas_signal: Optional[Any]) -> RiskFactor:
        """评估海外传导风险 [V8 NEW]

        风险来源:
          - 海外综合信号极度看空 (< 20)
          - CFTC 持仓极端 (拥挤多头/空头)
          - 美元指数突破 (DXY > 105)
          - 中美利差倒挂
          - VIX/QVIX 急剧上升
        """
        risk_score = 20.0
        overseas_composite = 50.0

        if overseas_signal is not None:
            try:
                # 提取海外综合信号
                if hasattr(overseas_signal, "composite_score"):
                    overseas_composite = float(overseas_signal.composite_score)
                elif isinstance(overseas_signal, dict):
                    overseas_composite = float(overseas_signal.get("composite_score", 50.0))

                # 海外信号极端看空 → 高风险
                extreme_low = self._overseas_thresholds.get("extreme_bearish", 20.0)
                if overseas_composite < extreme_low:
                    # 极度看空, 风险很高
                    risk_score = 70.0 + (extreme_low - overseas_composite) / extreme_low * 30.0
                elif overseas_composite < 35:
                    risk_score = 45.0 + (35.0 - overseas_composite) / 15.0 * 15.0
                elif overseas_composite > 80:
                    # 极度看多也有风险 (过度乐观后反转)
                    risk_score = 40.0 + (overseas_composite - 80.0) / 20.0 * 20.0
                else:
                    risk_score = 20.0

                # 检查冲突折扣
                if hasattr(overseas_signal, "conflict_discount"):
                    discount = overseas_signal.conflict_discount
                    if discount < 0.7:
                        # 高冲突 → 不确定性高 → 风险增加
                        risk_score += 15.0

                # 检查持仓信号
                if hasattr(overseas_signal, "position_signals"):
                    pos_signals = overseas_signal.position_signals
                    if pos_signals:
                        crowded_count = sum(
                            1 for ps in pos_signals.values()
                            if hasattr(ps, "position_crowding_label")
                            and ps.position_crowding_label in ("crowded_long", "crowded_short")
                        )
                        if crowded_count > 2:
                            risk_score += 10.0

            except Exception as e:
                self._logger.debug("海外风险评估异常: %s", e)

        risk_score = max(0.0, min(100.0, risk_score))
        level = self._score_to_level(risk_score)
        desc = f"海外综合信号={overseas_composite:.0f}"

        return RiskFactor(
            name="海外传导风险", category="overseas",
            score=risk_score, level=level,
            description=desc, value=overseas_composite,
            threshold=self._overseas_thresholds.get("extreme_bearish", 20.0),
        )

    # ═══════════════════════════════════════════════════════════════════════
    # 7. 期权情绪风险 [V8 NEW]
    # ═══════════════════════════════════════════════════════════════════════

    def _assess_pcr_risk(self, pcr_result: Optional[Any]) -> RiskFactor:
        """评估期权情绪风险 [V8 NEW]

        风险来源:
          - PCR 极端高位 (> 1.5) → 恐慌过度 (可能是反向信号)
          - PCR 极端低位 (< 0.5) → 贪婪过度
          - PCR 背离 (商品 vs 指数)
          - 波动率偏斜极端
        """
        risk_score = 20.0
        pcr_value = 1.0

        # 提前加载阈值 (确保在 try 块外也能访问)
        extreme_high = self._pcr_thresholds.get("extreme_high", 1.5)
        warning_high = self._pcr_thresholds.get("warning_high", 1.3)
        extreme_low = self._pcr_thresholds.get("extreme_low", 0.5)
        warning_low = self._pcr_thresholds.get("warning_low", 0.7)

        if pcr_result is not None:
            try:
                # 提取 PCR 值
                if hasattr(pcr_result, "composite_pcr"):
                    pcr_value = float(pcr_result.composite_pcr)
                elif isinstance(pcr_result, dict):
                    pcr_value = float(pcr_result.get("composite_pcr", 1.0))

                if pcr_value > extreme_high:
                    risk_score = 75.0 + min(25.0, (pcr_value - extreme_high) * 50.0)
                elif pcr_value > warning_high:
                    risk_score = 50.0 + (pcr_value - warning_high) / (extreme_high - warning_high) * 25.0
                elif pcr_value < extreme_low:
                    risk_score = 70.0 + min(25.0, (extreme_low - pcr_value) * 50.0)
                elif pcr_value < warning_low:
                    risk_score = 45.0 + (warning_low - pcr_value) / (warning_low - extreme_low) * 25.0
                else:
                    risk_score = 15.0

                # 检查 PCR 背离
                if hasattr(pcr_result, "is_divergent"):
                    if pcr_result.is_divergent:
                        risk_score += 15.0
                        self._logger.debug("PCR背离增加风险 +15")
                elif isinstance(pcr_result, dict):
                    div = pcr_result.get("divergence_signal")
                    if div and hasattr(div, "is_divergent") and div.is_divergent:
                        risk_score += 15.0

                # 检查信号级别
                if hasattr(pcr_result, "signal_level"):
                    if pcr_result.signal_level == "extreme":
                        risk_score += 10.0

            except Exception as e:
                self._logger.debug("PCR风险评估异常: %s", e)

        risk_score = max(0.0, min(100.0, risk_score))
        level = self._score_to_level(risk_score)

        if pcr_value > warning_high:
            desc = f"PCR偏高={pcr_value:.3f} (恐慌情绪)"
        elif pcr_value < warning_low:
            desc = f"PCR偏低={pcr_value:.3f} (贪婪情绪)"
        else:
            desc = f"PCR={pcr_value:.3f} (中性)"

        return RiskFactor(
            name="期权情绪风险", category="pcr_sentiment",
            score=risk_score, level=level,
            description=desc, value=pcr_value,
            threshold=extreme_high if pcr_value > 1.0 else extreme_low,
        )

    # ═══════════════════════════════════════════════════════════════════════
    # 综合风险计算
    # ═══════════════════════════════════════════════════════════════════════

    def _calculate_overall_risk(self, risk_factors: Dict[str, RiskFactor]) -> float:
        """计算综合风险评分

        加权汇总各维度风险评分.
        """
        total_score = 0.0
        total_weight = 0.0

        for category, weight in self._category_weights.items():
            factor = risk_factors.get(category)
            if factor is not None:
                total_score += factor.score * weight
                total_weight += weight

        if total_weight > 0:
            overall = total_score / total_weight
        else:
            overall = 0.0

        return max(0.0, min(100.0, overall))

    @staticmethod
    def _determine_risk_level(score: float) -> str:
        """确定风险级别"""
        if score >= RISK_LEVEL_THRESHOLDS["high"]:
            return "extreme" if score >= RISK_LEVEL_THRESHOLDS["extreme"] * 0.8 else "high"
        elif score >= RISK_LEVEL_THRESHOLDS["medium"]:
            return "medium"
        else:
            return "low"

    @staticmethod
    def _score_to_level(score: float) -> str:
        """评分→级别"""
        if score >= 70:
            return "extreme" if score >= 85 else "high"
        elif score >= 40:
            return "medium"
        else:
            return "low"

    # ═══════════════════════════════════════════════════════════════════════
    # 风险指标计算
    # ═══════════════════════════════════════════════════════════════════════

    def _calculate_risk_metrics(
        self, market_data: Optional[pd.DataFrame],
    ) -> RiskMetrics:
        """计算风险指标

        VaR_95, CVaR_95, 最大回撤, 波动率, 夏普比率
        """
        if market_data is None or market_data.empty:
            return RiskMetrics()

        try:
            close = market_data["close"].values.astype(float)
            if len(close) < 20:
                return RiskMetrics()

            # 日收益率
            returns = np.diff(close) / close[:-1]
            returns = returns[np.isfinite(returns)]

            if len(returns) < 10:
                return RiskMetrics()

            # VaR (95%)
            var_95 = float(np.percentile(returns, 5))

            # CVaR (95%)
            tail_returns = returns[returns <= var_95]
            cvar_95 = float(np.mean(tail_returns)) if len(tail_returns) > 0 else var_95

            # 最大回撤
            cumulative = np.cumprod(1.0 + returns)
            running_max = np.maximum.accumulate(cumulative)
            drawdowns = (cumulative - running_max) / running_max
            max_dd = float(np.min(drawdowns)) if len(drawdowns) > 0 else 0.0

            # 年化波动率
            vol = float(np.std(returns) * np.sqrt(252))

            # 夏普比率 (无风险利率取 2.5%)
            rf_daily = 0.025 / 252
            excess_returns = returns - rf_daily
            if np.std(excess_returns) > 0:
                sharpe = float(np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252))
            else:
                sharpe = 0.0

            return RiskMetrics(
                var_95=var_95,
                cvar_95=cvar_95,
                max_drawdown=max_dd,
                volatility=vol,
                sharpe=sharpe,
            )

        except Exception as e:
            self._logger.warning("风险指标计算异常: %s", e)
            return RiskMetrics()

    # ═══════════════════════════════════════════════════════════════════════
    # 配置加载
    # ═══════════════════════════════════════════════════════════════════════

    def _load_category_weights(self) -> Dict[str, float]:
        """加载风险因子类别权重"""
        if self._config is not None:
            try:
                weights = self._config.get("risk_category_weights", {})
                if weights:
                    return {k: float(v) for k, v in weights.items()}
            except Exception:
                pass
        return dict(RISK_CATEGORY_WEIGHTS)

    def _load_valuation_thresholds(self) -> Dict[str, float]:
        if self._config is not None:
            try:
                t = self._config.get("risk_thresholds.valuation", {})
                if t:
                    return {k: float(v) for k, v in t.items()}
            except Exception:
                pass
        return dict(VALUATION_RISK_THRESHOLDS)

    def _load_volatility_thresholds(self) -> Dict[str, float]:
        if self._config is not None:
            try:
                t = self._config.get("risk_thresholds.volatility", {})
                if t:
                    return {k: float(v) for k, v in t.items()}
            except Exception:
                pass
        return dict(VOLATILITY_RISK_THRESHOLDS)

    def _load_liquidity_thresholds(self) -> Dict[str, float]:
        if self._config is not None:
            try:
                t = self._config.get("risk_thresholds.liquidity", {})
                if t:
                    return {k: float(v) for k, v in t.items()}
            except Exception:
                pass
        return dict(LIQUIDITY_RISK_THRESHOLDS)

    def _load_overseas_thresholds(self) -> Dict[str, Any]:
        if self._config is not None:
            try:
                t = self._config.get("risk_thresholds.overseas_risk", {})
                if t:
                    return dict(t)
            except Exception:
                pass
        return dict(OVERSEAS_RISK_THRESHOLDS)

    def _load_pcr_thresholds(self) -> Dict[str, Any]:
        if self._config is not None:
            try:
                t = self._config.get("risk_thresholds.pcr", {})
                if t:
                    return dict(t)
            except Exception:
                pass
        return dict(PCR_RISK_THRESHOLDS)
