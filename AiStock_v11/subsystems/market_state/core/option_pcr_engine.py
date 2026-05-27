#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AiStock V11 — 期权PCR信号引擎 (Option PCR Signal Engine)

V11 NEW: 基于期权Put-Call Ratio构建情绪信号分量

数据来源:
  - TDX扩展端口: ETF期权K线数据 (510050/510300等)
  - DataLoaderService.load_option_data_for_pcr(): 已有PCR数据加载接口
  - DatabaseReader: 期权合约映射

PCR (Put-Call Ratio) 含义:
  - PCR > 1.0: 看跌期权成交/持仓 > 看涨, 市场恐慌偏多
  - PCR < 1.0: 看涨期权成交/持仓 > 看跌, 市场贪婪偏多
  - 反向指标: 极端恐慌(PCR极高)→看多, 极端贪婪(PCR极低)→看空

信号输出:
  OptionPCRSignal.composite_signal ∈ [-100, 100]
  OptionPCRSignal.composite_direction ∈ {"bullish", "bearish", "neutral"}

权重 (从 market_state.yaml pcr_weights 加载):
  volume_pcr: 0.40  — 成交量PCR
  oi_pcr:     0.40  — 持仓量PCR
  skew:       0.20  — 认购/认隐含波动率偏斜
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np

