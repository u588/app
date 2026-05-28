#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AiStock V11.5 — 资金流信号引擎 (Fund Flow Signal Engine)

V11.5 核心变更:
  - FundFlowEngine 重新激活, 从 DEPRECATED 升级为正式分量
  - 数据源: 仅使用 TDX 数据, 不引用 akshare 的
    ak.stock_individual_fund_flow() 和 ak.stock_market_fund_flow()
  - 构成7分量系统的第4分量 (权重0.10)

数据来源 (全部基于 TDX, 不使用 akshare fund flow 接口):
  1. 沪深300/中证500/中证1000 成交量变化率 → 市场整体资金流入/流出
  2. 大盘指数 vs 小盘指数 成交量比值变化 → 资金在大/小盘间轮动
  3. 股指期货成交量 vs 现货成交量比值 → 杠杆资金活跃度
  4. 市场成交量动量 (5日/20日) → 资金流趋势

信号逻辑:
  - 成交量上升+价格上升 → 资金主动流入 → 看多
  - 成交量上升+价格下降 → 资金主动流出 → 看空
  - 成交量萎缩 → 资金观望 → 中性偏空
  - 大盘成交量占比上升 → 资金流向大盘 → 结构性偏多(防御)
  - 小盘成交量占比上升 → 资金流向小盘 → 结构性偏多(进攻)

信号输出:
  FundFlowSignal.composite_signal ∈ [-100, 100]
  FundFlowSignal.composite_direction ∈ {"bullish", "bearish", "neutral"}

