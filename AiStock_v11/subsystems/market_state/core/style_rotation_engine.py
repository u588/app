#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AiStock V11 — 风格轮动信号引擎 (Style Rotation Signal Engine)

V11 NEW: 基于行业/风格/规模三维轮动构建风格轮动信号分量

数据来源:
  行业轮动 (中证全指行业系列, EX MarketCode=62):
    - 932075: 全指金融  → finance
    - 932077: 全指能源行业  → energy
    - 932078: 全指材料行业  → materials
    - 932079: 全指工业行业  → industrials
    - 932080: 全指可选行业  → discretionary
    - 932081: 全指消费行业  → staples
    - 932082: 全指医药行业  → healthcare
    - 932084: 全指信息行业  → info_tech
    - 932085: 全指通信行业  → telecom
    - 932086: 全指公用行业  → utilities

  风格轮动 (成长/价值对):
    Primary (EX, MarketCode=62 → get_macro_data):
      - 000918: 300成长 → growth_300
      - 000919: 300价值 → value_300
    Secondary (ST):
      - 000028: 180成长 (SH) → growth_180
      - 000029: 180价值 (SH) → value_180
      - 399370: 国证成长 (SZ) → growth_gz
      - 399371: 国证价值 (SZ) → value_gz

  规模轮动 (大中小盘三梯队):
    - 000016: 上证50  (SH) → large_cap_50
    - 000300: 沪深300 (SH) → large_cap_300
    - 000905: 中证500 (SH) → mid_cap_500
    - 000852: 中证1000 (SH) → small_cap_1000
    - 932000: 中证2000 (EX,MC=62) → micro_cap_2000
    - 399006: 创业板指 (SZ) → gem

信号逻辑:
  - 行业轮动: 各行业20日动量排名, top3与bottom3差值归一化
  - 风格轮动: 成长/价值指数比值变化率, 正=成长领先
  - 规模轮动: 大盘加权/小盘加权比值变化率, 正=大盘领先
  - 预警: 5日比值变化>3%时触发轮动预警

信号输出:
  StyleRotationSignal.composite_signal ∈ [-100, 100]
  StyleRotationSignal.composite_direction ∈ {"bullish", "bearish", "neutral"}

权重 (从 market_state.yaml style_rotation_weights 加载):
  industry: 0.35  — 行业轮动信号
  style:    0.35  — 成长/价值风格信号
  size:     0.30  — 大小盘规模信号
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

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
class IndustryRotationSignal:
    """行业轮动信号 (单行业)"""
    industry: str = ""          # 行业英文标识
    code: str = ""              # 指数代码
    name: str = ""              # 指数中文名
    momentum_5d: float = 0.0    # 5日动量 (%)
    momentum_20d: float = 0.0   # 20日动量 (%)
    signal: float = 0.0         # 行业信号值
    direction: str = "neutral"  # 方向
    rank: int = 0               # 排名 (1=最强)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "industry": self.industry,
            "code": self.code,
            "name": self.name,
            "momentum_5d": round(self.momentum_5d, 2),
            "momentum_20d": round(self.momentum_20d, 2),
            "signal": round(self.signal, 2),
            "direction": self.direction,
            "rank": self.rank,
        }


@dataclass
class StyleRotationSignal:
    """风格轮动信号 (三维轮动综合)"""
    # ─── 子维度信号 ─────────────────────────────────────────────────────
    industry_rotation: Dict[str, IndustryRotationSignal] = field(default_factory=dict)
    style_signal: float = 0.0           # 成长/价值信号 (正=成长领先)
    style_direction: str = "neutral"    # 成长/价值方向
    size_signal: float = 0.0            # 大小盘信号 (正=大盘领先)
    size_direction: str = "neutral"     # 大小盘方向

    # ─── 行业热力图排名 ─────────────────────────────────────────────────
    industry_heatmap_ranking: List[Tuple[str, float]] = field(default_factory=list)

    # ─── 轮动预警 ───────────────────────────────────────────────────────
    rotation_alerts: List[str] = field(default_factory=list)

    # ─── 综合信号 ───────────────────────────────────────────────────────
    composite_signal: float = 0.0       # 综合信号 [-100, 100]
    composite_direction: str = "neutral"  # 综合方向

    # ─── 状态 ───────────────────────────────────────────────────────────
    data_available: bool = False        # 数据是否可用

    # ─── 原始数据快照 ──────────────────────────────────────────────────
    snapshot: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "industry_rotation": {
                k: v.to_dict() for k, v in self.industry_rotation.items()
            },
            "style_signal": round(self.style_signal, 2),
            "style_direction": self.style_direction,
            "size_signal": round(self.size_signal, 2),
            "size_direction": self.size_direction,
            "industry_heatmap_ranking": [
                (k, round(v, 2)) for k, v in self.industry_heatmap_ranking
            ],
            "rotation_alerts": self.rotation_alerts,
            "composite_signal": round(self.composite_signal, 2),
            "composite_direction": self.composite_direction,
            "data_available": self.data_available,
            "snapshot": self.snapshot,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# V11 默认值 (仅 ConfigService 不可用时的回退)
