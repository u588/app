#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AiStock V11.5 — 宏观估值信号引擎 (Macro Valuation Signal Engine)

V11.5: PE only, no PB — 去除PB百分位, 仅使用PE百分位构建估值信号

数据来源:
  - TDX扩展端口 Market 38/50: 宏观经济指标
  - AK适配器 (在线优先): PE估值数据 (中证指数官网)
  - DatabaseReader (PostgreSQL降级): PE估值百分位

宏观指标 (TDX扩展端口):
  - 3_PMI:  制造业PMI       → 经济景气度
  - 3_PMIH: 非制造业PMI     → 服务业景气度
  - 5_TRY:  社融存量同比     → 信用扩张
  - 5_TRL:  人民币贷款同比   → 信贷扩张
  - 5_CNTY: 央行外汇占款     → 流动性
  - 5_SHS3M: Shibor3M       → 短端流动性
  - 8_ATY:  美国十年国债收益率 → 外部约束
  - 2_CPI:  CPI同比         → 通胀
  - 2_PPI:  PPI同比         → 工业通胀

估值数据 (在线优先, PG降级):
  - 在线优先: AK适配器 get_index_pe_csindex() 获取中证指数PE
  - PG降级: DatabaseReader.get_valuation_percentiles() 从PostgreSQL获取
  - V11.5: PE only, no PB — 不再使用PB百分位

信号输出:
  MacroValuationSignal.composite_signal ∈ [-100, 100]
  MacroValuationSignal.composite_direction ∈ {"bullish", "bearish", "neutral"}

权重 (从 market_state.yaml macro_valuation_weights 加载):
  pmi:        0.20  — 景气度
  credit:     0.20  — 信用扩张
  liquidity:  0.20  — 流动性
  inflation:  0.10  — 通胀
  valuation:  0.30  — 估值百分位 (PE only, 权重最高, 最直接)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

# ─── Type aliases ──────────────────────────────────────────────────────────────
TDXAdapter = Any
DatabaseReader = Any
AKAdapter = Any
ConfigService = Any
CacheService = Any

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# 数据类定义
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class MacroValuationSignal:
    """宏观估值信号 (V11.5: PE only, no PB)"""
    pmi_signal: float = 0.0         # 景气度信号
    credit_signal: float = 0.0      # 信用扩张信号
    liquidity_signal: float = 0.0   # 流动性信号
    inflation_signal: float = 0.0   # 通胀信号
    valuation_signal: float = 0.0   # 估值信号
    composite_signal: float = 0.0   # 综合信号 [-100, 100]
    composite_direction: str = "neutral"  # 综合方向

    # ─── 原始数据快照 ──────────────────────────────────────────────────
    pmi_latest: float = 0.0         # 最新PMI
    pmih_latest: float = 0.0        # 最新非制造业PMI
    social_finance_yoy: float = 0.0 # 社融同比
    loan_yoy: float = 0.0           # 贷款同比
    shibor_3m: float = 0.0          # Shibor3M
    us_10y_yield: float = 0.0       # 美国10年国债
    cpi_latest: float = 0.0         # 最新CPI
    ppi_latest: float = 0.0         # 最新PPI
    pe_percentile_avg: float = 0.0  # 平均PE百分位 (V11.5: PE only, no PB)
    data_available: bool = False    # 数据是否可用

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pmi_signal": round(self.pmi_signal, 2),
            "credit_signal": round(self.credit_signal, 2),
            "liquidity_signal": round(self.liquidity_signal, 2),
            "inflation_signal": round(self.inflation_signal, 2),
            "valuation_signal": round(self.valuation_signal, 2),
            "composite_signal": round(self.composite_signal, 2),
            "composite_direction": self.composite_direction,
            "snapshot": {
                "pmi": round(self.pmi_latest, 2),
                "pmih": round(self.pmih_latest, 2),
                "social_finance_yoy": round(self.social_finance_yoy, 4),
                "loan_yoy": round(self.loan_yoy, 4),
                "shibor_3m": round(self.shibor_3m, 4),
                "us_10y_yield": round(self.us_10y_yield, 4),
                "cpi": round(self.cpi_latest, 4),
                "ppi": round(self.ppi_latest, 4),
                "pe_percentile_avg": round(self.pe_percentile_avg, 4),
            },
            "data_available": self.data_available,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# V11 默认值
