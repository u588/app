#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AiStock V8 — OverseasFuturesSignalEngine
外盘期货四维信号引擎 (4-Dimension Signal System)

Based on: 《外盘期货数据优化与A股市场状态量化报告_final.pdf》
Core Innovation of V8: The 4-Dimension Signal Architecture

Dimensions:
  1. Price Signal    (40%) — 隔夜收益/动量/均线突破/期限结构/季节性调整
  2. Position Signal (25%) — CFTC净持仓/持仓拥挤度/持仓动量
  3. Macro Signal    (20%) — 中美利差/ISM PMI/LME库存/EIA原油库存
  4. Sentiment Signal(15%) — QVIX变化率/BTC波动率/黄金驱动力分解

Signal Fusion:
  - 加权组合: 0.40*price + 0.25*position + 0.20*macro + 0.15*sentiment
  - 交叉验证: 价格与情绪冲突时降低置信度
  - 冲突解决: 2+维度方向不一致时应用折扣因子
  - 输出: OverseasSignal 综合评分 0-100

Sector Transmission:
  - 外盘期货信号 → A股九大战略方向传导映射
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# ─── Type aliases ──────────────────────────────────────────────────────────────

CacheService = Any       # base_services.cache_service.CacheService
ConfigService = Any      # base_services.config_service.ConfigService
AKAdapter = Any          # data_service.ak_adapter.AKAdapter
DataLoaderService = Any  # data_service.data_loader_service.DataLoaderService
Logger = Any             # logging.Logger


# ═══════════════════════════════════════════════════════════════════════════════
# Dataclasses — 信号结果结构
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class PriceSignalResult:
    """价格信号维度结果 (Dimension 1)

    包含: 隔夜收益率, 20日动量, 均线突破, 期限结构, 季节性调整, 综合评分
    """
    symbol: str
    name: str = ""

    # 子信号
    overnight_return: float = 0.0        # 隔夜收益率 (%)
    momentum_20d: float = 0.0           # 20日动量 (%)
    ma_breakthrough: float = 0.0        # 均线突破信号 (-100 ~ +100)
    term_structure_signal: float = 0.0   # 期限结构信号 (-100 ~ +100)
    seasonal_zscore: float = 0.0        # 季节性调整z-score

    # 综合评分
    composite_score: float = 50.0       # 0-100 (50=中性)
    direction: str = "neutral"          # bullish / bearish / neutral
    confidence: float = 0.0             # 0-1

    # 原始数据
    current_price: float = 0.0
    price_20d_ago: float = 0.0
    ma5: float = 0.0
    ma10: float = 0.0
    ma20: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol, "name": self.name,
            "overnight_return": round(self.overnight_return, 4),
            "momentum_20d": round(self.momentum_20d, 4),
            "ma_breakthrough": round(self.ma_breakthrough, 2),
            "term_structure_signal": round(self.term_structure_signal, 2),
            "seasonal_zscore": round(self.seasonal_zscore, 4),
            "composite_score": round(self.composite_score, 2),
            "direction": self.direction,
            "confidence": round(self.confidence, 4),
            "current_price": round(self.current_price, 4),
            "price_20d_ago": round(self.price_20d_ago, 4),
            "ma5": round(self.ma5, 4), "ma10": round(self.ma10, 4), "ma20": round(self.ma20, 4),
        }


@dataclass
class PositionSignalResult:
    """持仓信号维度结果 (Dimension 2)

    基于CFTC持仓数据: 净持仓方向/拥挤度/动量
    """
    symbol: str
    name: str = ""

    # 子信号
    net_position_direction: float = 0.0   # 净持仓方向信号 (-100 ~ +100)
    position_crowding: float = 0.0        # 持仓拥挤度 (百分位 0-100)
    position_crowding_label: str = "neutral"  # neutral / crowded_long / crowded_short
    position_momentum_3w: float = 0.0     # 3周持仓动量 (%)

    # 综合评分
    composite_score: float = 50.0         # 0-100
    direction: str = "neutral"
    confidence: float = 0.0

    # 原始数据
    non_commercial_net: float = 0.0
    non_commercial_long: float = 0.0
    non_commercial_short: float = 0.0
    net_position_percentile: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol, "name": self.name,
            "net_position_direction": round(self.net_position_direction, 2),
            "position_crowding": round(self.position_crowding, 2),
            "position_crowding_label": self.position_crowding_label,
            "position_momentum_3w": round(self.position_momentum_3w, 4),
            "composite_score": round(self.composite_score, 2),
            "direction": self.direction,
            "confidence": round(self.confidence, 4),
            "non_commercial_net": round(self.non_commercial_net, 2),
            "net_position_percentile": round(self.net_position_percentile, 4),
        }


@dataclass
class MacroSignalResult:
    """宏观信号维度结果 (Dimension 3)

    中美利差/ISM PMI/LME库存/EIA原油库存
    """
    # 子信号
    cn_us_bond_spread: float = 0.0          # 中美10Y利差 (%)
    cn_us_spread_direction: float = 0.0      # 利差方向信号 (-100 ~ +100)
    cn_us_spread_rate_of_change: float = 0.0 # 利差变化速率

    ism_pmi: float = 0.0                    # ISM PMI值
    ism_pmi_signal: float = 0.0             # PMI信号 (-100 ~ +100)
    ism_direction_change: bool = False       # PMI方向是否发生变化

    lme_inventory_change_3w: float = 0.0     # LME 3周库存变化率 (%)
    lme_inventory_signal: float = 0.0        # 库存信号 (-100 ~ +100, 下降=看多)

    eia_crude_surprise: float = 0.0          # EIA库存意外值
    eia_crude_signal: float = 0.0            # EIA信号 (-100 ~ +100)

    # 综合评分
    composite_score: float = 50.0
    direction: str = "neutral"
    confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cn_us_bond_spread": round(self.cn_us_bond_spread, 4),
            "cn_us_spread_direction": round(self.cn_us_spread_direction, 2),
            "cn_us_spread_rate_of_change": round(self.cn_us_spread_rate_of_change, 4),
            "ism_pmi": round(self.ism_pmi, 2),
            "ism_pmi_signal": round(self.ism_pmi_signal, 2),
            "ism_direction_change": self.ism_direction_change,
            "lme_inventory_change_3w": round(self.lme_inventory_change_3w, 4),
            "lme_inventory_signal": round(self.lme_inventory_signal, 2),
            "eia_crude_surprise": round(self.eia_crude_surprise, 4),
            "eia_crude_signal": round(self.eia_crude_signal, 2),
            "composite_score": round(self.composite_score, 2),
            "direction": self.direction,
            "confidence": round(self.confidence, 4),
        }


@dataclass
class SentimentSignalResult:
    """情绪信号维度结果 (Dimension 4)

    QVIX变化率/BTC波动率/黄金驱动力分解
    """
    # 子信号
    qvix_50etf_change_rate: float = 0.0      # 50ETF QVIX 5日变化率 (%)
    qvix_300etf_change_rate: float = 0.0     # 300ETF QVIX 5日变化率 (%)
    qvix_signal: float = 0.0                 # QVIX综合信号 (-100 ~ +100)

    btc_realized_vol_20d: float = 0.0        # BTC 20日已实现波动率 (%)
    btc_vol_signal: float = 0.0              # BTC波动率信号 (-100 ~ +100)

    gc_xau_spread: float = 0.0               # GC-XAU价差
    gold_driver: str = "mixed"               # real_rate / safe_haven / mixed
    gold_driver_signal: float = 0.0          # 黄金驱动力信号 (-100 ~ +100)

    # 综合评分
    composite_score: float = 50.0
    direction: str = "neutral"
    confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "qvix_50etf_change_rate": round(self.qvix_50etf_change_rate, 4),
            "qvix_300etf_change_rate": round(self.qvix_300etf_change_rate, 4),
            "qvix_signal": round(self.qvix_signal, 2),
            "btc_realized_vol_20d": round(self.btc_realized_vol_20d, 4),
            "btc_vol_signal": round(self.btc_vol_signal, 2),
            "gc_xau_spread": round(self.gc_xau_spread, 4),
            "gold_driver": self.gold_driver,
            "gold_driver_signal": round(self.gold_driver_signal, 2),
            "composite_score": round(self.composite_score, 2),
            "direction": self.direction,
            "confidence": round(self.confidence, 4),
        }


@dataclass
class SpreadResult:
    """跨市场价格差结果"""
    name: str
    leg1_symbol: str = ""
    leg2_symbol: str = ""
    leg1_price: float = 0.0
    leg2_price: float = 0.0
    spread_value: float = 0.0
    spread_pct: float = 0.0
    spread_zscore: float = 0.0
    direction: str = "neutral"
    signal: float = 0.0  # -100 ~ +100

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "leg1_symbol": self.leg1_symbol, "leg2_symbol": self.leg2_symbol,
            "leg1_price": round(self.leg1_price, 4), "leg2_price": round(self.leg2_price, 4),
            "spread_value": round(self.spread_value, 4),
            "spread_pct": round(self.spread_pct, 4),
            "spread_zscore": round(self.spread_zscore, 4),
            "direction": self.direction, "signal": round(self.signal, 2),
        }


@dataclass
class SectorImpact:
    """A股行业影响结果"""
    sector: str
    impact_score: float = 0.0      # -100 ~ +100
    impact_direction: str = "neutral"  # bullish / bearish / neutral
    transmission_type: str = ""    # cost_push / price_sync / risk_sentiment
    source_symbols: List[str] = field(default_factory=list)
    confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sector": self.sector,
            "impact_score": round(self.impact_score, 2),
            "impact_direction": self.impact_direction,
            "transmission_type": self.transmission_type,
            "source_symbols": self.source_symbols,
            "confidence": round(self.confidence, 4),
        }