权重 (从 market_state.yaml fund_flow_weights 加载):
  volume_trend:  0.30  — 成交量趋势 (整体资金方向)
  size_rotation: 0.30  — 大小盘资金轮动
  leverage_ratio: 0.20  — 杠杆资金活跃度 (期货vs现货)
  momentum:      0.20  — 资金流短期动量
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
    """资金流信号 (V11.5 重新激活, 7分量系统)"""
    volume_trend_signal: float = 0.0       # 成交量趋势信号
    size_rotation_signal: float = 0.0      # 大小盘轮动信号
    leverage_signal: float = 0.0           # 杠杆资金信号
    momentum_signal: float = 0.0           # 资金流动量信号
    composite_signal: float = 0.0          # 综合信号 [-100, 100]
    composite_direction: str = "neutral"   # 综合方向

    # ─── 原始数据快照 ──────────────────────────────────────────────────
    volume_ratio_5d: float = 0.0           # 5日成交量比 (当前/5日均线)
    volume_ratio_20d: float = 0.0          # 20日成交量比 (当前/20日均线)
    large_cap_vol_pct: float = 0.0         # 大盘成交量占比
    small_cap_vol_pct: float = 0.0         # 小盘成交量占比
    size_vol_ratio_change: float = 0.0     # 大小盘成交量比值5日变化 (%)
    futures_spot_vol_ratio: float = 0.0    # 期货/现货成交量比
    data_available: bool = False           # 数据是否可用

    def to_dict(self) -> Dict[str, Any]:
        return {
            "volume_trend_signal": round(self.volume_trend_signal, 2),
            "size_rotation_signal": round(self.size_rotation_signal, 2),
            "leverage_signal": round(self.leverage_signal, 2),
            "momentum_signal": round(self.momentum_signal, 2),
            "composite_signal": round(self.composite_signal, 2),
            "composite_direction": self.composite_direction,
            "snapshot": {
                "volume_ratio_5d": round(self.volume_ratio_5d, 4),
                "volume_ratio_20d": round(self.volume_ratio_20d, 4),
                "large_cap_vol_pct": round(self.large_cap_vol_pct, 4),
                "small_cap_vol_pct": round(self.small_cap_vol_pct, 4),
                "size_vol_ratio_change": round(self.size_vol_ratio_change, 2),
                "futures_spot_vol_ratio": round(self.futures_spot_vol_ratio, 4),
            },
            "data_available": self.data_available,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# V11.5 默认值
# ═══════════════════════════════════════════════════════════════════════════════

_DEFAULT_FUND_FLOW_WEIGHTS = {
    "volume_trend": 0.30,
    "size_rotation": 0.30,
    "leverage_ratio": 0.20,
    "momentum": 0.20,
}

# 大盘指数 (沪深300 + 上证50)
_DEFAULT_LARGE_CAP_CODES = ["000300", "000016"]
# 小盘指数 (中证1000 + 创业板)
_DEFAULT_SMALL_CAP_CODES = ["000852", "399006"]
# 股指期货代码 (中金所主连)
_DEFAULT_INDEX_FUTURES_CODES = ["IFL8", "IML8"]


# ═══════════════════════════════════════════════════════════════════════════════
# 资金流信号引擎 V11.5
# ═══════════════════════════════════════════════════════════════════════════════

class FundFlowEngine:
    """资金流信号引擎 (V11.5 重新激活)

    基于TDX成交量数据构建资金流信号, 作为7分量模型的第4分量 (权重0.10)。
    不使用 akshare 的 ak.stock_individual_fund_flow() 和
    ak.stock_market_fund_flow() 接口。

    四维信号:
      1. volume_trend:   成交量趋势 — 整体资金方向
      2. size_rotation:  大小盘轮动 — 资金在规模间的轮动
      3. leverage_ratio: 杠杆资金活跃度 — 期货vs现货成交量比
      4. momentum:       资金流动量 — 短期资金流变化方向

    使用方式:
        >>> engine = FundFlowEngine(
        ...     tdx_adapter=tdx,
        ...     config=config_svc,
        ... )
        >>> signal = engine.calculate()
    """

    def __init__(
        self,
        tdx_adapter: Optional[TDXAdapter] = None,
        config: Optional[ConfigService] = None,
        cache: Optional[CacheService] = None,
        logger_instance: Optional[logging.Logger] = None,
    ) -> None:
        """初始化资金流信号引擎

        Args:
            tdx_adapter: TDXAdapter 实例 (标准+扩展端口)
            config: ConfigService 实例
            cache: CacheService 实例
            logger_instance: Logger 实例
        """
        self._tdx = tdx_adapter
        self._config = config
        self._cache = cache
        self._logger = logger_instance or logger

        # 从 ConfigService 加载配置
        self._weights = self._load_weights()
        self._large_cap_codes = self._load_large_cap_codes()
        self._small_cap_codes = self._load_small_cap_codes()
        self._futures_codes = self._load_futures_codes()

        self._logger.info(
            "FundFlowEngine V11.5 初始化完成 | 大盘: %s, 小盘: %s, 期货: %s, 权重: %s",
            self._large_cap_codes,
            self._small_cap_codes,
            self._futures_codes,
            {k: round(v, 2) for k, v in self._weights.items()},
        )

    # ──────────────────────────────────────────────────────────────
    #  配置加载
    # ──────────────────────────────────────────────────────────────

    def _load_weights(self) -> Dict[str, float]:
        """从 ConfigService 加载资金流权重"""
        if self._config is not None:
            weights = self._config.get("market_state.fund_flow_weights", None)
            if weights and isinstance(weights, dict):
                return {k: float(v) for k, v in weights.items()}
        return dict(_DEFAULT_FUND_FLOW_WEIGHTS)

    def _load_large_cap_codes(self) -> List[str]:
        """从 ConfigService 加载大盘指数代码"""
        if self._config is not None:
            codes = self._config.get("codes.fund_flow.large_cap_codes", None)
            if codes and isinstance(codes, list):
                return codes
        return list(_DEFAULT_LARGE_CAP_CODES)

    def _load_small_cap_codes(self) -> List[str]:
        """从 ConfigService 加载小盘指数代码"""
        if self._config is not None:
            codes = self._config.get("codes.fund_flow.small_cap_codes", None)
            if codes and isinstance(codes, list):
                return codes
        return list(_DEFAULT_SMALL_CAP_CODES)

    def _load_futures_codes(self) -> List[str]:
        """从 ConfigService 加载股指期货代码"""
        if self._config is not None:
            codes = self._config.get("codes.fund_flow.futures_codes", None)
            if codes and isinstance(codes, list):
                return codes
        return list(_DEFAULT_INDEX_FUTURES_CODES)

    # ═══════════════════════════════════════════════════════════════════════
    # 核心计算
    # ═══════════════════════════════════════════════════════════════════════

    def calculate(self) -> FundFlowSignal:
        """计算资金流信号

        Returns:
            FundFlowSignal 实例
        """
        start_time = time.time()
        signal = FundFlowSignal()

        if self._tdx is None:
            self._logger.warning("FundFlowEngine: TDXAdapter 不可用, 返回中性信号")
            return signal

        # 1. 获取大盘指数数据
        large_cap_data = self._fetch_index_data(self._large_cap_codes)
        # 2. 获取小盘指数数据
        small_cap_data = self._fetch_index_data(self._small_cap_codes)
        # 3. 获取股指期货数据
        futures_data = self._fetch_futures_data(self._futures_codes)

        # 检查是否有可用数据
        has_data = bool(large_cap_data) or bool(small_cap_data) or bool(futures_data)
        if not has_data:
            self._logger.warning("FundFlowEngine: 无可用数据, 返回中性信号")
            return signal

        signal.data_available = True

        # 4. 计算各子信号
        signal.volume_trend_signal = self._calc_volume_trend(
            large_cap_data, small_cap_data, signal,
        )
        signal.size_rotation_signal = self._calc_size_rotation(
            large_cap_data, small_cap_data, signal,
        )
        signal.leverage_signal = self._calc_leverage_signal(
            futures_data, large_cap_data, signal,
        )
        signal.momentum_signal = self._calc_momentum_signal(
            large_cap_data, small_cap_data, signal,
        )

        # 5. 加权合成
        w = self._weights
        composite = (
            signal.volume_trend_signal * w.get("volume_trend", 0.30)
            + signal.size_rotation_signal * w.get("size_rotation", 0.30)
            + signal.leverage_signal * w.get("leverage_ratio", 0.20)
            + signal.momentum_signal * w.get("momentum", 0.20)
        )
        composite = max(-100.0, min(100.0, composite))
        signal.composite_signal = composite
        signal.composite_direction = self._signal_to_direction(composite)

        elapsed = (time.time() - start_time) * 1000
        self._logger.info(
            "FundFlowEngine V11.5 计算: 综合=%.1f [%s] | 量趋势=%.1f 大小盘=%.1f "
            "杠杆=%.1f 动量=%.1f | %.0fms",
            composite, signal.composite_direction,
            signal.volume_trend_signal, signal.size_rotation_signal,
            signal.leverage_signal, signal.momentum_signal,
            elapsed,
        )

        return signal

    # ═══════════════════════════════════════════════════════════════════════
    # 子信号计算
    # ═══════════════════════════════════════════════════════════════════════

    def _calc_volume_trend(
        self,
        large_cap_data: Dict[str, pd.DataFrame],
        small_cap_data: Dict[str, pd.DataFrame],
        signal: FundFlowSignal,
    ) -> float:
        """计算成交量趋势信号 — 整体资金方向

        逻辑:
        - 计算全市场(大盘+小盘)总成交量的5日/20日比值
        - 成交量放大 → 资金活跃 → 看多(如果伴随价格涨)
        - 成交量萎缩 → 资金离场 → 看空
        - 结合价格涨跌方向: 放量上涨→正, 放量下跌→负
        """
        all_volumes = []
        all_close_changes = []

        for data_dict in [large_cap_data, small_cap_data]:
            for code, df in data_dict.items():
                if df is None or df.empty:
                    continue
                if "volume" not in df.columns or "close" not in df.columns:
                    continue

                vol = pd.to_numeric(df["volume"], errors="coerce").dropna()
                close = pd.to_numeric(df["close"], errors="coerce").dropna()

                if len(vol) >= 5:
                    vol_current = float(vol.iloc[-1])
                    vol_ma5 = float(vol.iloc[-5:].mean())
                    if vol_ma5 > 0:
                        all_volumes.append(vol_current / vol_ma5)

                if len(close) >= 2:
                    change = (float(close.iloc[-1]) / float(close.iloc[-2]) - 1.0) * 100.0
                    all_close_changes.append(change)

        if not all_volumes:
            return 0.0

        # 成交量比: 当前量 vs 5日均值
        avg_vol_ratio = float(np.mean(all_volumes))
        signal.volume_ratio_5d = avg_vol_ratio

        # 成交量比20日
        vol_ratios_20d = []
        for data_dict in [large_cap_data, small_cap_data]:
            for code, df in data_dict.items():
                if df is None or df.empty or "volume" not in df.columns:
                    continue
                vol = pd.to_numeric(df["volume"], errors="coerce").dropna()
                if len(vol) >= 20:
                    vol_current = float(vol.iloc[-1])
                    vol_ma20 = float(vol.iloc[-20:].mean())
                    if vol_ma20 > 0:
                        vol_ratios_20d.append(vol_current / vol_ma20)

        if vol_ratios_20d:
            signal.volume_ratio_20d = float(np.mean(vol_ratios_20d))

        # 成交量趋势信号
        # 成交量比 > 1.2 → 放量 (资金活跃)
        # 成交量比 < 0.8 → 缩量 (资金萎缩)
        vol_signal = 0.0
        if avg_vol_ratio > 1.2:
            vol_signal = min(100.0, (avg_vol_ratio - 1.0) * 100.0)
        elif avg_vol_ratio < 0.8:
            vol_signal = max(-100.0, (avg_vol_ratio - 1.0) * 100.0)
        else:
            # 0.8 ~ 1.2: 成交量正常范围, 微弱信号
            vol_signal = (avg_vol_ratio - 1.0) * 50.0

        # 价格方向修正: 放量+涨→正信号加强, 放量+跌→负信号
        if all_close_changes:
            avg_change = float(np.mean(all_close_changes))
            if avg_change > 0:
                vol_signal = abs(vol_signal) * 1.0  # 放量上涨 → 正信号
            elif avg_change < 0:
                vol_signal = -abs(vol_signal) * 1.0  # 放量下跌 → 负信号

        return max(-100.0, min(100.0, vol_signal))

    def _calc_size_rotation(
        self,
        large_cap_data: Dict[str, pd.DataFrame],
        small_cap_data: Dict[str, pd.DataFrame],
        signal: FundFlowSignal,
    ) -> float:
        """计算大小盘资金轮动信号

        逻辑:
        - 大盘成交量占比上升 → 资金流入大盘 (防御性, 偏谨慎但偏多大盘)
        - 小盘成交量占比上升 → 资金流入小盘 (进攻性, 偏乐观)
        - 通过成交量占比的5日变化来检测轮动
        """
        # 计算大盘/小盘成交量序列
        large_vol_series = self._aggregate_volume(large_cap_data)
        small_vol_series = self._aggregate_volume(small_cap_data)

        if large_vol_series is None or small_vol_series is None:
            return 0.0

        min_len = min(len(large_vol_series), len(small_vol_series))
        if min_len < 6:
            return 0.0

        large_vol = large_vol_series[-min_len:]
        small_vol = small_vol_series[-min_len:]

        # 大小盘比值
        total_vol = large_vol + small_vol
        total_vol = np.maximum(total_vol, 1e-10)  # 防除零

        large_pct = large_vol / total_vol
        small_pct = small_vol / total_vol

        # 当前占比
        signal.large_cap_vol_pct = float(large_pct[-1])
        signal.small_cap_vol_pct = float(small_pct[-1])

        # 大小盘成交量比值5日变化
        ratio = large_vol / np.maximum(small_vol, 1e-10)
        if len(ratio) >= 6 and ratio[-6] > 0:
            ratio_change_5d = (ratio[-1] / ratio[-6] - 1.0) * 100.0
        else:
            ratio_change_5d = 0.0
        signal.size_vol_ratio_change = ratio_change_5d

        # 轮动信号: 小盘占比上升→进攻性偏多(正), 大盘占比上升→防御性(微负)
        # 这是因为资金流向小盘通常是风险偏好上升的信号
        size_signal = -ratio_change_5d * 10.0  # 小盘占比上升→正信号

        return max(-100.0, min(100.0, size_signal))

    def _calc_leverage_signal(
        self,
        futures_data: Dict[str, pd.DataFrame],
        large_cap_data: Dict[str, pd.DataFrame],
        signal: FundFlowSignal,
    ) -> float:
        """计算杠杆资金活跃度信号 (期货vs现货成交量比)

        逻辑:
        - 股指期货成交量相对现货放大 → 杠杆资金活跃 → 市场情绪强
        - 期货成交量萎缩 → 杠杆资金离场 → 市场情绪弱
        - 期货/现货比值变化率作为信号
        """
        if not futures_data or not large_cap_data:
            return 0.0

        # 获取期货总成交量
        futures_vol = self._aggregate_volume(futures_data)
        spot_vol = self._aggregate_volume(large_cap_data)

        if futures_vol is None or spot_vol is None:
            return 0.0

        min_len = min(len(futures_vol), len(spot_vol))
        if min_len < 6:
            return 0.0

        f_vol = futures_vol[-min_len:]
        s_vol = spot_vol[-min_len:]

        # 期货/现货成交量比
        ratio = f_vol / np.maximum(s_vol, 1e-10)
        signal.futures_spot_vol_ratio = float(ratio[-1])

        # 比值5日变化率
        if len(ratio) >= 6 and ratio[-6] > 0:
            ratio_change = (ratio[-1] / ratio[-6] - 1.0) * 100.0
        else:
            ratio_change = 0.0

        # 杠杆信号: 期货放量→杠杆活跃→偏多; 期货缩量→杠杆离场→偏空
        # 放大倍数: 典型比值变化 [-10, 10] → 信号 [-100, 100]
        leverage_signal = ratio_change * 10.0

        return max(-100.0, min(100.0, leverage_signal))

    def _calc_momentum_signal(
        self,
        large_cap_data: Dict[str, pd.DataFrame],
        small_cap_data: Dict[str, pd.DataFrame],
        signal: FundFlowSignal,
    ) -> float:
        """计算资金流动量信号 (短期成交量变化方向)

        逻辑:
        - 成交量5日均值 > 20日均值 → 资金流入加速 → 偏多
        - 成交量5日均值 < 20日均值 → 资金流入减速 → 偏空
        - 结合价格动量方向确定正负
        """
        all_vol_momentum = []
        all_price_momentum = []

        for data_dict in [large_cap_data, small_cap_data]:
            for code, df in data_dict.items():
                if df is None or df.empty:
                    continue
                if "volume" not in df.columns or "close" not in df.columns:
                    continue

                vol = pd.to_numeric(df["volume"], errors="coerce").dropna()
                close = pd.to_numeric(df["close"], errors="coerce").dropna()

                # 成交量动量: 5日均值 vs 20日均值
                if len(vol) >= 20:
                    vol_ma5 = float(vol.iloc[-5:].mean())
                    vol_ma20 = float(vol.iloc[-20:].mean())
                    if vol_ma20 > 0:
                        vol_mom = (vol_ma5 / vol_ma20 - 1.0) * 100.0
                        all_vol_momentum.append(vol_mom)

                # 价格5日动量
                if len(close) >= 6 and close.iloc[-6] > 0:
                    price_mom = (float(close.iloc[-1]) / float(close.iloc[-6]) - 1.0) * 100.0
                    all_price_momentum.append(price_mom)

        if not all_vol_momentum:
            return 0.0

        avg_vol_mom = float(np.mean(all_vol_momentum))

        # 成交量动量信号
        # vol_mom > 0 → 成交量加速 → 资金流入加速 → 偏多
        # vol_mom < 0 → 成交量减速 → 资金流入减速 → 偏空
        mom_signal = avg_vol_mom * 5.0  # 放大: 典型 vol_mom ∈ [-20, 20]

        # 价格方向修正
        if all_price_momentum:
            avg_price_mom = float(np.mean(all_price_momentum))
            if avg_price_mom < 0 and mom_signal > 0:
                # 放量但价格下跌 → 资金流出而非流入
                mom_signal = -abs(mom_signal) * 0.7
            elif avg_price_mom > 0 and mom_signal < 0:
                # 缩量但价格上涨 → 卖压减轻
                mom_signal = abs(mom_signal) * 0.5

        return max(-100.0, min(100.0, mom_signal))

    # ═══════════════════════════════════════════════════════════════════════
    # 数据获取
    # ═══════════════════════════════════════════════════════════════════════

    def _fetch_index_data(self, codes: List[str]) -> Dict[str, pd.DataFrame]:
        """获取指数K线数据 (TDX标准端口)

        Args:
            codes: 指数代码列表 (如 ['000300', '000016'])

        Returns:
            {code: DataFrame} 各指数K线数据
        """
        result: Dict[str, pd.DataFrame] = {}

        for code in codes:
            try:
                # 判断市场类型
                if code.startswith("399"):
                    market_type = "index_sz"
                else:
                    market_type = "index_sh"

                if self._tdx is not None and hasattr(self._tdx, 'get_index_daily'):
                    df = self._tdx.get_index_daily(
                        code=code,
                        market_type=market_type,
                        count=60,  # 取60日数据用于5日/20日计算
                    )
                    if df is not None and not df.empty:
                        result[code] = df
                    else:
                        self._logger.debug("指数 %s 数据为空", code)
                else:
                    self._logger.debug("TDXAdapter 不可用或无 get_index_daily 方法")
            except Exception as e:
                self._logger.debug("指数 %s 数据获取失败: %s", code, e)

        return result

    def _fetch_futures_data(self, codes: List[str]) -> Dict[str, pd.DataFrame]:
        """获取股指期货K线数据 (TDX扩展端口)

        Args:
            codes: 期货代码列表 (如 ['IFL8', 'IML8'])

        Returns:
            {code: DataFrame} 各期货K线数据
        """
        result: Dict[str, pd.DataFrame] = {}

        for code in codes:
            try:
                # 股指期货在中金所
                market_type = "future_zj"

                if self._tdx is not None and hasattr(self._tdx, 'get_future_daily'):
                    df = self._tdx.get_future_daily(
                        code=code,
                        market_type=market_type,
                        count=60,
                    )
                    if df is not None and not df.empty:
                        result[code] = df
                    else:
                        self._logger.debug("期货 %s 数据为空", code)
            except Exception as e:
                self._logger.debug("期货 %s 数据获取失败: %s", code, e)

        return result

    def _aggregate_volume(
        self, data_dict: Dict[str, pd.DataFrame],
    ) -> Optional[np.ndarray]:
        """将多个指数/期货的成交量序列汇总为一条总量序列

        Args:
            data_dict: {code: DataFrame} 各标的K线数据

        Returns:
            成交量汇总序列 (ndarray) 或 None
        """
        if not data_dict:
            return None

        vol_series_list: List[np.ndarray] = []
        min_len = float('inf')

        for code, df in data_dict.items():
            if df is None or df.empty or "volume" not in df.columns:
                continue
            vol = pd.to_numeric(df["volume"], errors="coerce").fillna(0).values
            if len(vol) > 0:
                vol_series_list.append(vol)
                min_len = min(min_len, len(vol))

        if not vol_series_list or min_len < 6:
            return None

        # 对齐长度, 取最短序列的尾部
        aligned = np.array([v[-min_len:] for v in vol_series_list])
        return np.sum(aligned, axis=0)

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