# ═══════════════════════════════════════════════════════════════════════════════

_DEFAULT_MACRO_VALUATION_WEIGHTS = {
    "pmi": 0.20,
    "credit": 0.20,
    "liquidity": 0.20,
    "inflation": 0.10,
    "valuation": 0.30,
}

# TDX宏观指标代码 (market=38 或 50, 38为扩展接口的基金/宏观市场)
_DEFAULT_MACRO_INDICATORS = [
    {"code": "3_PMI",   "market": 38, "name": "制造业PMI",      "sub_signal": "pmi"},
    {"code": "3_PMIH",  "market": 38, "name": "非制造业PMI",    "sub_signal": "pmih"},
    {"code": "5_TRY",   "market": 38, "name": "社融存量同比",   "sub_signal": "social_finance"},
    {"code": "5_TRL",   "market": 38, "name": "人民币贷款同比", "sub_signal": "loan"},
    {"code": "5_CNTY",  "market": 38, "name": "央行外汇占款",   "sub_signal": "fx_occupation"},
    {"code": "5_SHS3M", "market": 38, "name": "Shibor3M",       "sub_signal": "shibor_3m"},
    {"code": "8_ATY",   "market": 38, "name": "美国十年国债",   "sub_signal": "us_10y"},
    {"code": "2_CPI",   "market": 38, "name": "CPI同比",        "sub_signal": "cpi"},
    {"code": "2_PPI",   "market": 38, "name": "PPI同比",        "sub_signal": "ppi"},
]

_DEFAULT_VALUATION_CODES = ["000300", "000905", "000852"]


# ═══════════════════════════════════════════════════════════════════════════════
# 宏观估值信号引擎 V11.5
# ═══════════════════════════════════════════════════════════════════════════════

