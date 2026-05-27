#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AiStock V11 — 基金资金流信号引擎 (Fund Flow Signal Engine)

V11 NEW: 基于 TDX 扩展接口 Market 38 数据构建基金资金流信号分量

数据来源 (TDX扩展端口, market=38):
  - 7_RZ:  沪深融资余额 → 融资杠杆信号
  - 7_RQ:  沪深融券余额 → 融券对冲信号
  - 7_TETF: ETF基金规模   → ETF资金流信号
  - 9_990014: 偏股混基指数 → 股债轮动信号 (偏股端)
  - 9_990015: 偏债混基指数 → 股债轮动信号 (偏债端)
  - 9_990011: 主动股基指数 → 主动/被动轮动信号 (主动端)
  - 9_990012: 被动股基指数 → 主动/被动轮动信号 (被动端)
  - 9_990002: 股票型基金指数 → 基金动量信号

重要数据质量说明:
  - TON(北上资金)/TOS(南下资金) 自 2023-08 起为 TDX 线性插值, 不纳入计算
  - 偏股/偏债基金比值 (990014/990015) 为隐藏金矿, 反映机构股债轮动方向

信号输出:
  FundFlowSignal.composite_signal ∈ [-100, 100]
  FundFlowSignal.composite_direction ∈ {"bullish", "bearish", "neutral"}