# ═══════════════════════════════════════════════════════════════════════════════

_DEFAULT_STYLE_ROTATION_WEIGHTS = {
    "industry": 0.35,
    "style": 0.35,
    "size": 0.30,
}

_DEFAULT_INDUSTRY_INDICES = [
    {"code": "932083", "market": 62, "market_type": "index_ext", "name": "全指金融行业", "industry": "finance"},
    {"code": "932077", "market": 62, "market_type": "index_ext", "name": "全指能源行业", "industry": "energy"},
    {"code": "932078", "market": 62, "market_type": "index_ext", "name": "全指材料行业", "industry": "materials"},
    {"code": "932079", "market": 62, "market_type": "index_ext", "name": "全指工业行业", "industry": "industrials"},
    {"code": "932080", "market": 62, "market_type": "index_ext", "name": "全指可选行业", "industry": "discretionary"},
    {"code": "932081", "market": 62, "market_type": "index_ext", "name": "全指消费行业", "industry": "staples"},
    {"code": "932082", "market": 62, "market_type": "index_ext", "name": "全指医药行业", "industry": "healthcare"},
    {"code": "932084", "market": 62, "market_type": "index_ext", "name": "全指信息行业", "industry": "info_tech"},
    {"code": "932085", "market": 62, "market_type": "index_ext", "name": "全指通信行业", "industry": "telecom"},
    {"code": "932086", "market": 62, "market_type": "index_ext", "name": "全指公用行业", "industry": "utilities"},
]

_DEFAULT_STYLE_INDICES = [
    {"code": "000918", "market_type": "index_sh", "name": "300成长", "role": "growth"},
    {"code": "000919", "market_type": "index_sh", "name": "300价值", "role": "value"},
    {"code": "399370", "market_type": "index_sz", "name": "国证成长", "role": "growth_alt"},
    {"code": "399371", "market_type": "index_sz", "name": "国证价值", "role": "value_alt"},
]

_DEFAULT_SIZE_INDICES = [
    {"code": "000016", "market_type": "index_sh", "name": "上证50",  "tier": "large"},
    {"code": "000300", "market_type": "index_sh", "name": "沪深300", "tier": "large"},
    {"code": "000905", "market_type": "index_sh", "name": "中证500", "tier": "mid"},
    {"code": "000852", "market_type": "index_sh", "name": "中证1000", "tier": "small"},
    {"code": "932000", "market": 62, "market_type": "index_ext", "name": "中证2000", "tier": "micro"},
    {"code": "399006", "market_type": "index_sz", "name": "创业板指", "tier": "gem"},
]


# ═══════════════════════════════════════════════════════════════════════════════
# 风格轮动信号引擎 V11
# ═══════════════════════════════════════════════════════════════════════════════