class MacroValuationEngine:
    """宏观估值信号引擎 (V11.5: PE only, no PB)

    基于宏观经济指标和估值数据, 构建宏观估值信号分量,
    作为7分量模型的第5分量 (权重0.10)。

    宏观数据为月频为主, 估值数据为日频, 引擎同时处理两种频率。

    V11.5 更新:
    - 去除PB百分位, 仅使用PE百分位构建估值信号
    - 在线优先: 通过AK适配器获取中证指数PE数据
    - PG降级: 通过DatabaseReader获取PostgreSQL估值数据

    使用方式:
        >>> engine = MacroValuationEngine(
        ...     tdx_adapter=tdx,
        ...     db_reader=db,
        ...     ak_adapter=ak,
        ...     config=config_svc,
        ... )
        >>> signal = engine.calculate()
    """

    def __init__(
        self,
        tdx_adapter: TDXAdapter,
        db_reader: Optional[DatabaseReader] = None,
        ak_adapter: Optional[AKAdapter] = None,
        config: Optional[ConfigService] = None,
        cache: Optional[CacheService] = None,
        logger_instance: Optional[logging.Logger] = None,
    ) -> None:
        """初始化宏观估值信号引擎

        Args:
            tdx_adapter: TDXAdapter 实例 (扩展端口获取宏观指标)
            db_reader: DatabaseReader 实例 (获取估值数据, PG降级)
            ak_adapter: AK适配器实例 (在线获取PE数据, 在线优先)
            config: ConfigService 实例
            cache: CacheService 实例
            logger_instance: Logger 实例
        """
        self._tdx = tdx_adapter
        self._db = db_reader
        self._ak = ak_adapter
        self._config = config
        self._cache = cache
        self._logger = logger_instance or logger

        # 从 ConfigService 加载配置
        self._weights = self._load_weights()
        self._indicators = self._load_indicators()
        self._valuation_codes = self._load_valuation_codes()

        self._logger.info(
            "MacroValuationEngine V11.5 初始化完成 | 宏观指标: %d, 估值代码: %d, 权重: %s, AK: %s",
            len(self._indicators),
            len(self._valuation_codes),
            {k: round(v, 2) for k, v in self._weights.items()},
            "可用" if self._ak is not None else "不可用",
        )

    # ──────────────────────────────────────────────────────────────
    #  配置加载
    # ──────────────────────────────────────────────────────────────

    def _load_weights(self) -> Dict[str, float]:
        """从 ConfigService 加载宏观估值权重"""
        if self._config is not None:
            weights = self._config.get("market_state.macro_valuation_weights", None)
            if weights and isinstance(weights, dict):
                return {k: float(v) for k, v in weights.items()}
        return dict(_DEFAULT_MACRO_VALUATION_WEIGHTS)

    def _load_indicators(self) -> List[Dict[str, Any]]:
        """从 ConfigService 加载宏观指标配置"""
        if self._config is not None:
            indicators = self._config.get("codes.macro_valuation.macro_indicators", None)
            if indicators and isinstance(indicators, list):
                return indicators
        return list(_DEFAULT_MACRO_INDICATORS)

    def _load_valuation_codes(self) -> List[str]:
        """从 ConfigService 加载估值代码"""
        if self._config is not None:
            codes = self._config.get("codes.macro_valuation.valuation_codes", None)
            if codes and isinstance(codes, list):
                return codes
            # 回退到 codes.valuation.codes
            codes = self._config.get("codes.valuation.codes", None)
            if codes and isinstance(codes, list):
                return codes
        return list(_DEFAULT_VALUATION_CODES)

    # ═══════════════════════════════════════════════════════════════════════
    # 核心计算
    # ═══════════════════════════════════════════════════════════════════════

    def calculate(self) -> MacroValuationSignal:
        """计算宏观估值信号

        Returns:
            MacroValuationSignal 实例
        """
        start_time = time.time()
        signal = MacroValuationSignal()

        # 1. 批量获取宏观指标数据
        macro_data = self._fetch_all_macro_indicators()

        # 2. 计算各子信号
        signal.pmi_signal = self._calc_pmi_signal(macro_data, signal)
        signal.credit_signal = self._calc_credit_signal(macro_data, signal)
        signal.liquidity_signal = self._calc_liquidity_signal(macro_data, signal)
        signal.inflation_signal = self._calc_inflation_signal(macro_data, signal)
        signal.valuation_signal = self._calc_valuation_signal(signal)

        # 3. 检查是否有任何子信号有数据
        has_data = any([
            signal.pmi_signal != 0.0,
            signal.credit_signal != 0.0,
            signal.liquidity_signal != 0.0,
            signal.inflation_signal != 0.0,
            signal.valuation_signal != 0.0,
        ])

        if not has_data:
            self._logger.warning("MacroValuationEngine: 无可用数据, 返回中性信号")
            return signal

        signal.data_available = True

        # 4. 加权合成
        w = self._weights
        composite = (
            signal.pmi_signal * w.get("pmi", 0.20)
            + signal.credit_signal * w.get("credit", 0.20)
            + signal.liquidity_signal * w.get("liquidity", 0.20)
            + signal.inflation_signal * w.get("inflation", 0.10)
            + signal.valuation_signal * w.get("valuation", 0.30)
        )
        composite = max(-100.0, min(100.0, composite))
        signal.composite_signal = composite
        signal.composite_direction = self._signal_to_direction(composite)

        elapsed = (time.time() - start_time) * 1000
        self._logger.info(
            "MacroValuationEngine V11.5 计算: 综合=%.1f [%s] | PMI=%.1f 信用=%.1f "
            "流动性=%.1f 通胀=%.1f 估值=%.1f (PE only) | %.0fms",
            composite, signal.composite_direction,
            signal.pmi_signal, signal.credit_signal,
            signal.liquidity_signal, signal.inflation_signal,
            signal.valuation_signal, elapsed,
        )

        return signal

    # ═══════════════════════════════════════════════════════════════════════
    # 子信号计算
    # ═══════════════════════════════════════════════════════════════════════

    def _calc_pmi_signal(
        self, macro_data: Dict[str, pd.DataFrame], signal: MacroValuationSignal,
    ) -> float:
        """计算景气度信号 (PMI + 非制造业PMI)

        逻辑:
        - PMI > 50 → 扩张区间, 偏多
        - PMI < 50 → 收缩区间, 偏空
        - PMI = 50 → 荣枯线, 中性
        - 使用PMI趋势 (5月移动均值变化) 增强信号
        """
        pmi_df = macro_data.get("pmi")
        pmih_df = macro_data.get("pmih")

        pmi_value = 50.0  # 默认中性

        if pmi_df is not None and not pmi_df.empty:
            close = pmi_df["close"].values.astype(float) if "close" in pmi_df.columns else np.array([])
            if len(close) >= 1:
                pmi_value = float(close[-1])
                signal.pmi_latest = pmi_value

        if pmih_df is not None and not pmih_df.empty:
            close = pmih_df["close"].values.astype(float) if "close" in pmih_df.columns else np.array([])
            if len(close) >= 1:
                signal.pmih_latest = float(close[-1])

        # PMI信号: 以50为中性点, 每1个点对应10分信号
        pmi_signal = (pmi_value - 50.0) * 10.0

        # PMI趋势增强: 如果5日均值趋势向上, 额外加10分
        if pmi_df is not None and not pmi_df.empty:
            close = pmi_df["close"].values.astype(float) if "close" in pmi_df.columns else np.array([])
            if len(close) >= 10:
                recent_avg = float(np.mean(close[-5:]))
                prev_avg = float(np.mean(close[-10:-5]))
                if recent_avg > prev_avg:
                    pmi_signal += 10.0
                elif recent_avg < prev_avg:
                    pmi_signal -= 10.0

        return max(-100.0, min(100.0, pmi_signal))

    def _calc_credit_signal(
        self, macro_data: Dict[str, pd.DataFrame], signal: MacroValuationSignal,
    ) -> float:
        """计算信用扩张信号 (社融 + 贷款)

        逻辑:
        - 社融同比上升 → 信用扩张, 偏多
        - 贷款同比上升 → 信贷扩张, 偏多
        - 社融/贷款数据为月频, 使用最近值和趋势变化
        """
        sf_df = macro_data.get("social_finance")  # 社融
        loan_df = macro_data.get("loan")           # 贷款

        sf_signal = 0.0
        loan_signal = 0.0

        # 社融信号
        if sf_df is not None and not sf_df.empty:
            close = sf_df["close"].values.astype(float) if "close" in sf_df.columns else np.array([])
            if len(close) >= 1:
                sf_latest = float(close[-1])
                signal.social_finance_yoy = sf_latest
                # 社融同比 > 0 → 扩张, 每1%对应5分
                sf_signal = sf_latest * 5.0

        # 贷款信号
        if loan_df is not None and not loan_df.empty:
            close = loan_df["close"].values.astype(float) if "close" in loan_df.columns else np.array([])
            if len(close) >= 1:
                loan_latest = float(close[-1])
                signal.loan_yoy = loan_latest
                loan_signal = loan_latest * 5.0

        # 综合: 社融权重60%, 贷款权重40%
        credit_signal = sf_signal * 0.6 + loan_signal * 0.4
        return max(-100.0, min(100.0, credit_signal))

    def _calc_liquidity_signal(
        self, macro_data: Dict[str, pd.DataFrame], signal: MacroValuationSignal,
    ) -> float:
        """计算流动性信号 (Shibor3M + 外汇占款 + 美国国债)

        逻辑:
        - Shibor3M 下降 → 流动性宽松, 偏多
        - 外汇占款增加 → 基础货币投放, 偏多
        - 美国国债收益率下降 → 外部约束减轻, 偏多
        """
        shibor_df = macro_data.get("shibor_3m")
        fx_df = macro_data.get("fx_occupation")
        us10y_df = macro_data.get("us_10y")

        shibor_signal = 0.0
        fx_signal = 0.0
        us_signal = 0.0

        # Shibor3M信号: 利率下降→流动性宽松→看多
        if shibor_df is not None and not shibor_df.empty:
            close = shibor_df["close"].values.astype(float) if "close" in shibor_df.columns else np.array([])
            if len(close) >= 1:
                signal.shibor_3m = float(close[-1])
            if len(close) >= 6 and close[-6] > 0:
                # 5日变化率 (反向: 下降=正信号)
                change_5d = (close[-1] / close[-6] - 1.0) * 100.0
                shibor_signal = -change_5d * 5.0  # 反向: 利率降→正信号

        # 外汇占款信号: 增加→正
        if fx_df is not None and not fx_df.empty:
            close = fx_df["close"].values.astype(float) if "close" in fx_df.columns else np.array([])
            if len(close) >= 6 and close[-6] > 0:
                change_5d = (close[-1] / close[-6] - 1.0) * 100.0
                fx_signal = change_5d * 3.0

        # 美国10年国债信号: 收益率降→正
        if us10y_df is not None and not us10y_df.empty:
            close = us10y_df["close"].values.astype(float) if "close" in us10y_df.columns else np.array([])
            if len(close) >= 1:
                signal.us_10y_yield = float(close[-1])
            if len(close) >= 6 and close[-6] > 0:
                change_5d = (close[-1] / close[-6] - 1.0) * 100.0
                us_signal = -change_5d * 3.0  # 反向: 收益率降→正信号

        # 综合: Shibor 40%, 外汇占款 30%, 美国10年 30%
        liquidity_signal = shibor_signal * 0.4 + fx_signal * 0.3 + us_signal * 0.3
        return max(-100.0, min(100.0, liquidity_signal))

    def _calc_inflation_signal(
        self, macro_data: Dict[str, pd.DataFrame], signal: MacroValuationSignal,
    ) -> float:
        """计算通胀信号 (CPI + PPI)

        逻辑:
        - 温和通胀 (CPI 1-3%) → 偏多 (经济健康)
        - 通缩 (CPI < 0) → 偏空
        - 高通胀 (CPI > 5%) → 偏空 (政策收紧风险)
        - PPI 反映工业品价格, 与企业盈利正相关
        """
        cpi_df = macro_data.get("cpi")
        ppi_df = macro_data.get("ppi")

        cpi_signal = 0.0
        ppi_signal = 0.0

        # CPI信号
        if cpi_df is not None and not cpi_df.empty:
            close = cpi_df["close"].values.astype(float) if "close" in cpi_df.columns else np.array([])
            if len(close) >= 1:
                cpi_value = float(close[-1])
                signal.cpi_latest = cpi_value
                # 最优区间: 1-3%, 低于0或高于5都不好
                if cpi_value < 0:
                    cpi_signal = -50.0  # 通缩
                elif cpi_value < 1:
                    cpi_signal = -20.0  # 通胀偏低
                elif cpi_value <= 3:
                    cpi_signal = 30.0   # 温和通胀, 最优
                elif cpi_value <= 5:
                    cpi_signal = -20.0  # 通胀偏高
                else:
                    cpi_signal = -50.0  # 高通胀

        # PPI信号
        if ppi_df is not None and not ppi_df.empty:
            close = ppi_df["close"].values.astype(float) if "close" in ppi_df.columns else np.array([])
            if len(close) >= 1:
                ppi_value = float(close[-1])
                signal.ppi_latest = ppi_value
                # PPI为正→企业定价能力→偏多; PPI为负→工业通缩→偏空
                ppi_signal = ppi_value * 10.0

        # 综合: CPI 60%, PPI 40%
        inflation_signal = cpi_signal * 0.6 + ppi_signal * 0.4
        return max(-100.0, min(100.0, inflation_signal))

    def _calc_valuation_signal(self, signal: MacroValuationSignal) -> float:
        """计算估值信号 (PE百分位, V11.5 纯PE模式)

        V11.5: 去除PB, 仅使用PE百分位
        - pe_percentile: 从在线API或PostgreSQL获取, 由DatabaseReader计算
        - 信号公式: (50 - pe_pct_avg) * 2.0
        """
        if self._db is None or not hasattr(self._db, 'is_connected') or not self._db.is_connected:
            # V11.5: 即使DB未连接, 也可以通过在线API获取
            if self._ak is None:
                self._logger.debug("MacroValuationEngine: 数据库和AK均不可用")
                return 0.0

        try:
            pe_percentiles = []

            for code in self._valuation_codes:
                try:
                    pe_pct = self._get_pe_percentile_for_code(code)
                    if not np.isnan(pe_pct):
                        pe_percentiles.append(pe_pct)
                except Exception as e:
                    self._logger.debug("估值数据获取失败 %s: %s", code, e)

            if not pe_percentiles:
                self._logger.warning("MacroValuationEngine: 所有指数PE数据均不可用")
                return 0.0

            avg_pe_pct = float(np.mean(pe_percentiles))
            signal.pe_percentile_avg = avg_pe_pct

            # 纯PE百分位信号
            val_signal = (50.0 - avg_pe_pct) * 2.0
            return max(-100.0, min(100.0, val_signal))

        except Exception as e:
            self._logger.warning("估值信号计算失败: %s", e)
            return 0.0

    def _get_pe_percentile_for_code(self, code: str) -> float:
        """获取单个指数的PE百分位 (在线优先, PG降级)"""
        # 1. 在线优先
        if self._ak is not None and hasattr(self._ak, 'get_index_pe_csindex'):
            try:
                df = self._ak.get_index_pe_csindex(code)
                if df is not None and not df.empty and "pe_ttm" in df.columns:
                    # 计算百分位
                    from data_service.database_reader import _calc_percentile_rank
                    pe_series = pd.to_numeric(df["pe_ttm"], errors="coerce").dropna()
                    if len(pe_series) >= 10:
                        pct_series = _calc_percentile_rank(pe_series, 2500)
                        return float(pct_series.iloc[0])
            except Exception as e:
                self._logger.debug("在线PE获取失败 %s: %s, 尝试PG降级", code, e)

        # 2. PG降级
        if self._db is not None and hasattr(self._db, 'is_connected') and self._db.is_connected:
            try:
                if hasattr(self._db, 'get_valuation_percentiles'):
                    val_data = self._db.get_valuation_percentiles(code, days=500)
                    if val_data.get("data_available", False):
                        return float(val_data.get("pe_percentile", np.nan))
                else:
                    df = self._db.get_index_pe(code, days=500)
                    if df is not None and not df.empty:
                        latest = df.iloc[0]
                        pe_pct = float(latest.get("pe_percentile", 0))
                        if pe_pct != 0 and not np.isnan(pe_pct):
                            return pe_pct
            except Exception as e:
                self._logger.debug("PG PE获取失败 %s: %s", code, e)

        return np.nan

    # ═══════════════════════════════════════════════════════════════════════
    # 数据获取
    # ═══════════════════════════════════════════════════════════════════════

    def _fetch_all_macro_indicators(self) -> Dict[str, pd.DataFrame]:
        """批量获取所有宏观指标数据"""
        result: Dict[str, pd.DataFrame] = {}

        for cfg in self._indicators:
            code = cfg.get("code", "")
            market = cfg.get("market", 38)
            sub_signal = cfg.get("sub_signal", code)
            name = cfg.get("name", code)

            try:
                df = self._fetch_indicator_data(code, market)
                if df is not None and not df.empty:
                    result[sub_signal] = df
                else:
                    self._logger.debug("宏观指标 %s (%s) 数据为空", name, code)
            except Exception as e:
                self._logger.debug("宏观指标 %s (%s) 获取失败: %s", name, code, e)

        self._logger.info(
            "MacroValuationEngine: 获取 %d/%d 宏观指标数据",
            len(result), len(self._indicators),
        )
        return result

    def _fetch_indicator_data(
        self, code: str, market: int = 38, count: int = 60,
    ) -> Optional[pd.DataFrame]:
        """获取单个宏观指标数据 (月频为主, 取60条)"""
        if self._tdx is None:
            return None
        try:
            return self._tdx.get_macro_data(code=code, market=market, count=count)
        except Exception as e:
            self._logger.debug("宏观指标数据获取失败 %s: %s", code, e)
            return None

    # ═══════════════════════════════════════════════════════════════════════
    # 辅助方法
    # ═══════════════════════════════════════════════════════════════════════

    @staticmethod
    def _signal_to_direction(signal: float) -> str:
        """信号值→方向"""
        if signal > 20:
            return "bullish"
        elif signal < -20:
            return "bearish"
        return "neutral"
