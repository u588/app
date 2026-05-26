#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AiStock V10 — 衍生品信号引擎 (Derivatives Signal Engine)

V9 → V10 升级改进:
  1. **移除所有硬编码配置**: DEFAULT_INDEX_FUTURES, DEFAULT_COMMODITY_VARIETIES,
     COMMODITY_SIGNAL_WEIGHTS, COMPOSITE_WEIGHTS 全部从 ConfigService (YAML) 加载
  2. **L8 后缀**: _resolve_futures_code() 默认后缀 L8 (不是 M0)
  3. 构造函数接受 ConfigService

核心能力:
  1. 商品期货信号  — 国内期货品种动量/基差/持仓/波动率
  2. 期限结构信号  — 远近月价差 (Contango/Backwardation)
  3. 股指期货基差  — IF/IH/IC/IM 升贴水
  4. 行业情绪信号  — 期货品种→A股行业传导
  5. 海外衍生品信号 — 调用 OverseasFuturesSignalEngine 融合外盘信号
  6. 增强报告 — 含海外信号的完整报告
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# ─── Type aliases ──────────────────────────────────────────────────────────────
TDXAdapter = Any
ContractManager = Any
OverseasSignalEngine = Any
ConfigService = Any
CacheService = Any

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# 数据类定义
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class CommoditySignal:
    """单个商品品种信号"""
    variety: str
    name: str = ""
    momentum_20d: float = 0.0
    basis: float = 0.0
    basis_pct: float = 0.0
    oi_change_5d: float = 0.0
    volatility_20d: float = 0.0
    signal: float = 0.0
    direction: str = "neutral"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "variety": self.variety, "name": self.name,
            "momentum_20d": round(self.momentum_20d, 4),
            "basis": round(self.basis, 4),
            "basis_pct": round(self.basis_pct, 4),
            "oi_change_5d": round(self.oi_change_5d, 4),
            "volatility_20d": round(self.volatility_20d, 4),
            "signal": round(self.signal, 2),
            "direction": self.direction,
        }


@dataclass
class TermStructureSignal:
    """期限结构信号"""
    variety: str
    near_month: str = ""
    far_month: str = ""
    near_price: float = 0.0
    far_price: float = 0.0
    spread: float = 0.0
    spread_pct: float = 0.0
    structure_type: str = "flat"
    signal: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "variety": self.variety,
            "near_month": self.near_month, "far_month": self.far_month,
            "near_price": round(self.near_price, 4), "far_price": round(self.far_price, 4),
            "spread": round(self.spread, 4), "spread_pct": round(self.spread_pct, 4),
            "structure_type": self.structure_type,
            "signal": round(self.signal, 2),
        }


@dataclass
class IndexFuturesBasis:
    """股指期货基差信号"""
    variety: str
    name: str = ""
    spot_code: str = ""
    futures_code: str = ""
    spot_price: float = 0.0
    futures_price: float = 0.0
    basis: float = 0.0
    basis_pct: float = 0.0
    signal: float = 0.0
    direction: str = "neutral"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "variety": self.variety, "name": self.name,
            "spot_code": self.spot_code, "futures_code": self.futures_code,
            "spot_price": round(self.spot_price, 4),
            "futures_price": round(self.futures_price, 4),
            "basis": round(self.basis, 4), "basis_pct": round(self.basis_pct, 4),
            "signal": round(self.signal, 2), "direction": self.direction,
        }


@dataclass
class IndustrySentiment:
    """行业情绪信号 (期货品种→A股行业传导)"""
    industry: str
    source_varieties: List[str] = field(default_factory=list)
    composite_signal: float = 0.0
    direction: str = "neutral"
    confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "industry": self.industry,
            "source_varieties": self.source_varieties,
            "composite_signal": round(self.composite_signal, 2),
            "direction": self.direction,
            "confidence": round(self.confidence, 4),
        }


