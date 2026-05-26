#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AiStock V10 — 交互可视化引擎 (PlotlyVisualizer)

V9 → V10 升级改进:
  1. 使用 ConfigService 加载阈值 (pcr_thresholds, state_thresholds)
  2. 其余逻辑从 V9 保持不变 (Plotly 绑定代码与配置无关)

基于 Plotly 生成交互式可视化图表, 支持中文显示。

图表类型:
  plot_market_state_4d()            — 4D雷达图 + 综合评分仪表盘
  plot_regime_probability()         — Regime概率交互柱状图
  plot_derivatives_dashboard()      — 衍生品信号多面板仪表板
  plot_risk_dashboard()             — 风险因子雷达 + 指标表
  save_html() / save_json()         — 输出保存

输出格式:
  - HTML: 独立交互式网页
  - Jupyter: 直接在 Notebook 内联显示
  - JSON: Plotly JSON 可嵌入前端

字体:     Noto Sans SC (中文字体)
配色:     深绿主题
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import plotly
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

logger = logging.getLogger(__name__)

_PLOTLY_VERSION = tuple(int(x) for x in plotly.__version__.split(".")[:2])
if _PLOTLY_VERSION < (6, 0):
    logger.warning(
        "PlotlyVisualizer 推荐 Plotly >= 6.0, 当前版本: %s", plotly.__version__
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 配色方案
# ═══════════════════════════════════════════════════════════════════════════════

COLORS = {
    "primary": "#2D6A4F",
    "secondary": "#40916C",
    "accent": "#52B788",
    "warning": "#E9C46A",
    "danger": "#E76F51",
    "info": "#264653",
    "neutral": "#6B7280",
    "background": "#F8F9FA",
    "grid": "#E5E7EB",
    "text": "#1F2937",
    "text_secondary": "#6B7280",
}

DIM_COLORS = {
    "valuation": "#2D6A4F",
    "momentum": "#40916C",
    "regime": "#52B788",
    "overseas": "#E9C46A",
}

SIGNAL_COLORS = {
    "bullish": "#2D6A4F",
    "neutral": "#6B7280",
    "bearish": "#E76F51",
}

REGIME_COLORS = {
    "牛市": "#2D6A4F", "熊市": "#E76F51", "震荡": "#E9C46A", "复苏": "#52B788",
    "bull": "#2D6A4F", "bear": "#E76F51", "volatile": "#E9C46A", "recovery": "#52B788",
}

_PLOTLY_LAYOUT_BASE = dict(
    font=dict(family="Noto Sans SC, Noto Serif SC, sans-serif", size=13),
    paper_bgcolor=COLORS["background"],
    plot_bgcolor="white",
    margin=dict(l=60, r=40, t=80, b=60),
    hoverlabel=dict(
        font_size=13,
        font_family="Noto Sans SC, sans-serif",
    ),
)


# ═══════════════════════════════════════════════════════════════════════════════
# 布局辅助函数
# ═══════════════════════════════════════════════════════════════════════════════

def _apply_layout(fig: go.Figure, title_text: str, **overrides) -> None:
    """Apply base layout + title to figure."""
    layout = dict(
        font=_PLOTLY_LAYOUT_BASE["font"],
        paper_bgcolor=_PLOTLY_LAYOUT_BASE["paper_bgcolor"],
        plot_bgcolor=_PLOTLY_LAYOUT_BASE["plot_bgcolor"],
        margin=_PLOTLY_LAYOUT_BASE["margin"],
        hoverlabel=_PLOTLY_LAYOUT_BASE["hoverlabel"],
        title=dict(text=title_text, x=0.5, font=dict(size=16, color=COLORS["text"])),
    )
    layout.update(overrides)
    fig.update_layout(**layout)


def _apply_axes(fig: go.Figure) -> None:
    """Apply base axis styling."""
    fig.update_xaxes(
        gridcolor=COLORS["grid"], zerolinecolor=COLORS["text_secondary"],
        linecolor=COLORS["grid"], title_font=dict(size=12, color=COLORS["text"]),
        tickfont=dict(size=11, color=COLORS["text_secondary"]),
    )
    fig.update_yaxes(
        gridcolor=COLORS["grid"], zerolinecolor=COLORS["text_secondary"],
        linecolor=COLORS["grid"], title_font=dict(size=12, color=COLORS["text"]),
        tickfont=dict(size=11, color=COLORS["text_secondary"]),
    )


def _apply_polar(fig: go.Figure, radial_range=(0, 100), angular_tickfont_size=12,
                 radial_tickfont_size=10, radial_tickvals=None) -> None:
    """Apply polar (radar) chart styling."""
    radialaxis = dict(
        visible=True,
        range=list(radial_range),
        tickfont=dict(size=radial_tickfont_size, color=COLORS["text_secondary"]),
        gridcolor=COLORS["grid"],
        linecolor=COLORS["grid"],
    )
    if radial_tickvals is not None:
        radialaxis["tickvals"] = radial_tickvals

    fig.update_layout(polar=dict(
        radialaxis=radialaxis,
        angularaxis=dict(
            tickfont=dict(size=angular_tickfont_size, color=COLORS["text"]),
            linecolor=COLORS["grid"],
            gridcolor=COLORS["grid"],
        ),
        bgcolor="white",
    ))


def _direction_color(direction: str) -> str:
    """方向 → 颜色"""
    d = direction.lower()
    if "bull" in d or d in ("up", "long", "positive"):
        return SIGNAL_COLORS["bullish"]
    elif "bear" in d or d in ("down", "short", "negative"):
        return SIGNAL_COLORS["bearish"]
    return SIGNAL_COLORS["neutral"]


def _score_to_color(score: float) -> str:
    """评分 → 颜色"""
    if score >= 65:
        return COLORS["primary"]
    elif score >= 50:
        return COLORS["warning"]
    else:
        return COLORS["danger"]


def _score_to_label(score: float) -> str:
    """评分 → 标签"""
    if score >= 80:
        return "战略进攻"
    elif score >= 65:
        return "积极配置"
    elif score >= 50:
        return "均衡持有"
    elif score >= 35:
        return "防御观望"
    else:
        return "战略防御"


def _safe_get(data: Any, key: str, default: Any = None) -> Any:
    """安全获取字典/对象属性"""
    if isinstance(data, dict):
        return data.get(key, default)
    if hasattr(data, key):
        return getattr(data, key, default)
    return default


def _to_dict_safe(obj: Any) -> Any:
    """递归转为可序列化字典"""
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if isinstance(obj, dict):
        return {k: _to_dict_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_dict_safe(v) for v in obj]
    return obj


# ═══════════════════════════════════════════════════════════════════════════════
# PlotlyVisualizer V10
# ═══════════════════════════════════════════════════════════════════════════════

class PlotlyVisualizer:
    """AiStock V10 交互可视化引擎

    V10: 使用 ConfigService 加载阈值参数。

    Args:
        output_dir:     输出目录
        config:         ConfigService 实例 (V10: 用于阈值)
        theme:          Plotly 主题: 'light' / 'dark' / 'custom'
        auto_open:      生成 HTML 后是否自动打开浏览器
    """

    def __init__(
        self,
        output_dir: Optional[str] = None,
        config: Any = None,
        theme: str = "light",
        auto_open: bool = False,
    ) -> None:
        project_root = Path(__file__).resolve().parent.parent.parent.parent

        if output_dir:
            self._output_dir = Path(output_dir)
        else:
            self._output_dir = project_root / "output" / "visualization"

        self._output_dir.mkdir(parents=True, exist_ok=True)

        self._config = config
        self._theme = theme
        self._auto_open = auto_open
        self._timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # V10: 从 ConfigService 加载阈值
        self._pcr_thresholds = self._load_pcr_thresholds()
        self._state_thresholds = self._load_state_thresholds()

        logger.info(
            "PlotlyVisualizer V10 初始化 | 输出目录: %s | 主题: %s | Plotly: %s",
            self._output_dir, theme, plotly.__version__,
        )

    def _load_pcr_thresholds(self) -> Dict[str, float]:
        """从 ConfigService 加载 PCR 阈值"""
        default = {
            "extreme_fear": 0.5, "fear": 0.7,
            "neutral_low": 0.85, "neutral_high": 1.15,
            "greed": 1.3, "extreme_greed": 1.5,
        }
        if self._config is not None:
            return self._config.get("market_state.pcr_thresholds", default)
        return default

    def _load_state_thresholds(self) -> Dict[str, float]:
        """从 ConfigService 加载市场状态阈值"""
        default = {
            "extreme_fear": -0.6, "fear": -0.3,
            "neutral_low": -0.1, "neutral_high": 0.1,
            "greed": 0.3, "extreme_greed": 0.6,
        }
        if self._config is not None:
            return self._config.get("market_state.state_thresholds", default)
        return default

    # ─── 保存/导出 ───────────────────────────────────────

    def save_html(self, fig: go.Figure, name: str, auto_open: bool = None) -> str:
        """保存图表为交互式 HTML"""
        filename = f"{name}_{self._timestamp}.html"
        filepath = self._output_dir / filename

        fig.write_html(
            str(filepath),
            include_plotlyjs="cdn",
            full_html=True,
            config=dict(
                displayModeBar=True,
                displaylogo=False,
                toImageButtonOptions=dict(
                    format="png", width=1600, height=900, scale=2,
                ),
                modeBarButtonsToRemove=["lasso2d", "select2d"],
            ),
        )

        open_flag = auto_open if auto_open is not None else self._auto_open
        if open_flag:
            import webbrowser
            webbrowser.open(f"file://{filepath.resolve()}")

        logger.info("交互图表已保存: %s", filepath)
        return str(filepath)

    def save_json(self, fig: go.Figure, name: str) -> str:
        """保存为 Plotly JSON"""
        filename = f"{name}_{self._timestamp}.json"
        filepath = self._output_dir / filename
        fig.write_json(str(filepath))
        logger.info("Plotly JSON 已保存: %s", filepath)
        return str(filepath)

    # ═══════════════════════════════════════════════════════════════════════
    # 1. 市场状态4D雷达图 + 仪表盘
    # ═══════════════════════════════════════════════════════════════════════

    def plot_market_state_4d(
        self,
        classification_result: Dict[str, Any],
    ) -> go.Figure:
        """绘制4D雷达图 + 综合评分仪表盘"""
        categories = ["估值", "动量", "Regime", "海外"]
        dim_keys = ["valuation_score", "momentum_score", "regime_score", "overseas_score"]
        dim_color_keys = ["valuation", "momentum", "regime", "overseas"]

        scores = [_safe_get(classification_result, k, 50) for k in dim_keys]
        composite = _safe_get(classification_result, "composite_score", 50)
        label = _safe_get(classification_result, "state_label", "均衡持有")
        direction = _safe_get(classification_result, "direction", "neutral")

        fig = make_subplots(
            rows=1, cols=2,
            column_widths=[0.55, 0.45],
            specs=[[dict(type="scatterpolar"), dict(type="indicator")]],
            subplot_titles=["4D 维度评分雷达", "综合评分仪表盘"],
            horizontal_spacing=0.12,
        )

        # 左: 雷达图
        fig.add_trace(
            go.Scatterpolar(
                r=scores + [scores[0]],
                theta=categories + [categories[0]],
                fill="toself",
                fillcolor=COLORS["accent"],
                opacity=0.25,
                line=dict(color=_score_to_color(composite), width=3),
                marker=dict(
                    size=10,
                    color=[DIM_COLORS[k] for k in dim_color_keys],
                    line=dict(width=2, color="white"),
                ),
                name="当前评分",
                hovertemplate="<b>%{theta}</b><br>评分: %{r:.1f}<extra></extra>",
            ),
            row=1, col=1,
        )

        fig.add_trace(
            go.Scatterpolar(
                r=[50] * 5,
                theta=categories + [categories[0]],
                fill="toself",
                fillcolor="rgba(107,114,128,0.05)",
                line=dict(color=COLORS["neutral"], width=1, dash="dash"),
                name="中性线 (50)",
                hoverinfo="skip",
                showlegend=True,
            ),
            row=1, col=1,
        )

        _apply_polar(fig, radial_range=(0, 100), radial_tickfont_size=10,
                     angular_tickfont_size=13, radial_tickvals=[20, 40, 60, 80, 100])

        # 右: 仪表盘
        gauge_color = _score_to_color(composite)
        steps_colors = [
            dict(range=[0, 35], color="#FECACA"),
            dict(range=[35, 50], color="#FEF08A"),
            dict(range=[50, 65], color="#D9F99D"),
            dict(range=[65, 80], color="#86EFAC"),
            dict(range=[80, 100], color="#2D6A4F"),
        ]

        fig.add_trace(
            go.Indicator(
                mode="gauge+number+delta",
                value=composite,
                delta=dict(
                    reference=50,
                    decreasing=dict(color=COLORS["danger"]),
                    increasing=dict(color=COLORS["primary"]),
                    font=dict(size=18),
                ),
                number=dict(
                    font=dict(size=42, color=gauge_color, family="Noto Sans SC"),
                    suffix="",
                ),
                title=dict(
                    text=f"<b>{label}</b><br><span style='font-size:12px;color:{_direction_color(direction)}'>"
                         f"方向: {direction}</span>",
                    font=dict(size=16),
                ),
                gauge=dict(
                    axis=dict(range=[0, 100], tickwidth=1, tickcolor=COLORS["grid"], tickfont=dict(size=10)),
                    bar=dict(color=gauge_color, thickness=0.3),
                    bgcolor="white",
                    borderwidth=2,
                    bordercolor=COLORS["grid"],
                    steps=steps_colors,
                    threshold=dict(
                        line=dict(color=COLORS["danger"], width=4),
                        thickness=0.75,
                        value=composite,
                    ),
                ),
            ),
            row=1, col=2,
        )

        subtitle_parts = " | ".join(f"{cat}={score:.0f}" for cat, score in zip(categories, scores))
        _color_text_sec = COLORS["text_secondary"]
        title_text = (
            f"AiStock V10 市场状态4D分析<br>"
            f"<span style='font-size:13px;color:{_color_text_sec}'>"
            f"{subtitle_parts}</span>"
        )
        _apply_layout(fig, title_text,
            legend=dict(orientation="h", yanchor="bottom", y=1.08, xanchor="center", x=0.3, font=dict(size=11)),
            height=600,
        )

        return fig

    # ═══════════════════════════════════════════════════════════════════════
    # 2. Regime概率交互柱状图
    # ═══════════════════════════════════════════════════════════════════════

    def plot_regime_probability(
        self,
        regime_result: Dict[str, Any],
    ) -> go.Figure:
        """绘制市场Regime概率交互柱状图"""
        probabilities = _safe_get(regime_result, "probabilities", {})
        current = _safe_get(regime_result, "current_regime", "未知")
        confirmation = _safe_get(regime_result, "confirmation_days", 0)
        regime_score = _safe_get(regime_result, "regime_score", 50)
        transition = _safe_get(regime_result, "transition_signals", [])

        if not probabilities:
            probabilities = {"牛市": 0.25, "熊市": 0.15, "震荡": 0.40, "复苏": 0.20}

        regimes = list(probabilities.keys())
        probs = list(probabilities.values())
        bar_colors = [REGIME_COLORS.get(r, COLORS["neutral"]) for r in regimes]

        line_widths = [3 if r == current else 0 for r in regimes]
        line_colors = [COLORS["danger"] if r == current else "white" for r in regimes]

        fig = go.Figure()

        fig.add_trace(
            go.Bar(
                y=regimes,
                x=probs,
                orientation="h",
                marker=dict(color=bar_colors, opacity=0.85,
                            line=dict(width=line_widths, color=line_colors)),
                text=[f"{p:.1%}" for p in probs],
                textposition="outside",
                textfont=dict(size=14, color=COLORS["text"]),
                hovertemplate="<b>%{y}</b><br>概率: %{x:.1%}<extra></extra>",
                name="概率",
            )
        )

        if transition:
            trans_text = "<br>".join(f"▸ {s}" for s in transition[:5])
            fig.add_annotation(
                x=0.98, y=0.02,
                text=f"<b>过渡信号:</b><br>{trans_text}",
                showarrow=False,
                xref="paper", yref="paper",
                font=dict(size=11, color=COLORS["info"]),
                align="right",
                bordercolor=COLORS["grid"],
                borderwidth=1,
                borderpad=8,
                bgcolor="rgba(255,255,255,0.9)",
            )

        _color_text_sec = COLORS["text_secondary"]
        title_text = (
            f"AiStock V10 市场Regime概率分布<br>"
            f"<span style='font-size:13px;color:{_color_text_sec}'>"
            f"当前: <b>{current}</b> | 确认天数: {confirmation} | "
            f"Regime评分: {regime_score:.1f}</span>"
        )
        _apply_layout(fig, title_text, height=500, showlegend=False)
        _apply_axes(fig)
        fig.update_layout(
            xaxis=dict(title="概率", tickformat=".0%",
                       range=[0, max(probs) * 1.35 if probs else 1.0]),
            yaxis=dict(title="", tickfont=dict(size=13, color=COLORS["text"])),
        )

        return fig

    # ═══════════════════════════════════════════════════════════════════════
    # 3. 衍生品信号仪表板
    # ═══════════════════════════════════════════════════════════════════════

    def plot_derivatives_dashboard(
        self,
        derivatives_result: Dict[str, Any],
    ) -> go.Figure:
        """绘制衍生品信号交互仪表板"""
        basis_signals = _safe_get(derivatives_result, "basis_signals", {})
        term_structure = _safe_get(derivatives_result, "term_structure", {})
        commodity_signals = _safe_get(derivatives_result, "commodity_signals", {})
        index_futures_basis = _safe_get(derivatives_result, "index_futures_basis", {})
        composite_signal = _safe_get(derivatives_result, "composite_signal", 50)
        signal_level = _safe_get(derivatives_result, "signal_level", "normal")

        has_basis = bool(basis_signals)
        has_term = bool(term_structure)
        has_commodity = bool(commodity_signals)
        has_basis_index = bool(index_futures_basis)

        subplot_count = 1 + int(has_term) + int(has_commodity) + int(has_basis_index)
        cols = min(subplot_count, 2)
        rows = (subplot_count + cols - 1) // cols

        specs = []
        for r in range(rows):
            row_specs = []
            for c in range(cols):
                idx = r * cols + c
                if idx < subplot_count:
                    row_specs.append(dict(type="xy"))
                else:
                    row_specs.append(None)
            specs.append(row_specs)

        titles = []
        if has_basis:
            titles.append("期货基差信号")
        if has_term:
            titles.append("期限结构")
        if has_commodity:
            titles.append("商品品种信号")
        if has_basis_index:
            titles.append("股指期货基差")
        while len(titles) < subplot_count:
            titles.append("")

        fig = make_subplots(
            rows=rows, cols=cols,
            specs=specs,
            subplot_titles=titles,
            vertical_spacing=0.12,
            horizontal_spacing=0.15,
        )

        subplot_idx = 0

        if has_basis:
            r, c = divmod(subplot_idx, cols)
            r, c = r + 1, c + 1
            contracts = list(basis_signals.keys())
            basis_vals = list(basis_signals.values())
            colors = [COLORS["primary"] if v > 0 else COLORS["danger"] for v in basis_vals]
            fig.add_trace(go.Bar(
                x=contracts, y=basis_vals,
                marker=dict(color=colors, opacity=0.85),
                name="基差率",
                hovertemplate="<b>%{x}</b><br>基差率: %{y:.4f}%<extra></extra>",
            ), row=r, col=c)
            fig.add_hline(y=0, line_dash="dash", line_color=COLORS["text"], line_width=1, row=r, col=c)
            fig.add_hline(y=-1.5, line_dash="dash", line_color=COLORS["warning"], line_width=1, row=r, col=c)
            fig.add_hline(y=-2.0, line_dash="dash", line_color=COLORS["danger"], line_width=1, row=r, col=c)
            fig.update_yaxes(title_text="基差率 (%)", row=r, col=c)
            subplot_idx += 1

        if has_term:
            r, c = divmod(subplot_idx, cols)
            r, c = r + 1, c + 1
            plot_colors = [COLORS["primary"], COLORS["accent"], COLORS["warning"], COLORS["info"], COLORS["danger"]]
            for i, (variety, months) in enumerate(term_structure.items()):
                if isinstance(months, dict):
                    month_labels = list(months.keys())
                    prices = list(months.values())
                    fig.add_trace(go.Scatter(
                        x=month_labels, y=prices,
                        mode="lines+markers", name=variety,
                        line=dict(color=plot_colors[i % len(plot_colors)], width=2.5),
                        marker=dict(size=8),
                        hovertemplate=f"<b>{variety}</b><br>%{{x}}: %{{y:.2f}}<extra></extra>",
                    ), row=r, col=c)
            fig.update_yaxes(title_text="价格", row=r, col=c)
            fig.update_xaxes(title_text="合约月份", row=r, col=c)
            subplot_idx += 1

        if has_commodity:
            r, c = divmod(subplot_idx, cols)
            r, c = r + 1, c + 1
            varieties = list(commodity_signals.keys())
            signals = []
            for v in varieties:
                data = commodity_signals[v]
                if hasattr(data, "to_dict"):
                    data = data.to_dict()
                signals.append(data.get("signal", 0) if isinstance(data, dict) else 0)

            scatter_colors = [COLORS["primary"] if s > 0 else COLORS["danger"] for s in signals]
            fig.add_trace(go.Bar(
                x=varieties, y=signals,
                marker=dict(color=scatter_colors, opacity=0.85),
                name="商品信号",
                hovertemplate="<b>%{x}</b><br>信号: %{y:.1f}<extra></extra>",
            ), row=r, col=c)
            fig.add_hline(y=0, line_dash="dash", line_color=COLORS["neutral"], line_width=1, row=r, col=c)
            fig.update_yaxes(title_text="信号强度 (-100~+100)", row=r, col=c)
            subplot_idx += 1

        if has_basis_index:
            r, c = divmod(subplot_idx, cols)
            r, c = r + 1, c + 1
            if_vars = list(index_futures_basis.keys())
            basis_pcts = []
            if_names = []
            for v in if_vars:
                data = index_futures_basis[v]
                if hasattr(data, "to_dict"):
                    data = data.to_dict()
                if isinstance(data, dict):
                    basis_pcts.append(data.get("basis_pct", 0))
                    if_names.append(data.get("name", v))
                else:
                    basis_pcts.append(0)
                    if_names.append(v)

            fig.add_trace(go.Bar(
                x=if_names, y=basis_pcts,
                marker=dict(color=[COLORS["primary"] if b > 0 else COLORS["danger"] for b in basis_pcts], opacity=0.85),
                name="股指基差率",
                hovertemplate="<b>%{x}</b><br>基差率: %{y:.4f}%<extra></extra>",
            ), row=r, col=c)
            fig.add_hline(y=0, line_dash="dash", line_color=COLORS["text"], line_width=1, row=r, col=c)
            fig.update_yaxes(title_text="基差率 (%)", row=r, col=c)
            subplot_idx += 1

        _color_text_sec = COLORS["text_secondary"]
        title_text = (
            f"AiStock V10 衍生品信号仪表板<br>"
            f"<span style='font-size:13px;color:{_color_text_sec}'>"
            f"综合信号: <b>{composite_signal:.1f}</b> | 级别: {signal_level}</span>"
        )
        _apply_layout(fig, title_text,
            height=max(500, rows * 380),
            barmode="relative",
            legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="center", x=0.5, font=dict(size=11)),
        )
        _apply_axes(fig)

        return fig

    # ═══════════════════════════════════════════════════════════════════════
    # 4. 风险评估仪表板
    # ═══════════════════════════════════════════════════════════════════════

    def plot_risk_dashboard(
        self,
        risk_result: Dict[str, Any],
    ) -> go.Figure:
        """绘制风险评估交互仪表板"""
        risk_factors = _safe_get(risk_result, "risk_factors", {})
        overall_score = _safe_get(risk_result, "overall_risk_score", 50)
        risk_level = _safe_get(risk_result, "risk_level", "moderate")
        risk_metrics = _safe_get(risk_result, "risk_metrics", {})
        warnings = _safe_get(risk_result, "warnings", [])

        factor_names = []
        factor_scores = []
        for k, v in risk_factors.items():
            factor_names.append(k)
            if isinstance(v, dict):
                factor_scores.append(v.get("score", v.get("value", 0)))
            elif hasattr(v, "score"):
                factor_scores.append(v.score)
            else:
                factor_scores.append(float(v) if v is not None else 0)

        fig = make_subplots(
            rows=1, cols=2,
            column_widths=[0.5, 0.5],
            specs=[[dict(type="scatterpolar"), dict(type="table")]],
            subplot_titles=["风险因子雷达", "风险指标详情"],
            horizontal_spacing=0.15,
        )

        if factor_names:
            fig.add_trace(
                go.Scatterpolar(
                    r=factor_scores + [factor_scores[0]],
                    theta=factor_names + [factor_names[0]],
                    fill="toself",
                    fillcolor=COLORS["danger"],
                    opacity=0.2,
                    line=dict(color=COLORS["danger"], width=2.5),
                    marker=dict(size=8, color=COLORS["danger"]),
                    name="风险评分",
                    hovertemplate="<b>%{theta}</b><br>评分: %{r:.1f}<extra></extra>",
                ),
                row=1, col=1,
            )

        _apply_polar(fig,
                     radial_range=(0, max(factor_scores) * 1.2 if factor_scores else 100),
                     radial_tickfont_size=10,
                     angular_tickfont_size=11)

        # 右: 指标表
        header_vals = ["<b>指标</b>", "<b>数值</b>"]
        cell_vals = [[], []]

        risk_color = COLORS["primary"] if overall_score >= 60 else (
            COLORS["warning"] if overall_score >= 40 else COLORS["danger"])

        cell_vals[0].append("综合风险评分")
        cell_vals[1].append(f"{overall_score:.1f}")
        cell_vals[0].append("风险级别")
        cell_vals[1].append(risk_level)

        for name, score in zip(factor_names, factor_scores):
            cell_vals[0].append(f"▸ {name}")
            cell_vals[1].append(f"{score:.1f}")

        if risk_metrics:
            for k, v in risk_metrics.items():
                cell_vals[0].append(f"◆ {k}")
                cell_vals[1].append(f"{v:.4f}" if isinstance(v, float) else str(v))

        if warnings:
            for w in warnings[:5]:
                cell_vals[0].append(f"⚠ {w}")
                cell_vals[1].append("")

        fig.add_trace(
            go.Table(
                header=dict(
                    values=header_vals,
                    fill_color=COLORS["primary"],
                    font=dict(color="white", size=13),
                    align="left",
                    height=36,
                ),
                cells=dict(
                    values=cell_vals,
                    fill_color=[
                        [COLORS["background"] if i % 2 == 0 else "white" for i in range(len(cell_vals[0]))],
                        [COLORS["background"] if i % 2 == 0 else "white" for i in range(len(cell_vals[0]))],
                    ],
                    font=dict(size=12, color=COLORS["text"]),
                    align="left",
                    height=30,
                ),
                columnwidth=[180, 120],
            ),
            row=1, col=2,
        )

        warn_text = ""
        if warnings:
            warn_text = f" | ⚠ {len(warnings)}条警告"

        title_text = (
            f"AiStock V10 风险评估仪表板<br>"
            f"<span style='font-size:13px;color:{risk_color}'>"
            f"综合评分: <b>{overall_score:.1f}</b> | 级别: {risk_level}{warn_text}</span>"
        )
        _apply_layout(fig, title_text, height=550)

        return fig

    # ═══════════════════════════════════════════════════════════════════════
    # 5. PCR仪表板
    # ═══════════════════════════════════════════════════════════════════════

    def plot_pcr_dashboard(
        self,
        pcr_result: Dict[str, Any],
    ) -> go.Figure:
        """绘制PCR多标的交互对比仪表板"""
        etf_pcr = _safe_get(pcr_result, "etf_pcr", {})
        cffex_pcr = _safe_get(pcr_result, "cffex_pcr", {})
        commodity_pcr = _safe_get(pcr_result, "commodity_pcr", {})
        composite = _safe_get(pcr_result, "composite_pcr", {})

        all_underlyings = []
        all_oi_pcr = []
        all_vol_pcr = []
        all_colors = []

        for source, data, color in [
            ("ETF", etf_pcr, COLORS["primary"]),
            ("CFFEX", cffex_pcr, COLORS["accent"]),
            ("商品", commodity_pcr, COLORS["warning"]),
        ]:
            for underlying, pcr_data in data.items():
                if isinstance(pcr_data, dict):
                    oi_pcr = pcr_data.get("oi_pcr", pcr_data.get("oi_pcr_ratio", 0))
                    vol_pcr = pcr_data.get("volume_pcr", pcr_data.get("volume_pcr_ratio", 0))
                elif hasattr(pcr_data, "oi_pcr"):
                    oi_pcr = pcr_data.oi_pcr
                    vol_pcr = pcr_data.volume_pcr
                else:
                    oi_pcr = 0
                    vol_pcr = 0
                all_underlyings.append(f"{source}:{underlying}")
                all_oi_pcr.append(oi_pcr)
                all_vol_pcr.append(vol_pcr)
                all_colors.append(color)

        fig = go.Figure()

        if all_underlyings:
            fig.add_trace(go.Bar(
                name="持仓PCR",
                x=all_underlyings,
                y=all_oi_pcr,
                marker_color=COLORS["primary"],
                opacity=0.85,
            ))
            fig.add_trace(go.Bar(
                name="成交量PCR",
                x=all_underlyings,
                y=all_vol_pcr,
                marker_color=COLORS["accent"],
                opacity=0.85,
            ))

            # V10: 使用配置阈值的中性线
            neutral_low = self._pcr_thresholds.get("neutral_low", 0.85)
            neutral_high = self._pcr_thresholds.get("neutral_high", 1.15)
            fig.add_hline(y=neutral_low, line_dash="dash", line_color=COLORS["neutral"],
                         annotation_text=f"中性低 {neutral_low}")
            fig.add_hline(y=neutral_high, line_dash="dash", line_color=COLORS["neutral"],
                         annotation_text=f"中性高 {neutral_high}")
            fig.add_hline(y=1.0, line_dash="dot", line_color=COLORS["grid"])

        composite_val = 0
        if isinstance(composite, dict):
            composite_val = composite.get("composite_pcr", composite.get("oi_pcr", 0))
        elif hasattr(composite, "composite_pcr"):
            composite_val = composite.composite_pcr

        _color_text_sec = COLORS["text_secondary"]
        title_text = (
            f"AiStock V10 PCR多标的仪表板<br>"
            f"<span style='font-size:13px;color:{_color_text_sec}'>"
            f"综合PCR: <b>{composite_val:.2f}</b> | 标的数: {len(all_underlyings)}</span>"
        )
        _apply_layout(fig, title_text,
            height=500,
            barmode="group",
            legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="center", x=0.5, font=dict(size=11)),
        )
        _apply_axes(fig)
        fig.update_yaxes(title_text="PCR 比率")

        return fig

    # ═══════════════════════════════════════════════════════════════════════
    # 6. 综合仪表板 (所有模块, Tab切换)
    # ═══════════════════════════════════════════════════════════════════════

    def plot_composite_dashboard(
        self,
        market_state_data: Dict[str, Any],
    ) -> go.Figure:
        """绘制综合仪表板

        Args:
            market_state_data: 包含所有子模块数据的字典:
                - classification: 市场状态分类结果
                - regime: Regime检测结果
                - derivatives: 衍生品信号结果
                - risk: 风险评估结果
                - pcr: PCR结果
        """
        classification = _safe_get(market_state_data, "classification", {})
        composite_score = _safe_get(classification, "composite_score", 50)
        direction = _safe_get(classification, "direction", "neutral")

        dim_keys = ["valuation_score", "momentum_score", "regime_score", "overseas_score"]
        dim_labels = ["估值", "动量", "Regime", "海外"]
        scores = [_safe_get(classification, k, 50) for k in dim_keys]

        # 综合面板: 左侧维度评分, 右侧指标概览
        fig = make_subplots(
            rows=2, cols=2,
            column_widths=[0.5, 0.5],
            row_heights=[0.4, 0.6],
            specs=[
                [dict(type="xy"), dict(type="indicator")],
                [dict(type="xy"), dict(type="xy")],
            ],
            subplot_titles=["维度评分", "综合评分", "信号分布", "关键指标"],
        )

        # 维度评分柱状图
        dim_colors = [DIM_COLORS.get(k, COLORS["neutral"]) for k in ["valuation", "momentum", "regime", "overseas"]]
        fig.add_trace(
            go.Bar(
                x=dim_labels,
                y=scores,
                marker=dict(color=dim_colors, opacity=0.85),
                name="维度评分",
                hovertemplate="<b>%{x}</b><br>评分: %{y:.1f}<extra></extra>",
            ),
            row=1, col=1,
        )

        # 综合评分仪表
        gauge_color = _score_to_color(composite_score)
        fig.add_trace(
            go.Indicator(
                mode="gauge+number",
                value=composite_score,
                number=dict(font=dict(size=36, color=gauge_color)),
                gauge=dict(
                    axis=dict(range=[0, 100]),
                    bar=dict(color=gauge_color, thickness=0.3),
                    bgcolor="white",
                    borderwidth=1,
                    bordercolor=COLORS["grid"],
                    steps=[
                        dict(range=[0, 35], color="#FECACA"),
                        dict(range=[35, 50], color="#FEF08A"),
                        dict(range=[50, 65], color="#D9F99D"),
                        dict(range=[65, 80], color="#86EFAC"),
                        dict(range=[80, 100], color="#2D6A4F"),
                    ],
                ),
            ),
            row=1, col=2,
        )

        # 信号分布 (衍生品)
        derivatives = _safe_get(market_state_data, "derivatives", {})
        commodity_signals = _safe_get(derivatives, "commodity_signals", {})
        if commodity_signals:
            varieties = list(commodity_signals.keys())
            signals = []
            for v in varieties:
                data = commodity_signals[v]
                if hasattr(data, "to_dict"):
                    data = data.to_dict()
                signals.append(data.get("signal", 0) if isinstance(data, dict) else 0)
            bar_colors = [COLORS["primary"] if s > 0 else COLORS["danger"] for s in signals]
            fig.add_trace(
                go.Bar(
                    x=varieties, y=signals,
                    marker=dict(color=bar_colors, opacity=0.85),
                    name="商品信号",
                ),
                row=2, col=1,
            )
            fig.add_hline(y=0, line_dash="dash", line_color=COLORS["neutral"], line_width=1, row=2, col=1)

        # 关键指标
        fig.add_trace(
            go.Table(
                header=dict(
                    values=["<b>指标</b>", "<b>数值</b>"],
                    fill_color=COLORS["primary"],
                    font=dict(color="white", size=12),
                    align="left",
                ),
                cells=dict(
                    values=[
                        ["综合评分", "方向", "估值", "动量", "Regime", "海外"],
                        [
                            f"{composite_score:.1f}",
                            direction,
                            f"{scores[0]:.1f}",
                            f"{scores[1]:.1f}",
                            f"{scores[2]:.1f}",
                            f"{scores[3]:.1f}",
                        ],
                    ],
                    font=dict(size=11, color=COLORS["text"]),
                    align="left",
                ),
                columnwidth=[120, 100],
            ),
            row=2, col=2,
        )

        _apply_layout(fig, "AiStock V10 市场状态综合仪表板", height=800)
        _apply_axes(fig)

        return fig