@dataclass
class OverseasCompositeSignal:
    """外盘期货综合信号结果

    融合四维度信号, 输出0-100综合评分
    """
    # 各维度评分
    price_score: float = 50.0
    position_score: float = 50.0
    macro_score: float = 50.0
    sentiment_score: float = 50.0

    # 综合评分
    composite_score: float = 50.0    # 0-100 (50=中性, >50看多, <50看空)
    direction: str = "neutral"       # bullish / bearish / neutral
    confidence: float = 0.0          # 0-1

    # 冲突检测
    conflict_count: int = 0          # 方向冲突的维度数
    conflict_discount: float = 1.0   # 冲突折扣因子

    # 跨市场价差
    cross_market_spreads: Dict[str, SpreadResult] = field(default_factory=dict)

    # 隔夜收益汇总
    overnight_returns: Dict[str, float] = field(default_factory=dict)

    # 行业影响
    sector_impacts: Dict[str, SectorImpact] = field(default_factory=dict)

    # 详细结果
    price_signals: Dict[str, PriceSignalResult] = field(default_factory=dict)
    position_signals: Dict[str, PositionSignalResult] = field(default_factory=dict)
    macro_signal: Optional[MacroSignalResult] = None
    sentiment_signal: Optional[SentimentSignalResult] = None

    # 元数据
    timestamp: str = ""
    data_quality: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "price_score": round(self.price_score, 2),
            "position_score": round(self.position_score, 2),
            "macro_score": round(self.macro_score, 2),
            "sentiment_score": round(self.sentiment_score, 2),
            "composite_score": round(self.composite_score, 2),
            "direction": self.direction,
            "confidence": round(self.confidence, 4),
            "conflict_count": self.conflict_count,
            "conflict_discount": round(self.conflict_discount, 4),
            "cross_market_spreads": {k: v.to_dict() for k, v in self.cross_market_spreads.items()},
            "overnight_returns": {k: round(v, 4) for k, v in self.overnight_returns.items()},
            "sector_impacts": {k: v.to_dict() for k, v in self.sector_impacts.items()},
            "price_signals": {k: v.to_dict() for k, v in self.price_signals.items()},
            "position_signals": {k: v.to_dict() for k, v in self.position_signals.items()},
            "macro_signal": self.macro_signal.to_dict() if self.macro_signal else None,
            "sentiment_signal": self.sentiment_signal.to_dict() if self.sentiment_signal else None,
            "timestamp": self.timestamp,
            "data_quality": self.data_quality,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# 常量与配置
# ═══════════════════════════════════════════════════════════════════════════════

# 默认权重
DEFAULT_DIMENSION_WEIGHTS = {
    "price": 0.40,
    "position": 0.25,
    "macro": 0.20,
    "sentiment": 0.15,
}

# 价格子信号权重
PRICE_SUB_WEIGHTS = {
    "overnight_return": 0.20,
    "momentum_20d": 0.30,
    "ma_breakthrough": 0.20,
    "term_structure": 0.15,
    "seasonal_adjustment": 0.15,
}

# 持仓子信号权重
POSITION_SUB_WEIGHTS = {
    "net_direction": 0.40,
    "crowding": 0.30,
    "position_momentum": 0.30,
}

# 宏观子信号权重
MACRO_SUB_WEIGHTS = {
    "cn_us_spread": 0.25,
    "ism_pmi": 0.25,
    "lme_inventory": 0.25,
    "eia_crude": 0.25,
}

# 情绪子信号权重
SENTIMENT_SUB_WEIGHTS = {
    "qvix": 0.30,
    "btc_vol": 0.25,
    "gold_driver": 0.25,
    "sentiment_momentum": 0.20,
}

# 层级权重
TIER_WEIGHTS = {
    "core": 0.50,
    "extended": 0.30,
    "auxiliary": 0.20,
}

# CFTC持仓拥挤度阈值
CROWDING_EXTREME_LONG = 90.0   # 百分位 90%+ = 拥挤多头
CROWDING_EXTREME_SHORT = 10.0  # 百分位 10%- = 拥挤空头
CROWDING_NEUTRAL_HIGH = 60.0
CROWDING_NEUTRAL_LOW = 40.0

# A股行业→外盘品种传导映射
SECTOR_TRANSMISSION_MAP: Dict[str, List[Dict[str, Any]]] = {
    "石油石化": [
        {"symbol": "CL", "type": "cost_push", "strength": 0.80, "lag": 1},
        {"symbol": "OIL", "type": "cost_push", "strength": 0.75, "lag": 1},
    ],
    "化工": [
        {"symbol": "CL", "type": "cost_push", "strength": 0.70, "lag": 1},
        {"symbol": "NG", "type": "cost_push", "strength": 0.60, "lag": 1},
    ],
    "交运": [
        {"symbol": "CL", "type": "cost_push", "strength": 0.65, "lag": 1},
    ],
    "贵金属": [
        {"symbol": "GC", "type": "price_sync", "strength": 0.90, "lag": 0},
        {"symbol": "XAU", "type": "price_sync", "strength": 0.88, "lag": 0},
    ],
    "有色金属": [
        {"symbol": "HG", "type": "price_sync", "strength": 0.85, "lag": 0},
        {"symbol": "LHC", "type": "price_sync", "strength": 0.70, "lag": 0},
    ],
    "光伏": [
        {"symbol": "SI", "type": "cost_push", "strength": 0.65, "lag": 1},
    ],
    "电子": [
        {"symbol": "SI", "type": "cost_push", "strength": 0.55, "lag": 1},
        {"symbol": "HG", "type": "cost_push", "strength": 0.50, "lag": 1},
    ],
    "农业种植": [
        {"symbol": "S", "type": "cost_push", "strength": 0.70, "lag": 1},
        {"symbol": "C", "type": "cost_push", "strength": 0.65, "lag": 1},
    ],
    "纺织": [
        {"symbol": "CT", "type": "cost_push", "strength": 0.75, "lag": 1},
    ],
    "燃气": [
        {"symbol": "NG", "type": "cost_push", "strength": 0.80, "lag": 0},
    ],
    "钢铁": [
        {"symbol": "FEF", "type": "cost_push", "strength": 0.70, "lag": 1},
    ],
    "数字货币": [
        {"symbol": "BTC", "type": "risk_sentiment", "strength": 0.50, "lag": 0},
    ],
    "食用油": [
        {"symbol": "BO", "type": "cost_push", "strength": 0.65, "lag": 1},
        {"symbol": "FCPO", "type": "cost_push", "strength": 0.55, "lag": 1},
    ],
    "碳中和": [
        {"symbol": "EUA", "type": "cost_push", "strength": 0.60, "lag": 1},
    ],
    "外资重仓": [
        {"symbol": "DX", "type": "risk_sentiment", "strength": 0.60, "lag": 0},
    ],
}

# 跨市场价格差对定义
CROSS_MARKET_SPREADS = [
    {"name": "WTI-Brent", "leg1": "CL", "leg2": "OIL", "type": "energy"},
    {"name": "LME_CU-COMEX_HG", "leg1": "LHC", "leg2": "HG", "type": "metal"},
    {"name": "Gold-Silver", "leg1": "GC", "leg2": "SI", "type": "precious"},
    {"name": "GC-XAU", "leg1": "GC", "leg2": "XAU", "type": "gold_basis"},
]


# ═══════════════════════════════════════════════════════════════════════════════
# OverseasFuturesSignalEngine
# ═══════════════════════════════════════════════════════════════════════════════