# ─── Type aliases ──────────────────────────────────────────────────────────────
TDXAdapter = Any
DataLoaderService = Any
DatabaseReader = Any
ConfigService = Any
CacheService = Any

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# 数据类定义
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class OptionPCRSignal:
    """期权PCR信号"""
    etf50_pcr: float = 0.0       # 50ETF PCR
    etf300_pcr: float = 0.0      # 300ETF PCR
    volume_pcr: float = 0.0      # 成交量PCR综合值
    oi_pcr: float = 0.0          # 持仓量PCR综合值
    skew: float = 0.0            # 波动率偏斜
    composite_signal: float = 0.0     # 综合信号 [-100, 100]
    composite_direction: str = "neutral"  # 综合方向

    # ─── 原始数据快照 ──────────────────────────────────────────────────
    pcr_volume_50: float = 0.0   # 50ETF成交量PCR
    pcr_volume_300: float = 0.0  # 300ETF成交量PCR
    pcr_oi_50: float = 0.0       # 50ETF持仓PCR
    pcr_oi_300: float = 0.0      # 300ETF持仓PCR
    call_volume_total: int = 0   # 总看涨成交量
    put_volume_total: int = 0    # 总看跌成交量
    call_oi_total: int = 0       # 总看涨持仓量
    put_oi_total: int = 0        # 总看跌持仓量
    data_available: bool = False  # 数据是否可用

    def to_dict(self) -> Dict[str, Any]:
        return {
            "etf50_pcr": round(self.etf50_pcr, 4),
            "etf300_pcr": round(self.etf300_pcr, 4),
            "volume_pcr": round(self.volume_pcr, 4),
            "oi_pcr": round(self.oi_pcr, 4),
            "skew": round(self.skew, 4),
            "composite_signal": round(self.composite_signal, 2),
            "composite_direction": self.composite_direction,
            "snapshot": {
                "pcr_volume_50": round(self.pcr_volume_50, 4),
                "pcr_volume_300": round(self.pcr_volume_300, 4),
                "pcr_oi_50": round(self.pcr_oi_50, 4),
                "pcr_oi_300": round(self.pcr_oi_300, 4),
                "call_volume_total": self.call_volume_total,
                "put_volume_total": self.put_volume_total,
                "call_oi_total": self.call_oi_total,
                "put_oi_total": self.put_oi_total,
            },
            "data_available": self.data_available,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# V11 默认值
# ═══════════════════════════════════════════════════════════════════════════════

_DEFAULT_PCR_WEIGHTS = {
    "volume_pcr": 0.40,
    "oi_pcr": 0.40,
    "skew": 0.20,
}

_DEFAULT_PCR_THRESHOLDS = {
    "extreme_greed": 0.5,    # PCR <= 0.5 → 极端贪婪 (看涨过度, 反向看空)
    "greed": 0.7,            # PCR <= 0.7 → 贪婪 (看涨偏多)
    "neutral_low": 0.85,    # PCR 中性区间下界
    "neutral_high": 1.15,   # PCR 中性区间上界
    "fear": 1.3,            # PCR >= 1.3 → 恐惧 (看跌偏多)
    "extreme_fear": 1.5,    # PCR >= 1.5 → 极端恐惧 (看跌过度, 反向看多)
}

# 主要ETF期权标的 (用于PCR计算)
_DEFAULT_PCR_UNDERLYINGS = ["510050", "510300"]


# ═══════════════════════════════════════════════════════════════════════════════
# 期权PCR信号引擎 V11
# ═══════════════════════════════════════════════════════════════════════════════

class OptionPCREngine:
    """期权PCR信号引擎 (V11 NEW)

    基于ETF期权的Put-Call Ratio数据, 构建期权情绪信号分量,
    作为6分量模型的第5分量 (权重0.15)。

    PCR是反向指标:
      - 极端高PCR (恐慌过度) → 看多信号
      - 极端低PCR (贪婪过度) → 看空信号
      - 中等PCR → 中性

    使用方式:
        >>> engine = OptionPCREngine(
        ...     data_service=data_loader,
        ...     config=config_svc,
        ... )
        >>> signal = engine.calculate()
    """

    def __init__(
        self,
        data_service: DataLoaderService,
        config: Optional[ConfigService] = None,
        cache: Optional[CacheService] = None,
        logger_instance: Optional[logging.Logger] = None,
    ) -> None:
        """初始化期权PCR信号引擎

        Args:
            data_service: DataLoaderService 实例 (含 load_option_data_for_pcr)
            config: ConfigService 实例
            cache: CacheService 实例
            logger_instance: Logger 实例
        """
        self._data_service = data_service
        self._config = config
        self._cache = cache
        self._logger = logger_instance or logger

        # 从 ConfigService 加载配置
        self._weights = self._load_weights()
        self._thresholds = self._load_thresholds()
        self._underlyings = self._load_underlyings()

        self._logger.info(
            "OptionPCREngine V11 初始化完成 | 标的: %s, 权重: %s",
            self._underlyings,
            {k: round(v, 2) for k, v in self._weights.items()},
        )

    # ──────────────────────────────────────────────────────────────
    #  配置加载
    # ──────────────────────────────────────────────────────────────

    def _load_weights(self) -> Dict[str, float]:
        """从 ConfigService 加载PCR权重"""
        if self._config is not None:
            weights = self._config.get("market_state.pcr_weights", None)
            if weights and isinstance(weights, dict):
                return {k: float(v) for k, v in weights.items()}
        return dict(_DEFAULT_PCR_WEIGHTS)

    def _load_thresholds(self) -> Dict[str, float]:
        """从 ConfigService 加载PCR阈值"""
        if self._config is not None:
            thresholds = self._config.get("market_state.pcr_thresholds", None)
            if thresholds and isinstance(thresholds, dict):
                return {k: float(v) for k, v in thresholds.items()}
        return dict(_DEFAULT_PCR_THRESHOLDS)

    def _load_underlyings(self) -> List[str]:
        """从 ConfigService 加载期权标的列表"""
        if self._config is not None:
            # 优先读取专用的 pcr_underlyings 配置
            underlyings = self._config.get("market_state.pcr_underlyings", None)
            if underlyings and isinstance(underlyings, list):
                return underlyings
            # 回退到 option_underlyings 的 key 列表 (ETF类)
            opt_cfg = self._config.get("codes.option_underlyings", {})
            if opt_cfg and isinstance(opt_cfg, dict):
                etf_keys = [k for k in opt_cfg.keys()
                            if k.isdigit() or k.startswith("5") or k.startswith("1")]
                return etf_keys[:4] if etf_keys else list(_DEFAULT_PCR_UNDERLYINGS)
        return list(_DEFAULT_PCR_UNDERLYINGS)

    # ═══════════════════════════════════════════════════════════════════════
    # 核心计算
    # ═══════════════════════════════════════════════════════════════════════

    def calculate(self) -> OptionPCRSignal:
        """计算期权PCR信号

        Returns:
            OptionPCRSignal 实例
        """
        start_time = time.time()
        signal = OptionPCRSignal()

        pcr_results: Dict[str, Dict[str, Any]] = {}

        # 1. 逐标的获取PCR数据
        for underlying in self._underlyings:
            try:
                pcr_data = self._fetch_pcr_data(underlying)
                if pcr_data and pcr_data.get("call_volume", 0) + pcr_data.get("put_volume", 0) > 0:
                    pcr_results[underlying] = pcr_data
            except Exception as e:
                self._logger.debug("PCR数据获取失败 %s: %s", underlying, e)

        if not pcr_results:
            self._logger.warning("OptionPCREngine: 无可用PCR数据, 返回中性信号")
            return signal

        signal.data_available = True

        # 2. 提取各标PCR值
        volume_pcrs = []
        oi_pcrs = []

        for underlying, data in pcr_results.items():
            vol_pcr = data.get("pcr_volume", 0.0)
            oi_pcr = data.get("pcr_oi", 0.0)

            if vol_pcr > 0:
                volume_pcrs.append(vol_pcr)
            if oi_pcr > 0:
                oi_pcrs.append(oi_pcr)

            # 更新信号快照
            if underlying == "510050":
                signal.etf50_pcr = vol_pcr
                signal.pcr_volume_50 = vol_pcr
                signal.pcr_oi_50 = oi_pcr
            elif underlying == "510300":
                signal.etf300_pcr = vol_pcr
                signal.pcr_volume_300 = vol_pcr
                signal.pcr_oi_300 = oi_pcr

            # 累计成交量/持仓量
            signal.call_volume_total += data.get("call_volume", 0)
            signal.put_volume_total += data.get("put_volume", 0)
            signal.call_oi_total += data.get("call_oi", 0)
            signal.put_oi_total += data.get("put_oi", 0)

        # 3. 综合PCR值 (多标的均值)
        signal.volume_pcr = float(np.mean(volume_pcrs)) if volume_pcrs else 0.0
        signal.oi_pcr = float(np.mean(oi_pcrs)) if oi_pcrs else 0.0

        # 4. 各子信号计算
        vol_signal = self._pcr_to_signal(signal.volume_pcr)
        oi_signal = self._pcr_to_signal(signal.oi_pcr)
        skew_signal = self._calc_skew_signal(signal.volume_pcr, signal.oi_pcr)

        signal.skew = skew_signal / 100.0  # 归一化到 [-1, 1] 范围存储

        # 5. 加权合成
        w = self._weights
        composite = (
            vol_signal * w.get("volume_pcr", 0.40)
            + oi_signal * w.get("oi_pcr", 0.40)
            + skew_signal * w.get("skew", 0.20)
        )
        composite = max(-100.0, min(100.0, composite))
        signal.composite_signal = composite
        signal.composite_direction = self._signal_to_direction(composite)

        elapsed = (time.time() - start_time) * 1000
        self._logger.info(
            "OptionPCREngine 计算: 综合=%.1f [%s] | Vol_PCR=%.3f OI_PCR=%.3f "
            "Skew=%.3f | 标的=%d | %.0fms",
            composite, signal.composite_direction,
            signal.volume_pcr, signal.oi_pcr,
            signal.skew, len(pcr_results), elapsed,
        )

        return signal

    # ═══════════════════════════════════════════════════════════════════════
    # 子信号计算
    # ═══════════════════════════════════════════════════════════════════════

    def _pcr_to_signal(self, pcr: float) -> float:
        """将PCR值转换为信号 (反向指标)

        PCR含义 (反向指标):
          - PCR极低 → 市场贪婪过度 (看涨过度) → 看空 (负信号)
          - PCR极高 → 市场恐慌过度 (看跌过度) → 看多 (正信号)
          - PCR中性 → 中性

        PCR = 看跌成交量 / 看涨成交量
          PCR < 1.0 → 看涨多于看跌 → 市场偏贪婪
          PCR > 1.0 → 看跌多于看涨 → 市场偏恐惧
        """
        t = self._thresholds

        if pcr <= 0:
            return 0.0

        # 极端贪婪 (PCR极低) → 强看空 (反向)
        if pcr <= t.get("extreme_greed", 0.5):
            return -80.0
        # 贪婪 (PCR偏低) → 看空
        elif pcr <= t.get("greed", 0.7):
            eg = t.get("extreme_greed", 0.5)
            g = t.get("greed", 0.7)
            ratio = (pcr - eg) / max(g - eg, 0.01)
            return -80.0 + ratio * 40.0  # -80 → -40
        # 中性偏低 → 轻微看空
        elif pcr <= t.get("neutral_low", 0.85):
            g = t.get("greed", 0.7)
            nl = t.get("neutral_low", 0.85)
            ratio = (pcr - g) / max(nl - g, 0.01)
            return -40.0 + ratio * 30.0  # -40 → -10
        # 中性区间
        elif pcr <= t.get("neutral_high", 1.15):
            return 0.0
        # 恐惧 (PCR偏高) → 看多
        elif pcr <= t.get("fear", 1.3):
            nh = t.get("neutral_high", 1.15)
            f = t.get("fear", 1.3)
            ratio = (pcr - nh) / max(f - nh, 0.01)
            return ratio * 30.0  # 0 → 30
        # 极端恐惧 (PCR极高) → 强看多 (反向)
        elif pcr <= t.get("extreme_fear", 1.5):
            f = t.get("fear", 1.3)
            ef = t.get("extreme_fear", 1.5)
            ratio = (pcr - f) / max(ef - f, 0.01)
            return 30.0 + ratio * 50.0  # 30 → 80
        else:
            return 80.0

    def _calc_skew_signal(self, volume_pcr: float, oi_pcr: float) -> float:
        """计算PCR偏斜信号

        逻辑:
        - 成交量PCR与持仓PCR的偏离度反映短期vs中期情绪差异
        - OI_PCR >> Vol_PCR → 长期持仓偏空但短期交易偏多 → 可能反转
        - OI_PCR << Vol_PCR → 长期持仓偏多但短期交易偏空 → 可能反转
        """
        if volume_pcr <= 0 or oi_pcr <= 0:
            return 0.0

        # 偏斜度 = (OI_PCR - Vol_PCR) / 平均值
        avg_pcr = (volume_pcr + oi_pcr) / 2.0
        if avg_pcr <= 0:
            return 0.0

        skew = (oi_pcr - volume_pcr) / avg_pcr

        # 偏斜信号: 正偏斜(OI>Vol) → 中期偏空但短期偏多 → 轻微看空
        #           负偏斜(OI<Vol) → 中期偏多但短期偏空 → 轻微看多
        skew_signal = -skew * 50.0  # 反向: 正偏斜→看空
        return max(-100.0, min(100.0, skew_signal))

    # ═══════════════════════════════════════════════════════════════════════
    # 数据获取
    # ═══════════════════════════════════════════════════════════════════════

    def _fetch_pcr_data(self, underlying: str) -> Optional[Dict[str, Any]]:
        """获取指定标的的PCR数据

        优先使用 DataLoaderService.load_option_data_for_pcr(),
        该方法已实现完整的PCR计算逻辑。
        """
        if self._data_service is None:
            return None

        try:
            # DataLoaderService 有专用的PCR数据加载方法
            if hasattr(self._data_service, 'load_option_data_for_pcr'):
                return self._data_service.load_option_data_for_pcr(underlying)
        except Exception as e:
            self._logger.debug("PCR数据加载失败 %s: %s", underlying, e)

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