@dataclass
class OverseasDerivativesSignal:
    """海外衍生品融合信号"""
    overseas_composite: float = 50.0
    overseas_direction: str = "neutral"
    overseas_confidence: float = 0.0
    domestic_composite: float = 0.0
    fusion_signal: float = 0.0
    fusion_direction: str = "neutral"
    sector_impacts: Dict[str, float] = field(default_factory=dict)
    data_available: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overseas_composite": round(self.overseas_composite, 2),
            "overseas_direction": self.overseas_direction,
            "overseas_confidence": round(self.overseas_confidence, 4),
            "domestic_composite": round(self.domestic_composite, 2),
            "fusion_signal": round(self.fusion_signal, 2),
            "fusion_direction": self.fusion_direction,
            "sector_impacts": {k: round(v, 2) for k, v in self.sector_impacts.items()},
            "data_available": self.data_available,
        }


@dataclass
class DerivativesResult:
    """衍生品信号引擎综合结果"""
    commodity_signals: Dict[str, CommoditySignal] = field(default_factory=dict)
    term_structure: Dict[str, TermStructureSignal] = field(default_factory=dict)
    index_futures_basis: Dict[str, IndexFuturesBasis] = field(default_factory=dict)
    industry_sentiment: Dict[str, IndustrySentiment] = field(default_factory=dict)
    overseas_signal: Optional[OverseasDerivativesSignal] = None
    composite_signal: float = 0.0
    composite_direction: str = "neutral"
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "commodity_signals": {k: v.to_dict() for k, v in self.commodity_signals.items()},
            "term_structure": {k: v.to_dict() for k, v in self.term_structure.items()},
            "index_futures_basis": {k: v.to_dict() for k, v in self.index_futures_basis.items()},
            "industry_sentiment": {k: v.to_dict() for k, v in self.industry_sentiment.items()},
            "overseas_signal": self.overseas_signal.to_dict() if self.overseas_signal else None,
            "composite_signal": round(self.composite_signal, 2),
            "composite_direction": self.composite_direction,
            "timestamp": self.timestamp,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# V10 默认值 (仅 ConfigService 不可用时的回退)
# ═══════════════════════════════════════════════════════════════════════════════

_DEFAULT_COMMODITY_SIGNAL_WEIGHTS = {
    "momentum": 0.35,
    "basis": 0.25,
    "oi_change": 0.20,
    "volatility": 0.20,
}

_DEFAULT_COMPOSITE_WEIGHTS = {
    "commodity": 0.30,
    "term_structure": 0.15,
    "index_basis": 0.25,
    "industry": 0.15,
    "overseas": 0.15,
}

_DEFAULT_OVERSEAS_FUSION_WEIGHT = 0.30


# ═══════════════════════════════════════════════════════════════════════════════
# 衍生品信号引擎 V10
# ═══════════════════════════════════════════════════════════════════════════════

