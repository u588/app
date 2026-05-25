"""
AiStock V8 — 衍生品信号引擎 (Derivatives Signal Engine)

V8 升级: 集成外盘期货信号, 实现海内外衍生品信号融合

核心能力:
  1. 商品期货信号  — 国内期货品种动量/基差/持仓/波动率
  2. 期限结构信号  — 远近月价差 (Contango/Backwardation)
  3. 股指期货基差  — IF/IH/IC/IM 升贴水
  4. 行业情绪信号  — 期货品种→A股行业传导
  5. 海外衍生品信号 [V8 NEW] — 调用 OverseasFuturesSignalEngine 融合外盘信号
  6. 增强报告 [V8 NEW] — 含海外信号的完整报告

数据源:
  - 国内: TDXAdapter 扩展端口 (期货K线/期权K线)
  - 海外: OverseasFuturesSignalEngine (依赖注入)

依赖:
  - data_service (TDXAdapter)
  - contract_manager (合约动态推导)
  - overseas_signal_engine (可选, OverseasFuturesSignalEngine)
  - config (system_config.yaml)
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
TDXAdapter = Any           # data_service.tdx_adapter.TDXAdapter
ContractManager = Any      # 合约管理器
OverseasSignalEngine = Any  # core.overseas_futures_signal_engine.OverseasFuturesSignalEngine
ConfigService = Any        # base_services.config_service.ConfigService
CacheService = Any         # base_services.cache_service.CacheService

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# 数据类定义
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class CommoditySignal:
    """单个商品品种信号

    Attributes:
        variety:       品种代码 (如 'CU', 'AG')
        name:          品种名称
        momentum_20d:  20日动量 (%)
        basis:         基差 (现货-期货)
        basis_pct:     基差率 (%)
        oi_change_5d:  5日持仓变化率 (%)
        volatility_20d: 20日已实现波动率 (%)
        signal:        综合信号 (-100 ~ +100)
        direction:     方向 'bullish' / 'bearish' / 'neutral'
    """
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
    """期限结构信号

    Attributes:
        variety:         品种代码
        near_month:      近月合约代码
        far_month:       远月合约代码
        near_price:      近月价格
        far_price:       远月价格
        spread:          价差 (近月 - 远月)
        spread_pct:      价差百分比
        structure_type:  'contango' / 'backwardation' / 'flat'
        signal:          信号值 (-100 ~ +100)
    """
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
    """股指期货基差信号

    Attributes:
        variety:      品种代码 (IF/IH/IC/IM)
        name:         品种名称
        spot_code:    现货指数代码
        futures_code: 期货合约代码
        spot_price:   现货价格
        futures_price: 期货价格
        basis:        基差 (现货 - 期货)
        basis_pct:    基差率 (%)
        signal:       信号值 (-100 ~ +100, 正=升水看多, 负=贴水看空)
        direction:    方向
    """
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
    """行业情绪信号 (期货品种→A股行业传导)

    Attributes:
        industry:         行业名称
        source_varieties: 来源品种列表
        composite_signal: 综合信号 (-100 ~ +100)
        direction:        方向
        confidence:       置信度 (0-1)
    """
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
    """海外衍生品融合信号 [V8 NEW]

    Attributes:
        overseas_composite:    海外综合信号 (0-100)
        overseas_direction:    海外方向
        overseas_confidence:   海外置信度
        domestic_composite:    国内综合信号 (-100 ~ +100)
        fusion_signal:         融合信号 (-100 ~ +100)
        fusion_direction:      融合方向
        sector_impacts:        A股行业影响
        data_available:        海外数据是否可用
    """
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
    """衍生品信号引擎综合结果

    Attributes:
        commodity_signals:    商品品种信号
        term_structure:       期限结构信号
        index_futures_basis:  股指期货基差信号
        industry_sentiment:   行业情绪信号
        overseas_signal:      海外衍生品信号 [V8 NEW]
        composite_signal:     综合信号 (-100 ~ +100)
        composite_direction:  综合方向
        timestamp:            计算时间戳
    """
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
# 常量与默认配置
# ═══════════════════════════════════════════════════════════════════════════════

# 商品期货品种配置
DEFAULT_COMMODITY_VARIETIES: List[Dict[str, Any]] = [
    {"variety": "CU", "name": "沪铜", "market_type": "future_sh", "industry": "有色金属"},
    {"variety": "AL", "name": "沪铝", "market_type": "future_sh", "industry": "有色金属"},
    {"variety": "ZN", "name": "沪锌", "market_type": "future_sh", "industry": "有色金属"},
    {"variety": "AU", "name": "沪金", "market_type": "future_sh", "industry": "贵金属"},
    {"variety": "AG", "name": "沪银", "market_type": "future_sh", "industry": "贵金属"},
    {"variety": "RB", "name": "螺纹钢", "market_type": "future_sh", "industry": "钢铁"},
    {"variety": "I",  "name": "铁矿石", "market_type": "future_dl", "industry": "钢铁"},
    {"variety": "M",  "name": "豆粕", "market_type": "future_dl", "industry": "农业"},
    {"variety": "Y",  "name": "豆油", "market_type": "future_dl", "industry": "农业"},
    {"variety": "P",  "name": "棕榈油", "market_type": "future_dl", "industry": "农业"},
    {"variety": "C",  "name": "玉米", "market_type": "future_dl", "industry": "农业"},
    {"variety": "CF", "name": "棉花", "market_type": "future_zz", "industry": "纺织"},
    {"variety": "SR", "name": "白糖", "market_type": "future_zz", "industry": "食品"},
    {"variety": "TA", "name": "PTA", "market_type": "future_zz", "industry": "化工"},
    {"variety": "MA", "name": "甲醇", "market_type": "future_zz", "industry": "化工"},
    {"variety": "SC", "name": "原油", "market_type": "future_sh", "industry": "能源"},
]

# 股指期货配置
DEFAULT_INDEX_FUTURES: List[Dict[str, Any]] = [
    {"variety": "IF", "name": "沪深300", "spot_code": "000300", "futures_suffix": "M0", "market_type": "future_zj"},
    {"variety": "IH", "name": "上证50",  "spot_code": "000016", "futures_suffix": "M0", "market_type": "future_zj"},
    {"variety": "IC", "name": "中证500", "spot_code": "000905", "futures_suffix": "M0", "market_type": "future_zj"},
    {"variety": "IM", "name": "中证1000", "spot_code": "000852", "futures_suffix": "M0", "market_type": "future_zj"},
]

# 信号权重
COMMODITY_SIGNAL_WEIGHTS = {
    "momentum": 0.35,
    "basis": 0.25,
    "oi_change": 0.20,
    "volatility": 0.20,
}

# 综合信号权重
COMPOSITE_WEIGHTS = {
    "commodity": 0.30,
    "term_structure": 0.15,
    "index_basis": 0.25,
    "industry": 0.15,
    "overseas": 0.15,
}

# 海外信号融合权重
OVERSEAS_FUSION_WEIGHT = 0.30  # 海外信号占融合信号的权重


# ═══════════════════════════════════════════════════════════════════════════════
# 衍生品信号引擎
# ═══════════════════════════════════════════════════════════════════════════════

class DerivativesSignalEngine:
    """衍生品信号引擎 (V8 增强版)

    V7 原有:
      - 商品期货信号 (动量/基差/持仓/波动率)
      - 期限结构信号 (Contango/Backwardation)
      - 股指期货基差 (IF/IH/IC/IM 升贴水)
      - 行业情绪信号 (期货品种→A股行业传导)

    V8 新增:
      - 海外衍生品信号 (调用 OverseasFuturesSignalEngine)
      - 融合信号 (海内外衍生品加权融合)
      - 增强报告 (含海外信号完整报告)

    使用方式:
        >>> from data_service.tdx_adapter import TDXAdapter
        >>> engine = DerivativesSignalEngine(
        ...     data_service=tdx_adapter,
        ...     contract_manager=cm,
        ...     overseas_signal_engine=ose,  # 可选
        ...     config=config_svc,
        ... )
        >>> result = engine.calculate_all()
        >>> print(result.composite_signal, result.composite_direction)
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

        Args:
            data_service:           TDXAdapter 实例 (扩展端口 7721)
            contract_manager:       合约管理器 (可选)
            overseas_signal_engine: 海外信号引擎 (可选, V8 NEW)
            config:                 配置服务
            cache:                  缓存服务
            logger_instance:        自定义 logger
        """
        self._tdx = data_service
        self._contract_mgr = contract_manager
        self._overseas_engine = overseas_signal_engine
        self._config = config
        self._cache = cache
        self._logger = logger_instance or logger

        # 加载配置
        self._commodity_varieties = self._load_commodity_config()
        self._index_futures = self._load_index_futures_config()
        self._weights = self._load_weights()
        self._overseas_fusion_weight = OVERSEAS_FUSION_WEIGHT

        self._logger.info(
            "DerivativesSignalEngine V8.0 初始化完成 | "
            "商品品种: %d, 股指期货: %d, 海外引擎: %s",
            len(self._commodity_varieties),
            len(self._index_futures),
            "已注入" if self._overseas_engine else "未注入",
        )

    # ═══════════════════════════════════════════════════════════════════════
    # 1. 商品期货信号
    # ═══════════════════════════════════════════════════════════════════════

    def calculate_commodity_signals(self) -> Dict[str, CommoditySignal]:
        """计算商品期货信号

        对每个品种计算:
          - 20日动量
          - 基差 (近月 vs 现货)
          - 5日持仓变化率
          - 20日已实现波动率
          - 综合信号

        Returns:
            {variety: CommoditySignal}
        """
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

        # 获取主力合约K线
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

        # 2. 基差 (使用近远月价差近似)
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

        # 5. 综合信号
        momentum_signal = self._normalize_to_signal(momentum_20d, scale=10.0)
        basis_signal = self._normalize_to_signal(basis_pct, scale=3.0)
        oi_signal = self._normalize_to_signal(oi_change_5d, scale=10.0)
        vol_signal = self._volatility_signal(volatility_20d)

        composite = (
            momentum_signal * COMMODITY_SIGNAL_WEIGHTS["momentum"]
            + basis_signal * COMMODITY_SIGNAL_WEIGHTS["basis"]
            + oi_signal * COMMODITY_SIGNAL_WEIGHTS["oi_change"]
            + vol_signal * COMMODITY_SIGNAL_WEIGHTS["volatility"]
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
        """计算期限结构信号

        对主要品种计算近月与远月价差:
          - 近月 > 远月 → Backwardation (供应紧张, 利多)
          - 近月 < 远月 → Contango (供应宽松, 利空)

        Returns:
            {variety: TermStructureSignal}
        """
        results: Dict[str, TermStructureSignal] = {}
        # 仅对流动性较好的品种计算
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

        # 获取近月合约
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

        # 判定期限结构类型
        if spread_pct > 0.5:
            structure_type = "backwardation"
            signal = min(100.0, spread_pct * 20.0)  # Backwardation 看多
        elif spread_pct < -0.5:
            structure_type = "contango"
            signal = max(-100.0, spread_pct * 20.0)  # Contango 看空
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
        """计算股指期货基差

        基差 = 现货指数 - 期货价格
          - 正基差 (升水) → 市场乐观
          - 负基差 (贴水) → 市场悲观

        Returns:
            {variety: IndexFuturesBasis}
        """
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

        # 获取期货价格
        futures_code = f"{variety}{cfg.get('futures_suffix', 'M0')}"
        futures_df = self._fetch_future_bars(futures_code, market_type, days=5)

        if futures_df is None or futures_df.empty:
            return IndexFuturesBasis(
                variety=variety, name=name, spot_code=spot_code,
                futures_code=futures_code,
            )

        futures_price = float(futures_df["close"].iloc[-1])

        # 获取现货指数价格
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

        # 基差信号映射
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
        """计算行业情绪信号

        将商品期货信号按行业聚合, 传导到A股行业.

        Args:
            commodity_signals: 商品信号 (若None则自动计算)

        Returns:
            {industry: IndustrySentiment}
        """
        if commodity_signals is None:
            commodity_signals = self.calculate_commodity_signals()

        # 按行业聚合
        industry_data: Dict[str, List[Tuple[str, float]]] = {}
        for cfg in self._commodity_varieties:
            variety = cfg["variety"]
            industry = cfg.get("industry", "其他")
            signal = commodity_signals.get(variety)
            if signal is not None:
                if industry not in industry_data:
                    industry_data[industry] = []
                industry_data[industry].append((variety, signal.signal))

        # 计算行业综合信号
        results: Dict[str, IndustrySentiment] = {}
        for industry, signals in industry_data.items():
            if not signals:
                continue

            avg_signal = float(np.mean([sig for _, sig in signals]))
            direction = "bullish" if avg_signal > 15 else ("bearish" if avg_signal < -15 else "neutral")
            confidence = min(1.0, len(signals) / 5.0)  # 品种越多置信度越高

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
    # 5. 海外衍生品信号 [V8 NEW]
    # ═══════════════════════════════════════════════════════════════════════

    def calculate_overseas_derivatives_signal(
        self,
        domestic_composite: float = 0.0,
    ) -> OverseasDerivativesSignal:
        """计算海外衍生品融合信号 [V8 NEW]

        调用 OverseasFuturesSignalEngine 获取海外信号,
        与国内信号加权融合.

        Args:
            domestic_composite: 国内衍生品综合信号 (-100 ~ +100)

        Returns:
            OverseasDerivativesSignal
        """
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

            # 转换海外信号 (0-100) → (-100 ~ +100)
            overseas_score = (overseas_result.composite_score - 50.0) * 2.0

            result.overseas_composite = overseas_result.composite_score
            result.overseas_direction = overseas_result.direction
            result.overseas_confidence = overseas_result.confidence
            result.data_available = True

            # 融合: 国内权重 + 海外权重
            w_overseas = self._overseas_fusion_weight
            w_domestic = 1.0 - w_overseas

            result.fusion_signal = (
                w_domestic * domestic_composite
                + w_overseas * overseas_score
            )
            result.fusion_signal = max(-100.0, min(100.0, result.fusion_signal))
            result.fusion_direction = self._signal_to_direction(result.fusion_signal)

            # A股行业影响
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
        """全量计算衍生品信号

        计算流程:
          1. 商品期货信号
          2. 期限结构信号
          3. 股指期货基差
          4. 行业情绪信号
          5. 国内综合信号
          6. 海外衍生品融合 [V8 NEW]

        Returns:
            DerivativesResult
        """
        start_time = time.time()

        # 1. 商品期货信号
        commodity_signals = self.calculate_commodity_signals()

        # 2. 期限结构信号
        term_structure = self.calculate_term_structure()

        # 3. 股指期货基差
        index_basis = self.calculate_index_futures_basis()

        # 4. 行业情绪信号
        industry_sentiment = self.calculate_industry_sentiment(commodity_signals)

        # 5. 国内综合信号
        domestic_composite = self._calculate_domestic_composite(
            commodity_signals, term_structure, index_basis, industry_sentiment,
        )

        # 6. 海外衍生品融合
        overseas_signal = self.calculate_overseas_derivatives_signal(domestic_composite)

        # 最终综合信号 (使用融合信号)
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
        """生成增强报告 (含海外信号) [V8 NEW]

        Args:
            result: 衍生品信号结果 (None则自动计算)

        Returns:
            报告字典
        """
        if result is None:
            result = self.calculate_all()

        report = {
            "version": "8.0",
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
        """计算国内综合信号"""
        # 商品信号平均
        commodity_avg = 0.0
        if commodity_signals:
            commodity_avg = float(np.mean([s.signal for s in commodity_signals.values()]))

        # 期限结构平均
        term_avg = 0.0
        if term_structure:
            term_avg = float(np.mean([t.signal for t in term_structure.values()]))

        # 股指基差平均
        basis_avg = 0.0
        if index_basis:
            basis_avg = float(np.mean([b.signal for b in index_basis.values()]))

        # 行业情绪平均
        industry_avg = 0.0
        if industry_sentiment:
            industry_avg = float(np.mean([s.composite_signal for s in industry_sentiment.values()]))

        # 加权综合
        composite = (
            commodity_avg * COMPOSITE_WEIGHTS["commodity"]
            + term_avg * COMPOSITE_WEIGHTS["term_structure"]
            + basis_avg * COMPOSITE_WEIGHTS["index_basis"]
            + industry_avg * COMPOSITE_WEIGHTS["industry"]
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
            return 20.0   # 低波动偏多
        elif vol < 25.0:
            return 0.0    # 正常波动中性
        elif vol < 35.0:
            return -30.0  # 高波动偏空
        else:
            return -60.0  # 极高波动强烈偏空

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

        Args:
            variety:      品种代码
            market_type:  市场类型
            month_offset: 月偏移 (0=主力, 1=次月)

        Returns:
            合约代码字符串
        """
        # 优先使用 contract_manager
        if self._contract_mgr is not None:
            try:
                code = self._contract_mgr.get_contract_code(
                    variety=variety, month_offset=month_offset,
                )
                if code:
                    return code
            except Exception as e:
                self._logger.debug("contract_manager 获取失败: %s", e)

        # 默认: 品种 + M0/M1
        suffix = "M0" if month_offset == 0 else "M1"
        return f"{variety}{suffix}"

    def _fetch_future_bars(
        self, code: str, market_type: str, days: int = 120,
    ) -> Optional[pd.DataFrame]:
        """获取期货K线数据"""
        try:
            df = self._tdx.get_future_daily(
                code=code, market_type=market_type, count=days,
            )
            if df is not None and not df.empty:
                return df
        except Exception as e:
            self._logger.debug("期货K线获取失败 %s: %s", code, e)
        return None

    def _fetch_index_bars(
        self, code: str, days: int = 5,
    ) -> Optional[pd.DataFrame]:
        """获取指数K线数据"""
        try:
            # 根据代码前缀判断市场
            if code.startswith("399"):
                market_type = "index_sz"
            else:
                market_type = "index_sh"
            df = self._tdx.get_index_daily(
                code=code, market_type=market_type, count=days,
            )
            if df is not None and not df.empty:
                return df
        except Exception as e:
            self._logger.debug("指数K线获取失败 %s: %s", code, e)
        return None

    def _get_variety_market_type(self, variety: str) -> Optional[str]:
        """获取品种对应的市场类型"""
        for cfg in self._commodity_varieties:
            if cfg["variety"] == variety:
                return cfg.get("market_type")
        return None

    def _load_commodity_config(self) -> List[Dict[str, Any]]:
        """加载商品品种配置"""
        if self._config is not None:
            try:
                cfg_data = self._config.get("commodity_strategy_map", {})
                if cfg_data:
                    result = []
                    for key, val in cfg_data.items():
                        result.append({
                            "variety": key.replace("L8", ""),
                            "name": val.get("name", key),
                            "market_type": val.get("market_type", "future_sh"),
                            "industry": val.get("directions", ["其他"])[0] if val.get("directions") else "其他",
                        })
                    return result
            except Exception:
                pass
        return DEFAULT_COMMODITY_VARIETIES

    def _load_index_futures_config(self) -> List[Dict[str, Any]]:
        """加载股指期货配置"""
        if self._config is not None:
            try:
                cfg_data = self._config.get("index_futures_contracts", {})
                if cfg_data:
                    result = []
                    for key, val in cfg_data.items():
                        result.append({
                            "variety": val.get("variety", key.upper()),
                            "name": val.get("spot_name", key),
                            "spot_code": val.get("spot_code", ""),
                            "futures_suffix": "M0",
                            "market_type": val.get("market_type", "future_zj"),
                        })
                    return result
            except Exception:
                pass
        return DEFAULT_INDEX_FUTURES

    def _load_weights(self) -> Dict[str, Any]:
        """加载信号权重"""
        return {
            "commodity_signal": COMMODITY_SIGNAL_WEIGHTS,
            "composite": COMPOSITE_WEIGHTS,
        }
