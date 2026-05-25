"""
AiStock V8 — 期权PCR计算引擎 (Option PCR Engine)

取代 v6.1 伪数据实现, 基于 TDX 扩展端口 (7721) 获取真实期权数据,
计算全维度 Put-Call Ratio (PCR).

三大 PCR 维度:
  1. Stock ETF PCR — 9 个 ETF 标的 (上交所5 + 深交所4)
     - 含调整合约 (A 后缀), 占 OI 的 5-13%
     - PCR(OI) 和 PCR(Volume) 分离计算
     - 当月合约 PCR (CCM/PCM) 单独统计

  2. CFFEX Index PCR — 3 个股指期权 (IO/HO/MO)
     - 分月 PCR + 总 PCR
     - 反映机构观点, 与 ETF PCR 互补

  3. Commodity Option PCR — Top 20 商品期权
     - 按流动性加权商品 PCR
     - 商品 PCR vs 指数 PCR 背离 = 风险预警信号

设计参考: TDX分析报告 — 期权数据全量获取方案
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from .option_code_parser import OptionCodeParser, OptionContractInfo

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# 数据类定义
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class PCRResult:
    """单个标的 PCR 计算结果

    Attributes:
        underlying:              标的代码
        pcr_oi:                  PCR(OI) = Put OI / Call OI
        pcr_volume:              PCR(Volume) = Put Volume / Call Volume
        pcr_oi_current_month:    当月合约 PCR(OI)
        total_call_oi:           Call 总持仓量
        total_put_oi:            Put 总持仓量
        total_call_volume:       Call 总成交量
        total_put_volume:        Put 总成交量
        contract_count:          总合约数
        adjusted_contract_count: 调整合约数
        timestamp:               计算时间戳
    """

    underlying: str
    pcr_oi: float = 0.0
    pcr_volume: float = 0.0
    pcr_oi_current_month: float = 0.0
    total_call_oi: int = 0
    total_put_oi: int = 0
    total_call_volume: int = 0
    total_put_volume: int = 0
    contract_count: int = 0
    adjusted_contract_count: int = 0
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    @property
    def is_valid(self) -> bool:
        """计算结果是否有效 (至少有 Call 或 Put 数据)"""
        return self.contract_count > 0 and (
            self.total_call_oi > 0 or self.total_put_oi > 0
        )

    @property
    def total_oi(self) -> int:
        """总持仓量"""
        return self.total_call_oi + self.total_put_oi

    @property
    def total_volume(self) -> int:
        """总成交量"""
        return self.total_call_volume + self.total_put_volume

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "underlying": self.underlying,
            "pcr_oi": round(self.pcr_oi, 4),
            "pcr_volume": round(self.pcr_volume, 4),
            "pcr_oi_current_month": round(self.pcr_oi_current_month, 4),
            "total_call_oi": self.total_call_oi,
            "total_put_oi": self.total_put_oi,
            "total_call_volume": self.total_call_volume,
            "total_put_volume": self.total_put_volume,
            "contract_count": self.contract_count,
            "adjusted_contract_count": self.adjusted_contract_count,
            "timestamp": self.timestamp,
        }

    def __repr__(self) -> str:
        return (
            f"PCRResult({self.underlying} "
            f"OI={self.pcr_oi:.3f} Vol={self.pcr_volume:.3f} "
            f"CCM_OI={self.pcr_oi_current_month:.3f} "
            f"contracts={self.contract_count})"
        )


@dataclass
class CompositePCRResult:
    """综合 PCR 计算结果

    Attributes:
        etf_pcr:       ETF 期权加权 PCR
        cffex_pcr:     中金所期权加权 PCR
        commodity_pcr: 商品期权加权 PCR
        composite_pcr: 综合加权 PCR
        signal_level:  信号级别: 'normal' / 'warning' / 'extreme'
        timestamp:     计算时间戳
    """

    etf_pcr: float = 0.0
    cffex_pcr: float = 0.0
    commodity_pcr: float = 0.0
    composite_pcr: float = 0.0
    signal_level: str = "normal"
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "etf_pcr": round(self.etf_pcr, 4),
            "cffex_pcr": round(self.cffex_pcr, 4),
            "commodity_pcr": round(self.commodity_pcr, 4),
            "composite_pcr": round(self.composite_pcr, 4),
            "signal_level": self.signal_level,
            "timestamp": self.timestamp,
        }

    def __repr__(self) -> str:
        return (
            f"CompositePCR("
            f"ETF={self.etf_pcr:.3f} CFFEX={self.cffex_pcr:.3f} "
            f"Comm={self.commodity_pcr:.3f} → {self.composite_pcr:.3f} "
            f"[{self.signal_level}])"
        )


@dataclass
class PCRDivergenceSignal:
    """PCR 背离信号

    商品 PCR 与指数 PCR 走势背离 → 风险预警

    Attributes:
        commodity_pcr_direction: 商品 PCR 趋势方向 ('rising' / 'falling' / 'stable')
        index_pcr_direction:     指数 PCR 趋势方向 ('rising' / 'falling' / 'stable')
        divergence_type:         背离类型:
                                 'commodity_bearish_index_bullish' — 商品看空 vs 指数看多
                                 'commodity_bullish_index_bearish' — 商品看多 vs 指数看空
                                 'aligned_bullish' — 同向看多
                                 'aligned_bearish' — 同向看空
                                 'no_divergence'   — 无明显背离
        risk_level:              风险级别: 'low' / 'medium' / 'high' / 'extreme'
        commodity_pcr_value:     商品 PCR 当前值
        index_pcr_value:         指数 PCR 当前值
        divergence_magnitude:    背离幅度 (0.0-1.0)
        timestamp:               信号时间戳
    """

    commodity_pcr_direction: str = "stable"
    index_pcr_direction: str = "stable"
    divergence_type: str = "no_divergence"
    risk_level: str = "low"
    commodity_pcr_value: float = 0.0
    index_pcr_value: float = 0.0
    divergence_magnitude: float = 0.0
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    @property
    def is_divergent(self) -> bool:
        """是否存在背离"""
        return self.divergence_type not in ("no_divergence", "aligned_bullish", "aligned_bearish")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "commodity_pcr_direction": self.commodity_pcr_direction,
            "index_pcr_direction": self.index_pcr_direction,
            "divergence_type": self.divergence_type,
            "risk_level": self.risk_level,
            "commodity_pcr_value": round(self.commodity_pcr_value, 4),
            "index_pcr_value": round(self.index_pcr_value, 4),
            "divergence_magnitude": round(self.divergence_magnitude, 4),
            "is_divergent": self.is_divergent,
            "timestamp": self.timestamp,
        }

    def __repr__(self) -> str:
        return (
            f"PCRDivergence("
            f"type={self.divergence_type} "
            f"risk={self.risk_level} "
            f"mag={self.divergence_magnitude:.2f})"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# ETF 标的配置
# ═══════════════════════════════════════════════════════════════════════════════

# 上交所 ETF 期权标的 (Market=8)
SH_ETF_UNDERLYINGS: List[Dict[str, Any]] = [
    {"code": "510050", "name": "上证50ETF",     "weight": 0.30},
    {"code": "510300", "name": "沪深300ETF(沪)", "weight": 0.28},
    {"code": "510500", "name": "中证500ETF(沪)", "weight": 0.12},
    {"code": "588000", "name": "科创50ETF",      "weight": 0.15},
    {"code": "588080", "name": "科创板50ETF",     "weight": 0.15},
]

# 深交所 ETF 期权标的 (Market=9)
SZ_ETF_UNDERLYINGS: List[Dict[str, Any]] = [
    {"code": "159901", "name": "深证100ETF",     "weight": 0.15},
    {"code": "159915", "name": "创业板ETF",      "weight": 0.30},
    {"code": "159919", "name": "沪深300ETF(深)", "weight": 0.30},
    {"code": "159922", "name": "中证500ETF(深)", "weight": 0.25},
]

# 全部 ETF 标的
ALL_ETF_UNDERLYINGS = SH_ETF_UNDERLYINGS + SZ_ETF_UNDERLYINGS

# 中金所指数期权品种
CFFEX_UNDERLYINGS: List[Dict[str, Any]] = [
    {"code": "IO", "name": "沪深300股指期权", "market_code": 7, "weight": 0.55},
    {"code": "HO", "name": "上证50股指期权",  "market_code": 7, "weight": 0.15},
    {"code": "MO", "name": "中证1000股指期权", "market_code": 7, "weight": 0.30},
]

# 默认商品期权品种 (Top 20 按流动性)
DEFAULT_COMMODITY_VARIETIES: List[str] = [
    "CU", "AG", "I", "AU", "AL",
    "ZN", "RB", "NI", "RU", "SN",
    "M", "Y", "P", "C", "CF",
    "SR", "TA", "MA", "AP", "PB",
]


# ═══════════════════════════════════════════════════════════════════════════════
# 默认权重与阈值
# ═══════════════════════════════════════════════════════════════════════════════

# 综合 PCR 权重
DEFAULT_COMPOSITE_WEIGHTS: Dict[str, float] = {
    "etf": 0.45,
    "cffex": 0.30,
    "commodity": 0.25,
}

# PCR 信号阈值
DEFAULT_PCR_THRESHOLDS: Dict[str, Any] = {
    "etf_warning_high": 1.3,
    "etf_warning_low": 0.7,
    "etf_extreme_high": 1.5,
    "etf_extreme_low": 0.5,
    "cffex_warning_high": 1.2,
    "cffex_warning_low": 0.8,
    "cffex_extreme_high": 1.4,
    "cffex_extreme_low": 0.6,
    "commodity_warning_high": 1.5,
    "commodity_warning_low": 0.5,
    "commodity_extreme_high": 2.0,
    "commodity_extreme_low": 0.3,
}

# PCR 背离检测阈值
_DIVERGENCE_THRESHOLD_LOW = 0.15
_DIVERGENCE_THRESHOLD_MEDIUM = 0.30
_DIVERGENCE_THRESHOLD_HIGH = 0.50

# PCR 趋势判定阈值 (5日变化率)
_TREND_THRESHOLD = 0.05

# TDX 扩展端口市场编号
_MARKET_SH_ETF = 8       # 上交所ETF期权
_MARKET_SZ_ETF = 9       # 深交所ETF期权
_MARKET_CFFEX = 7        # 中金所期权
_MARKET_SHFE_OPT = 6     # 上期所商品期权
_MARKET_DCE_OPT = 5      # 大商所商品期权
_MARKET_CZCE_OPT = 28    # 郑商所商品期权


# ═══════════════════════════════════════════════════════════════════════════════
# 期权 PCR 计算引擎
# ═══════════════════════════════════════════════════════════════════════════════

class OptionPCREngine:
    """期权 PCR (Put-Call Ratio) 全量计算引擎

    基于 TDX 扩展端口 (7721) 获取真实期权数据, 计算:
      - ETF PCR:   9 个 ETF 标的, 含调整合约
      - CFFEX PCR: 3 个股指期权品种
      - Commodity PCR: Top 20 商品期权
      - Composite PCR: 加权综合 PCR
      - Divergence Signal: 商品/指数背离信号

    使用方式:
        >>> from data_service.tdx_adapter import TDXAdapter
        >>> from base_services import CacheService, ConfigService
        >>>
        >>> tdx = TDXAdapter()
        >>> cache = CacheService()
        >>> config = ConfigService()
        >>>
        >>> engine = OptionPCREngine(tdx, config, cache)
        >>>
        >>> # 单标的 ETF PCR
        >>> pcr = engine.calculate_etf_pcr("510050")
        >>> print(pcr.pcr_oi, pcr.pcr_volume)
        >>>
        >>> # 全部 ETF PCR
        >>> all_pcr = engine.calculate_all_etf_pcr()
        >>>
        >>> # 综合PCR
        >>> composite = engine.calculate_composite_pcr()
        >>> print(composite.composite_pcr, composite.signal_level)
    """

    def __init__(
        self,
        tdx_adapter: Any,
        config: Any,
        cache_service: Any,
        logger_instance: Optional[logging.Logger] = None,
    ) -> None:
        """初始化 PCR 引擎

        Args:
            tdx_adapter:     TDXAdapter 实例 (扩展端口 7721)
            config:          ConfigService 实例
            cache_service:   CacheService 实例
            logger_instance: 可选自定义 logger
        """
        self._tdx = tdx_adapter
        self._config = config
        self._cache = cache_service
        self._logger = logger_instance or logger

        # 期权代码解析器
        self._parser = OptionCodeParser()

        # 加载配置
        self._weights = self._load_weights()
        self._thresholds = self._load_thresholds()
        self._cache_ttls = self._load_cache_ttls()

        # PCR 历史缓存 (用于趋势判断)
        self._pcr_history: Dict[str, List[float]] = {}
        self._history_max_len: int = 20

        # 缓存命名空间
        self._cache_ns = self._cache.namespace("pcr") if self._cache else None

        self._logger.info(
            "OptionPCREngine 初始化完成 — 权重: ETF=%.2f CFFEX=%.2f Comm=%.2f",
            self._weights["etf"],
            self._weights["cffex"],
            self._weights["commodity"],
        )

    # ═════════════════════════════════════════════════════════════════════
    # ETF PCR 计算
    # ═════════════════════════════════════════════════════════════════════

    def calculate_etf_pcr(self, underlying: str) -> PCRResult:
        """计算单个 ETF 标的 PCR

        获取该标的下所有期权合约的 OI 和 Volume,
        分离 Call/Put 并计算 PCR.

        必须包含调整合约 (A 后缀), 其 OI 占比 5-13%.

        Args:
            underlying: ETF 标的代码 (如 '510050', '159915')

        Returns:
            PCRResult 数据类
        """
        # 检查缓存
        cache_key = f"etf_pcr_{underlying}"
        cached = self._get_cache(cache_key)
        if cached is not None:
            self._logger.debug("ETF PCR 命中缓存: %s", underlying)
            return cached

        # 确定市场编号
        market_code = self._get_etf_market_code(underlying)
        if market_code is None:
            self._logger.warning("未知 ETF 标的: %s", underlying)
            return PCRResult(underlying=underlying)

        start_time = time.time()

        try:
            # 1. 获取该标的的期权合约列表
            contracts_info = self._fetch_etf_option_contracts(underlying, market_code)

            if not contracts_info:
                self._logger.warning("ETF期权合约列表为空: %s", underlying)
                return PCRResult(underlying=underlying)

            # 2. 解析合约代码
            parsed = self._parser.parse_batch(contracts_info)

            # 3. 过滤: 只保留属于该标的的合约
            target_parsed = [p for p in parsed if p.underlying == underlying]

            # 4. 获取各合约的 OI/Volume
            call_oi, put_oi, call_vol, put_vol = 0, 0, 0, 0
            call_oi_cm, put_oi_cm = 0, 0  # 当月
            adj_count = 0

            for info in target_parsed:
                oi, volume = self._fetch_contract_oi_volume(
                    info.code_name, market_code,
                )

                if info.is_call:
                    call_oi += oi
                    call_vol += volume
                    if info.is_current_month:
                        call_oi_cm += oi
                elif info.is_put:
                    put_oi += oi
                    put_vol += volume
                    if info.is_current_month:
                        put_oi_cm += oi

                if info.is_adjusted:
                    adj_count += 1

            # 5. 计算 PCR
            pcr_oi = put_oi / call_oi if call_oi > 0 else 0.0
            pcr_volume = put_vol / call_vol if call_vol > 0 else 0.0
            pcr_oi_cm = put_oi_cm / call_oi_cm if call_oi_cm > 0 else 0.0

            result = PCRResult(
                underlying=underlying,
                pcr_oi=pcr_oi,
                pcr_volume=pcr_volume,
                pcr_oi_current_month=pcr_oi_cm,
                total_call_oi=call_oi,
                total_put_oi=put_oi,
                total_call_volume=call_vol,
                total_put_volume=put_vol,
                contract_count=len(target_parsed),
                adjusted_contract_count=adj_count,
            )

            # 缓存结果
            self._set_cache(cache_key, result, ttl=self._cache_ttls.get("etf_options", 1800))

            elapsed = (time.time() - start_time) * 1000
            self._logger.info(
                "ETF PCR 计算: %s → OI=%.3f Vol=%.3f CCM=%.3f | %d合约 %d调整 | %.0fms",
                underlying, pcr_oi, pcr_volume, pcr_oi_cm,
                len(target_parsed), adj_count, elapsed,
            )

            # 记录历史 (用于趋势判断)
            self._record_pcr_history(f"etf_{underlying}", pcr_oi)

            return result

        except Exception as e:
            self._logger.error("calculate_etf_pcr(%s) 异常: %s", underlying, e)
            return PCRResult(underlying=underlying)

    def calculate_all_etf_pcr(self) -> Dict[str, PCRResult]:
        """计算全部 9 个 ETF 标的的 PCR

        Returns:
            {underlying: PCRResult} 字典
        """
        results: Dict[str, PCRResult] = {}
        all_underlyings = SH_ETF_UNDERLYINGS + SZ_ETF_UNDERLYINGS

        for cfg in all_underlyings:
            code = cfg["code"]
            try:
                results[code] = self.calculate_etf_pcr(code)
            except Exception as e:
                self._logger.error("ETF PCR 计算失败: %s — %s", code, e)
                results[code] = PCRResult(underlying=code)

        valid_count = sum(1 for r in results.values() if r.is_valid)
        self._logger.info(
            "全部 ETF PCR 计算: %d/%d 有效", valid_count, len(results),
        )
        return results

    # ═════════════════════════════════════════════════════════════════════
    # CFFEX PCR 计算
    # ═════════════════════════════════════════════════════════════════════

    def calculate_cffex_pcr(self, variety: str) -> PCRResult:
        """计算单个中金所指数期权 PCR

        Args:
            variety: 品种代码 ('IO', 'HO', 'MO')

        Returns:
            PCRResult
        """
        cache_key = f"cffex_pcr_{variety}"
        cached = self._get_cache(cache_key)
        if cached is not None:
            return cached

        start_time = time.time()

        try:
            # 获取 CFFEX 合约列表
            contracts_info = self._fetch_cffex_option_contracts(variety)

            if not contracts_info:
                self._logger.warning("CFFEX期权合约列表为空: %s", variety)
                return PCRResult(underlying=variety)

            # 解析
            parsed = self._parser.parse_batch(contracts_info)
            target_parsed = [p for p in parsed if p.underlying == variety or p.variety == variety]

            # 汇总 OI/Volume
            call_oi, put_oi, call_vol, put_vol = 0, 0, 0, 0
            call_oi_cm, put_oi_cm = 0, 0

            # 按月分组统计
            monthly_data: Dict[int, Dict[str, int]] = {}

            for info in target_parsed:
                oi, volume = self._fetch_contract_oi_volume(
                    info.code_name, _MARKET_CFFEX,
                )

                month = info.delivery_month
                if month not in monthly_data:
                    monthly_data[month] = {"call_oi": 0, "put_oi": 0, "call_vol": 0, "put_vol": 0}

                if info.is_call:
                    call_oi += oi
                    call_vol += volume
                    monthly_data[month]["call_oi"] += oi
                    monthly_data[month]["call_vol"] += volume
                    if info.is_current_month:
                        call_oi_cm += oi
                elif info.is_put:
                    put_oi += oi
                    put_vol += volume
                    monthly_data[month]["put_oi"] += oi
                    monthly_data[month]["put_vol"] += volume
                    if info.is_current_month:
                        put_oi_cm += oi

            pcr_oi = put_oi / call_oi if call_oi > 0 else 0.0
            pcr_volume = put_vol / call_vol if call_vol > 0 else 0.0
            pcr_oi_cm = put_oi_cm / call_oi_cm if call_oi_cm > 0 else 0.0

            result = PCRResult(
                underlying=variety,
                pcr_oi=pcr_oi,
                pcr_volume=pcr_volume,
                pcr_oi_current_month=pcr_oi_cm,
                total_call_oi=call_oi,
                total_put_oi=put_oi,
                total_call_volume=call_vol,
                total_put_volume=put_vol,
                contract_count=len(target_parsed),
                adjusted_contract_count=0,
            )

            self._set_cache(cache_key, result, ttl=self._cache_ttls.get("cffex_options", 1800))

            elapsed = (time.time() - start_time) * 1000
            self._logger.info(
                "CFFEX PCR: %s → OI=%.3f Vol=%.3f CCM=%.3f | %d合约 | %.0fms",
                variety, pcr_oi, pcr_volume, pcr_oi_cm, len(target_parsed), elapsed,
            )

            self._record_pcr_history(f"cffex_{variety}", pcr_oi)
            return result

        except Exception as e:
            self._logger.error("calculate_cffex_pcr(%s) 异常: %s", variety, e)
            return PCRResult(underlying=variety)

    def calculate_all_cffex_pcr(self) -> Dict[str, PCRResult]:
        """计算全部 3 个中金所指数期权 PCR

        Returns:
            {variety: PCRResult} 字典
        """
        results: Dict[str, PCRResult] = {}

        for cfg in CFFEX_UNDERLYINGS:
            variety = cfg["code"]
            try:
                results[variety] = self.calculate_cffex_pcr(variety)
            except Exception as e:
                self._logger.error("CFFEX PCR 计算失败: %s — %s", variety, e)
                results[variety] = PCRResult(underlying=variety)

        return results

    # ═════════════════════════════════════════════════════════════════════
    # 商品期权 PCR 计算
    # ═════════════════════════════════════════════════════════════════════

    def calculate_commodity_pcr(self, variety: str) -> PCRResult:
        """计算单个商品期权 PCR

        Args:
            variety: 商品品种代码 (如 'CU', 'AG', 'I')

        Returns:
            PCRResult
        """
        cache_key = f"commodity_pcr_{variety}"
        cached = self._get_cache(cache_key)
        if cached is not None:
            return cached

        start_time = time.time()

        try:
            # 获取商品期权合约列表
            contracts_info = self._fetch_commodity_option_contracts(variety)

            if not contracts_info:
                self._logger.warning("商品期权合约列表为空: %s", variety)
                return PCRResult(underlying=variety)

            # 解析
            parsed = self._parser.parse_batch(contracts_info)
            target_parsed = [p for p in parsed if p.variety == variety or p.underlying == variety]

            # 汇总
            call_oi, put_oi, call_vol, put_vol = 0, 0, 0, 0
            call_oi_cm, put_oi_cm = 0, 0

            # 获取市场编号
            market_code = self._get_commodity_market_code(variety)

            for info in target_parsed:
                oi, volume = self._fetch_contract_oi_volume(
                    info.code_name, market_code,
                )

                if info.is_call:
                    call_oi += oi
                    call_vol += volume
                    if info.is_current_month:
                        call_oi_cm += oi
                elif info.is_put:
                    put_oi += oi
                    put_vol += volume
                    if info.is_current_month:
                        put_oi_cm += oi

            pcr_oi = put_oi / call_oi if call_oi > 0 else 0.0
            pcr_volume = put_vol / call_vol if call_vol > 0 else 0.0
            pcr_oi_cm = put_oi_cm / call_oi_cm if call_oi_cm > 0 else 0.0

            result = PCRResult(
                underlying=variety,
                pcr_oi=pcr_oi,
                pcr_volume=pcr_volume,
                pcr_oi_current_month=pcr_oi_cm,
                total_call_oi=call_oi,
                total_put_oi=put_oi,
                total_call_volume=call_vol,
                total_put_volume=put_vol,
                contract_count=len(target_parsed),
                adjusted_contract_count=0,
            )

            self._set_cache(cache_key, result, ttl=self._cache_ttls.get("commodity_options", 1800))

            elapsed = (time.time() - start_time) * 1000
            self._logger.info(
                "商品 PCR: %s → OI=%.3f Vol=%.3f | %d合约 | %.0fms",
                variety, pcr_oi, pcr_volume, len(target_parsed), elapsed,
            )

            self._record_pcr_history(f"commodity_{variety}", pcr_oi)
            return result

        except Exception as e:
            self._logger.error("calculate_commodity_pcr(%s) 异常: %s", variety, e)
            return PCRResult(underlying=variety)

    def calculate_top_commodity_pcr(
        self,
        top_n: int = 20,
    ) -> Dict[str, PCRResult]:
        """计算 Top N 商品期权 PCR (按流动性排序)

        Args:
            top_n: 计算前 N 个品种 (默认 20)

        Returns:
            {variety: PCRResult} 字典
        """
        varieties = DEFAULT_COMMODITY_VARIETIES[:top_n]
        results: Dict[str, PCRResult] = {}

        for variety in varieties:
            try:
                results[variety] = self.calculate_commodity_pcr(variety)
            except Exception as e:
                self._logger.error("商品 PCR 计算失败: %s — %s", variety, e)
                results[variety] = PCRResult(underlying=variety)

        valid_count = sum(1 for r in results.values() if r.is_valid)
        self._logger.info(
            "Top %d 商品 PCR: %d/%d 有效", top_n, valid_count, len(results),
        )
        return results

    # ═════════════════════════════════════════════════════════════════════
    # 综合 PCR 与背离检测
    # ═════════════════════════════════════════════════════════════════════

    def calculate_composite_pcr(self) -> CompositePCRResult:
        """计算综合加权 PCR

        权重 (可配置):
          - ETF:      0.45
          - CFFEX:    0.30
          - Commodity: 0.25

        Returns:
            CompositePCRResult
        """
        cache_key = "composite_pcr"
        cached = self._get_cache(cache_key)
        if cached is not None:
            return cached

        start_time = time.time()

        try:
            # 1. 计算 ETF PCR (加权平均)
            etf_results = self.calculate_all_etf_pcr()
            etf_pcr = self._weighted_average_pcr(
                etf_results, ALL_ETF_UNDERLYINGS,
            )

            # 2. 计算 CFFEX PCR (加权平均)
            cffex_results = self.calculate_all_cffex_pcr()
            cffex_pcr = self._weighted_average_pcr(
                cffex_results, CFFEX_UNDERLYINGS,
            )

            # 3. 计算商品 PCR (简单平均, 或按 OI 加权)
            commodity_results = self.calculate_top_commodity_pcr()
            commodity_pcr = self._simple_average_pcr(commodity_results)

            # 4. 综合加权 PCR
            composite = (
                self._weights["etf"] * etf_pcr
                + self._weights["cffex"] * cffex_pcr
                + self._weights["commodity"] * commodity_pcr
            )

            # 5. 判定信号级别
            signal_level = self._determine_signal_level(
                etf_pcr, cffex_pcr, commodity_pcr,
            )

            result = CompositePCRResult(
                etf_pcr=etf_pcr,
                cffex_pcr=cffex_pcr,
                commodity_pcr=commodity_pcr,
                composite_pcr=composite,
                signal_level=signal_level,
            )

            self._set_cache(cache_key, result, ttl=self._cache_ttls.get("pcr_full", 1800))

            elapsed = (time.time() - start_time) * 1000
            self._logger.info(
                "综合 PCR: ETF=%.3f CFFEX=%.3f Comm=%.3f → %.3f [%s] | %.0fms",
                etf_pcr, cffex_pcr, commodity_pcr, composite, signal_level, elapsed,
            )

            return result

        except Exception as e:
            self._logger.error("calculate_composite_pcr 异常: %s", e)
            return CompositePCRResult()

    def detect_pcr_divergence(self) -> Optional[PCRDivergenceSignal]:
        """检测商品 PCR 与指数 PCR 的背离

        背离定义:
          - 商品 PCR 上升 + 指数 PCR 下降 → 商品看空 vs 指数看多 (风险信号)
          - 商品 PCR 下降 + 指数 PCR 上升 → 商品看多 vs 指数看空 (机会信号)

        Returns:
            PCRDivergenceSignal 或 None (数据不足时)
        """
        try:
            # 获取当前 PCR
            commodity_results = self.calculate_top_commodity_pcr()
            cffex_results = self.calculate_all_cffex_pcr()
            etf_results = self.calculate_all_etf_pcr()

            # 商品 PCR 综合
            commodity_pcr = self._simple_average_pcr(commodity_results)

            # 指数 PCR 综合 (CFFEX + ETF 加权)
            cffex_pcr = self._weighted_average_pcr(cffex_results, CFFEX_UNDERLYINGS)
            etf_pcr = self._weighted_average_pcr(etf_results, ALL_ETF_UNDERLYINGS)
            index_pcr = 0.6 * cffex_pcr + 0.4 * etf_pcr

            # 趋势判断
            commodity_trend = self._determine_pcr_trend("commodity_composite", commodity_pcr)
            index_trend = self._determine_pcr_trend("index_composite", index_pcr)

            # 背离类型判定
            divergence_type = self._classify_divergence(commodity_trend, index_trend)

            # 背离幅度
            magnitude = self._calculate_divergence_magnitude(
                commodity_trend, index_trend, commodity_pcr, index_pcr,
            )

            # 风险级别
            risk_level = self._assess_divergence_risk(
                divergence_type, magnitude,
            )

            signal = PCRDivergenceSignal(
                commodity_pcr_direction=commodity_trend,
                index_pcr_direction=index_trend,
                divergence_type=divergence_type,
                risk_level=risk_level,
                commodity_pcr_value=commodity_pcr,
                index_pcr_value=index_pcr,
                divergence_magnitude=magnitude,
            )

            if signal.is_divergent:
                self._logger.warning(
                    "PCR 背离检测: %s | 商品=%.3f(%s) 指数=%.3f(%s) | 幅度=%.2f | 风险=%s",
                    divergence_type,
                    commodity_pcr, commodity_trend,
                    index_pcr, index_trend,
                    magnitude, risk_level,
                )

            return signal

        except Exception as e:
            self._logger.error("detect_pcr_divergence 异常: %s", e)
            return None

    # ═════════════════════════════════════════════════════════════════════
    # 数据获取 (TDX 扩展端口)
    # ═════════════════════════════════════════════════════════════════════

    def _fetch_etf_option_contracts(
        self,
        underlying: str,
        market_code: int,
    ) -> List[Dict[str, Any]]:
        """获取 ETF 期权合约列表 (通过 TDX 扩展端口)

        使用 TDXAdapter.get_instrument_info() 获取全量合约,
        然后按标的前缀筛选.

        Args:
            underlying:   标的代码
            market_code:  市场编号

        Returns:
            合约字典列表 [{'code_name': ..., 'market_code': ...}, ...]
        """
        try:
            df = self._tdx.get_instrument_info(market=market_code)

            if df is None or df.empty:
                self._logger.debug("ETF合约列表为空: market=%d", market_code)
                return []

            # 按标的前缀筛选
            # ETF 期权代码以标的代码开头
            mask = df["code"].str.startswith(underlying)
            filtered = df[mask]

            contracts: List[Dict[str, Any]] = []
            for _, row in filtered.iterrows():
                code = str(row.get("code", ""))
                name = str(row.get("name", ""))
                if code:
                    contracts.append({
                        "code_name": code,
                        "market_code": market_code,
                        "name": name,
                    })

            self._logger.debug(
                "ETF合约获取: %s market=%d → %d 合约",
                underlying, market_code, len(contracts),
            )
            return contracts

        except Exception as e:
            self._logger.error("获取ETF合约列表异常: %s — %s", underlying, e)
            return []

    def _fetch_cffex_option_contracts(
        self,
        variety: str,
    ) -> List[Dict[str, Any]]:
        """获取中金所指数期权合约列表

        Args:
            variety: 品种代码 ('IO', 'HO', 'MO')

        Returns:
            合约字典列表
        """
        try:
            df = self._tdx.get_instrument_info(market=_MARKET_CFFEX)

            if df is None or df.empty:
                return []

            # CFFEX 合约以品种代码开头
            mask = df["code"].str.startswith(variety)
            filtered = df[mask]

            contracts: List[Dict[str, Any]] = []
            for _, row in filtered.iterrows():
                code = str(row.get("code", ""))
                if code:
                    contracts.append({
                        "code_name": code,
                        "market_code": _MARKET_CFFEX,
                    })

            return contracts

        except Exception as e:
            self._logger.error("获取CFFEX合约列表异常: %s — %s", variety, e)
            return []

    def _fetch_commodity_option_contracts(
        self,
        variety: str,
    ) -> List[Dict[str, Any]]:
        """获取商品期权合约列表

        Args:
            variety: 商品品种代码

        Returns:
            合约字典列表
        """
        market_code = self._get_commodity_market_code(variety)
        if market_code is None:
            return []

        try:
            df = self._tdx.get_instrument_info(market=market_code)

            if df is None or df.empty:
                return []

            # 商品期权合约以品种代码开头
            mask = df["code"].str.startswith(variety)
            filtered = df[mask]

            contracts: List[Dict[str, Any]] = []
            for _, row in filtered.iterrows():
                code = str(row.get("code", ""))
                if code:
                    contracts.append({
                        "code_name": code,
                        "market_code": market_code,
                    })

            return contracts

        except Exception as e:
            self._logger.error("获取商品期权合约列表异常: %s — %s", variety, e)
            return []

    def _fetch_contract_oi_volume(
        self,
        code: str,
        market_code: int,
    ) -> Tuple[int, int]:
        """获取单个合约的持仓量 (OI) 和成交量

        通过 TDX 扩展端口获取最近1天K线数据提取 OI 和 Volume.

        注意: pytdx 扩展端口的 K线数据中:
          - volume 字段为成交量
          - 持仓量需从特定接口获取 (或使用 amount 近似)

        Args:
            code:        合约代码
            market_code: 市场编号

        Returns:
            (oi, volume) 元组
        """
        try:
            from data_service.tdx_adapter import BarCategory

            df = self._tdx.get_bars(
                market_type=self._market_code_to_type(market_code),
                code=code,
                category=BarCategory.DAILY,
                start=0,
                count=1,
            )

            if df is None or df.empty:
                return 0, 0

            latest = df.iloc[-1]
            volume = int(latest.get("volume", 0))

            # OI: pytdx 扩展端口 K线中 amount 有时可作为持仓近似
            # 精确 OI 需通过分时数据或其他接口获取
            # 此处使用 amount 字段 (若可用) 或设为 0
            oi = int(latest.get("amount", 0))

            # 如果 amount 不可用, 尝试从 close*volume 估算
            if oi == 0 and volume > 0:
                close_price = float(latest.get("close", 0))
                if close_price > 0:
                    # 粗略估算: 使用成交额/收盘价近似持仓
                    oi = int(latest.get("amount", 0) / close_price) if close_price > 0 else 0

            return oi, volume

        except Exception as e:
            self._logger.debug("获取合约OI/Volume失败: %s — %s", code, e)
            return 0, 0

    # ═════════════════════════════════════════════════════════════════════
    # 辅助计算方法
    # ═════════════════════════════════════════════════════════════════════

    @staticmethod
    def _weighted_average_pcr(
        pcr_results: Dict[str, PCRResult],
        weight_config: List[Dict[str, Any]],
    ) -> float:
        """计算加权平均 PCR

        Args:
            pcr_results:  PCR 结果字典
            weight_config: 权重配置 [{'code': ..., 'weight': ...}, ...]

        Returns:
            加权平均 PCR (OI-based)
        """
        total_weight = 0.0
        weighted_sum = 0.0

        for cfg in weight_config:
            code = cfg["code"]
            weight = cfg.get("weight", 0.1)
            result = pcr_results.get(code)

            if result is not None and result.is_valid:
                weighted_sum += result.pcr_oi * weight
                total_weight += weight

        if total_weight == 0:
            return 0.0
        return weighted_sum / total_weight

    @staticmethod
    def _simple_average_pcr(pcr_results: Dict[str, PCRResult]) -> float:
        """计算简单平均 PCR (用于商品期权)

        仅计算有效结果的平均值.

        Args:
            pcr_results: PCR 结果字典

        Returns:
            简单平均 PCR
        """
        valid_pcrs = [r.pcr_oi for r in pcr_results.values() if r.is_valid and r.pcr_oi > 0]

        if not valid_pcrs:
            return 0.0
        return sum(valid_pcrs) / len(valid_pcrs)

    def _determine_signal_level(
        self,
        etf_pcr: float,
        cffex_pcr: float,
        commodity_pcr: float,
    ) -> str:
        """判定综合 PCR 信号级别

        级别:
          - 'extreme': 任一维度触及极端阈值
          - 'warning': 任一维度触及警告阈值
          - 'normal':  所有维度在正常范围

        Args:
            etf_pcr:       ETF PCR 值
            cffex_pcr:     CFFEX PCR 值
            commodity_pcr: 商品 PCR 值

        Returns:
            信号级别字符串
        """
        th = self._thresholds

        # 极端判定
        if (
            etf_pcr >= th["etf_extreme_high"] or etf_pcr <= th["etf_extreme_low"]
            or cffex_pcr >= th["cffex_extreme_high"] or cffex_pcr <= th["cffex_extreme_low"]
            or commodity_pcr >= th["commodity_extreme_high"]
            or commodity_pcr <= th["commodity_extreme_low"]
        ):
            return "extreme"

        # 警告判定
        if (
            etf_pcr >= th["etf_warning_high"] or etf_pcr <= th["etf_warning_low"]
            or cffex_pcr >= th["cffex_warning_high"] or cffex_pcr <= th["cffex_warning_low"]
            or commodity_pcr >= th["commodity_warning_high"]
            or commodity_pcr <= th["commodity_warning_low"]
        ):
            return "warning"

        return "normal"

    def _determine_pcr_trend(
        self,
        key: str,
        current_pcr: float,
    ) -> str:
        """判断 PCR 趋势方向

        基于最近 N 次 PCR 值的变化率判断趋势.

        Args:
            key:        PCR 历史键
            current_pcr: 当前 PCR 值

        Returns:
            'rising' / 'falling' / 'stable'
        """
        history = self._pcr_history.get(key, [])

        if len(history) < 2:
            return "stable"

        # 比较最近值与5日前的值
        recent = history[-1] if history else current_pcr
        lookback = min(5, len(history))
        past = history[-lookback]

        if past == 0:
            return "stable"

        change_rate = (current_pcr - past) / past

        if change_rate > _TREND_THRESHOLD:
            return "rising"
        elif change_rate < -_TREND_THRESHOLD:
            return "falling"
        return "stable"

    @staticmethod
    def _classify_divergence(
        commodity_trend: str,
        index_trend: str,
    ) -> str:
        """分类背离类型

        Args:
            commodity_trend: 商品 PCR 趋势
            index_trend:     指数 PCR 趋势

        Returns:
            背离类型字符串
        """
        # 商品 PCR 上升 → 商品市场看空情绪增强
        # 指数 PCR 下降 → 指数市场看多情绪增强
        # 背离 = 商品看空 vs 指数看多 = 风险信号
        if commodity_trend == "rising" and index_trend == "falling":
            return "commodity_bearish_index_bullish"

        # 商品 PCR 下降 → 商品市场看多
        # 指数 PCR 上升 → 指数市场看空
        # 背离 = 商品看多 vs 指数看空 = 可能的机会
        if commodity_trend == "falling" and index_trend == "rising":
            return "commodity_bullish_index_bearish"

        # 同向
        if commodity_trend == "rising" and index_trend == "rising":
            return "aligned_bearish"

        if commodity_trend == "falling" and index_trend == "falling":
            return "aligned_bullish"

        return "no_divergence"

    @staticmethod
    def _calculate_divergence_magnitude(
        commodity_trend: str,
        index_trend: str,
        commodity_pcr: float,
        index_pcr: float,
    ) -> float:
        """计算背离幅度

        幅度 = |商品PCR变化率 - 指数PCR变化率| 归一化到 0-1

        Args:
            commodity_trend: 商品 PCR 趋势
            index_trend:     指数 PCR 趋势
            commodity_pcr:   商品 PCR 值
            index_pcr:       指数 PCR 值

        Returns:
            背离幅度 (0.0-1.0)
        """
        if commodity_trend == "stable" or index_trend == "stable":
            return 0.0

        # 同向不背离
        if commodity_trend == index_trend:
            return 0.0

        # 背离幅度: 基于 PCR 值差异
        if index_pcr == 0:
            return 0.0

        diff = abs(commodity_pcr - index_pcr) / max(index_pcr, 0.01)
        return min(diff, 1.0)

    @staticmethod
    def _assess_divergence_risk(
        divergence_type: str,
        magnitude: float,
    ) -> str:
        """评估背离风险级别

        Args:
            divergence_type: 背离类型
            magnitude:       背离幅度

        Returns:
            风险级别: 'low' / 'medium' / 'high' / 'extreme'
        """
        if divergence_type == "no_divergence":
            return "low"

        if divergence_type in ("aligned_bullish", "aligned_bearish"):
            return "low"

        # 商品看空 vs 指数看多 → 高风险
        if divergence_type == "commodity_bearish_index_bullish":
            if magnitude >= _DIVERGENCE_THRESHOLD_HIGH:
                return "extreme"
            elif magnitude >= _DIVERGENCE_THRESHOLD_MEDIUM:
                return "high"
            elif magnitude >= _DIVERGENCE_THRESHOLD_LOW:
                return "medium"
            return "low"

        # 商品看多 vs 指数看空 → 中等风险
        if divergence_type == "commodity_bullish_index_bearish":
            if magnitude >= _DIVERGENCE_THRESHOLD_HIGH:
                return "high"
            elif magnitude >= _DIVERGENCE_THRESHOLD_MEDIUM:
                return "medium"
            return "low"

        return "low"

    # ═════════════════════════════════════════════════════════════════════
    # 辅助映射方法
    # ═════════════════════════════════════════════════════════════════════

    @staticmethod
    def _get_etf_market_code(underlying: str) -> Optional[int]:
        """获取 ETF 标的对应的市场编号

        上交所 ETF (5xxxxx) → Market=8
        深交所 ETF (1xxxxx) → Market=9
        """
        if underlying.startswith("5"):
            return _MARKET_SH_ETF
        elif underlying.startswith("1"):
            return _MARKET_SZ_ETF
        return None

    @staticmethod
    def _get_commodity_market_code(variety: str) -> Optional[int]:
        """获取商品品种对应的市场编号

        SHFE 品种 → 6
        DCE 品种  → 5
        CZCE 品种 → 28
        """
        from .option_code_parser import COMMODITY_VARIETIES

        info = COMMODITY_VARIETIES.get(variety, {})
        return info.get("market_code")

    @staticmethod
    def _market_code_to_type(market_code: int) -> str:
        """将市场编号映射为 TDXAdapter 的 market_type 字符串

        Args:
            market_code: TDX 市场编号

        Returns:
            MarketType 字符串
        """
        mapping = {
            _MARKET_SH_ETF: "option_sh",
            _MARKET_SZ_ETF: "option_sz",
            _MARKET_CFFEX: "option_zj",
            _MARKET_SHFE_OPT: "coption_sh",
            _MARKET_DCE_OPT: "coption_dl",
            _MARKET_CZCE_OPT: "coption_zz",
        }
        return mapping.get(market_code, "option_zj")

    # ═════════════════════════════════════════════════════════════════════
    # 缓存与历史管理
    # ═════════════════════════════════════════════════════════════════════

    def _get_cache(self, key: str) -> Any:
        """从缓存读取"""
        if self._cache_ns is None:
            return None
        try:
            return self._cache_ns.get(key)
        except Exception:
            return None

    def _set_cache(self, key: str, value: Any, ttl: float = 1800) -> None:
        """写入缓存"""
        if self._cache_ns is None:
            return
        try:
            self._cache_ns.set(key, value, ttl=ttl)
        except Exception as e:
            self._logger.debug("缓存写入失败: %s — %s", key, e)

    def _record_pcr_history(self, key: str, pcr_value: float) -> None:
        """记录 PCR 历史 (用于趋势判断)

        保留最近 N 个值.

        Args:
            key:       历史键
            pcr_value: PCR 值
        """
        if key not in self._pcr_history:
            self._pcr_history[key] = []

        self._pcr_history[key].append(pcr_value)

        # 限制长度
        if len(self._pcr_history[key]) > self._history_max_len:
            self._pcr_history[key] = self._pcr_history[key][-self._history_max_len:]

    # ═════════════════════════════════════════════════════════════════════
    # 配置加载
    # ═════════════════════════════════════════════════════════════════════

    def _load_weights(self) -> Dict[str, float]:
        """从配置加载综合 PCR 权重"""
        if self._config is None:
            return DEFAULT_COMPOSITE_WEIGHTS.copy()

        try:
            weights = self._config.get_section("option_tolerance.full_pcr_weights")
            if weights and isinstance(weights, dict):
                return {
                    "etf": float(weights.get("stock_etf", DEFAULT_COMPOSITE_WEIGHTS["etf"])),
                    "cffex": float(weights.get("cffex", DEFAULT_COMPOSITE_WEIGHTS["cffex"])),
                    "commodity": float(weights.get("commodity", DEFAULT_COMPOSITE_WEIGHTS["commodity"])),
                }
        except Exception:
            pass

        return DEFAULT_COMPOSITE_WEIGHTS.copy()

    def _load_thresholds(self) -> Dict[str, Any]:
        """从配置加载 PCR 阈值"""
        if self._config is None:
            return DEFAULT_PCR_THRESHOLDS.copy()

        try:
            thresholds = self._config.get_section("option_tolerance.pcr_thresholds")
            if thresholds and isinstance(thresholds, dict):
                result = DEFAULT_PCR_THRESHOLDS.copy()
                for category in ("stock_etf_option", "cffex_option", "commodity_option"):
                    cat_data = thresholds.get(category, {})
                    if not isinstance(cat_data, dict):
                        continue

                    prefix = {
                        "stock_etf_option": "etf",
                        "cffex_option": "cffex",
                        "commodity_option": "commodity",
                    }.get(category, "")

                    if prefix:
                        for suffix in ("warning_high", "warning_low", "extreme_high", "extreme_low"):
                            key = f"{prefix}_{suffix}"
                            if suffix in cat_data:
                                result[key] = cat_data[suffix]

                return result
        except Exception:
            pass

        return DEFAULT_PCR_THRESHOLDS.copy()

    def _load_cache_ttls(self) -> Dict[str, float]:
        """从配置加载缓存 TTL"""
        if self._config is None:
            return {
                "etf_options": 1800,
                "cffex_options": 1800,
                "commodity_options": 1800,
                "pcr_full": 1800,
            }

        try:
            ttl_config = self._config.get_section("cache.ttl")
            if ttl_config and isinstance(ttl_config, dict):
                return {
                    "etf_options": float(ttl_config.get("etf_options", 1800)),
                    "cffex_options": float(ttl_config.get("cffex_options", 1800)),
                    "commodity_options": float(ttl_config.get("commodity_options", 1800)),
                    "pcr_full": float(ttl_config.get("pcr_full", 1800)),
                }
        except Exception:
            pass

        return {
            "etf_options": 1800,
            "cffex_options": 1800,
            "commodity_options": 1800,
            "pcr_full": 1800,
        }

    # ═════════════════════════════════════════════════════════════════════
    # 状态查询
    # ═════════════════════════════════════════════════════════════════════

    @property
    def parser(self) -> OptionCodeParser:
        """获取底层解析器实例"""
        return self._parser

    @property
    def weights(self) -> Dict[str, float]:
        """当前权重配置"""
        return self._weights.copy()

    @property
    def thresholds(self) -> Dict[str, Any]:
        """当前阈值配置"""
        return self._thresholds.copy()

    @property
    def pcr_history(self) -> Dict[str, List[float]]:
        """PCR 历史数据"""
        return self._pcr_history.copy()

    def clear_cache(self) -> None:
        """清除 PCR 缓存"""
        if self._cache_ns:
            self._cache_ns.clear()
        self._logger.info("PCR 缓存已清空")

    def __repr__(self) -> str:
        return (
            f"OptionPCREngine("
            f"weights=ETF:{self._weights['etf']:.0%}/"
            f"CFFEX:{self._weights['cffex']:.0%}/"
            f"Comm:{self._weights['commodity']:.0%})"
        )