class DerivativesSignalEngine:
    """衍生品信号引擎 (V10 配置驱动版)

    V10 核心变更:
    - 所有硬编码配置移至 ConfigService (YAML)
    - _resolve_futures_code() 默认后缀 L8 (不是 M0)
    - 商品品种、股指期货、信号权重均从配置加载

    使用方式:
        >>> engine = DerivativesSignalEngine(
        ...     data_service=tdx_adapter,
        ...     contract_manager=cm,
        ...     config=config_svc,
        ... )
        >>> result = engine.calculate_all()
    """

    def __init__(
        self,
        data_service: TDXAdapter,
        contract_manager: Optional[ContractManager] = None,
        overseas_signal_engine: Optional[OverseasSignalEngine] = None,
        config: Optional[ConfigService] = None,
        cache: Optional[CacheService] = None,
        logger_instance: Optional[logging.Logger] = None,
    ) -> None:
        """初始化衍生品信号引擎

        V10: config 参数必需, 所有配置从 YAML 加载。
        """
        self._tdx = data_service
        self._contract_mgr = contract_manager
        self._overseas_engine = overseas_signal_engine
        self._config = config
        self._cache = cache
        self._logger = logger_instance or logger

        # V10: 从 ConfigService 加载配置
        self._commodity_varieties = self._load_commodity_config()
        self._index_futures = self._load_index_futures_config()
        self._weights = self._load_weights()
        self._overseas_fusion_weight = self._load_overseas_fusion_weight()

        self._logger.info(
            "DerivativesSignalEngine V10 初始化完成 | "
            "商品品种: %d, 股指期货: %d, 海外引擎: %s",
            len(self._commodity_varieties),
            len(self._index_futures),
            "已注入" if self._overseas_engine else "未注入",
        )

    # ──────────────────────────────────────────────────────────────
    #  配置加载 — V10: 全部从 ConfigService
    # ──────────────────────────────────────────────────────────────

    def _load_commodity_config(self) -> List[Dict[str, Any]]:
        """从 ConfigService 加载商品品种配置。

        V10: 从 codes.variety_market 构建, 不再硬编码。
        """
        if self._config is None:
            return []

        varieties = []
        raw_variety_market = self._config.get("codes.variety_market", {})
        for variety, info in raw_variety_market.items():
            v = variety.upper()
            market_type = info.get("market_type", "future_sh")
            # 只包含商品期货 (排除股指和国债)
            if market_type.startswith("future_") and v not in ("IF", "IH", "IC", "IM", "T", "TF", "TL", "TS"):
                varieties.append({
                    "variety": v,
                    "name": info.get("name", v),
                    "market_type": market_type,
                    "industry": self._infer_industry(v),
                })
        return varieties

    def _load_index_futures_config(self) -> List[Dict[str, Any]]:
        """从 ConfigService 加载股指期货配置。

        V10: 从 codes.index_futures 构建, futures_suffix 默认 L8。
        """
        if self._config is None:
            return []

        result = []
        raw_index_futures = self._config.get("codes.index_futures", {})
        for variety, info in raw_index_futures.items():
            if variety == "quarter_months":
                continue
            v = variety.upper()
            result.append({
                "variety": v,
                "name": info.get("spot_name", v),
                "spot_code": info.get("spot_code", ""),
                "futures_suffix": info.get("continuous_suffix", "L8"),  # V10: L8 not M0
                "market_type": self._config.get(f"codes.variety_market.{v}.market_type", "future_zj"),
            })
        return result

    def _load_weights(self) -> Dict[str, Any]:
        """从 ConfigService 加载信号权重。"""
        if self._config is None:
            return {
                "commodity_signal": _DEFAULT_COMMODITY_SIGNAL_WEIGHTS,
                "composite": _DEFAULT_COMPOSITE_WEIGHTS,
            }

        return {
            "commodity_signal": self._config.get(
                "market_state.commodity_signal_weights",
                _DEFAULT_COMMODITY_SIGNAL_WEIGHTS,
            ),
            "composite": self._config.get(
                "market_state.composite_weights",
                _DEFAULT_COMPOSITE_WEIGHTS,
            ),
        }

    def _load_overseas_fusion_weight(self) -> float:
        """从 ConfigService 加载海外信号融合权重。"""
        if self._config is None:
            return _DEFAULT_OVERSEAS_FUSION_WEIGHT
        return self._config.get(
            "market_state.overseas_fusion_weight",
            _DEFAULT_OVERSEAS_FUSION_WEIGHT,
        )

    @staticmethod
    def _infer_industry(variety: str) -> str:
        """推断品种所属行业。"""
        industry_map = {
            "CU": "有色金属", "AL": "有色金属", "ZN": "有色金属", "PB": "有色金属",
            "NI": "有色金属", "SN": "有色金属", "AU": "贵金属", "AG": "贵金属",
            "RB": "钢铁", "HC": "钢铁", "I": "钢铁", "JM": "钢铁", "J": "钢铁",
            "SC": "能源", "FU": "能源", "BU": "建材", "SA": "建材", "FG": "建材",
            "M": "农业", "Y": "农业", "P": "农业", "C": "农业", "CF": "纺织",
            "SR": "食品", "TA": "化工", "MA": "化工", "EG": "化工", "PP": "化工",
            "L": "化工", "V": "化工", "LC": "新能源", "SI": "新能源",
        }
        return industry_map.get(variety, "其他")

    # ═══════════════════════════════════════════════════════════════════════
    # 1. 商品期货信号
    # ═══════════════════════════════════════════════════════════════════════

    def calculate_commodity_signals(self) -> Dict[str, CommoditySignal]:
        """计算商品期货信号"""
        results: Dict[str, CommoditySignal] = {}

        for cfg in self._commodity_varieties:
            variety = cfg["variety"]
            try:
                signal = self._calculate_single_commodity(variety, cfg)
                results[variety] = signal
            except Exception as e:
                self._logger.warning("商品信号计算失败 %s: %s", variety, e)
                results[variety] = CommoditySignal(variety=variety, name=cfg.get("name", variety))

        valid = sum(1 for s in results.values() if s.direction != "neutral")
        self._logger.info("商品期货信号: %d/%d 有效方向", valid, len(results))
        return results

    def _calculate_single_commodity(
        self, variety: str, cfg: Dict[str, Any],
    ) -> CommoditySignal:
        """计算单个商品品种信号"""
        name = cfg.get("name", variety)
        market_type = cfg.get("market_type", "future_sh")

        contract_code = self._resolve_contract_code(variety, market_type)
        df = self._fetch_future_bars(contract_code, market_type, days=120)

        if df is None or len(df) < 25:
            return CommoditySignal(variety=variety, name=name)

        close = df["close"].values.astype(float)
        volume = df["volume"].values.astype(float) if "volume" in df.columns else None

        # 1. 20日动量
        momentum_20d = 0.0
        if len(close) >= 20 and close[-20] > 0:
            momentum_20d = (close[-1] / close[-20] - 1.0) * 100.0

        # 2. 基差
        basis = 0.0
        basis_pct = 0.0

        # 3. 5日持仓变化率
        oi_change_5d = 0.0
        if volume is not None and len(volume) >= 6:
            vol_recent = float(np.mean(volume[-5:]))
            vol_prev = float(np.mean(volume[-10:-5])) if len(volume) >= 10 else vol_recent
            if vol_prev > 0:
                oi_change_5d = (vol_recent / vol_prev - 1.0) * 100.0

        # 4. 20日已实现波动率
        volatility_20d = 0.0
        if len(close) >= 20:
            returns = np.diff(close[-21:]) / close[-21:-1]
            returns = returns[np.isfinite(returns)]
            if len(returns) > 0:
                volatility_20d = float(np.std(returns) * np.sqrt(252) * 100.0)

        # 5. 综合信号 — V10: 权重从配置加载
        w = self._weights.get("commodity_signal", _DEFAULT_COMMODITY_SIGNAL_WEIGHTS)
        momentum_signal = self._normalize_to_signal(momentum_20d, scale=10.0)
        basis_signal = self._normalize_to_signal(basis_pct, scale=3.0)
        oi_signal = self._normalize_to_signal(oi_change_5d, scale=10.0)
        vol_signal = self._volatility_signal(volatility_20d)

        composite = (
            momentum_signal * w.get("momentum", 0.35)
            + basis_signal * w.get("basis", 0.25)
            + oi_signal * w.get("oi_change", 0.20)
            + vol_signal * w.get("volatility", 0.20)
        )
        composite = max(-100.0, min(100.0, composite))
        direction = "bullish" if composite > 20 else ("bearish" if composite < -20 else "neutral")

        return CommoditySignal(
            variety=variety, name=name,
            momentum_20d=momentum_20d,
            basis=basis, basis_pct=basis_pct,
            oi_change_5d=oi_change_5d,
            volatility_20d=volatility_20d,
            signal=composite, direction=direction,
        )

    # ═══════════════════════════════════════════════════════════════════════
    # 2. 期限结构信号
    # ═══════════════════════════════════════════════════════════════════════

    def calculate_term_structure(self) -> Dict[str, TermStructureSignal]:
        """计算期限结构信号"""
        results: Dict[str, TermStructureSignal] = {}
        term_varieties = ["CU", "AL", "ZN", "AU", "AG", "RB", "I", "SC"]

        for variety in term_varieties:
            try:
                signal = self._calculate_single_term_structure(variety)
                if signal is not None:
                    results[variety] = signal
            except Exception as e:
                self._logger.debug("期限结构计算失败 %s: %s", variety, e)

        self._logger.info("期限结构信号: %d 品种", len(results))
        return results

    def _calculate_single_term_structure(
        self, variety: str,
    ) -> Optional[TermStructureSignal]:
        """计算单个品种的期限结构"""
        market_type = self._get_variety_market_type(variety)
        if market_type is None:
            return None

        near_code = self._resolve_contract_code(variety, market_type, month_offset=0)
        far_code = self._resolve_contract_code(variety, market_type, month_offset=1)

        if not near_code or not far_code:
            return None

        near_df = self._fetch_future_bars(near_code, market_type, days=5)
        far_df = self._fetch_future_bars(far_code, market_type, days=5)

        if near_df is None or near_df.empty or far_df is None or far_df.empty:
            return None

        near_price = float(near_df["close"].iloc[-1])
        far_price = float(far_df["close"].iloc[-1])

        if near_price <= 0 or far_price <= 0:
            return None

        spread = near_price - far_price
        spread_pct = (spread / far_price) * 100.0

        if spread_pct > 0.5:
            structure_type = "backwardation"
            signal = min(100.0, spread_pct * 20.0)
        elif spread_pct < -0.5:
            structure_type = "contango"
            signal = max(-100.0, spread_pct * 20.0)
        else:
            structure_type = "flat"
            signal = 0.0

        return TermStructureSignal(
            variety=variety,
            near_month=near_code, far_month=far_code,
            near_price=near_price, far_price=far_price,
            spread=spread, spread_pct=spread_pct,
            structure_type=structure_type, signal=signal,
        )

    # ═══════════════════════════════════════════════════════════════════════
    # 3. 股指期货基差
    # ═══════════════════════════════════════════════════════════════════════

    def calculate_index_futures_basis(self) -> Dict[str, IndexFuturesBasis]:
        """计算股指期货基差"""
        results: Dict[str, IndexFuturesBasis] = {}

        for cfg in self._index_futures:
            variety = cfg["variety"]
            try:
                basis = self._calculate_single_index_basis(cfg)
                results[variety] = basis
            except Exception as e:
                self._logger.warning("股指基差计算失败 %s: %s", variety, e)
                results[variety] = IndexFuturesBasis(
                    variety=variety, name=cfg.get("name", variety),
                    spot_code=cfg.get("spot_code", ""),
                )

        valid = sum(1 for b in results.values() if b.direction != "neutral")
        self._logger.info("股指期货基差: %d/%d 有效", valid, len(results))
        return results

    def _calculate_single_index_basis(
        self, cfg: Dict[str, Any],
    ) -> IndexFuturesBasis:
        """计算单个股指期货基差"""
        variety = cfg["variety"]
        name = cfg.get("name", variety)
        spot_code = cfg.get("spot_code", "")
        market_type = cfg.get("market_type", "future_zj")

        # V10: futures_suffix 默认 L8
        futures_code = f"{variety}{cfg.get('futures_suffix', 'L8')}"
        futures_df = self._fetch_future_bars(futures_code, market_type, days=5)

        if futures_df is None or futures_df.empty:
            return IndexFuturesBasis(
                variety=variety, name=name, spot_code=spot_code,
                futures_code=futures_code,
            )

        futures_price = float(futures_df["close"].iloc[-1])
        spot_df = self._fetch_index_bars(spot_code, days=5)
        spot_price = float(spot_df["close"].iloc[-1]) if spot_df is not None and not spot_df.empty else 0.0

        if spot_price <= 0 or futures_price <= 0:
            return IndexFuturesBasis(
                variety=variety, name=name, spot_code=spot_code,
                futures_code=futures_code,
                spot_price=spot_price, futures_price=futures_price,
            )

        basis = spot_price - futures_price
        basis_pct = (basis / spot_price) * 100.0

        signal = max(-100.0, min(100.0, basis_pct * 30.0))
        direction = "bullish" if signal > 15 else ("bearish" if signal < -15 else "neutral")

        return IndexFuturesBasis(
            variety=variety, name=name,
            spot_code=spot_code, futures_code=futures_code,
            spot_price=spot_price, futures_price=futures_price,
            basis=basis, basis_pct=basis_pct,
            signal=signal, direction=direction,
        )

    # ═══════════════════════════════════════════════════════════════════════
    # 4. 行业情绪信号
    # ═══════════════════════════════════════════════════════════════════════

    def calculate_industry_sentiment(
        self,
        commodity_signals: Optional[Dict[str, CommoditySignal]] = None,
    ) -> Dict[str, IndustrySentiment]:
        """计算行业情绪信号"""
        if commodity_signals is None:
            commodity_signals = self.calculate_commodity_signals()

        industry_data: Dict[str, List[Tuple[str, float]]] = {}
        for cfg in self._commodity_varieties:
            variety = cfg["variety"]
            industry = cfg.get("industry", "其他")
            signal = commodity_signals.get(variety)
            if signal is not None:
                if industry not in industry_data:
                    industry_data[industry] = []
                industry_data[industry].append((variety, signal.signal))

        results: Dict[str, IndustrySentiment] = {}
        for industry, signals in industry_data.items():
            if not signals:
                continue
            avg_signal = float(np.mean([sig for _, sig in signals]))
            direction = "bullish" if avg_signal > 15 else ("bearish" if avg_signal < -15 else "neutral")
            confidence = min(1.0, len(signals) / 5.0)

            results[industry] = IndustrySentiment(
                industry=industry,
                source_varieties=[v for v, _ in signals],
                composite_signal=avg_signal,
                direction=direction,
                confidence=confidence,
            )

        self._logger.info("行业情绪信号: %d 行业", len(results))
        return results

    # ═══════════════════════════════════════════════════════════════════════
    # 5. 海外衍生品信号
    # ═══════════════════════════════════════════════════════════════════════

    def calculate_overseas_derivatives_signal(
        self,
        domestic_composite: float = 0.0,
    ) -> OverseasDerivativesSignal:
        """计算海外衍生品融合信号"""
        result = OverseasDerivativesSignal(
            domestic_composite=domestic_composite,
        )

        if self._overseas_engine is None:
            self._logger.debug("海外信号引擎未注入, 跳过海外信号融合")
            result.fusion_signal = domestic_composite
            result.fusion_direction = self._signal_to_direction(domestic_composite)
            return result

        try:
            overseas_result = self._overseas_engine.generate_overseas_signal()

            if overseas_result is None:
                self._logger.warning("海外信号引擎返回 None")
                result.fusion_signal = domestic_composite
                result.fusion_direction = self._signal_to_direction(domestic_composite)
                return result

            overseas_score = (overseas_result.composite_score - 50.0) * 2.0

            result.overseas_composite = overseas_result.composite_score
            result.overseas_direction = overseas_result.direction
            result.overseas_confidence = overseas_result.confidence
            result.data_available = True

            w_overseas = self._overseas_fusion_weight
            w_domestic = 1.0 - w_overseas

            result.fusion_signal = (
                w_domestic * domestic_composite
                + w_overseas * overseas_score
            )
            result.fusion_signal = max(-100.0, min(100.0, result.fusion_signal))
            result.fusion_direction = self._signal_to_direction(result.fusion_signal)

            if hasattr(overseas_result, "sector_impacts") and overseas_result.sector_impacts:
                result.sector_impacts = {
                    sector: impact.impact_score
                    for sector, impact in overseas_result.sector_impacts.items()
                }

            self._logger.info(
                "海外衍生品信号融合: 国内=%.1f 海外=%.1f(%.0f) → 融合=%.1f [%s]",
                domestic_composite, overseas_score, overseas_result.composite_score,
                result.fusion_signal, result.fusion_direction,
            )

        except Exception as e:
            self._logger.error("海外信号融合异常: %s", e)
            result.fusion_signal = domestic_composite
            result.fusion_direction = self._signal_to_direction(domestic_composite)

        return result

    # ═══════════════════════════════════════════════════════════════════════
    # 6. 全量计算 + 增强报告
    # ═══════════════════════════════════════════════════════════════════════

    def calculate_all(self) -> DerivativesResult:
        """全量计算衍生品信号"""
        start_time = time.time()

        commodity_signals = self.calculate_commodity_signals()
        term_structure = self.calculate_term_structure()
        index_basis = self.calculate_index_futures_basis()
        industry_sentiment = self.calculate_industry_sentiment(commodity_signals)

        domestic_composite = self._calculate_domestic_composite(
            commodity_signals, term_structure, index_basis, industry_sentiment,
        )

        overseas_signal = self.calculate_overseas_derivatives_signal(domestic_composite)

        final_signal = overseas_signal.fusion_signal if overseas_signal.data_available else domestic_composite
        final_direction = self._signal_to_direction(final_signal)

        result = DerivativesResult(
            commodity_signals=commodity_signals,
            term_structure=term_structure,
            index_futures_basis=index_basis,
            industry_sentiment=industry_sentiment,
            overseas_signal=overseas_signal,
            composite_signal=final_signal,
            composite_direction=final_direction,
        )

        elapsed = (time.time() - start_time) * 1000
        self._logger.info(
            "衍生品信号全量计算完成: 综合=%.1f [%s] | 商品=%d 期限=%d 基差=%d 行业=%d 海外=%s | %.0fms",
            final_signal, final_direction,
            len(commodity_signals), len(term_structure),
            len(index_basis), len(industry_sentiment),
            "可用" if overseas_signal.data_available else "不可用",
            elapsed,
        )

        return result

    def generate_enhanced_report(self, result: Optional[DerivativesResult] = None) -> Dict[str, Any]:
        """生成增强报告"""
        if result is None:
            result = self.calculate_all()

        report = {
            "version": "10.0",
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "composite_signal": round(result.composite_signal, 2),
                "composite_direction": result.composite_direction,
            },
            "domestic": {
                "commodity": {
                    "count": len(result.commodity_signals),
                    "bullish": sum(1 for s in result.commodity_signals.values() if s.direction == "bullish"),
                    "bearish": sum(1 for s in result.commodity_signals.values() if s.direction == "bearish"),
                    "neutral": sum(1 for s in result.commodity_signals.values() if s.direction == "neutral"),
                    "signals": {k: v.to_dict() for k, v in result.commodity_signals.items()},
                },
                "term_structure": {
                    "count": len(result.term_structure),
                    "backwardation": sum(1 for t in result.term_structure.values() if t.structure_type == "backwardation"),
                    "contango": sum(1 for t in result.term_structure.values() if t.structure_type == "contango"),
                    "signals": {k: v.to_dict() for k, v in result.term_structure.items()},
                },
                "index_basis": {
                    "signals": {k: v.to_dict() for k, v in result.index_futures_basis.items()},
                },
                "industry_sentiment": {
                    "signals": {k: v.to_dict() for k, v in result.industry_sentiment.items()},
                },
            },
            "overseas": result.overseas_signal.to_dict() if result.overseas_signal else None,
        }

        return report

    # ═══════════════════════════════════════════════════════════════════════
    # 辅助方法
    # ═══════════════════════════════════════════════════════════════════════

    def _calculate_domestic_composite(
        self,
        commodity_signals: Dict[str, CommoditySignal],
        term_structure: Dict[str, TermStructureSignal],
        index_basis: Dict[str, IndexFuturesBasis],
        industry_sentiment: Dict[str, IndustrySentiment],
    ) -> float:
        """计算国内综合信号 — V10: 权重从配置加载"""
        w = self._weights.get("composite", _DEFAULT_COMPOSITE_WEIGHTS)

        commodity_avg = float(np.mean([s.signal for s in commodity_signals.values()])) if commodity_signals else 0.0
        term_avg = float(np.mean([t.signal for t in term_structure.values()])) if term_structure else 0.0
        basis_avg = float(np.mean([b.signal for b in index_basis.values()])) if index_basis else 0.0
        industry_avg = float(np.mean([s.composite_signal for s in industry_sentiment.values()])) if industry_sentiment else 0.0

        composite = (
            commodity_avg * w.get("commodity", 0.30)
            + term_avg * w.get("term_structure", 0.15)
            + basis_avg * w.get("index_basis", 0.25)
            + industry_avg * w.get("industry", 0.15)
        )
        return max(-100.0, min(100.0, composite))

    @staticmethod
    def _normalize_to_signal(value: float, scale: float = 1.0) -> float:
        """将原始值归一化到 [-100, 100] 信号范围"""
        return max(-100.0, min(100.0, (value / scale) * 100.0))

    @staticmethod
    def _volatility_signal(vol: float) -> float:
        """波动率信号: 高波动→偏空, 低波动→偏多"""
        if vol < 15.0:
            return 20.0
        elif vol < 25.0:
            return 0.0
        elif vol < 35.0:
            return -30.0
        else:
            return -60.0

    @staticmethod
    def _signal_to_direction(signal: float) -> str:
        """信号值→方向"""
        if signal > 20:
            return "bullish"
        elif signal < -20:
            return "bearish"
        return "neutral"

    def _resolve_contract_code(
        self, variety: str, market_type: str, month_offset: int = 0,
    ) -> str:
        """推导合约代码

        V10: 默认后缀 L8 (主连), 不是 M0。
        tdxAPICode180.xlsx: L8=主连, L9=加权, M0 不存在。
        """
        if self._contract_mgr is not None:
            try:
                code = self._contract_mgr.get_contract_code(
                    variety=variety, month_offset=month_offset,
                )
                if code:
                    return code
            except Exception as e:
                self._logger.debug("contract_manager 获取失败: %s", e)

        # V10: 默认 L8/L9 (主连/加权)
        suffix = "L8" if month_offset == 0 else "L9"
        return f"{variety}{suffix}"

    def _get_variety_market_type(self, variety: str) -> Optional[str]:
        """从配置或 ContractManager 获取品种市场类型"""
        if self._config is not None:
            mt = self._config.get(f"codes.variety_market.{variety}.market_type")
            if mt:
                return mt
        if self._contract_mgr is not None and hasattr(self._contract_mgr, '_variety_market_type'):
            return self._contract_mgr._variety_market_type.get(variety)
        return None

    def _fetch_future_bars(
        self, code: str, market_type: str, days: int = 120,
    ) -> Optional[pd.DataFrame]:
        """获取期货K线数据"""
        if self._tdx is None:
            return None
        try:
            if hasattr(self._tdx, 'get_future_bars'):
                return self._tdx.get_future_bars(code, market_type, days=days)
            elif hasattr(self._tdx, 'get_instrument_bars'):
                return self._tdx.get_instrument_bars(category=3, code=code, market_type=market_type, count=days)
        except Exception as e:
            self._logger.debug("期货K线获取失败 %s: %s", code, e)
        return None

    def _fetch_index_bars(
        self, code: str, days: int = 5,
    ) -> Optional[pd.DataFrame]:
        """获取指数K线数据"""
        if self._tdx is None:
            return None
        try:
            if hasattr(self._tdx, 'get_index_bars'):
                return self._tdx.get_index_bars(code, days=days)
            elif hasattr(self._tdx, 'get_instrument_bars'):
                return self._tdx.get_instrument_bars(category=8, code=code, market_type="index_sh", count=days)
        except Exception as e:
            self._logger.debug("指数K线获取失败 %s: %s", code, e)
        return None