class StyleRotationEngine:
    """风格轮动信号引擎 (V11 NEW)

    基于行业/风格/规模三维轮动数据, 构建风格轮动信号分量。

    三维轮动逻辑:
      - 行业轮动: 各行业动量排名, top3与bottom3差值反映行业分化程度
      - 风格轮动: 成长/价值指数比值变化, 反映市场风格偏好切换
      - 规模轮动: 大盘/小盘指数比值变化, 反映资金在大与小之间的轮动

    使用方式:
        >>> engine = StyleRotationEngine(
        ...     tdx_adapter=tdx,
        ...     config=config_svc,
        ... )
        >>> signal = engine.calculate()
    """

    def __init__(
        self,
        tdx_adapter: TDXAdapter,
        config: Optional[ConfigService] = None,
        cache: Optional[CacheService] = None,
        logger_instance: Optional[logging.Logger] = None,
    ) -> None:
        """初始化风格轮动信号引擎

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
        self._industry_indices = self._load_industry_indices()
        self._style_indices = self._load_style_indices()
        self._size_indices = self._load_size_indices()

        self._logger.info(
            "StyleRotationEngine V11 初始化完成 | 行业: %d, 风格: %d, 规模: %d, 权重: %s",
            len(self._industry_indices),
            len(self._style_indices),
            len(self._size_indices),
            {k: round(v, 2) for k, v in self._weights.items()},
        )

    # ──────────────────────────────────────────────────────────────
    #  配置加载
    # ──────────────────────────────────────────────────────────────

    def _load_weights(self) -> Dict[str, float]:
        """从 ConfigService 加载风格轮动权重"""
        if self._config is not None:
            weights = self._config.get("market_state.style_rotation_weights", None)
            if weights and isinstance(weights, dict):
                return {k: float(v) for k, v in weights.items()}
        return dict(_DEFAULT_STYLE_ROTATION_WEIGHTS)

    def _load_industry_indices(self) -> List[Dict[str, Any]]:
        """从 ConfigService 加载行业指数配置"""
        if self._config is not None:
            indices = self._config.get("codes.style_rotation.industry_indices", None)
            if indices and isinstance(indices, list):
                return indices
        return list(_DEFAULT_INDUSTRY_INDICES)

    def _load_style_indices(self) -> List[Dict[str, Any]]:
        """从 ConfigService 加载风格指数配置"""
        if self._config is not None:
            indices = self._config.get("codes.style_rotation.style_indices", None)
            if indices and isinstance(indices, list):
                return indices
        return list(_DEFAULT_STYLE_INDICES)

    def _load_size_indices(self) -> List[Dict[str, Any]]:
        """从 ConfigService 加载规模指数配置"""
        if self._config is not None:
            indices = self._config.get("codes.style_rotation.size_indices", None)
            if indices and isinstance(indices, list):
                return indices
        return list(_DEFAULT_SIZE_INDICES)

    # ═══════════════════════════════════════════════════════════════════════
    # 核心计算
    # ═══════════════════════════════════════════════════════════════════════

    def calculate(self) -> StyleRotationSignal:
        """计算风格轮动信号

        Returns:
            StyleRotationSignal 实例
        """
        start_time = time.time()
        signal = StyleRotationSignal()

        # 1. 批量获取所有指数数据
        industry_data = self._fetch_industry_data()
        style_data = self._fetch_style_data()
        size_data = self._fetch_size_data()

        # 检查是否至少有一个维度有数据
        has_industry = bool(industry_data)
        has_style = bool(style_data)
        has_size = bool(size_data)

        if not has_industry and not has_style and not has_size:
            self._logger.warning("StyleRotationEngine: 无可用数据, 返回中性信号")
            return signal

        signal.data_available = True

        # 2. 计算各子信号
        industry_signal = 0.0
        if has_industry:
            industry_signal = self._calc_industry_rotation(industry_data, signal)

        style_signal_val = 0.0
        if has_style:
            style_signal_val = self._calc_style_rotation(style_data, signal)

        size_signal_val = 0.0
        if has_size:
            size_signal_val = self._calc_size_rotation(size_data, signal)

        # 3. 生成轮动预警
        signal.rotation_alerts = self._generate_rotation_alerts(
            signal, style_data, size_data,
        )

        # 4. 加权合成
        w = self._weights
        composite = (
            industry_signal * w.get("industry", 0.35)
            + style_signal_val * w.get("style", 0.35)
            + size_signal_val * w.get("size", 0.30)
        )
        composite = max(-100.0, min(100.0, composite))
        signal.composite_signal = composite
        signal.composite_direction = self._signal_to_direction(composite)

        # 5. 构建快照
        signal.snapshot = self._build_snapshot(
            industry_data, style_data, size_data,
        )

        elapsed = (time.time() - start_time) * 1000
        self._logger.info(
            "StyleRotationEngine 计算: 综合=%.1f [%s] | 行业=%.1f 风格=%.1f "
            "规模=%.1f | 预警=%d | %.0fms",
            composite, signal.composite_direction,
            industry_signal, style_signal_val, size_signal_val,
            len(signal.rotation_alerts), elapsed,
        )

        return signal

    # ═══════════════════════════════════════════════════════════════════════
    # 子信号计算 — 行业轮动
    # ═══════════════════════════════════════════════════════════════════════

    def _calc_industry_rotation(
        self,
        industry_data: Dict[str, pd.DataFrame],
        signal: StyleRotationSignal,
    ) -> float:
        """计算行业轮动信号

        逻辑:
        - 计算每个行业的5日和20日动量
        - 按动量排名 (1=最强)
        - top3平均动量 - bottom3平均动量 → 行业分化度
        - 分化度归一化为信号值

        Args:
            industry_data: {industry_key: DataFrame}
            signal: StyleRotationSignal 用于写入子信号

        Returns:
            行业轮动信号值
        """
        industry_signals: Dict[str, IndustryRotationSignal] = {}
        momentum_list: List[Tuple[str, float]] = []  # (industry, momentum_20d)

        for cfg in self._industry_indices:
            industry = cfg.get("industry", "")
            code = cfg.get("code", "")
            name = cfg.get("name", "")

            df = industry_data.get(industry)
            if df is None or df.empty:
                industry_signals[industry] = IndustryRotationSignal(
                    industry=industry, code=code, name=name,
                )
                continue

            close = df["close"].values.astype(float) if "close" in df.columns else np.array([])
            if len(close) < 2:
                industry_signals[industry] = IndustryRotationSignal(
                    industry=industry, code=code, name=name,
                )
                continue

            # 5日动量
            momentum_5d = 0.0
            if len(close) >= 6 and close[-6] > 0:
                momentum_5d = (close[-1] / close[-6] - 1.0) * 100.0

            # 20日动量
            momentum_20d = 0.0
            if len(close) >= 21 and close[-21] > 0:
                momentum_20d = (close[-1] / close[-21] - 1.0) * 100.0

            momentum_list.append((industry, momentum_20d))

            industry_signals[industry] = IndustryRotationSignal(
                industry=industry,
                code=code,
                name=name,
                momentum_5d=momentum_5d,
                momentum_20d=momentum_20d,
                direction="neutral",
            )

        # 按20日动量排名
        momentum_list.sort(key=lambda x: x[1], reverse=True)
        for rank, (industry, _) in enumerate(momentum_list, start=1):
            if industry in industry_signals:
                industry_signals[industry].rank = rank

        # 设置方向
        for ind_sig in industry_signals.values():
            ind_sig.direction = self._signal_to_direction(ind_sig.momentum_20d * 5.0)

        # 计算行业分化度信号: top3均值 - bottom3均值
        top3_avg = 0.0
        bottom3_avg = 0.0
        n = len(momentum_list)

        if n >= 3:
            top3_momenta = [m for _, m in momentum_list[:3]]
            bottom3_momenta = [m for _, m in momentum_list[-3:]]
            top3_avg = float(np.mean(top3_momenta))
            bottom3_avg = float(np.mean(bottom3_momenta))
        elif n >= 2:
            top3_avg = momentum_list[0][1]
            bottom3_avg = momentum_list[-1][1]

        # 分化度: top3 - bottom3, 归一化
        dispersion = top3_avg - bottom3_avg

        # 行业分化信号: 分化度高→行业差异大→结构性机会多→偏多
        # 分化度低→行业趋同→系统性风险高→偏空
        # 典型分化度范围 [-15, 15], 放大约6.67倍到 [-100, 100]
        industry_signal = dispersion * 6.67
        industry_signal = max(-100.0, min(100.0, industry_signal))

        # 写入信号
        signal.industry_rotation = industry_signals

        # 行业热力图排名 (按20日动量降序)
        signal.industry_heatmap_ranking = [
            (industry, round(momentum, 2)) for industry, momentum in momentum_list
        ]

        self._logger.debug(
            "行业轮动: 分化度=%.2f, top3=%.2f, bottom3=%.2f, 信号=%.1f",
            dispersion, top3_avg, bottom3_avg, industry_signal,
        )

        return industry_signal

    # ═══════════════════════════════════════════════════════════════════════
    # 子信号计算 — 风格轮动
    # ═══════════════════════════════════════════════════════════════════════

    def _calc_style_rotation(
        self,
        style_data: Dict[str, pd.DataFrame],
        signal: StyleRotationSignal,
    ) -> float:
        """计算风格轮动信号 (成长/价值)

        逻辑:
        - 计算成长指数/价值指数的比值
        - 跟踪比值的5日和20日变化率
        - 比值上升 → 成长领先 → 正信号
        - 比值下降 → 价值领先 → 负信号
        - 使用主指标 (300成长/300价值) 和辅助指标交叉验证

        Args:
            style_data: {role_key: DataFrame}
            signal: StyleRotationSignal 用于写入子信号

        Returns:
            风格轮动信号值
        """
        # 主指标: 300成长 / 300价值
        primary_signal = self._calc_style_pair_signal(
            style_data, "growth", "value",
        )

        # 辅助指标: 国证成长 / 国证价值
        alt_signal = self._calc_style_pair_signal(
            style_data, "growth_alt", "value_alt",
        )

        # 综合信号: 主指标权重70%, 辅助指标权重30%
        if primary_signal != 0.0 and alt_signal != 0.0:
            style_signal_val = primary_signal * 0.7 + alt_signal * 0.3
        elif primary_signal != 0.0:
            style_signal_val = primary_signal
        elif alt_signal != 0.0:
            style_signal_val = alt_signal
        else:
            style_signal_val = 0.0

        style_signal_val = max(-100.0, min(100.0, style_signal_val))

        signal.style_signal = style_signal_val
        signal.style_direction = self._style_signal_to_direction(style_signal_val)

        self._logger.debug(
            "风格轮动: 主信号=%.1f, 辅助信号=%.1f, 综合=%.1f [%s]",
            primary_signal, alt_signal, style_signal_val, signal.style_direction,
        )

        return style_signal_val

    def _calc_style_pair_signal(
        self,
        style_data: Dict[str, pd.DataFrame],
        growth_key: str,
        value_key: str,
    ) -> float:
        """计算一对成长/价值指数的风格信号

        Args:
            style_data: {role_key: DataFrame}
            growth_key: 成长指数的 role key
            value_key: 价值指数的 role key

        Returns:
            风格信号值 (正=成长领先, 负=价值领先)
        """
        growth_df = style_data.get(growth_key)
        value_df = style_data.get(value_key)

        if growth_df is None or growth_df.empty or value_df is None or value_df.empty:
            return 0.0

        growth_close = growth_df["close"].values.astype(float) if "close" in growth_df.columns else np.array([])
        value_close = value_df["close"].values.astype(float) if "close" in value_df.columns else np.array([])

        if len(growth_close) < 6 or len(value_close) < 6:
            return 0.0

        # 计算比值序列
        min_len = min(len(growth_close), len(value_close))
        ratio = growth_close[-min_len:] / np.maximum(value_close[-min_len:], 1e-6)

        # 比值5日变化率
        ratio_change_5d = 0.0
        if len(ratio) >= 6 and ratio[-6] > 0:
            ratio_change_5d = (ratio[-1] / ratio[-6] - 1.0) * 100.0

        # 比值20日变化率
        ratio_change_20d = 0.0
        if len(ratio) >= 21 and ratio[-21] > 0:
            ratio_change_20d = (ratio[-1] / ratio[-21] - 1.0) * 100.0

        # 信号: 短期权重60%, 中期权重40%
        # 放大倍数: 典型比值变化 [-5, 5] → 信号 [-100, 100]
        style_signal = ratio_change_5d * 12.0 * 0.6 + ratio_change_20d * 8.0 * 0.4

        return max(-100.0, min(100.0, style_signal))

    # ═══════════════════════════════════════════════════════════════════════
    # 子信号计算 — 规模轮动
    # ═══════════════════════════════════════════════════════════════════════

    def _calc_size_rotation(
        self,
        size_data: Dict[str, pd.DataFrame],
        signal: StyleRotationSignal,
    ) -> float:
        """计算规模轮动信号 (大盘/小盘)

        逻辑:
        - 大盘: 上证50 + 沪深300 加权均值
        - 小盘: 中证1000 + 中证2000 + 创业板 加权均值
        - 中盘: 中证500 作为中间参考
        - 大盘/小盘比值上升 → 大盘领先 → 正信号
        - 大盘/小盘比值下降 → 小盘领先 → 负信号

        Args:
            size_data: {tier_key: DataFrame}
            signal: StyleRotationSignal 用于写入子信号

        Returns:
            规模轮动信号值
        """
        # 构建各梯度的归一化价格序列
        large_prices = self._extract_tier_prices(size_data, "large")
        mid_prices = self._extract_tier_prices(size_data, "mid")
        small_prices = self._extract_tier_prices(size_data, "small")
        micro_prices = self._extract_tier_prices(size_data, "micro")
        gem_prices = self._extract_tier_prices(size_data, "gem")

        # 大盘指数: large梯度 + mid梯度 (加权: large 60%, mid 40%)
        large_composite = self._weighted_price(large_prices, mid_prices, 0.6, 0.4)

        # 小盘指数: small梯度 + micro梯度 + gem (加权: small 40%, micro 30%, gem 30%)
        small_temp = self._weighted_price(small_prices, micro_prices, 0.57, 0.43)
        small_composite = self._weighted_price(small_temp, gem_prices, 0.7, 0.3)

        if large_composite is None or small_composite is None:
            return 0.0

        # 计算大盘/小盘比值
        min_len = min(len(large_composite), len(small_composite))
        if min_len < 6:
            return 0.0

        ratio = large_composite[-min_len:] / np.maximum(small_composite[-min_len:], 1e-6)

        # 比值5日变化率
        ratio_change_5d = 0.0
        if len(ratio) >= 6 and ratio[-6] > 0:
            ratio_change_5d = (ratio[-1] / ratio[-6] - 1.0) * 100.0

        # 比值20日变化率
        ratio_change_20d = 0.0
        if len(ratio) >= 21 and ratio[-21] > 0:
            ratio_change_20d = (ratio[-1] / ratio[-21] - 1.0) * 100.0

        # 信号: 短期权重60%, 中期权重40%
        # 放大倍数: 典型比值变化 [-5, 5] → 信号 [-100, 100]
        size_signal = ratio_change_5d * 12.0 * 0.6 + ratio_change_20d * 8.0 * 0.4
        size_signal = max(-100.0, min(100.0, size_signal))

        signal.size_signal = size_signal
        signal.size_direction = self._size_signal_to_direction(size_signal)

        self._logger.debug(
            "规模轮动: 5d变化=%.2f%%, 20d变化=%.2f%%, 信号=%.1f [%s]",
            ratio_change_5d, ratio_change_20d, size_signal, signal.size_direction,
        )

        return size_signal

    def _extract_tier_prices(
        self,
        size_data: Dict[str, pd.DataFrame],
        tier: str,
    ) -> Optional[np.ndarray]:
        """从规模数据中提取指定梯度的归一化价格

        同一梯度可能有多个指数, 取均值。

        Args:
            size_data: {tier_key: DataFrame}
            tier: 梯度名称 ("large", "mid", "small", "micro", "gem")

        Returns:
            归一化价格序列 (最新值=1.0) 或 None
        """
        tier_dfs: List[pd.DataFrame] = []
        for key, df in size_data.items():
            if key == tier and df is not None and not df.empty:
                tier_dfs.append(df)

        if not tier_dfs:
            return None

        # 各指数归一化后取均值
        normalized_list: List[np.ndarray] = []
        for df in tier_dfs:
            close = df["close"].values.astype(float) if "close" in df.columns else np.array([])
            if len(close) < 2 or close[-1] <= 0:
                continue
            normalized = close / close[-1]  # 以最新值为1.0归一化
            normalized_list.append(normalized)

        if not normalized_list:
            return None

        # 取等长部分均值
        min_len = min(len(arr) for arr in normalized_list)
        if min_len < 2:
            return None

        stacked = np.array([arr[-min_len:] for arr in normalized_list])
        return np.mean(stacked, axis=0)

    @staticmethod
    def _weighted_price(
        prices_a: Optional[np.ndarray],
        prices_b: Optional[np.ndarray],
        weight_a: float,
        weight_b: float,
    ) -> Optional[np.ndarray]:
        """计算两个价格序列的加权组合

        Args:
            prices_a: 价格序列A (归一化)
            prices_b: 价格序列B (归一化)
            weight_a: A的权重
            weight_b: B的权重

        Returns:
            加权价格序列或None
        """
        if prices_a is None and prices_b is None:
            return None
        if prices_a is None:
            return prices_b
        if prices_b is None:
            return prices_a

        min_len = min(len(prices_a), len(prices_b))
        if min_len < 2:
            return prices_a if len(prices_a) >= len(prices_b) else prices_b

        return prices_a[-min_len:] * weight_a + prices_b[-min_len:] * weight_b

    # ═══════════════════════════════════════════════════════════════════════
    # 轮动预警
    # ═══════════════════════════════════════════════════════════════════════

    def _generate_rotation_alerts(
        self,
        signal: StyleRotationSignal,
        style_data: Dict[str, pd.DataFrame],
        size_data: Dict[str, pd.DataFrame],
    ) -> List[str]:
        """生成轮动预警消息

        预警条件:
        - 成长/价值比值5日变化 > 3% → "价值→成长风格切换"
        - 成长/价值比值5日变化 < -3% → "成长→价值风格切换"
        - 大盘/小盘比值5日变化 > 3% → "小盘→大盘轮动预警"
        - 大盘/小盘比值5日变化 < -3% → "大盘→小盘轮动预警"
        - 行业top1与bottom1动量差 > 15% → "行业分化加剧"

        Args:
            signal: 已计算的 StyleRotationSignal
            style_data: 风格指数数据
            size_data: 规模指数数据

        Returns:
            预警消息列表
        """
        alerts: List[str] = []
        threshold = 3.0  # 5日变化率阈值 (%)

        # 风格切换预警
        style_change_5d = self._calc_style_ratio_change_5d(style_data)
        if style_change_5d > threshold:
            alerts.append("价值→成长风格切换 (5日比值变化: +{:.1f}%)".format(style_change_5d))
        elif style_change_5d < -threshold:
            alerts.append("成长→价值风格切换 (5日比值变化: {:.1f}%)".format(style_change_5d))

        # 规模轮动预警
        size_change_5d = self._calc_size_ratio_change_5d(size_data)
        if size_change_5d > threshold:
            alerts.append("小盘→大盘轮动预警 (5日比值变化: +{:.1f}%)".format(size_change_5d))
        elif size_change_5d < -threshold:
            alerts.append("大盘→小盘轮动预警 (5日比值变化: {:.1f}%)".format(size_change_5d))

        # 行业分化预警
        if signal.industry_heatmap_ranking:
            top_momentum = signal.industry_heatmap_ranking[0][1]
            bottom_momentum = signal.industry_heatmap_ranking[-1][1]
            spread = top_momentum - bottom_momentum
            if spread > 15.0:
                top_name = signal.industry_heatmap_ranking[0][0]
                bottom_name = signal.industry_heatmap_ranking[-1][0]
                alerts.append(
                    "行业分化加剧 (领先:{} {:.1f}%, 滞后:{} {:.1f}%, 差值:{:.1f}%)".format(
                        top_name, top_momentum, bottom_name, bottom_momentum, spread,
                    )
                )

        return alerts

    def _calc_style_ratio_change_5d(
        self, style_data: Dict[str, pd.DataFrame],
    ) -> float:
        """计算成长/价值比值5日变化率 (用于预警)"""
        growth_df = style_data.get("growth")
        value_df = style_data.get("value")

        if growth_df is None or growth_df.empty or value_df is None or value_df.empty:
            # 尝试辅助指标
            growth_df = style_data.get("growth_alt")
            value_df = style_data.get("value_alt")

        if growth_df is None or growth_df.empty or value_df is None or value_df.empty:
            return 0.0

        growth_close = growth_df["close"].values.astype(float) if "close" in growth_df.columns else np.array([])
        value_close = value_df["close"].values.astype(float) if "close" in value_df.columns else np.array([])

        if len(growth_close) < 6 or len(value_close) < 6:
            return 0.0

        min_len = min(len(growth_close), len(value_close))
        ratio = growth_close[-min_len:] / np.maximum(value_close[-min_len:], 1e-6)

        if len(ratio) >= 6 and ratio[-6] > 0:
            return (ratio[-1] / ratio[-6] - 1.0) * 100.0

        return 0.0

    def _calc_size_ratio_change_5d(
        self, size_data: Dict[str, pd.DataFrame],
    ) -> float:
        """计算大盘/小盘比值5日变化率 (用于预警)"""
        large_prices = self._extract_tier_prices(size_data, "large")
        mid_prices = self._extract_tier_prices(size_data, "mid")
        small_prices = self._extract_tier_prices(size_data, "small")
        micro_prices = self._extract_tier_prices(size_data, "micro")
        gem_prices = self._extract_tier_prices(size_data, "gem")

        large_composite = self._weighted_price(large_prices, mid_prices, 0.6, 0.4)
        small_temp = self._weighted_price(small_prices, micro_prices, 0.57, 0.43)
        small_composite = self._weighted_price(small_temp, gem_prices, 0.7, 0.3)

        if large_composite is None or small_composite is None:
            return 0.0

        min_len = min(len(large_composite), len(small_composite))
        if min_len < 6:
            return 0.0

        ratio = large_composite[-min_len:] / np.maximum(small_composite[-min_len:], 1e-6)

        if len(ratio) >= 6 and ratio[-6] > 0:
            return (ratio[-1] / ratio[-6] - 1.0) * 100.0

        return 0.0

    # ═══════════════════════════════════════════════════════════════════════
    # 数据获取
    # ═══════════════════════════════════════════════════════════════════════

    def _fetch_industry_data(self) -> Dict[str, pd.DataFrame]:
        """批量获取行业指数数据

        行业指数均在 EX MarketCode=62, 使用 get_macro_data

        Returns:
            {industry_key: DataFrame}
        """
        result: Dict[str, pd.DataFrame] = {}

        for cfg in self._industry_indices:
            code = cfg.get("code", "")
            market = cfg.get("market", 62)
            industry = cfg.get("industry", code)
            name = cfg.get("name", code)

            try:
                df = self._fetch_index_data(code=code, market=market, market_type="index_ext")
                if df is not None and not df.empty:
                    result[industry] = df
                else:
                    self._logger.debug("行业指数 %s (%s) 数据为空", name, code)
            except Exception as e:
                self._logger.warning("行业指数 %s (%s) 获取失败: %s", name, code, e)

        self._logger.info(
            "StyleRotationEngine: 获取 %d/%d 行业指数数据",
            len(result), len(self._industry_indices),
        )
        return result

    def _fetch_style_data(self) -> Dict[str, pd.DataFrame]:
        """批量获取风格指数数据

        ST指数 (SH/SZ): 使用 get_index_daily 或 get_bars
        EX指数: 使用 get_macro_data

        Returns:
            {role_key: DataFrame}
        """
        result: Dict[str, pd.DataFrame] = {}

        for cfg in self._style_indices:
            code = cfg.get("code", "")
            market_type = cfg.get("market_type", "index_sh")
            role = cfg.get("role", code)
            name = cfg.get("name", code)
            market = cfg.get("market", None)

            try:
                df = self._fetch_index_data(
                    code=code, market=market, market_type=market_type,
                )
                if df is not None and not df.empty:
                    result[role] = df
                else:
                    self._logger.debug("风格指数 %s (%s) 数据为空", name, code)
            except Exception as e:
                self._logger.warning("风格指数 %s (%s) 获取失败: %s", name, code, e)

        self._logger.info(
            "StyleRotationEngine: 获取 %d/%d 风格指数数据",
            len(result), len(self._style_indices),
        )
        return result

    def _fetch_size_data(self) -> Dict[str, pd.DataFrame]:
        """批量获取规模指数数据

        Returns:
            {tier_key: DataFrame}
        """
        result: Dict[str, pd.DataFrame] = {}

        for cfg in self._size_indices:
            code = cfg.get("code", "")
            market_type = cfg.get("market_type", "index_sh")
            tier = cfg.get("tier", code)
            name = cfg.get("name", code)
            market = cfg.get("market", None)

            try:
                df = self._fetch_index_data(
                    code=code, market=market, market_type=market_type,
                )
                if df is not None and not df.empty:
                    result[tier] = df
                else:
                    self._logger.debug("规模指数 %s (%s) 数据为空", name, code)
            except Exception as e:
                self._logger.warning("规模指数 %s (%s) 获取失败: %s", name, code, e)

        self._logger.info(
            "StyleRotationEngine: 获取 %d/%d 规模指数数据",
            len(result), len(self._size_indices),
        )
        return result

    def _fetch_index_data(
        self,
        code: str,
        market: Optional[int] = None,
        market_type: str = "index_sh",
        count: int = 120,
    ) -> Optional[pd.DataFrame]:
        """获取单个指数K线数据

        根据market_type选择不同的TDX接口:
        - "index_ext": EX扩展接口, 使用 get_macro_data(code, market=62)
        - "index_sh": ST标准接口(SH), 使用 get_index_daily 或 get_bars
        - "index_sz": ST标准接口(SZ), 使用 get_index_daily 或 get_bars

        Args:
            code: 指数代码
            market: 市场代码 (仅index_ext使用)
            market_type: 市场类型
            count: 数据条数

        Returns:
            DataFrame 或 None
        """
        if self._tdx is None:
            return None

        try:
            # EX扩展接口 (MarketCode=62)
            if market_type == "index_ext":
                mk = market if market is not None else 62
                return self._tdx.get_macro_data(code=code, market=mk, count=count)

            # ST标准接口 — 尝试 get_index_daily
            if hasattr(self._tdx, "get_index_daily"):
                df = self._tdx.get_index_daily(
                    code=code, market_type=market_type, count=count,
                )
                if df is not None and not df.empty:
                    return df

            # 回退: get_bars
            if hasattr(self._tdx, "get_bars"):
                df = self._tdx.get_bars(
                    code=code, market_type=market_type, count=count,
                )
                if df is not None and not df.empty:
                    return df

            self._logger.debug("指数数据获取: %s (%s) 无可用接口", code, market_type)
            return None

        except Exception as e:
            self._logger.debug("指数数据获取失败 %s (%s): %s", code, market_type, e)
            return None

    # ═══════════════════════════════════════════════════════════════════════
    # 辅助方法
    # ═══════════════════════════════════════════════════════════════════════

    @staticmethod
    def _signal_to_direction(signal: float) -> str:
        """综合信号值→方向"""
        if signal > 20:
            return "bullish"
        elif signal < -20:
            return "bearish"
        return "neutral"

    @staticmethod
    def _style_signal_to_direction(signal: float) -> str:
        """风格信号→方向 (正=成长领先, 负=价值领先)"""
        if signal > 15:
            return "growth_leading"
        elif signal < -15:
            return "value_leading"
        return "neutral"

    @staticmethod
    def _size_signal_to_direction(signal: float) -> str:
        """规模信号→方向 (正=大盘领先, 负=小盘领先)"""
        if signal > 15:
            return "large_cap_leading"
        elif signal < -15:
            return "small_cap_leading"
        return "neutral"

    def _build_snapshot(
        self,
        industry_data: Dict[str, pd.DataFrame],
        style_data: Dict[str, pd.DataFrame],
        size_data: Dict[str, pd.DataFrame],
    ) -> Dict[str, Any]:
        """构建原始数据快照

        Args:
            industry_data: 行业指数数据
            style_data: 风格指数数据
            size_data: 规模指数数据

        Returns:
            可序列化的快照字典
        """
        snapshot: Dict[str, Any] = {
            "industry_latest": {},
            "style_latest": {},
            "size_latest": {},
        }

        # 行业指数最新值
        for cfg in self._industry_indices:
            industry = cfg.get("industry", "")
            name = cfg.get("name", "")
            df = industry_data.get(industry)
            if df is not None and not df.empty and "close" in df.columns:
                close = df["close"].values.astype(float)
                if len(close) >= 1:
                    snapshot["industry_latest"][industry] = {
                        "name": name,
                        "close": round(float(close[-1]), 2),
                    }

        # 风格指数最新值
        for cfg in self._style_indices:
            role = cfg.get("role", "")
            name = cfg.get("name", "")
            df = style_data.get(role)
            if df is not None and not df.empty and "close" in df.columns:
                close = df["close"].values.astype(float)
                if len(close) >= 1:
                    snapshot["style_latest"][role] = {
                        "name": name,
                        "close": round(float(close[-1]), 2),
                    }

        # 规模指数最新值
        for cfg in self._size_indices:
            tier = cfg.get("tier", "")
            name = cfg.get("name", "")
            df = size_data.get(tier)
            if df is not None and not df.empty and "close" in df.columns:
                close = df["close"].values.astype(float)
                if len(close) >= 1:
                    snapshot["size_latest"][tier] = {
                        "name": name,
                        "close": round(float(close[-1]), 2),
                    }

        return snapshot