权重 (从 market_state.yaml 加载):
  margin:             0.25  — 融资融券余额变化
  etf_scale:          0.20  — ETF规模变化
  stock_bond_rotation: 0.25 — 偏股/偏债基金轮动
  active_passive:     0.15  — 主动/被动基金轮动
  fund_momentum:      0.15  — 股票型基金动量
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
ConfigService = Any
CacheService = Any

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# 数据类定义
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class FundFlowSignal:
    """基金资金流信号"""
    margin_signal: float = 0.0          # 融资融券信号
    etf_scale_signal: float = 0.0       # ETF规模信号
    stock_bond_rotation: float = 0.0    # 偏股/偏债轮动信号
    active_passive_signal: float = 0.0  # 主动/被动轮动信号
    fund_momentum: float = 0.0          # 基金动量信号
    composite_signal: float = 0.0       # 综合信号 [-100, 100]
    composite_direction: str = "neutral" # 综合方向

    # ─── 原始数据快照 (用于报告) ──────────────────────────────────────────
    margin_long_latest: float = 0.0     # 最新融资余额(亿)
    margin_short_latest: float = 0.0    # 最新融券余额(亿)
    etf_scale_latest: float = 0.0       # 最新ETF规模(亿)
    stock_fund_idx: float = 0.0         # 偏股混基指数
    bond_fund_idx: float = 0.0          # 偏债混基指数
    active_fund_idx: float = 0.0        # 主动股基指数
    passive_fund_idx: float = 0.0       # 被动股基指数
    stock_type_fund_idx: float = 0.0    # 股票型基金指数
    data_available: bool = False        # 数据是否可用

    def to_dict(self) -> Dict[str, Any]:
        return {
            "margin_signal": round(self.margin_signal, 2),
            "etf_scale_signal": round(self.etf_scale_signal, 2),
            "stock_bond_rotation": round(self.stock_bond_rotation, 2),
            "active_passive_signal": round(self.active_passive_signal, 2),
            "fund_momentum": round(self.fund_momentum, 2),
            "composite_signal": round(self.composite_signal, 2),
            "composite_direction": self.composite_direction,
            "snapshot": {
                "margin_long": round(self.margin_long_latest, 2),
                "margin_short": round(self.margin_short_latest, 2),
                "etf_scale": round(self.etf_scale_latest, 2),
                "stock_fund_idx": round(self.stock_fund_idx, 4),
                "bond_fund_idx": round(self.bond_fund_idx, 4),
                "active_fund_idx": round(self.active_fund_idx, 4),
                "passive_fund_idx": round(self.passive_fund_idx, 4),
                "stock_type_fund_idx": round(self.stock_type_fund_idx, 4),
            },
            "data_available": self.data_available,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# V11 默认值 (仅 ConfigService 不可用时的回退)
# ═══════════════════════════════════════════════════════════════════════════════

_DEFAULT_FUND_FLOW_WEIGHTS = {
    "margin": 0.25,
    "etf_scale": 0.20,
    "stock_bond_rotation": 0.25,
    "active_passive": 0.15,
    "fund_momentum": 0.15,
}

# TDX扩展接口 Market 38 指标代码映射
_DEFAULT_FUND_FLOW_INDICATORS = [
    {"code": "7_RZ",    "market": 38, "name": "沪深融资余额",  "sub_signal": "margin_long"},
    {"code": "7_RQ",    "market": 38, "name": "沪深融券余额",  "sub_signal": "margin_short"},
    {"code": "7_TETF",  "market": 38, "name": "ETF基金规模",  "sub_signal": "etf_scale"},
    {"code": "9_990014","market": 38, "name": "偏股混基指数",  "sub_signal": "stock_fund"},
    {"code": "9_990015","market": 38, "name": "偏债混基指数",  "sub_signal": "bond_fund"},
    {"code": "9_990011","market": 38, "name": "主动股基指数",  "sub_signal": "active_fund"},
    {"code": "9_990012","market": 38, "name": "被动股基指数",  "sub_signal": "passive_fund"},
    {"code": "9_990002","market": 38, "name": "股票型基金指数", "sub_signal": "fund_index"},
]


# ═══════════════════════════════════════════════════════════════════════════════
# 基金资金流信号引擎 V11
# ═══════════════════════════════════════════════════════════════════════════════

class FundFlowEngine:
    """基金资金流信号引擎 (V11 NEW)

    基于 TDX 扩展接口 Market 38 的资金流和基金指数数据,
    构建基金资金流信号分量, 作为6分量模型的第4分量 (权重0.20)。

    使用方式:
        >>> engine = FundFlowEngine(
        ...     data_service=tdx_adapter,
        ...     config=config_svc,
        ... )
        >>> signal = engine.calculate()
    """

    def __init__(
        self,
        data_service: TDXAdapter,
        config: Optional[ConfigService] = None,
        cache: Optional[CacheService] = None,
        logger_instance: Optional[logging.Logger] = None,
    ) -> None:
        """初始化基金资金流信号引擎

        Args:
            data_service: TDXAdapter 实例 (扩展端口)
            config: ConfigService 实例
            cache: CacheService 实例
            logger_instance: Logger 实例
        """
        self._tdx = data_service
        self._config = config
        self._cache = cache
        self._logger = logger_instance or logger

        # 从 ConfigService 加载配置
        self._weights = self._load_weights()
        self._indicators = self._load_indicators()

        self._logger.info(
            "FundFlowEngine V11 初始化完成 | 指标: %d, 权重: %s",
            len(self._indicators),
            {k: round(v, 2) for k, v in self._weights.items()},
        )

    # ──────────────────────────────────────────────────────────────
    #  配置加载
    # ──────────────────────────────────────────────────────────────

    def _load_weights(self) -> Dict[str, float]:
        """从 ConfigService 加载基金资金流权重"""
        if self._config is not None:
            weights = self._config.get("market_state.fund_flow_weights", None)
            if weights and isinstance(weights, dict):
                return {k: float(v) for k, v in weights.items()}
        return dict(_DEFAULT_FUND_FLOW_WEIGHTS)

    def _load_indicators(self) -> List[Dict[str, Any]]:
        """从 ConfigService 加载指标配置"""
        if self._config is not None:
            indicators = self._config.get("codes.fund_flow.indicators", None)
            if indicators and isinstance(indicators, list):
                return indicators
        return list(_DEFAULT_FUND_FLOW_INDICATORS)

    # ═══════════════════════════════════════════════════════════════════════
    # 核心计算
    # ═══════════════════════════════════════════════════════════════════════

    def calculate(self) -> FundFlowSignal:
        """计算基金资金流信号

        Returns:
            FundFlowSignal 实例
        """
        start_time = time.time()
        signal = FundFlowSignal()

        # 1. 批量获取所有指标数据
        data_map = self._fetch_all_indicators()
        if not data_map:
            self._logger.warning("FundFlowEngine: 无可用数据, 返回中性信号")
            return signal

        signal.data_available = True

        # 2. 计算各子信号
        signal.margin_signal = self._calc_margin_signal(data_map, signal)
        signal.etf_scale_signal = self._calc_etf_scale_signal(data_map, signal)
        signal.stock_bond_rotation = self._calc_stock_bond_rotation(data_map, signal)
        signal.active_passive_signal = self._calc_active_passive_signal(data_map, signal)
        signal.fund_momentum = self._calc_fund_momentum(data_map, signal)

        # 3. 加权合成
        w = self._weights
        composite = (
            signal.margin_signal * w.get("margin", 0.25)
            + signal.etf_scale_signal * w.get("etf_scale", 0.20)
            + signal.stock_bond_rotation * w.get("stock_bond_rotation", 0.25)
            + signal.active_passive_signal * w.get("active_passive", 0.15)
            + signal.fund_momentum * w.get("fund_momentum", 0.15)
        )
        composite = max(-100.0, min(100.0, composite))
        signal.composite_signal = composite
        signal.composite_direction = self._signal_to_direction(composite)

        elapsed = (time.time() - start_time) * 1000
        self._logger.info(
            "FundFlowEngine 计算: 综合=%.1f [%s] | 融资=%.1f ETF=%.1f "
            "股债轮动=%.1f 主被动=%.1f 动量=%.1f | %.0fms",
            composite, signal.composite_direction,
            signal.margin_signal, signal.etf_scale_signal,
            signal.stock_bond_rotation, signal.active_passive_signal,
            signal.fund_momentum, elapsed,
        )

        return signal

    # ═══════════════════════════════════════════════════════════════════════
    # 子信号计算
    # ═══════════════════════════════════════════════════════════════════════

    def _calc_margin_signal(
        self, data_map: Dict[str, pd.DataFrame], signal: FundFlowSignal,
    ) -> float:
        """计算融资融券信号

        逻辑:
        - 融资余额环比增加 → 看多 (杠杆资金流入)
        - 融券余额环比增加 → 看空 (对冲资金增加)
        - 融资净变化率与融券净变化率之差构成信号
        """
        rz_df = data_map.get("margin_long")  # 融资余额
        rq_df = data_map.get("margin_short")  # 融券余额

        if rz_df is None or rz_df.empty:
            return 0.0

        close = rz_df["close"].values.astype(float) if "close" in rz_df.columns else np.array([])
        if len(close) < 2:
            return 0.0

        signal.margin_long_latest = float(close[-1])

        # 融资余额5日变化率
        rz_change_5d = 0.0
        if len(close) >= 6 and close[-6] > 0:
            rz_change_5d = (close[-1] / close[-6] - 1.0) * 100.0

        # 融券余额5日变化率
        rq_change_5d = 0.0
        if rq_df is not None and not rq_df.empty:
            rq_close = rq_df["close"].values.astype(float) if "close" in rq_df.columns else np.array([])
            if len(rq_close) >= 1:
                signal.margin_short_latest = float(rq_close[-1])
            if len(rq_close) >= 6 and rq_close[-6] > 0:
                rq_change_5d = (rq_close[-1] / rq_close[-6] - 1.0) * 100.0

        # 信号: 融资增加 + 融券减少 = 看多; 反之看空
        margin_signal = (rz_change_5d - rq_change_5d) * 10.0
        return max(-100.0, min(100.0, margin_signal))

    def _calc_etf_scale_signal(
        self, data_map: Dict[str, pd.DataFrame], signal: FundFlowSignal,
    ) -> float:
        """计算ETF规模变化信号

        逻辑:
        - ETF规模增加 → 资金通过ETF流入市场, 看多
        - ETF规模减少 → 资金从ETF撤出, 看空
        """
        etf_df = data_map.get("etf_scale")
        if etf_df is None or etf_df.empty:
            return 0.0

        close = etf_df["close"].values.astype(float) if "close" in etf_df.columns else np.array([])
        if len(close) < 2:
            return 0.0

        signal.etf_scale_latest = float(close[-1])

        # 5日变化率
        change_5d = 0.0
        if len(close) >= 6 and close[-6] > 0:
            change_5d = (close[-1] / close[-6] - 1.0) * 100.0

        # 20日变化率 (中期趋势)
        change_20d = 0.0
        if len(close) >= 21 and close[-21] > 0:
            change_20d = (close[-1] / close[-21] - 1.0) * 100.0

        # 信号: 短期权重60%, 中期权重40%
        etf_signal = change_5d * 6.0 * 0.6 + change_20d * 3.0 * 0.4
        return max(-100.0, min(100.0, etf_signal))

    def _calc_stock_bond_rotation(
        self, data_map: Dict[str, pd.DataFrame], signal: FundFlowSignal,
    ) -> float:
        """计算偏股/偏债基金轮动信号 (隐藏金矿)

        逻辑:
        - 偏股基金指数/偏债基金指数 比值上升 → 机构资金从债转股, 看多
        - 比值下降 → 机构资金从股转债, 看空
        - 这是机构股债轮动的最直接指标
        """
        stock_df = data_map.get("stock_fund")   # 990014 偏股混基
        bond_df = data_map.get("bond_fund")      # 990015 偏债混基

        if stock_df is None or stock_df.empty or bond_df is None or bond_df.empty:
            return 0.0

        stock_close = stock_df["close"].values.astype(float) if "close" in stock_df.columns else np.array([])
        bond_close = bond_df["close"].values.astype(float) if "close" in bond_df.columns else np.array([])

        if len(stock_close) < 6 or len(bond_close) < 6:
            return 0.0

        signal.stock_fund_idx = float(stock_close[-1])
        signal.bond_fund_idx = float(bond_close[-1])

        # 计算比值序列 (取等长部分)
        min_len = min(len(stock_close), len(bond_close))
        ratio = stock_close[-min_len:] / np.maximum(bond_close[-min_len:], 1e-6)

        # 比值5日变化率
        ratio_change_5d = 0.0
        if len(ratio) >= 6 and ratio[-6] > 0:
            ratio_change_5d = (ratio[-1] / ratio[-6] - 1.0) * 100.0

        # 比值20日变化率
        ratio_change_20d = 0.0
        if len(ratio) >= 21 and ratio[-21] > 0:
            ratio_change_20d = (ratio[-1] / ratio[-21] - 1.0) * 100.0

        # 信号: 比值上升=股强于债=看多
        rotation_signal = ratio_change_5d * 8.0 * 0.6 + ratio_change_20d * 4.0 * 0.4
        return max(-100.0, min(100.0, rotation_signal))

    def _calc_active_passive_signal(
        self, data_map: Dict[str, pd.DataFrame], signal: FundFlowSignal,
    ) -> float:
        """计算主动/被动基金轮动信号

        逻辑:
        - 主动基金跑赢被动基金 → 市场选股 alpha 机会多, 偏多
        - 被动基金跑赢主动基金 → 市场趋于有效, 偏中性/防御
        """
        active_df = data_map.get("active_fund")   # 990011 主动股基
        passive_df = data_map.get("passive_fund")  # 990012 被动股基

        if active_df is None or active_df.empty or passive_df is None or passive_df.empty:
            return 0.0

        active_close = active_df["close"].values.astype(float) if "close" in active_df.columns else np.array([])
        passive_close = passive_df["close"].values.astype(float) if "close" in passive_df.columns else np.array([])

        if len(active_close) < 6 or len(passive_close) < 6:
            return 0.0

        signal.active_fund_idx = float(active_close[-1])
        signal.passive_fund_idx = float(passive_close[-1])

        # 计算比值序列
        min_len = min(len(active_close), len(passive_close))
        ratio = active_close[-min_len:] / np.maximum(passive_close[-min_len:], 1e-6)

        # 比值5日变化率
        ratio_change_5d = 0.0
        if len(ratio) >= 6 and ratio[-6] > 0:
            ratio_change_5d = (ratio[-1] / ratio[-6] - 1.0) * 100.0

        # 信号: 主动跑赢 → 偏多
        ap_signal = ratio_change_5d * 8.0
        return max(-100.0, min(100.0, ap_signal))

    def _calc_fund_momentum(
        self, data_map: Dict[str, pd.DataFrame], signal: FundFlowSignal,
    ) -> float:
        """计算股票型基金动量信号

        逻辑:
        - 股票型基金指数上涨 → 基金持仓整体盈利, 偏多
        - 股票型基金指数下跌 → 基金持仓整体亏损, 偏空
        - 使用20日动量作为中期趋势判断
        """
        fund_df = data_map.get("fund_index")  # 990002 股票型基金
        if fund_df is None or fund_df.empty:
            return 0.0

        close = fund_df["close"].values.astype(float) if "close" in fund_df.columns else np.array([])
        if len(close) < 21:
            return 0.0

        signal.stock_type_fund_idx = float(close[-1])

        # 20日动量
        momentum_20d = (close[-1] / close[-21] - 1.0) * 100.0

        # 5日动量 (短期)
        momentum_5d = (close[-1] / close[-6] - 1.0) * 100.0 if len(close) >= 6 and close[-6] > 0 else 0.0

        # 信号: 正动量→看多, 负动量→看空
        momentum_signal = momentum_5d * 3.0 * 0.4 + momentum_20d * 2.0 * 0.6
        return max(-100.0, min(100.0, momentum_signal))

    # ═══════════════════════════════════════════════════════════════════════
    # 数据获取
    # ═══════════════════════════════════════════════════════════════════════

    def _fetch_all_indicators(self) -> Dict[str, pd.DataFrame]:
        """批量获取所有资金流指标数据

        Returns:
            {sub_signal: DataFrame, ...} 映射
        """
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
                    self._logger.debug("资金流指标 %s (%s) 数据为空", name, code)
            except Exception as e:
                self._logger.warning("资金流指标 %s (%s) 获取失败: %s", name, code, e)

        self._logger.info("FundFlowEngine: 获取 %d/%d 指标数据", len(result), len(self._indicators))
        return result

    def _fetch_indicator_data(
        self, code: str, market: int = 38, count: int = 120,
    ) -> Optional[pd.DataFrame]:
        """获取单个指标数据 (TDX扩展端口, market=38)"""
        if self._tdx is None:
            return None
        try:
            return self._tdx.get_macro_data(code=code, market=market, count=count)
        except Exception as e:
            self._logger.debug("指标数据获取失败 %s: %s", code, e)
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