class OverseasFuturesSignalEngine:
    """外盘期货四维信号引擎

    AiStock V8 核心创新 — 4维度信号架构:
      D1: 价格信号 (40%) — 隔夜收益/动量/均线/期限结构/季节性
      D2: 持仓信号 (25%) — CFTC净持仓/拥挤度/持仓动量
      D3: 宏观信号 (20%) — 中美利差/PMI/库存/EIA
      D4: 情绪信号 (15%) — QVIX/BTC波动率/黄金驱动力

    使用方式:
        >>> engine = OverseasFuturesSignalEngine(ak_adapter, data_loader, config, cache, logger)
        >>> signal = engine.generate_overseas_signal()
        >>> print(signal.composite_score, signal.direction)
    """

    def __init__(
        self,
        ak_adapter: AKAdapter,
        data_loader: DataLoaderService,
        config: Optional[ConfigService] = None,
        cache: Optional[CacheService] = None,
        logger: Optional[Logger] = None,
    ):
        """
        Args:
            ak_adapter: AKShare 数据适配器 (29品种 + 辅助数据)
            data_loader: 数据加载编排服务
            config: 配置服务 (读取 system_config.yaml)
            cache: 缓存服务 (中间结果缓存)
            logger: 日志记录器
        """
        self._ak = ak_adapter
        self._data_loader = data_loader
        self._config = config
        self._cache = cache
        self._logger = logger or self._create_default_logger()

        # 从配置中读取参数
        self._dimension_weights = self._load_dimension_weights()
        self._price_sub_weights = PRICE_SUB_WEIGHTS
        self._position_sub_weights = POSITION_SUB_WEIGHTS
        self._macro_sub_weights = MACRO_SUB_WEIGHTS
        self._sentiment_sub_weights = SENTIMENT_SUB_WEIGHTS
        self._tier_weights = TIER_WEIGHTS

        # 内部缓存 (历史数据, CFTC等, 避免重复请求)
        self._hist_cache: Dict[str, pd.DataFrame] = {}
        self._aux_cache: Dict[str, pd.DataFrame] = {}

        self._logger.info(
            "OverseasFuturesSignalEngine V8.0 初始化完成 | "
            "权重: price=%.0f%% position=%.0f%% macro=%.0f%% sentiment=%.0f%%",
            self._dimension_weights["price"] * 100,
            self._dimension_weights["position"] * 100,
            self._dimension_weights["macro"] * 100,
            self._dimension_weights["sentiment"] * 100,
        )

    # ═══════════════════════════════════════════════════════════════════════
    # Dimension 1: Price Signal (40%)
    # ═══════════════════════════════════════════════════════════════════════

    def calculate_price_signals(
        self, tier: str = "core",
    ) -> Dict[str, PriceSignalResult]:
        """
        计算价格信号维度

        子信号:
          - 隔夜收益率: A股收盘(15:00)→次日开盘(9:00)价格变化
          - 20日动量: (current / price_20d_ago - 1) * 100
          - 均线突破: price vs MA5/MA10/MA20 交叉信号
          - 期限结构: WTI-Brent价差, LME CU-COMEX HG价差, 金银比, 铁矿石-螺纹钢比
          - 季节性调整: 当前价格 vs 同月历史均价 z-score

        Args:
            tier: "core" / "extended" / "auxiliary"

        Returns:
            {symbol: PriceSignalResult}
        """
        results: Dict[str, PriceSignalResult] = {}

        # 确定品种范围
        from data_service.ak_adapter import (
            CORE_SYMBOLS, EXTENDED_SYMBOLS, AUXILIARY_SYMBOLS, FUTURES_SYMBOL_MAP,
        )
        tier_map = {
            "core": CORE_SYMBOLS,
            "extended": EXTENDED_SYMBOLS,
            "auxiliary": AUXILIARY_SYMBOLS,
        }
        symbols = tier_map.get(tier, CORE_SYMBOLS)

        for symbol in symbols:
            try:
                result = self._calculate_single_price_signal(symbol)
                if result is not None:
                    results[symbol] = result
            except Exception as e:
                self._logger.warning("价格信号计算失败 %s: %s", symbol, e)

        self._logger.info(
            "D1 价格信号计算完成: %d/%d 品种 (tier=%s)",
            len(results), len(symbols), tier,
        )
        return results

    def _calculate_single_price_signal(
        self, symbol: str,
    ) -> Optional[PriceSignalResult]:
        """计算单个品种的价格信号"""
        hist = self._get_hist_data(symbol, days=120)
        if hist is None or len(hist) < 25:
            self._logger.debug("价格信号: %s 数据不足 (需要>=25行)", symbol)
            return None

        info = self._ak.get_symbol_info(symbol)
        name = info.name if info else symbol

        close = hist["close"].values
        current_price = float(close[-1])
        price_20d_ago = float(close[-20]) if len(close) >= 20 else float(close[0])

        # 1. 隔夜收益率
        overnight_ret = self._calculate_overnight_return_single(hist)

        # 2. 20日动量
        momentum_20d = (current_price / price_20d_ago - 1.0) * 100.0 if price_20d_ago > 0 else 0.0

        # 3. 均线突破信号
        ma_breakthrough = self._calculate_ma_breakthrough(hist)

        # 4. 期限结构信号 (仅对相关品种)
        term_signal = self._calculate_term_structure_for_symbol(symbol, hist)

        # 5. 季节性调整 z-score
        seasonal_z = self._calculate_seasonal_zscore(symbol, hist)

        # 综合评分
        sub_scores = {
            "overnight_return": self._normalize_to_score(overnight_ret, scale=3.0),
            "momentum_20d": self._normalize_to_score(momentum_20d, scale=10.0),
            "ma_breakthrough": ma_breakthrough,
            "term_structure": term_signal,
            "seasonal_adjustment": self._normalize_to_score(seasonal_z, scale=2.0),
        }

        composite = sum(
            sub_scores[k] * self._price_sub_weights.get(k, 0.0)
            for k in sub_scores
        )
        # Clamp to [0, 100]
        composite = max(0.0, min(100.0, composite))

        # 方向判断
        direction = "bullish" if composite > 60 else ("bearish" if composite < 40 else "neutral")
        confidence = abs(composite - 50.0) / 50.0

        # 均线值
        ma5 = float(close[-5:].mean()) if len(close) >= 5 else current_price
        ma10 = float(close[-10:].mean()) if len(close) >= 10 else current_price
        ma20 = float(close[-20:].mean()) if len(close) >= 20 else current_price

        return PriceSignalResult(
            symbol=symbol, name=name,
            overnight_return=overnight_ret,
            momentum_20d=momentum_20d,
            ma_breakthrough=ma_breakthrough,
            term_structure_signal=term_signal,
            seasonal_zscore=seasonal_z,
            composite_score=composite,
            direction=direction,
            confidence=confidence,
            current_price=current_price,
            price_20d_ago=price_20d_ago,
            ma5=ma5, ma10=ma10, ma20=ma20,
        )

    def _calculate_overnight_return_single(
        self, hist: pd.DataFrame,
    ) -> float:
        """
        计算隔夜收益率

        A股收盘 (15:00 北京时间) 到次日开盘 (9:00) 的海外期货价格变化。
        由于akshare日频数据无法精确到小时, 使用 close[t-1] → open[t] 近似。
        """
        if len(hist) < 2:
            return 0.0

        prev_close = float(hist["close"].iloc[-2])
        curr_open = float(hist["open"].iloc[-1])

        if prev_close <= 0:
            return 0.0

        return (curr_open / prev_close - 1.0) * 100.0

    def _calculate_ma_breakthrough(self, hist: pd.DataFrame) -> float:
        """
        计算均线突破信号

        综合考量 price vs MA5/MA10/MA20 的位置关系和交叉信号:
          - 价格站上所有均线 → +100
          - 价格跌破所有均线 → -100
          - 金叉 (MA5上穿MA20) → 加分
          - 死叉 (MA5下穿MA20) → 减分
        """
        close = hist["close"].values
        n = len(close)
        if n < 20:
            return 0.0

        current = float(close[-1])
        ma5 = float(close[-5:].mean())
        ma10 = float(close[-10:].mean())
        ma20 = float(close[-20:].mean())

        # 位置信号: 价格相对均线
        above_count = sum(1 for ma in [ma5, ma10, ma20] if current > ma)
        position_score = (above_count / 3.0) * 100.0  # 0, 33.3, 66.7, 100

        # 交叉信号: MA5 vs MA20 金叉/死叉
        cross_score = 0.0
        if n >= 25:
            prev_ma5 = float(close[-6:-1].mean())
            prev_ma20 = float(close[-21:-1].mean())
            curr_ma5 = ma5
            curr_ma20 = ma20

            if prev_ma5 <= prev_ma20 and curr_ma5 > curr_ma20:
                # 金叉
                cross_score = 30.0
            elif prev_ma5 >= prev_ma20 and curr_ma5 < curr_ma20:
                # 死叉
                cross_score = -30.0

        # 距离信号: 价格距MA20的偏离度
        if ma20 > 0:
            deviation = (current - ma20) / ma20 * 100.0
            deviation_score = max(-20.0, min(20.0, deviation * 4.0))
        else:
            deviation_score = 0.0

        total = position_score * 0.4 + (50.0 + cross_score) * 0.3 + (50.0 + deviation_score) * 0.3
        return max(-100.0, min(100.0, total - 50.0))  # 归一化到 [-100, 100] → 再映射

    def _calculate_term_structure_for_symbol(
        self, symbol: str, hist: pd.DataFrame,
    ) -> float:
        """
        计算品种相关的期限结构信号

        使用近期价格动量作为期限结构的代理:
          - 近期涨速 > 远期涨速 → backwardation倾向 (供应紧张)
          - 近期涨速 < 远期涨速 → contango倾向 (供应宽松)
        """
        close = hist["close"].values
        n = len(close)
        if n < 40:
            return 0.0

        # 5日收益率 vs 20日收益率
        ret_5d = (float(close[-1]) / float(close[-5]) - 1.0) if close[-5] > 0 else 0.0
        ret_20d = (float(close[-1]) / float(close[-20]) - 1.0) if close[-20] > 0 else 0.0

        # 近期 vs 远期动量差异
        diff = (ret_5d / 5.0 - ret_20d / 20.0) * 100.0  # 日均差异

        # 映射到 [-100, 100]
        return max(-100.0, min(100.0, diff * 50.0))

    def _calculate_seasonal_zscore(
        self, symbol: str, hist: pd.DataFrame,
    ) -> float:
        """
        计算季节性调整 z-score

        当前价格 vs 同月历史均价的标准化偏差
        使用5年同月数据计算
        """
        if "date" not in hist.columns or len(hist) < 30:
            return 0.0

        try:
            # 确保日期列是datetime类型
            dates = pd.to_datetime(hist["date"])
            current_month = dates.iloc[-1].month

            # 筛选同月数据
            same_month_mask = dates.dt.month == current_month
            same_month_prices = hist.loc[same_month_mask, "close"].values.astype(float)

            if len(same_month_prices) < 5:
                return 0.0

            current_price = float(hist["close"].iloc[-1])
            mean_price = np.mean(same_month_prices)
            std_price = np.std(same_month_prices)

            if std_price < 1e-8:
                return 0.0

            return (current_price - mean_price) / std_price

        except Exception as e:
            self._logger.debug("季节性z-score计算失败 %s: %s", symbol, e)
            return 0.0

    # ═══════════════════════════════════════════════════════════════════════
    # Dimension 2: Position Signal (25%)
    # ═══════════════════════════════════════════════════════════════════════

    def calculate_position_signals(
        self,
    ) -> Dict[str, PositionSignalResult]:
        """
        计算持仓信号维度 (基于CFTC数据)

        子信号:
          - 净持仓方向信号: 非商业净持仓符号变化
          - 持仓拥挤度: 净持仓历史百分位 (90%+拥挤多头, 10%-拥挤空头)
          - 持仓动量: 3周净持仓变化方向

        Returns:
            {symbol: PositionSignalResult}
        """
        results: Dict[str, PositionSignalResult] = {}

        cftc_df = self._get_auxiliary_data("cftc")
        if cftc_df is None or cftc_df.empty:
            self._logger.warning("D2 持仓信号: CFTC数据不可用, 返回空结果")
            return results

        # 获取CFTC覆盖的核心品种
        cftc_symbols = self._extract_cftc_symbols(cftc_df)

        for symbol in cftc_symbols:
            try:
                result = self._calculate_single_position_signal(symbol, cftc_df)
                if result is not None:
                    results[symbol] = result
            except Exception as e:
                self._logger.warning("持仓信号计算失败 %s: %s", symbol, e)

        self._logger.info("D2 持仓信号计算完成: %d 品种", len(results))
        return results

    def _extract_cftc_symbols(self, cftc_df: pd.DataFrame) -> List[str]:
        """从CFTC数据中提取可用品种列表"""
        from data_service.ak_adapter import FUTURES_SYMBOL_MAP

        symbols = []
        # 尝试从数据中识别品种
        if "品种" in cftc_df.columns:
            unique_names = cftc_df["品种"].unique()
            for name in unique_names:
                for sym, info in FUTURES_SYMBOL_MAP.items():
                    if info.name in str(name) or info.ak_code in str(name):
                        symbols.append(sym)
                        break
        elif "symbol" in cftc_df.columns:
            symbols = [s for s in cftc_df["symbol"].unique() if s in FUTURES_SYMBOL_MAP]
        else:
            # 回退: 使用核心品种
            symbols = ["CL", "GC", "SI", "HG", "S", "CT"]

        return list(set(symbols))

    def _calculate_single_position_signal(
        self, symbol: str, cftc_df: pd.DataFrame,
    ) -> Optional[PositionSignalResult]:
        """计算单个品种的持仓信号"""
        info = self._ak.get_symbol_info(symbol)
        name = info.name if info else symbol

        # 尝试从CFTC数据中提取该品种的持仓数据
        symbol_data = self._filter_cftc_for_symbol(symbol, cftc_df)
        if symbol_data is None or len(symbol_data) < 4:
            return None

        # 计算非商业净持仓
        nc_long, nc_short = self._extract_non_commercial(symbol_data)
        if nc_long is None or nc_short is None:
            return None

        net_position = nc_long - nc_short

        # 1. 净持仓方向信号
        net_direction = self._calculate_net_position_direction(symbol_data)

        # 2. 持仓拥挤度 (历史百分位)
        crowding, crowding_label = self._calculate_position_crowding(symbol_data)

        # 3. 持仓动量 (3周变化)
        position_momentum = self._calculate_position_momentum(symbol_data)

        # 综合评分
        sub_scores = {
            "net_direction": net_direction,
            "crowding": self._invert_crowding_score(crowding, crowding_label),
            "position_momentum": self._normalize_to_score(position_momentum, scale=10.0),
        }

        composite = sum(
            sub_scores[k] * self._position_sub_weights.get(k, 0.0)
            for k in sub_scores
        )
        composite = max(0.0, min(100.0, composite))

        direction = "bullish" if composite > 60 else ("bearish" if composite < 40 else "neutral")
        confidence = abs(composite - 50.0) / 50.0

        return PositionSignalResult(
            symbol=symbol, name=name,
            net_position_direction=net_direction,
            position_crowding=crowding,
            position_crowding_label=crowding_label,
            position_momentum_3w=position_momentum,
            composite_score=composite,
            direction=direction,
            confidence=confidence,
            non_commercial_net=net_position,
            non_commercial_long=nc_long,
            non_commercial_short=nc_short,
            net_position_percentile=crowding,
        )

    def _filter_cftc_for_symbol(
        self, symbol: str, cftc_df: pd.DataFrame,
    ) -> Optional[pd.DataFrame]:
        """从CFTC数据中筛选指定品种"""
        info = self._ak.get_symbol_info(symbol)
        if info is None:
            return None

        # 尝试多种列名匹配
        for col in ["品种", "commodity", "symbol", "name"]:
            if col in cftc_df.columns:
                mask = cftc_df[col].astype(str).str.contains(
                    info.name, na=False, regex=False,
                ) | cftc_df[col].astype(str).str.contains(
                    info.ak_code, na=False, regex=False,
                )
                filtered = cftc_df[mask]
                if not filtered.empty:
                    return filtered.sort_values(
                        by=cftc_df.columns[0] if "date" not in cftc_df.columns else "date",
                    ).tail(30)
        return None

    def _extract_non_commercial(
        self, data: pd.DataFrame,
    ) -> Tuple[Optional[float], Optional[float]]:
        """提取非商业持仓 (多头/空头)"""
        # 尝试多种列名
        long_cols = ["非商业多头", "non_commercial_long", "非商业买权", "投机多头"]
        short_cols = ["非商业空头", "non_commercial_short", "非商业卖权", "投机空头"]

        nc_long = self._find_numeric_value(data, long_cols)
        nc_short = self._find_numeric_value(data, short_cols)

        return nc_long, nc_short

    def _find_numeric_value(
        self, df: pd.DataFrame, col_candidates: List[str],
    ) -> Optional[float]:
        """在DataFrame中查找候选列并返回最后一行的数值"""
        for col in col_candidates:
            if col in df.columns:
                try:
                    val = pd.to_numeric(df[col].iloc[-1], errors="coerce")
                    if not pd.isna(val):
                        return float(val)
                except (IndexError, ValueError):
                    continue
        return None

    def _calculate_net_position_direction(
        self, data: pd.DataFrame,
    ) -> float:
        """
        净持仓方向信号

        逻辑:
          - 净持仓为正 → 看多信号
          - 净持仓符号变化 (空→多) → 强看多
          - 净持仓符号变化 (多→空) → 强看空
        """
        nc_long, nc_short = self._extract_non_commercial(data)
        if nc_long is None or nc_short is None:
            return 0.0

        net = nc_long - nc_short
        total = nc_long + nc_short

        if total == 0:
            return 0.0

        # 净持仓比例
        net_ratio = net / total

        # 检查是否有符号变化
        if len(data) >= 2:
            prev_long, prev_short = None, None
            long_cols = ["非商业多头", "non_commercial_long", "投机多头"]
            short_cols = ["非商业空头", "non_commercial_short", "投机空头"]

            for col in long_cols:
                if col in data.columns:
                    try:
                        prev_long = float(pd.to_numeric(data[col].iloc[-2], errors="coerce"))
                    except (IndexError, ValueError):
                        pass
                    break

            for col in short_cols:
                if col in data.columns:
                    try:
                        prev_short = float(pd.to_numeric(data[col].iloc[-2], errors="coerce"))
                    except (IndexError, ValueError):
                        pass
                    break

            if prev_long is not None and prev_short is not None:
                prev_net = prev_long - prev_short
                # 符号变化检测
                if prev_net < 0 and net > 0:
                    # 空→多: 强看多
                    return min(100.0, 50.0 + net_ratio * 100.0 + 20.0)
                elif prev_net > 0 and net < 0:
                    # 多→空: 强看空
                    return max(-100.0, 50.0 + net_ratio * 100.0 - 20.0)

        # 无符号变化, 按比例映射
        return 50.0 + net_ratio * 50.0

    def _calculate_position_crowding(
        self, data: pd.DataFrame,
    ) -> Tuple[float, str]:
        """
        持仓拥挤度 (历史百分位)

        90%+ = 拥挤多头 (反转风险)
        10%- = 拥挤空头 (反转机会)
        """
        nc_long, nc_short = self._extract_non_commercial(data)
        if nc_long is None or nc_short is None:
            return 50.0, "neutral"

        net = nc_long - nc_short

        # 计算历史净持仓序列
        net_series = []
        long_cols = ["非商业多头", "non_commercial_long", "投机多头"]
        short_cols = ["非商业空头", "non_commercial_short", "投机空头"]

        long_col = next((c for c in long_cols if c in data.columns), None)
        short_col = next((c for c in short_cols if c in data.columns), None)

        if long_col and short_col:
            for i in range(len(data)):
                try:
                    l = float(pd.to_numeric(data[long_col].iloc[i], errors="coerce"))
                    s = float(pd.to_numeric(data[short_col].iloc[i], errors="coerce"))
                    if not pd.isna(l) and not pd.isna(s):
                        net_series.append(l - s)
                except (IndexError, ValueError):
                    continue

        if len(net_series) < 5:
            return 50.0, "neutral"

        # 计算百分位
        percentile = self._percentile_rank(net_series, net)

        # 拥挤度标签
        if percentile >= CROWDING_EXTREME_LONG:
            label = "crowded_long"
        elif percentile <= CROWDING_EXTREME_SHORT:
            label = "crowded_short"
        elif percentile >= CROWDING_NEUTRAL_HIGH:
            label = "leaning_long"
        elif percentile <= CROWDING_NEUTRAL_LOW:
            label = "leaning_short"
        else:
            label = "neutral"

        return percentile, label

    def _calculate_position_momentum(
        self, data: pd.DataFrame,
    ) -> float:
        """
        持仓动量 (3周净持仓变化方向)

        正值 = 多头增仓
        负值 = 空头增仓
        """
        long_cols = ["非商业多头", "non_commercial_long", "投机多头"]
        short_cols = ["非商业空头", "non_commercial_short", "投机空头"]

        long_col = next((c for c in long_cols if c in data.columns), None)
        short_col = next((c for c in short_cols if c in data.columns), None)

        if not long_col or not short_col or len(data) < 4:
            return 0.0

        try:
            current_long = float(pd.to_numeric(data[long_col].iloc[-1], errors="coerce"))
            current_short = float(pd.to_numeric(data[short_col].iloc[-1], errors="coerce"))
            past_long = float(pd.to_numeric(data[long_col].iloc[-4], errors="coerce"))
            past_short = float(pd.to_numeric(data[short_col].iloc[-4], errors="coerce"))

            if any(pd.isna(v) for v in [current_long, current_short, past_long, past_short]):
                return 0.0

            current_net = current_long - current_short
            past_net = past_long - past_short

            if abs(past_net) < 1e-8:
                return 0.0

            return (current_net - past_net) / abs(past_net) * 100.0

        except (IndexError, ValueError):
            return 0.0

    def _invert_crowding_score(
        self, crowding: float, label: str,
    ) -> float:
        """
        将拥挤度转换为反向信号

        拥挤多头 → 反转风险 → 看空
        拥挤空头 → 反转机会 → 看多
        """
        if label == "crowded_long":
            # 90%+百分位 → 强看空信号
            return max(0.0, 50.0 - (crowding - 80.0) * 3.0)
        elif label == "crowded_short":
            # 10%-百分位 → 强看多信号
            return min(100.0, 50.0 + (20.0 - crowding) * 3.0)
        elif label == "leaning_long":
            return 45.0
        elif label == "leaning_short":
            return 55.0
        else:
            return 50.0

    # ═══════════════════════════════════════════════════════════════════════
    # Dimension 3: Macro Signal (20%)
    # ═══════════════════════════════════════════════════════════════════════

    def calculate_macro_signals(self) -> MacroSignalResult:
        """
        计算宏观信号维度

        子信号:
          - 中美10Y利差: 方向和变化速率
          - ISM PMI: 50以上/以下, 方向变化
          - LME库存: 3周变化率 (下降=看多, 上升=看空)
          - EIA原油库存: 意外值

        Returns:
            MacroSignalResult
        """
        result = MacroSignalResult()

        # 1. 中美利差
        self._calculate_cn_us_bond_spread(result)

        # 2. ISM PMI
        self._calculate_ism_pmi(result)

        # 3. LME库存
        self._calculate_lme_inventory(result)

        # 4. EIA原油库存
        self._calculate_eia_crude(result)

        # 综合评分
        sub_scores = {
            "cn_us_spread": result.cn_us_spread_direction,
            "ism_pmi": result.ism_pmi_signal,
            "lme_inventory": result.lme_inventory_signal,
            "eia_crude": result.eia_crude_signal,
        }

        composite = sum(
            sub_scores[k] * self._macro_sub_weights.get(k, 0.0)
            for k in sub_scores
        )
        # 从 [-100, 100] 映射到 [0, 100]
        result.composite_score = max(0.0, min(100.0, (composite + 100.0) / 2.0))
        result.direction = "bullish" if result.composite_score > 60 else (
            "bearish" if result.composite_score < 40 else "neutral"
        )
        result.confidence = abs(result.composite_score - 50.0) / 50.0

        self._logger.info(
            "D3 宏观信号: score=%.1f direction=%s | 利差=%.2f PMI=%.1f LME=%.2f EIA=%.2f",
            result.composite_score, result.direction,
            result.cn_us_bond_spread, result.ism_pmi,
            result.lme_inventory_change_3w, result.eia_crude_surprise,
        )
        return result

    def _calculate_cn_us_bond_spread(self, result: MacroSignalResult) -> None:
        """计算中美10Y利差信号"""
        bond_df = self._get_auxiliary_data("bond_zh_us")
        if bond_df is None or bond_df.empty:
            self._logger.debug("中美利差数据不可用")
            return

        try:
            # 尝试提取中国10Y和美国10Y收益率
            cn_10y = self._extract_bond_yield(bond_df, ["中国10年期", "cn_10y", "10年期国债收益率"])
            us_10y = self._extract_bond_yield(bond_df, ["美国10年期", "us_10y", "美国10年期国债收益率"])

            if cn_10y is not None and us_10y is not None:
                spread = cn_10y - us_10y
                result.cn_us_bond_spread = spread

                # 利差方向信号
                # 利差扩大 → 资本流入中国 → 看多A股
                # 利差倒挂 (<-1.5%) → 风险信号
                if spread > 0:
                    result.cn_us_spread_direction = min(100.0, 50.0 + spread * 20.0)
                elif spread > -1.0:
                    result.cn_us_spread_direction = 40.0
                elif spread > -1.5:
                    result.cn_us_spread_direction = 30.0
                else:
                    result.cn_us_spread_direction = max(0.0, 20.0 + (spread + 1.5) * 10.0)

                # 变化速率
                if len(bond_df) >= 5:
                    prev_cn = self._extract_bond_yield_at(bond_df, -5, ["中国10年期", "cn_10y"])
                    prev_us = self._extract_bond_yield_at(bond_df, -5, ["美国10年期", "us_10y"])
                    if prev_cn is not None and prev_us is not None:
                        prev_spread = prev_cn - prev_us
                        result.cn_us_spread_rate_of_change = spread - prev_spread

        except Exception as e:
            self._logger.warning("中美利差计算异常: %s", e)

    def _extract_bond_yield(
        self, df: pd.DataFrame, col_candidates: List[str],
    ) -> Optional[float]:
        """从债券收益率数据中提取最新值"""
        for col in col_candidates:
            if col in df.columns:
                try:
                    val = pd.to_numeric(df[col].iloc[-1], errors="coerce")
                    if not pd.isna(val):
                        return float(val)
                except (IndexError, ValueError):
                    continue
        return None

    def _extract_bond_yield_at(
        self, df: pd.DataFrame, idx: int, col_candidates: List[str],
    ) -> Optional[float]:
        """从债券收益率数据中提取指定行的值"""
        for col in col_candidates:
            if col in df.columns:
                try:
                    val = pd.to_numeric(df[col].iloc[idx], errors="coerce")
                    if not pd.isna(val):
                        return float(val)
                except (IndexError, ValueError):
                    continue
        return None

    def _calculate_ism_pmi(self, result: MacroSignalResult) -> None:
        """计算ISM PMI信号"""
        pmi_df = self._get_auxiliary_data("ism_pmi")
        if pmi_df is None or pmi_df.empty:
            self._logger.debug("ISM PMI数据不可用")
            return

        try:
            pmi_val = self._extract_numeric_from_df(pmi_df, ["PMI", "ism_pmi", "制造业PMI", "index"])
            if pmi_val is not None:
                result.ism_pmi = pmi_val

                # PMI信号
                if pmi_val >= 55:
                    result.ism_pmi_signal = 80.0  # 强扩张
                elif pmi_val >= 50:
                    result.ism_pmi_signal = 50.0 + (pmi_val - 50.0) * 6.0  # 扩张
                elif pmi_val >= 48:
                    result.ism_pmi_signal = 30.0  # 轻微收缩
                elif pmi_val >= 45:
                    result.ism_pmi_signal = 15.0  # 收缩
                else:
                    result.ism_pmi_signal = 0.0   # 深度收缩

                # PMI方向变化检测
                if len(pmi_df) >= 2:
                    prev_pmi = self._extract_numeric_from_df_at(
                        pmi_df, -2, ["PMI", "ism_pmi", "制造业PMI", "index"],
                    )
                    if prev_pmi is not None:
                        # 方向变化: 从扩张到收缩, 或从收缩到扩张
                        if (prev_pmi >= 50 and pmi_val < 50) or (prev_pmi < 50 and pmi_val >= 50):
                            result.ism_direction_change = True

        except Exception as e:
            self._logger.warning("ISM PMI计算异常: %s", e)

    def _calculate_lme_inventory(self, result: MacroSignalResult) -> None:
        """
        计算LME库存信号

        3周库存变化率:
          - 下降 → 看多 (供应紧张)
          - 上升 → 看空 (供应充足)
        """
        lme_df = self._get_auxiliary_data("lme_stock")
        if lme_df is None or lme_df.empty:
            self._logger.debug("LME库存数据不可用")
            return

        try:
            # 尝试提取库存数据 (铜为主)
            inventory = self._extract_numeric_from_df(
                lme_df, ["库存", "inventory", "铜库存", "CU"],
            )
            if inventory is None:
                return

            # 3周前的库存
            if len(lme_df) >= 15:
                past_inventory = self._extract_numeric_from_df_at(
                    lme_df, -15, ["库存", "inventory", "铜库存", "CU"],
                )
                if past_inventory is not None and past_inventory > 0:
                    change_rate = (inventory / past_inventory - 1.0) * 100.0
                    result.lme_inventory_change_3w = change_rate

                    # 反向信号: 库存下降=看多, 库存上升=看空
                    if change_rate <= -10.0:
                        result.lme_inventory_signal = 90.0  # 大幅去库, 强看多
                    elif change_rate <= -5.0:
                        result.lme_inventory_signal = 70.0  # 显著去库
                    elif change_rate <= 0:
                        result.lme_inventory_signal = 55.0  # 温和去库
                    elif change_rate <= 5.0:
                        result.lme_inventory_signal = 45.0  # 温和累库
                    elif change_rate <= 10.0:
                        result.lme_inventory_signal = 30.0  # 显著累库
                    else:
                        result.lme_inventory_signal = 10.0  # 大幅累库, 强看空

        except Exception as e:
            self._logger.warning("LME库存计算异常: %s", e)

    def _calculate_eia_crude(self, result: MacroSignalResult) -> None:
        """
        计算EIA原油库存信号

        库存意外 (surprise vs expectations):
          - 超预期去库 → 看多
          - 超预期累库 → 看空
        """
        eia_df = self._get_auxiliary_data("eia_crude")
        if eia_df is None or eia_df.empty:
            self._logger.debug("EIA原油库存数据不可用")
            return

        try:
            # 提取库存变化值
            change = self._extract_numeric_from_df(
                eia_df, ["变化", "change", "库存变化", "weekly_change"],
            )

            # 提取预期值
            expected = self._extract_numeric_from_df(
                eia_df, ["预期", "expected", "预期变化", "forecast"],
            )

            if change is not None:
                if expected is not None:
                    # 意外值 = 实际 - 预期
                    surprise = change - expected
                    result.eia_crude_surprise = surprise
                else:
                    # 无预期值, 直接使用变化值
                    result.eia_crude_surprise = change
                    surprise = change

                # 信号映射 (去库=看多, 累库=看空)
                if surprise <= -10.0:
                    result.eia_crude_signal = 90.0
                elif surprise <= -5.0:
                    result.eia_crude_signal = 70.0
                elif surprise <= 0:
                    result.eia_crude_signal = 55.0
                elif surprise <= 5.0:
                    result.eia_crude_signal = 45.0
                elif surprise <= 10.0:
                    result.eia_crude_signal = 30.0
                else:
                    result.eia_crude_signal = 10.0

        except Exception as e:
            self._logger.warning("EIA原油库存计算异常: %s", e)

    def _extract_numeric_from_df(
        self, df: pd.DataFrame, col_candidates: List[str],
    ) -> Optional[float]:
        """从DataFrame提取最后行的数值"""
        return self._extract_numeric_from_df_at(df, -1, col_candidates)

    def _extract_numeric_from_df_at(
        self, df: pd.DataFrame, idx: int, col_candidates: List[str],
    ) -> Optional[float]:
        """从DataFrame提取指定行的数值"""
        for col in col_candidates:
            if col in df.columns:
                try:
                    val = pd.to_numeric(df[col].iloc[idx], errors="coerce")
                    if not pd.isna(val):
                        return float(val)
                except (IndexError, ValueError):
                    continue
        return None

    # ═══════════════════════════════════════════════════════════════════════
    # Dimension 4: Sentiment Signal (15%)
    # ═══════════════════════════════════════════════════════════════════════

    def calculate_sentiment_signals(self) -> SentimentSignalResult:
        """
        计算情绪信号维度

        子信号:
          - QVIX变化率: (current_qvix / qvix_5d_ago - 1) * 100
          - BTC波动率: 20日已实现波动率
          - 黄金驱动力分解: GC-XAU价差 → 实际利率 vs 避险驱动力识别

        Returns:
            SentimentSignalResult
        """
        result = SentimentSignalResult()

        # 1. QVIX变化率
        self._calculate_qvix_signals(result)

        # 2. BTC波动率
        self._calculate_btc_volatility(result)

        # 3. 黄金驱动力分解
        self._calculate_gold_driver(result)

        # 4. 情绪动量 (综合)
        sentiment_momentum = self._calculate_sentiment_momentum(result)

        # 综合评分
        sub_scores = {
            "qvix": result.qvix_signal,
            "btc_vol": result.btc_vol_signal,
            "gold_driver": result.gold_driver_signal,
            "sentiment_momentum": sentiment_momentum,
        }

        composite = sum(
            sub_scores[k] * self._sentiment_sub_weights.get(k, 0.0)
            for k in sub_scores
        )
        result.composite_score = max(0.0, min(100.0, (composite + 100.0) / 2.0))
        result.direction = "bullish" if result.composite_score > 60 else (
            "bearish" if result.composite_score < 40 else "neutral"
        )
        result.confidence = abs(result.composite_score - 50.0) / 50.0

        self._logger.info(
            "D4 情绪信号: score=%.1f direction=%s | QVIX=%.2f BTC_vol=%.2f gold_driver=%s",
            result.composite_score, result.direction,
            result.qvix_signal, result.btc_realized_vol_20d, result.gold_driver,
        )
        return result

    def _calculate_qvix_signals(self, result: SentimentSignalResult) -> None:
        """
        计算QVIX信号

        50ETF QVIX 和 300ETF QVIX 的5日变化率:
          - QVIX大幅上升 → 恐慌加剧 → 逆向看多
          - QVIX大幅下降 → 恐慌缓解 → 确认信号
        """
        qvix_50_df = self._get_auxiliary_data("qvix_50etf")
        qvix_300_df = self._get_auxiliary_data("qvix_300etf")

        qvix_signals = []

        for df, label, attr in [
            (qvix_50_df, "50ETF", "qvix_50etf_change_rate"),
            (qvix_300_df, "300ETF", "qvix_300etf_change_rate"),
        ]:
            if df is not None and len(df) >= 6:
                current = self._extract_numeric_from_df(df, ["QVIX", "qvix", "vix", "波动率"])
                past_5d = self._extract_numeric_from_df_at(df, -6, ["QVIX", "qvix", "vix", "波动率"])

                if current is not None and past_5d is not None and past_5d > 0:
                    change_rate = (current / past_5d - 1.0) * 100.0
                    setattr(result, attr, change_rate)
                    qvix_signals.append(change_rate)
                else:
                    qvix_signals.append(0.0)
            else:
                qvix_signals.append(0.0)

        # 综合QVIX信号 (逆向: QVIX飙升=恐慌=逆向看多)
        avg_change = sum(qvix_signals) / len(qvix_signals) if qvix_signals else 0.0
        if avg_change > 50.0:
            result.qvix_signal = 80.0   # 极度恐慌 → 逆向看多
        elif avg_change > 20.0:
            result.qvix_signal = 65.0   # 恐慌加剧
        elif avg_change > 0:
            result.qvix_signal = 50.0   # 微幅上升
        elif avg_change > -20.0:
            result.qvix_signal = 45.0   # 波动下降
        else:
            result.qvix_signal = 30.0   # 波动极低 → 可能过度乐观

    def _calculate_btc_volatility(self, result: SentimentSignalResult) -> None:
        """
        计算BTC 20日已实现波动率

        高波动率 → 风险偏好高 → 市场情绪偏乐观
        低波动率 → 风险规避 → 市场情绪偏谨慎
        """
        btc_hist = self._get_hist_data("BTC", days=30)
        if btc_hist is None or len(btc_hist) < 20:
            self._logger.debug("BTC历史数据不足, 跳过波动率计算")
            return

        try:
            returns = btc_hist["close"].pct_change().dropna()
            if len(returns) < 15:
                return

            # 20日已实现波动率 (年化)
            realized_vol = float(returns.tail(20).std() * math.sqrt(252) * 100.0)
            result.btc_realized_vol_20d = realized_vol

            # 信号映射
            if realized_vol > 80.0:
                result.btc_vol_signal = 70.0   # 极高波动 → 风险偏好强
            elif realized_vol > 60.0:
                result.btc_vol_signal = 60.0   # 高波动
            elif realized_vol > 40.0:
                result.btc_vol_signal = 50.0   # 正常波动
            elif realized_vol > 25.0:
                result.btc_vol_signal = 40.0   # 低波动
            else:
                result.btc_vol_signal = 25.0   # 极低波动 → 风险规避

        except Exception as e:
            self._logger.warning("BTC波动率计算异常: %s", e)

    def _calculate_gold_driver(self, result: SentimentSignalResult) -> None:
        """
        黄金驱动力分解

        GC(期货) vs XAU(现货) 价差分析:
          - GC > XAU 且价差扩大 → 实际利率驱动 (避险+通胀对冲)
          - GC < XAU 或价差收窄 → 避险驱动 (恐慌买入)
          - 信号含义: 避险驱动时, A股可能承压; 实际利率驱动时, 影响偏中性
        """
        gc_hist = self._get_hist_data("GC", days=30)
        xau_hist = self._get_hist_data("XAU", days=30)

        if gc_hist is None or xau_hist is None or len(gc_hist) < 5 or len(xau_hist) < 5:
            self._logger.debug("GC/XAU数据不足, 跳过黄金驱动力分解")
            return

        try:
            gc_price = float(gc_hist["close"].iloc[-1])
            xau_price = float(xau_hist["close"].iloc[-1])

            if xau_price <= 0:
                return

            # GC-XAU 价差 (百分比)
            spread = (gc_price / xau_price - 1.0) * 100.0
            result.gc_xau_spread = spread

            # 历史价差
            if len(gc_hist) >= 10 and len(xau_hist) >= 10:
                gc_prev = float(gc_hist["close"].iloc[-5])
                xau_prev = float(xau_hist["close"].iloc[-5])

                if xau_prev > 0:
                    prev_spread = (gc_prev / xau_prev - 1.0) * 100.0
                    spread_change = spread - prev_spread
                else:
                    spread_change = 0.0
            else:
                spread_change = 0.0

            # 驱动力判断
            if spread > 0.5 and spread_change > 0.1:
                # GC升水且扩大 → 实际利率驱动 (通胀对冲)
                result.gold_driver = "real_rate"
                result.gold_driver_signal = 55.0  # 偏中性
            elif spread < -0.3 or (spread < 0.5 and spread_change < -0.1):
                # GC贴水或收窄 → 避险驱动
                result.gold_driver = "safe_haven"
                result.gold_driver_signal = -30.0  # 避险=对A股偏空
            else:
                result.gold_driver = "mixed"
                result.gold_driver_signal = 0.0

        except Exception as e:
            self._logger.warning("黄金驱动力分解异常: %s", e)

    def _calculate_sentiment_momentum(
        self, result: SentimentSignalResult,
    ) -> float:
        """
        计算情绪动量信号

        综合近期情绪变化趋势:
          - QVIX + BTC + 黄金驱动力 的10日方向
        """
        # 简化: 基于已有信号的综合动量
        signals = []
        if result.qvix_signal != 0.0:
            signals.append(result.qvix_signal)
        if result.btc_vol_signal != 0.0:
            signals.append(result.btc_vol_signal)
        if result.gold_driver_signal != 0.0:
            signals.append(result.gold_driver_signal)

        if not signals:
            return 0.0

        avg = sum(signals) / len(signals)
        # 映射到 [-100, 100]
        return max(-100.0, min(100.0, avg))

    # ═══════════════════════════════════════════════════════════════════════
    # Overnight Return Calculator
    # ═══════════════════════════════════════════════════════════════════════

    def calculate_overnight_returns(self) -> Dict[str, float]:
        """
        计算所有核心品种的隔夜收益率

        A股收盘(15:00 北京) → 次日开盘(9:00) 价格变化
        使用 close[t-1] → open[t] 近似

        Returns:
            {symbol: overnight_return_pct}
        """
        from data_service.ak_adapter import CORE_SYMBOLS

        results: Dict[str, float] = {}
        for symbol in CORE_SYMBOLS:
            hist = self._get_hist_data(symbol, days=5)
            if hist is not None and len(hist) >= 2:
                ret = self._calculate_overnight_return_single(hist)
                results[symbol] = ret

        self._logger.info(
            "隔夜收益率: %d 品种 | 均值=%.2f%%",
            len(results),
            sum(results.values()) / len(results) if results else 0.0,
        )
        return results

    # ═══════════════════════════════════════════════════════════════════════
    # Cross-Market Spreads
    # ═══════════════════════════════════════════════════════════════════════

    def calculate_cross_market_spreads(self) -> Dict[str, SpreadResult]:
        """
        计算跨市场价格差

        价差对:
          - WTI-Brent spread (能源)
          - LME CU-COMEX HG spread (有色金属)
          - Gold-Silver ratio (贵金属)
          - GC-XAU spread (黄金期现)

        Returns:
            {spread_name: SpreadResult}
        """
        results: Dict[str, SpreadResult] = {}

        for spread_def in CROSS_MARKET_SPREADS:
            name = spread_def["name"]
            leg1 = spread_def["leg1"]
            leg2 = spread_def["leg2"]

            try:
                result = self._calculate_single_spread(name, leg1, leg2, spread_def["type"])
                if result is not None:
                    results[name] = result
            except Exception as e:
                self._logger.warning("价差计算失败 %s: %s", name, e)

        self._logger.info("跨市场价格差: %d/%d 成功", len(results), len(CROSS_MARKET_SPREADS))
        return results

    def _calculate_single_spread(
        self, name: str, leg1: str, leg2: str, spread_type: str,
    ) -> Optional[SpreadResult]:
        """计算单个价差"""
        leg1_data = self._ak.get_futures_realtime(leg1)
        leg2_data = self._ak.get_futures_realtime(leg2)

        if leg1_data is None or leg2_data is None:
            return None

        leg1_price = float(leg1_data.get("price", 0))
        leg2_price = float(leg2_data.get("price", 0))

        if leg1_price <= 0 or leg2_price <= 0:
            return None

        # 计算价差
        if spread_type in ("energy", "metal"):
            # 绝对价差
            spread_value = leg1_price - leg2_price
            spread_pct = (leg1_price / leg2_price - 1.0) * 100.0
        elif spread_type == "precious":
            # 金银比
            spread_value = leg1_price / leg2_price
            spread_pct = spread_value
        elif spread_type == "gold_basis":
            # 期现价差
            spread_value = leg1_price - leg2_price
            spread_pct = (leg1_price / leg2_price - 1.0) * 100.0
        else:
            spread_value = leg1_price - leg2_price
            spread_pct = (leg1_price / leg2_price - 1.0) * 100.0

        # 历史z-score
        spread_zscore = self._calculate_spread_zscore(leg1, leg2, spread_value, spread_type)

        # 方向和信号
        if spread_type == "precious":
            # 金银比: >80 偏高(避险强), <70 偏低(风险偏好强)
            if spread_pct > 85:
                direction, signal = "bearish_for_risk", -60.0
            elif spread_pct > 75:
                direction, signal = "neutral", 0.0
            else:
                direction, signal = "bullish_for_risk", 40.0
        elif spread_type == "gold_basis":
            # GC-XAU: 正价差=正常, 负价差=异常
            if spread_pct > 0.5:
                direction, signal = "normal_contango", 10.0
            elif spread_pct > -0.3:
                direction, signal = "neutral", 0.0
            else:
                direction, signal = "backwardation", -20.0
        else:
            # 通用价差: z-score映射
            direction = "wide" if spread_zscore > 1.0 else ("narrow" if spread_zscore < -1.0 else "neutral")
            signal = max(-100.0, min(100.0, -spread_zscore * 30.0))

        return SpreadResult(
            name=name,
            leg1_symbol=leg1, leg2_symbol=leg2,
            leg1_price=leg1_price, leg2_price=leg2_price,
            spread_value=spread_value, spread_pct=spread_pct,
            spread_zscore=spread_zscore,
            direction=direction, signal=signal,
        )

    def _calculate_spread_zscore(
        self, leg1: str, leg2: str, current_spread: float, spread_type: str,
    ) -> float:
        """计算价差的历史z-score"""
        leg1_hist = self._get_hist_data(leg1, days=60)
        leg2_hist = self._get_hist_data(leg2, days=60)

        if leg1_hist is None or leg2_hist is None:
            return 0.0
        if len(leg1_hist) < 20 or len(leg2_hist) < 20:
            return 0.0

        # 对齐日期 (取交集)
        min_len = min(len(leg1_hist), len(leg2_hist))
        p1 = leg1_hist["close"].values[-min_len:].astype(float)
        p2 = leg2_hist["close"].values[-min_len:].astype(float)

        # 计算历史价差序列
        if spread_type == "precious":
            # 金银比
            valid = p2 > 0
            if not valid.all():
                return 0.0
            spreads = p1[valid] / p2[valid]
        else:
            spreads = p1 - p2

        if len(spreads) < 10:
            return 0.0

        mean_spread = float(np.mean(spreads))
        std_spread = float(np.std(spreads))

        if std_spread < 1e-8:
            return 0.0

        return (current_spread - mean_spread) / std_spread

    # ═══════════════════════════════════════════════════════════════════════
    # Signal Fusion
    # ═══════════════════════════════════════════════════════════════════════

    def fuse_signals(
        self,
        price: Dict[str, PriceSignalResult],
        position: Dict[str, PositionSignalResult],
        macro: MacroSignalResult,
        sentiment: SentimentSignalResult,
    ) -> OverseasCompositeSignal:
        """
        信号融合 — 加权组合四维度信号

        规则:
          1. 加权组合: w_price * price + w_position * position + w_macro * macro + w_sentiment * sentiment
          2. 交叉验证: 价格与情绪冲突时, 降低置信度
          3. 冲突解决: 2+维度方向不一致时, 应用折扣因子
          4. 输出: 0-100综合评分

        Args:
            price: 价格信号结果
            position: 持仓信号结果
            macro: 宏观信号结果
            sentiment: 情绪信号结果

        Returns:
            OverseasCompositeSignal 综合信号
        """
        # 1. 计算各维度加权评分
        # 价格维度: 各品种评分按层级加权平均
        price_score = self._aggregate_price_score(price)
        position_score = self._aggregate_position_score(position)
        macro_score = macro.composite_score
        sentiment_score = sentiment.composite_score

        # 2. 加权组合
        raw_composite = (
            self._dimension_weights["price"] * price_score
            + self._dimension_weights["position"] * position_score
            + self._dimension_weights["macro"] * macro_score
            + self._dimension_weights["sentiment"] * sentiment_score
        )

        # 3. 冲突检测
        directions = {
            "price": "bullish" if price_score > 55 else ("bearish" if price_score < 45 else "neutral"),
            "position": "bullish" if position_score > 55 else ("bearish" if position_score < 45 else "neutral"),
            "macro": "bullish" if macro_score > 55 else ("bearish" if macro_score < 45 else "neutral"),
            "sentiment": "bullish" if sentiment_score > 55 else ("bearish" if sentiment_score < 45 else "neutral"),
        }

        bullish_count = sum(1 for d in directions.values() if d == "bullish")
        bearish_count = sum(1 for d in directions.values() if d == "bearish")

        conflict_count = min(bullish_count, bearish_count)  # 方向冲突数

        # 4. 冲突折扣
        if conflict_count >= 2:
            conflict_discount = 0.70  # 2+维度冲突, 30%折扣
        elif conflict_count == 1:
            conflict_discount = 0.85  # 1维冲突, 15%折扣
        else:
            conflict_discount = 1.0   # 无冲突

        # 5. 价格-情绪交叉验证
        if directions["price"] != directions["sentiment"] and directions["price"] != "neutral" and directions["sentiment"] != "neutral":
            # 价格与情绪方向冲突, 降低置信度
            cross_validation_penalty = 0.90
        else:
            cross_validation_penalty = 1.0

        # 6. 最终综合评分
        composite = raw_composite * conflict_discount * cross_validation_penalty
        composite = max(0.0, min(100.0, composite))

        # 方向
        final_direction = "bullish" if composite > 60 else ("bearish" if composite < 40 else "neutral")
        confidence = abs(composite - 50.0) / 50.0 * conflict_discount * cross_validation_penalty

        # 构建结果
        signal = OverseasCompositeSignal(
            price_score=price_score,
            position_score=position_score,
            macro_score=macro_score,
            sentiment_score=sentiment_score,
            composite_score=composite,
            direction=final_direction,
            confidence=confidence,
            conflict_count=conflict_count,
            conflict_discount=conflict_discount,
            price_signals=price,
            position_signals=position,
            macro_signal=macro,
            sentiment_signal=sentiment,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

        self._logger.info(
            "信号融合: composite=%.2f direction=%s confidence=%.2f | "
            "price=%.1f pos=%.1f macro=%.1f sent=%.1f | 冲突=%d 折扣=%.2f",
            composite, final_direction, confidence,
            price_score, position_score, macro_score, sentiment_score,
            conflict_count, conflict_discount,
        )

        return signal

    def _aggregate_price_score(
        self, price_signals: Dict[str, PriceSignalResult],
    ) -> float:
        """按层级加权聚合价格信号评分"""
        if not price_signals:
            return 50.0

        tier_scores: Dict[str, List[float]] = {"core": [], "extended": [], "auxiliary": []}

        for symbol, ps in price_signals.items():
            info = self._ak.get_symbol_info(symbol)
            tier = info.tier if info else "core"
            if tier in tier_scores:
                tier_scores[tier].append(ps.composite_score)

        # 各层级平均
        tier_avgs: Dict[str, float] = {}
        for tier, scores in tier_scores.items():
            if scores:
                tier_avgs[tier] = sum(scores) / len(scores)
            else:
                tier_avgs[tier] = 50.0

        # 加权平均
        weighted = sum(
            tier_avgs.get(tier, 50.0) * self._tier_weights.get(tier, 0.0)
            for tier in ["core", "extended", "auxiliary"]
        )
        total_weight = sum(
            self._tier_weights.get(tier, 0.0)
            for tier in tier_avgs if tier_avgs[tier] != 50.0 or tier == "core"
        )
        if total_weight > 0:
            weighted /= total_weight

        return max(0.0, min(100.0, weighted))

    def _aggregate_position_score(
        self, position_signals: Dict[str, PositionSignalResult],
    ) -> float:
        """聚合持仓信号评分"""
        if not position_signals:
            return 50.0

        scores = [ps.composite_score for ps in position_signals.values()]
        return sum(scores) / len(scores)

    # ═══════════════════════════════════════════════════════════════════════
    # Sector Impact Transmission
    # ═══════════════════════════════════════════════════════════════════════

    def calculate_sector_impact(
        self, composite_signal: OverseasCompositeSignal,
    ) -> Dict[str, SectorImpact]:
        """
        计算外盘信号对A股行业的传导影响

        传导路径:
          - 成本推动型 (cost_push): 原油→化工/交运, 铜→电力设备
          - 价格同步型 (price_sync): 黄金→贵金属, 铜→有色金属
          - 风险情绪型 (risk_sentiment): BTC→科技, 美元指数→外资重仓

        Args:
            composite_signal: 综合信号

        Returns:
            {sector_name: SectorImpact}
        """
        results: Dict[str, SectorImpact] = {}

        for sector, transmissions in SECTOR_TRANSMISSION_MAP.items():
            impact_scores = []
            source_symbols = []

            for trans in transmissions:
                symbol = trans["symbol"]
                trans_type = trans["type"]
                strength = trans["strength"]

                # 获取该品种的价格信号
                ps = composite_signal.price_signals.get(symbol)
                if ps is None:
                    continue

                # 根据传导类型调整评分
                if trans_type == "cost_push":
                    # 成本推动: 海外涨价 → A股利空 (反向)
                    score = 100.0 - ps.composite_score
                elif trans_type == "price_sync":
                    # 价格同步: 海外涨价 → A股利好 (同向)
                    score = ps.composite_score
                elif trans_type == "risk_sentiment":
                    # 风险情绪: 综合信号高 → 风险偏好强 → 利好
                    score = composite_signal.composite_score
                else:
                    score = ps.composite_score

                # 加权
                weighted_score = score * strength
                impact_scores.append(weighted_score)
                source_symbols.append(symbol)

            if impact_scores:
                avg_impact = sum(impact_scores) / len(impact_scores)
                avg_impact = max(0.0, min(100.0, avg_impact))

                # 映射到 -100 ~ +100
                impact_value = (avg_impact - 50.0) * 2.0

                direction = "bullish" if impact_value > 20 else (
                    "bearish" if impact_value < -20 else "neutral"
                )

                # 确定主要传导类型
                main_trans_type = transmissions[0]["type"] if transmissions else ""

                # 置信度: 来源品种越多, 置信度越高
                confidence = min(1.0, len(source_symbols) * 0.3 + 0.4)

                results[sector] = SectorImpact(
                    sector=sector,
                    impact_score=impact_value,
                    impact_direction=direction,
                    transmission_type=main_trans_type,
                    source_symbols=source_symbols,
                    confidence=confidence,
                )

        self._logger.info(
            "行业影响: %d 行业 | 看多=%d 看空=%d 中性=%d",
            len(results),
            sum(1 for s in results.values() if s.impact_direction == "bullish"),
            sum(1 for s in results.values() if s.impact_direction == "bearish"),
            sum(1 for s in results.values() if s.impact_direction == "neutral"),
        )
        return results

    # ═══════════════════════════════════════════════════════════════════════
    # Main Entry
    # ═══════════════════════════════════════════════════════════════════════

    def generate_overseas_signal(self) -> OverseasCompositeSignal:
        """
        主入口: 生成外盘期货综合信号

        流程:
          1. 计算D1价格信号 (所有核心品种)
          2. 计算D2持仓信号 (CFTC品种)
          3. 计算D3宏观信号 (利差/PMI/库存/EIA)
          4. 计算D4情绪信号 (QVIX/BTC/黄金)
          5. 计算隔夜收益率
          6. 计算跨市场价格差
          7. 信号融合
          8. 计算行业传导影响

        Returns:
            OverseasCompositeSignal 完整信号结果
        """
        start_time = time.time()

        self._logger.info("=" * 60)
        self._logger.info("外盘期货四维信号引擎 — 开始计算")
        self._logger.info("=" * 60)

        # D1: 价格信号
        price_signals = self.calculate_price_signals(tier="core")

        # D2: 持仓信号
        position_signals = self.calculate_position_signals()

        # D3: 宏观信号
        macro_signal = self.calculate_macro_signals()

        # D4: 情绪信号
        sentiment_signal = self.calculate_sentiment_signals()

        # 隔夜收益率
        overnight_returns = self.calculate_overnight_returns()

        # 跨市场价格差
        cross_market_spreads = self.calculate_cross_market_spreads()

        # 信号融合
        composite = self.fuse_signals(
            price=price_signals,
            position=position_signals,
            macro=macro_signal,
            sentiment=sentiment_signal,
        )

        # 附加信息
        composite.overnight_returns = overnight_returns
        composite.cross_market_spreads = cross_market_spreads

        # 行业传导影响
        sector_impacts = self.calculate_sector_impact(composite)
        composite.sector_impacts = sector_impacts

        # 数据质量
        elapsed_ms = (time.time() - start_time) * 1000.0
        composite.data_quality = {
            "price_signals_count": len(price_signals),
            "position_signals_count": len(position_signals),
            "macro_signal_available": macro_signal.composite_score != 50.0,
            "sentiment_signal_available": sentiment_signal.composite_score != 50.0,
            "cross_market_spreads_count": len(cross_market_spreads),
            "sector_impacts_count": len(sector_impacts),
            "calculation_time_ms": round(elapsed_ms, 1),
        }

        self._logger.info("=" * 60)
        self._logger.info(
            "外盘期货四维信号 — 计算完成 | score=%.2f direction=%s confidence=%.2f | 耗时=%.0fms",
            composite.composite_score, composite.direction, composite.confidence, elapsed_ms,
        )
        self._logger.info("=" * 60)

        return composite

    # ═══════════════════════════════════════════════════════════════════════
    # Data Access Helpers
    # ═══════════════════════════════════════════════════════════════════════

    def _get_hist_data(
        self, symbol: str, days: int = 120,
    ) -> Optional[pd.DataFrame]:
        """获取历史数据 (带缓存)"""
        cache_key = f"hist_{symbol}_{days}"

        # 检查内部缓存
        if cache_key in self._hist_cache:
            return self._hist_cache[cache_key]

        # 检查外部缓存
        if self._cache is not None:
            cached = self._cache.get(f"overseas_signal:{cache_key}")
            if cached is not None:
                self._hist_cache[cache_key] = cached
                return cached

        # 通过AKAdapter获取
        hist = self._ak.get_futures_hist(symbol, days=days)

        if hist is not None:
            # 写入缓存
            self._hist_cache[cache_key] = hist
            if self._cache is not None:
                self._cache.set(f"overseas_signal:{cache_key}", hist, ttl=600)

        return hist

    def _get_auxiliary_data(self, data_type: str) -> Optional[pd.DataFrame]:
        """获取辅助数据 (带缓存)"""
        if data_type in self._aux_cache:
            return self._aux_cache[data_type]

        if self._cache is not None:
            cached = self._cache.get(f"overseas_signal:aux_{data_type}")
            if cached is not None:
                self._aux_cache[data_type] = cached
                return cached

        data = self._ak.get_auxiliary_data(data_type)

        if data is not None:
            self._aux_cache[data_type] = data
            if self._cache is not None:
                self._cache.set(f"overseas_signal:aux_{data_type}", data, ttl=1800)

        return data

    # ═══════════════════════════════════════════════════════════════════════
    # Utility Methods
    # ═══════════════════════════════════════════════════════════════════════

    def _normalize_to_score(self, value: float, scale: float = 1.0) -> float:
        """
        将原始值归一化到 [0, 100] 评分

        使用 sigmoid 变换: score = 100 / (1 + exp(-value / scale))

        Args:
            value: 原始值 (正值=看多, 负值=看空)
            scale: 归一化尺度

        Returns:
            0-100评分 (50=中性)
        """
        if scale <= 0:
            return 50.0
        try:
            x = value / scale
            # 防止溢出
            if x > 20:
                return 100.0
            elif x < -20:
                return 0.0
            score = 100.0 / (1.0 + math.exp(-x))
            return max(0.0, min(100.0, score))
        except (OverflowError, ValueError):
            return 50.0

    @staticmethod
    def _percentile_rank(series: List[float], value: float) -> float:
        """
        计算值在序列中的百分位排名

        Args:
            series: 参考序列
            value: 目标值

        Returns:
            百分位 (0-100)
        """
        if not series:
            return 50.0

        below = sum(1 for v in series if v < value)
        equal = sum(1 for v in series if abs(v - value) < 1e-10)

        # 使用 (below + 0.5 * equal) / n 的百分位方法
        rank = (below + 0.5 * equal) / len(series) * 100.0
        return max(0.0, min(100.0, rank))

    def _load_dimension_weights(self) -> Dict[str, float]:
        """从配置加载维度权重"""
        defaults = DEFAULT_DIMENSION_WEIGHTS.copy()

        if self._config is None:
            return defaults

        try:
            # 尝试从配置文件读取
            overseas_cfg = self._config.get_section("overseas_signal_engine")
            if overseas_cfg and "dimensions" in overseas_cfg:
                dims = overseas_cfg["dimensions"]
                for dim_name in ["price", "position", "macro", "sentiment"]:
                    if dim_name in dims and "weight" in dims[dim_name]:
                        defaults[dim_name] = float(dims[dim_name]["weight"])
        except Exception:
            pass

        return defaults

    @staticmethod
    def _create_default_logger() -> Logger:
        """创建默认日志记录器"""
        import logging
        _logger = logging.getLogger("aistock.overseas_signal")
        if not _logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(
                logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
            )
            _logger.addHandler(handler)
            _logger.setLevel(logging.INFO)
        return _logger

    def clear_cache(self) -> None:
        """清空所有缓存"""
        self._hist_cache.clear()
        self._aux_cache.clear()
        if self._cache is not None:
            self._cache.clear_namespace("overseas_signal")
        self._logger.info("OverseasFuturesSignalEngine 缓存已清空")

    def get_engine_status(self) -> Dict[str, Any]:
        """获取引擎状态"""
        return {
            "dimension_weights": self._dimension_weights,
            "hist_cache_size": len(self._hist_cache),
            "aux_cache_size": len(self._aux_cache),
            "ak_adapter_health": self._ak.health_check() if self._ak else {"available": False},
            "cache_health": {
                "available": self._cache is not None,
                "stats": str(self._cache.stats) if self._cache is not None else None,
            },
        }
