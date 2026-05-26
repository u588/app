"""
AiStock V8 — 宏观信号引擎 (Macro Signal Engine)

V8 NEW — 处理 99 宏观指标 (TDX 扩展端口 + akshare)

5 大指标组:
  1. inflation (通胀)  — CPI/PPI/CPI食品/PPIRM/CoreCPI
  2. growth (增长)     — GDP/PMI制造业/PMI非制造/工业增加值/FAI/社零
  3. liquidity (流动性) — SHIBOR3M/M2/社融/信用脉冲/DR007/LPR1Y
  4. external_risk (外部风险) — 美10Y/USDCNY/中美利差/ISM PMI/EIA/LME/美元指数/联邦基金利率
  5. market_sentiment (市场情绪) — 融资余额比/新增投资者/换手率/北向资金/QVIX/PCR

数据源:
  - TDX 扩展端口 (7721): 宏观指标K线 (market=50)
  - akshare: 中美利差/ISM PMI/EIA/LME库存/国债收益率

计算结果:
  - 5 组评分 (0-100)
  - 综合宏观评分
  - 趋势方向
  - 预警信号

配置驱动: system_config.yaml → macro_indicators section
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
TDXAdapter = Any          # data_service.tdx_adapter.TDXAdapter
AKAdapter = Any           # data_service.ak_adapter.AKAdapter
ConfigService = Any       # base_services.config_service.ConfigService
CacheService = Any        # base_services.cache_service.CacheService

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# 数据类定义
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class IndicatorResult:
    """单个宏观指标结果

    Attributes:
        code:        指标代码
        name:        指标名称
        group:       所属分组
        value:       当前值
        prev_value:  前值
        change:      变化值
        change_pct:  变化率 (%)
        direction:   方向 'positive' / 'negative' / 'neutral' / 'contrarian'
        signal:      信号评分 (0-100)
        surprise:    意外程度 (实际 vs 预期偏离)
    """
    code: str
    name: str = ""
    group: str = ""
    value: float = 0.0
    prev_value: float = 0.0
    change: float = 0.0
    change_pct: float = 0.0
    direction: str = "neutral"
    signal: float = 50.0
    surprise: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code, "name": self.name, "group": self.group,
            "value": round(self.value, 4), "prev_value": round(self.prev_value, 4),
            "change": round(self.change, 4), "change_pct": round(self.change_pct, 4),
            "direction": self.direction, "signal": round(self.signal, 2),
            "surprise": round(self.surprise, 4),
        }


@dataclass
class GroupResult:
    """指标组结果

    Attributes:
        group_name:  组名
        weight:      组权重
        score:       组评分 (0-100)
        direction:   组方向
        indicators:  组内各指标结果
        warning:     组预警
    """
    group_name: str
    weight: float = 0.20
    score: float = 50.0
    direction: str = "neutral"
    indicators: Dict[str, IndicatorResult] = field(default_factory=dict)
    warning: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "group_name": self.group_name,
            "weight": round(self.weight, 4),
            "score": round(self.score, 2),
            "direction": self.direction,
            "indicators": {k: v.to_dict() for k, v in self.indicators.items()},
            "warning": self.warning,
        }


@dataclass
class MacroSignalResult:
    """宏观信号综合结果

    Attributes:
        groups:               各组结果
        composite_macro_score: 综合宏观评分 (0-100)
        trend_direction:       趋势方向 'improving' / 'deteriorating' / 'stable'
        warnings:              预警信号列表
        indicator_count:       已处理指标数
        data_quality:          数据质量 {'available': int, 'missing': int}
        timestamp:             计算时间戳
    """
    groups: Dict[str, GroupResult] = field(default_factory=dict)
    composite_macro_score: float = 50.0
    trend_direction: str = "stable"
    warnings: List[str] = field(default_factory=list)
    indicator_count: int = 0
    data_quality: Dict[str, int] = field(default_factory=lambda: {"available": 0, "missing": 0})
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "groups": {k: v.to_dict() for k, v in self.groups.items()},
            "composite_macro_score": round(self.composite_macro_score, 2),
            "trend_direction": self.trend_direction,
            "warnings": self.warnings,
            "indicator_count": self.indicator_count,
            "data_quality": self.data_quality,
            "timestamp": self.timestamp,
        }

    def __repr__(self) -> str:
        return (
            f"MacroSignalResult(score={self.composite_macro_score:.1f} "
            f"trend={self.trend_direction} indicators={self.indicator_count})"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 默认指标配置
# ═══════════════════════════════════════════════════════════════════════════════

# 指标组权重 (来自 system_config.yaml macro_indicators section)
DEFAULT_GROUP_WEIGHTS = {
    "inflation": 0.20,
    "growth": 0.25,
    "liquidity": 0.25,
    "external_risk": 0.18,
    "market_sentiment": 0.12,
}

# 通胀组指标
INFLATION_INDICATORS = {
    "CPI":      {"code": "2_CPI",  "name": "CPI同比",   "direction": "negative", "warning_high": 3.0, "warning_low": -1.0},
    "PPI":      {"code": "2_PPI",  "name": "PPI同比",   "direction": "neutral",  "warning_high": 5.0, "warning_low": -3.0},
    "CPI_FOOD": {"code": "2_CPIF", "name": "CPI食品",   "direction": "negative", "warning_high": 6.0, "warning_low": -2.0},
    "PPI_RM":   {"code": "2_PPIRM","name": "PPIRM同比", "direction": "negative", "warning_high": 8.0, "warning_low": -4.0},
    "CORE_CPI": {"code": "2_CCPI", "name": "核心CPI",   "direction": "negative", "warning_high": 2.5, "warning_low": 0.0},
}

# 增长组指标
GROWTH_INDICATORS = {
    "GDP":                {"code": "1_GDPI", "name": "GDP同比",       "direction": "positive", "warning_high": 6.0, "warning_low": 4.0},
    "PMI_MANUFACTURING":  {"code": "1_PMI",  "name": "制造业PMI",     "direction": "positive", "warning_high": 55.0,"warning_low": 48.0},
    "PMI_NON_MANUFACTURING": {"code": "1_NPMI", "name": "非制造业PMI","direction": "positive", "warning_high": 58.0,"warning_low": 50.0},
    "INDUSTRIAL_OUTPUT":  {"code": "1_GYI",  "name": "工业增加值",    "direction": "positive", "warning_high": 7.0, "warning_low": 4.0},
    "FAI":                {"code": "1_FAI",  "name": "固定资产投资",  "direction": "positive", "warning_high": 8.0, "warning_low": 3.0},
    "RETAIL_SALES":       {"code": "1_RTS",  "name": "社会消费品零售","direction": "positive", "warning_high": 10.0,"warning_low": 5.0},
}

# 流动性组指标
LIQUIDITY_INDICATORS = {
    "SHIBOR_3M":      {"code": "5_SHS3M", "name": "SHIBOR 3M",    "direction": "negative", "warning_high": 3.5, "warning_low": 1.5},
    "M2_YOY":         {"code": "5_M2",    "name": "M2同比",       "direction": "positive", "warning_high": 12.0,"warning_low": 7.0},
    "SOCIAL_FINANCING":{"code": "5_SFS",   "name": "社融规模",     "direction": "positive", "warning_high": 15.0,"warning_low": 8.0},
    "CREDIT_IMPULSE": {"code": "5_CI",     "name": "信用脉冲",     "direction": "positive", "warning_high": 20.0,"warning_low": 5.0},
    "DR007":          {"code": "5_DR007",  "name": "DR007",        "direction": "negative", "warning_high": 2.5, "warning_low": 1.5},
    "LPR_1Y":         {"code": "5_LPR1Y", "name": "LPR 1年期",    "direction": "negative", "warning_high": 4.5, "warning_low": 3.0},
}

# 外部风险组指标
EXTERNAL_RISK_INDICATORS = {
    "US_10Y_YIELD":    {"code": "8_ATY",   "name": "美国10Y国债",   "direction": "negative", "warning_high": 4.5, "warning_low": 3.0},
    "USD_CNY":         {"code": "5_RMBUS", "name": "美元/人民币",    "direction": "negative", "warning_high": 7.3, "warning_low": 6.5},
    "CN_US_BOND_SPREAD":{"code": "8_CUS10", "name": "中美利差",      "direction": "negative", "warning_high": 0.0, "warning_low": -2.0},
    "ISM_PMI":         {"code": "8_ISM",   "name": "ISM PMI",       "direction": "positive", "warning_high": 55.0,"warning_low": 48.0},
    "EIA_CRUDE":       {"code": "8_EIA",   "name": "EIA原油库存变化","direction": "neutral",  "warning_high": 5.0, "warning_low": -5.0},
    "LME_INVENTORY":   {"code": "8_LME",   "name": "LME库存变化",   "direction": "inverse",  "warning_high": 5.0, "warning_low": -5.0},
    "US_DOLLAR_INDEX": {"code": "8_DXY",   "name": "美元指数",      "direction": "negative", "warning_high": 105.0,"warning_low": 95.0},
    "FED_FUNDS_RATE":  {"code": "8_FFR",   "name": "联邦基金利率",  "direction": "negative", "warning_high": 5.5, "warning_low": 2.0},
}

# 市场情绪组指标
MARKET_SENTIMENT_INDICATORS = {
    "MARGIN_TRADE_RATIO": {"code": "6_MGTR", "name": "融资余额比",  "direction": "contrarian","warning_high": 0.12,  "warning_low": 0.07},
    "NEW_INVESTOR_COUNT": {"code": "6_NIC",   "name": "新增投资者",  "direction": "contrarian","warning_high": 200000,"warning_low": 50000},
    "TURNOVER_RATE":      {"code": "6_TVR",   "name": "换手率",      "direction": "contrarian","warning_high": 2.5,   "warning_low": 0.8},
    "NORTHBOUND_FLOW":    {"code": "6_NBF",   "name": "北向资金",    "direction": "positive", "warning_high": 100.0, "warning_low": -80.0},
    "QVIX_INDEX":         {"code": "6_QVIX",  "name": "QVIX波动率",  "direction": "contrarian","warning_high": 35.0,  "warning_low": 15.0},
    "PUT_CALL_RATIO":     {"code": "6_PCR",   "name": "PCR",         "direction": "contrarian","warning_high": 1.3,   "warning_low": 0.7},
}

# 全部指标组映射
ALL_INDICATOR_GROUPS = {
    "inflation": INFLATION_INDICATORS,
    "growth": GROWTH_INDICATORS,
    "liquidity": LIQUIDITY_INDICATORS,
    "external_risk": EXTERNAL_RISK_INDICATORS,
    "market_sentiment": MARKET_SENTIMENT_INDICATORS,
}

# TDX 宏观市场编号
TDX_MACRO_MARKET = 50


# ═══════════════════════════════════════════════════════════════════════════════
# 宏观信号引擎
# ═══════════════════════════════════════════════════════════════════════════════

class MacroSignalEngine:
    """宏观信号引擎 (V8 NEW)

    处理 99 宏观指标, 分 5 组计算评分, 输出综合宏观评分.

    数据源:
      - TDX 扩展端口: 国内宏观指标 (CPI/PPI/PMI/M2/SHIBOR...)
      - akshare: 海外宏观指标 (中美利差/ISM PMI/EIA/LME)

    5 大指标组:
      1. inflation (通胀, 20%): CPI/PPI/CoreCPI...
      2. growth (增长, 25%): GDP/PMI/工业增加值/社零...
      3. liquidity (流动性, 25%): SHIBOR/M2/社融/DR007/LPR...
      4. external_risk (外部风险, 18%): 美10Y/USDCNY/中美利差/ISM/EIA/DXY...
      5. market_sentiment (市场情绪, 12%): 融资余额/北向/QVIX/PCR...

    使用方式:
        >>> engine = MacroSignalEngine(
        ...     tdx_adapter=tdx,
        ...     ak_adapter=ak,
        ...     config=config,
        ... )
        >>> result = engine.calculate_macro_signals()
        >>> print(result.composite_macro_score, result.trend_direction)
    """

    def __init__(
        self,
        tdx_adapter: Optional[TDXAdapter] = None,
        ak_adapter: Optional[AKAdapter] = None,
        config: Optional[ConfigService] = None,
        cache: Optional[CacheService] = None,
        logger_instance: Optional[logging.Logger] = None,
    ) -> None:
        """初始化宏观信号引擎

        Args:
            tdx_adapter:     TDXAdapter 实例 (扩展端口 7721)
            ak_adapter:      AKAdapter 实例 (海外宏观数据)
            config:          配置服务 (system_config.yaml macro_indicators section)
            cache:           缓存服务
            logger_instance: 自定义 logger
        """
        self._tdx = tdx_adapter
        self._ak = ak_adapter
        self._config = config
        self._cache = cache
        self._logger = logger_instance or logger

        # 加载配置
        self._group_weights = self._load_group_weights()
        self._indicator_groups = self._load_indicator_groups()
        self._macro_market = TDX_MACRO_MARKET

        # 统计指标总数
        total_indicators = sum(
            len(indicators) for indicators in self._indicator_groups.values()
        )

        self._logger.info(
            "MacroSignalEngine V8.0 初始化完成 | "
            "%d 组 / %d 指标 | TDX=%s AK=%s",
            len(self._indicator_groups), total_indicators,
            "已注入" if self._tdx else "未注入",
            "已注入" if self._ak else "未注入",
        )

    # ═══════════════════════════════════════════════════════════════════════
    # 核心计算方法
    # ═══════════════════════════════════════════════════════════════════════

    def calculate_macro_signals(self) -> MacroSignalResult:
        """计算宏观信号

        流程:
          1. 逐组获取指标数据
          2. 逐指标计算信号评分
          3. 加权汇总组评分
          4. 计算综合宏观评分
          5. 判断趋势方向
          6. 生成预警

        Returns:
            MacroSignalResult
        """
        start_time = time.time()

        groups: Dict[str, GroupResult] = {}
        available_count = 0
        missing_count = 0
        all_warnings: List[str] = []

        # 逐组计算
        for group_name, indicators in self._indicator_groups.items():
            group_weight = self._group_weights.get(group_name, 0.20)

            group_result = self._calculate_group(group_name, indicators, group_weight)
            groups[group_name] = group_result

            available_count += len([v for v in group_result.indicators.values() if v.signal != 50.0])
            missing_count += len([v for v in group_result.indicators.values() if v.signal == 50.0])

            if group_result.warning:
                all_warnings.append(f"[{group_name}] {group_result.warning}")

        # 综合宏观评分
        composite_score = self._calculate_composite_score(groups)

        # 趋势方向
        trend_direction = self._determine_trend_direction(groups)

        result = MacroSignalResult(
            groups=groups,
            composite_macro_score=composite_score,
            trend_direction=trend_direction,
            warnings=all_warnings,
            indicator_count=available_count + missing_count,
            data_quality={"available": available_count, "missing": missing_count},
        )

        elapsed = (time.time() - start_time) * 1000
        self._logger.info(
            "宏观信号: score=%.1f trend=%s | 通胀=%.1f 增长=%.1f 流动性=%.1f "
            "外部=%.1f 情绪=%.1f | 可用=%d 缺失=%d | warnings=%d | %.0fms",
            composite_score, trend_direction,
            groups.get("inflation", GroupResult("")).score,
            groups.get("growth", GroupResult("")).score,
            groups.get("liquidity", GroupResult("")).score,
            groups.get("external_risk", GroupResult("")).score,
            groups.get("market_sentiment", GroupResult("")).score,
            available_count, missing_count,
            len(all_warnings), elapsed,
        )

        return result

    # ═══════════════════════════════════════════════════════════════════════
    # 指标组计算
    # ═══════════════════════════════════════════════════════════════════════

    def _calculate_group(
        self,
        group_name: str,
        indicators: Dict[str, Dict[str, Any]],
        weight: float,
    ) -> GroupResult:
        """计算单个指标组

        Args:
            group_name: 组名
            indicators: 指标配置字典
            weight:     组权重

        Returns:
            GroupResult
        """
        indicator_results: Dict[str, IndicatorResult] = {}
        group_warning = ""

        for key, cfg in indicators.items():
            try:
                result = self._calculate_single_indicator(key, cfg, group_name)
                indicator_results[key] = result
            except Exception as e:
                self._logger.debug("宏观指标 %s 计算失败: %s", key, e)
                indicator_results[key] = IndicatorResult(
                    code=cfg.get("code", key),
                    name=cfg.get("name", key),
                    group=group_name,
                )

        # 组评分: 各指标信号加权平均 (等权)
        signals = [ir.signal for ir in indicator_results.values()]
        if signals:
            score = float(np.mean(signals))
        else:
            score = 50.0

        # 组方向
        if score >= 60:
            direction = "positive"
        elif score <= 40:
            direction = "negative"
        else:
            direction = "neutral"

        # 组预警
        extreme_indicators = [
            ir.name for ir in indicator_results.values()
            if ir.signal >= 80 or ir.signal <= 20
        ]
        if extreme_indicators:
            group_warning = f"极端指标: {', '.join(extreme_indicators[:3])}"

        return GroupResult(
            group_name=group_name,
            weight=weight,
            score=score,
            direction=direction,
            indicators=indicator_results,
            warning=group_warning,
        )

    def _calculate_single_indicator(
        self,
        key: str,
        cfg: Dict[str, Any],
        group_name: str,
    ) -> IndicatorResult:
        """计算单个宏观指标信号

        Args:
            key:        指标键名
            cfg:        指标配置
            group_name: 组名

        Returns:
            IndicatorResult
        """
        code = cfg.get("code", key)
        name = cfg.get("name", key)
        direction = cfg.get("direction", "neutral")
        warning_high = cfg.get("warning_high", 0.0)
        warning_low = cfg.get("warning_low", 0.0)

        # 获取指标数据
        value, prev_value = self._fetch_indicator_data(code, group_name)

        # 计算变化
        change = value - prev_value if prev_value != 0 else 0.0
        change_pct = (change / abs(prev_value) * 100.0) if prev_value != 0 else 0.0

        # 计算信号评分
        signal = self._calculate_indicator_signal(
            value, direction, warning_high, warning_low,
        )

        # 计算意外程度
        surprise = self._calculate_surprise(value, prev_value, warning_high, warning_low)

        return IndicatorResult(
            code=code, name=name, group=group_name,
            value=value, prev_value=prev_value,
            change=change, change_pct=change_pct,
            direction=direction, signal=signal,
            surprise=surprise,
        )

    # ═══════════════════════════════════════════════════════════════════════
    # 指标数据获取
    # ═══════════════════════════════════════════════════════════════════════

    def _fetch_indicator_data(
        self, code: str, group_name: str,
    ) -> Tuple[float, float]:
        """获取宏观指标数据

        优先使用 TDX 扩展端口, 回退到 akshare.

        Args:
            code:       指标代码
            group_name: 组名

        Returns:
            (current_value, previous_value)
        """
        value = 0.0
        prev_value = 0.0

        # 尝试 TDX
        if self._tdx is not None:
            try:
                df = self._tdx.get_macro_data(
                    code=code, market=self._macro_market, count=5,
                )
                if df is not None and not df.empty:
                    close_col = "close" if "close" in df.columns else None
                    if close_col is None:
                        # 尝试其他列名
                        for col in df.columns:
                            if col not in ("date", "year", "month", "day", "open", "high", "low", "volume", "amount"):
                                close_col = col
                                break

                    if close_col and len(df) >= 2:
                        try:
                            value = float(df[close_col].iloc[-1])
                            prev_value = float(df[close_col].iloc[-2])
                            return value, prev_value
                        except (ValueError, TypeError):
                            pass
            except Exception as e:
                self._logger.debug("TDX宏观指标 %s 获取失败: %s", code, e)

        # 尝试 akshare (针对特定指标)
        if self._ak is not None and group_name == "external_risk":
            value, prev_value = self._fetch_akshare_data(code, value, prev_value)

        return value, prev_value

    def _fetch_akshare_data(
        self, code: str, default_value: float, default_prev: float,
    ) -> Tuple[float, float]:
        """通过 akshare 获取海外宏观数据

        针对特定指标:
          - 中美利差: bond_zh_us
          - ISM PMI: ism_pmi
          - EIA: eia_crude
          - LME: lme_stock
          - 美元指数: global_index
        """
        try:
            # 中美利差
            if "CUS" in code:
                df = self._ak.get_auxiliary_data("bond_zh_us")
                if df is not None and not df.empty:
                    # 尝试提取利差
                    val_col = None
                    for col in df.columns:
                        if "利差" in str(col) or "spread" in str(col).lower():
                            val_col = col
                            break
                    if val_col is None and len(df.columns) > 1:
                        val_col = df.columns[-1]

                    if val_col:
                        try:
                            val = float(df[val_col].iloc[-1])
                            prev = float(df[val_col].iloc[-2]) if len(df) >= 2 else val
                            return val, prev
                        except (ValueError, TypeError, IndexError):
                            pass

            # ISM PMI
            elif "ISM" in code:
                df = self._ak.get_auxiliary_data("ism_pmi")
                if df is not None and not df.empty:
                    val_col = df.columns[-1] if len(df.columns) > 0 else None
                    if val_col:
                        try:
                            val = float(df[val_col].iloc[-1])
                            prev = float(df[val_col].iloc[-2]) if len(df) >= 2 else val
                            return val, prev
                        except (ValueError, TypeError, IndexError):
                            pass

            # EIA 原油
            elif "EIA" in code:
                df = self._ak.get_auxiliary_data("eia_crude")
                if df is not None and not df.empty:
                    val_col = df.columns[-1] if len(df.columns) > 0 else None
                    if val_col:
                        try:
                            val = float(df[val_col].iloc[-1])
                            prev = float(df[val_col].iloc[-2]) if len(df) >= 2 else val
                            return val, prev
                        except (ValueError, TypeError, IndexError):
                            pass

            # LME 库存
            elif "LME" in code:
                df = self._ak.get_auxiliary_data("lme_stock")
                if df is not None and not df.empty:
                    val_col = df.columns[-1] if len(df.columns) > 0 else None
                    if val_col:
                        try:
                            val = float(df[val_col].iloc[-1])
                            prev = float(df[val_col].iloc[-2]) if len(df) >= 2 else val
                            return val, prev
                        except (ValueError, TypeError, IndexError):
                            pass

        except Exception as e:
            self._logger.debug("akshare 宏观数据 %s 获取失败: %s", code, e)

        return default_value, default_prev

    # ═══════════════════════════════════════════════════════════════════════
    # 信号计算
    # ═══════════════════════════════════════════════════════════════════════

    @staticmethod
    def _calculate_indicator_signal(
        value: float,
        direction: str,
        warning_high: float,
        warning_low: float,
    ) -> float:
        """计算单个指标信号评分 (0-100)

        评分逻辑:
          - direction = 'positive': 值越高越好 → 高值=高分
          - direction = 'negative': 值越低越好 → 低值=高分
          - direction = 'neutral':  中间值最好 → 接近中值=高分
          - direction = 'contrarian': 极端值反转 → 中间区域高分
          - direction = 'inverse': 与值反向 → 值越低越好

        Args:
            value:        当前值
            direction:    方向
            warning_high: 高预警阈值
            warning_low:  低预警阈值

        Returns:
            信号评分 (0-100)
        """
        if value == 0.0 and warning_high == 0.0 and warning_low == 0.0:
            return 50.0  # 无数据

        if direction == "positive":
            # 值越高越好
            if warning_high == warning_low:
                return 50.0
            # 值在 warning_low 以下 → 低分
            # 值在 warning_high 以上 → 高分
            range_size = warning_high - warning_low
            if range_size == 0:
                return 50.0
            normalized = (value - warning_low) / range_size
            score = max(0.0, min(100.0, normalized * 100.0))

        elif direction == "negative":
            # 值越低越好
            if warning_high == warning_low:
                return 50.0
            range_size = warning_high - warning_low
            if range_size == 0:
                return 50.0
            normalized = (warning_high - value) / range_size
            score = max(0.0, min(100.0, normalized * 100.0))

        elif direction == "contrarian":
            # 反向指标: 中间区域最好, 极端值反转
            if warning_high == warning_low:
                return 50.0
            mid = (warning_high + warning_low) / 2.0
            half_range = (warning_high - warning_low) / 2.0
            if half_range == 0:
                return 50.0
            # 越接近中值 → 分数越高
            deviation = abs(value - mid) / half_range
            score = max(0.0, min(100.0, (1.0 - deviation) * 100.0))

        elif direction == "inverse":
            # 反向: 值越低, 评分越高 (类似 negative)
            if warning_high == warning_low:
                return 50.0
            range_size = warning_high - warning_low
            if range_size == 0:
                return 50.0
            normalized = (warning_high - value) / range_size
            score = max(0.0, min(100.0, normalized * 100.0))

        else:  # neutral
            # 中性: 中间区域最好
            if warning_high == warning_low:
                return 50.0
            mid = (warning_high + warning_low) / 2.0
            half_range = (warning_high - warning_low) / 2.0
            if half_range == 0:
                return 50.0
            deviation = abs(value - mid) / half_range
            score = max(0.0, min(100.0, (1.0 - min(1.0, deviation)) * 100.0))

        return score

    @staticmethod
    def _calculate_surprise(
        value: float,
        prev_value: float,
        warning_high: float,
        warning_low: float,
    ) -> float:
        """计算指标意外程度

        值偏离正常范围的程度.

        Returns:
            surprise (0 = 无意外, 正值 = 高于预期, 负值 = 低于预期)
        """
        if warning_high == 0 and warning_low == 0:
            return 0.0

        mid = (warning_high + warning_low) / 2.0
        half_range = (warning_high - warning_low) / 2.0

        if half_range == 0:
            return 0.0

        surprise = (value - mid) / half_range
        return max(-2.0, min(2.0, surprise))

    # ═══════════════════════════════════════════════════════════════════════
    # 综合计算
    # ═══════════════════════════════════════════════════════════════════════

    def _calculate_composite_score(
        self, groups: Dict[str, GroupResult],
    ) -> float:
        """计算综合宏观评分"""
        total = 0.0
        for group_name, group in groups.items():
            weight = self._group_weights.get(group_name, 0.20)
            total += group.score * weight

        return max(0.0, min(100.0, total))

    def _determine_trend_direction(
        self, groups: Dict[str, GroupResult],
    ) -> str:
        """判断趋势方向

        基于增长+流动性两大组的评分:
          - 两组均 > 55 → improving
          - 两组均 < 45 → deteriorating
          - 其他 → stable
        """
        growth_score = groups.get("growth", GroupResult("")).score
        liquidity_score = groups.get("liquidity", GroupResult("")).score

        if growth_score > 55 and liquidity_score > 55:
            return "improving"
        elif growth_score < 45 and liquidity_score < 45:
            return "deteriorating"
        else:
            return "stable"

    # ═══════════════════════════════════════════════════════════════════════
    # 配置加载
    # ═══════════════════════════════════════════════════════════════════════

    def _load_group_weights(self) -> Dict[str, float]:
        """加载指标组权重"""
        if self._config is not None:
            try:
                weights = {}
                for group_name in DEFAULT_GROUP_WEIGHTS:
                    cfg = self._config.get(f"macro_indicators.{group_name}.weight", None)
                    if cfg is not None:
                        weights[group_name] = float(cfg)
                    else:
                        weights[group_name] = DEFAULT_GROUP_WEIGHTS[group_name]
                return weights
            except Exception:
                pass
        return dict(DEFAULT_GROUP_WEIGHTS)

    def _load_indicator_groups(self) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """加载指标组配置

        优先从 system_config.yaml macro_indicators section 加载,
        回退到内置默认值.
        """
        if self._config is not None:
            try:
                cfg_groups = self._config.get("macro_indicators", {})
                if cfg_groups:
                    result: Dict[str, Dict[str, Dict[str, Any]]] = {}
                    for group_name, group_cfg in cfg_groups.items():
                        if not isinstance(group_cfg, dict):
                            continue
                        if "indicators" not in group_cfg:
                            continue

                        indicators = group_cfg.get("indicators", {})
                        if isinstance(indicators, dict) and indicators:
                            result[group_name] = {}
                            for key, ind_cfg in indicators.items():
                                if isinstance(ind_cfg, dict):
                                    result[group_name][key] = ind_cfg
                            if result[group_name]:
                                continue

                    if result:
                        return result
            except Exception:
                pass

        return dict(ALL_INDICATOR_GROUPS)
