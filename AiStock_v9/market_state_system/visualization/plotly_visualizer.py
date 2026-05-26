#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AiStock V8 — 交互可视化引擎 (PlotlyVisualizer)

基于 Plotly 6.7.0 生成交互式可视化图表, 支持中文显示。

图表类型:
  plot_market_state_4d()            — 4D雷达图 + 综合评分仪表盘
  plot_regime_probability()         — Regime概率交互柱状图
  plot_derivatives_dashboard()      — 衍生品信号多面板仪表板
  plot_risk_dashboard()             — 风险因子雷达 + 指标表
  plot_pcr_dashboard()              — PCR多标的交互对比
  plot_overseas_signal_dashboard()  — 外盘四维信号面板
  plot_macro_dashboard()            — 宏观信号五维度面板
  plot_composite_dashboard()        — 综合仪表板 (所有模块, Tab切换)

输出格式:
  - HTML: 独立交互式网页, 支持缩放/悬停/筛选/导出
  - Jupyter: 直接在 Notebook 内联显示
  - JSON: Plotly JSON 可嵌入前端

字体:     Noto Sans SC (中文字体)
配色:     与 StateVisualizer 一致的深绿主题
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

# ─── Plotly 版本校验 ─────────────────────────────────────────
_PLOTLY_VERSION = tuple(int(x) for x in plotly.__version__.split(".")[:2])
if _PLOTLY_VERSION < (6, 0):
    logger.warning(
        "PlotlyVisualizer 推荐 Plotly >= 6.0, 当前版本: %s", plotly.__version__
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 配色方案 (与 StateVisualizer 保持一致)
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
    "牛市": "#2D6A4F",
    "熊市": "#E76F51",
    "震荡": "#E9C46A",
    "复苏": "#52B788",
    "bull": "#2D6A4F",
    "bear": "#E76F51",
    "volatile": "#E9C46A",
    "recovery": "#52B788",
}

# Plotly 主题模板
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

_PLOTLY_AXIS_BASE = dict(
    gridcolor=COLORS["grid"],
    zerolinecolor=COLORS["text_secondary"],
    linecolor=COLORS["grid"],
    title_font=dict(size=12, color=COLORS["text"]),
)


# ═══════════════════════════════════════════════════════════════════════════════
# 布局 / 轴 / 极坐标 辅助函数
# ═══════════════════════════════════════════════════════════════════════════════

def _apply_layout(fig: go.Figure, title_text: str, **overrides) -> None:
    """Apply base layout + title to figure.

    Avoids ``**_PLOTLY_LAYOUT_BASE`` which can conflict with an explicit
    *title* keyword passed at the same time.
    """
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
    """Apply base axis styling.

    Separates *tickfont* from the old ``_PLOTLY_AXIS_BASE`` so that callers
    can override tickfont without keyword conflicts.
    """
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
    """Apply polar (radar) chart styling.

    Uses ``fig.update_layout(polar=dict(...))`` instead of the removed
    ``fig.update_polar(...)`` which does not exist in Plotly 6.7.0.
    """
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


# ═══════════════════════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════════════════════

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
# PlotlyVisualizer
# ═══════════════════════════════════════════════════════════════════════════════

class PlotlyVisualizer:
    """AiStock V8 交互可视化引擎

    基于 Plotly 6.7.0 生成专业级交互式量化分析图表。

    Args:
        output_dir:     输出目录, 默认为项目根目录下 output/visualization/
        config:         ConfigService 实例 (可选)
        theme:          Plotly 主题: 'light' / 'dark' / 'custom'
        auto_open:      生成 HTML 后是否自动打开浏览器

    Example:
        >>> viz = PlotlyVisualizer()
        >>> fig = viz.plot_market_state_4d(classification_result)
        >>> fig.show()                              # Jupyter 内联
        >>> viz.save_html(fig, "market_state_4d")   # 保存 HTML
    """

    def __init__(
        self,
        output_dir: Optional[str] = None,
        config: Any = None,
        theme: str = "light",
        auto_open: bool = False,
    ) -> None:
        project_root = Path(__file__).resolve().parent.parent.parent

        if output_dir:
            self._output_dir = Path(output_dir)
        else:
            self._output_dir = project_root / "output" / "visualization"

        self._output_dir.mkdir(parents=True, exist_ok=True)

        self._config = config
        self._theme = theme
        self._auto_open = auto_open
        self._timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        logger.info(
            "PlotlyVisualizer 初始化 | 输出目录: %s | 主题: %s | Plotly: %s",
            self._output_dir, theme, plotly.__version__,
        )

    # ─── 保存/导出 ───────────────────────────────────────

    def save_html(self, fig: go.Figure, name: str, auto_open: bool = None) -> str:
        """保存图表为交互式 HTML

        Args:
            fig:       Plotly Figure 对象
            name:      文件名 (不含扩展名)
            auto_open: 是否自动打开浏览器 (覆盖实例设置)

        Returns:
            保存路径
        """
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
                    format="png",
                    width=1600,
                    height=900,
                    scale=2,
                ),
                modeBarButtonsToRemove=[
                    "lasso2d", "select2d",
                ],
            ),
        )

        open_flag = auto_open if auto_open is not None else self._auto_open
        if open_flag:
            import webbrowser
            webbrowser.open(f"file://{filepath.resolve()}")

        logger.info("交互图表已保存: %s", filepath)
        return str(filepath)

    def save_json(self, fig: go.Figure, name: str) -> str:
        """保存为 Plotly JSON (可嵌入前端)

        Args:
            fig:  Plotly Figure 对象
            name: 文件名 (不含扩展名)

        Returns:
            保存路径
        """
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
        """绘制4D雷达图 + 综合评分仪表盘

        Args:
            classification_result: 市场状态分类结果, 含:
                - valuation_score / momentum_score / regime_score / overseas_score
                - composite_score, state_label, direction, weights

        Returns:
            Plotly Figure
        """
        categories = ["估值", "动量", "Regime", "海外"]
        dim_keys = ["valuation_score", "momentum_score", "regime_score", "overseas_score"]
        dim_color_keys = ["valuation", "momentum", "regime", "overseas"]

        scores = [_safe_get(classification_result, k, 50) for k in dim_keys]
        composite = _safe_get(classification_result, "composite_score", 50)
        label = _safe_get(classification_result, "state_label", "均衡持有")
        direction = _safe_get(classification_result, "direction", "neutral")
        weights = _safe_get(classification_result, "weights", {})

        # ─── 创建双子图 ────────────────────────────────────
        fig = make_subplots(
            rows=1, cols=2,
            column_widths=[0.55, 0.45],
            specs=[
                [dict(type="scatterpolar"), dict(type="indicator")],
            ],
            subplot_titles=["4D 维度评分雷达", "综合评分仪表盘"],
            horizontal_spacing=0.12,
        )

        # ─── 左: 雷达图 ────────────────────────────────────
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

        # 中性线 (50分)
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

        _apply_polar(
            fig,
            radial_range=(0, 100),
            radial_tickfont_size=10,
            angular_tickfont_size=13,
            radial_tickvals=[20, 40, 60, 80, 100],
        )

        # ─── 右: 仪表盘 ──────────────────────────────────
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
                    axis=dict(
                        range=[0, 100],
                        tickwidth=1,
                        tickcolor=COLORS["grid"],
                        tickfont=dict(size=10),
                    ),
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

        # ─── 布局 ──────────────────────────────────────────
        subtitle_parts = " | ".join(
            f"{cat}={score:.0f}" for cat, score in zip(categories, scores)
        )
        _color_text_sec = COLORS["text_secondary"]
        title_text = (
            f"AiStock V8 市场状态4D分析<br>"
            f"<span style='font-size:13px;color:{_color_text_sec}'>"
            f"{subtitle_parts}</span>"
        )
        _apply_layout(fig, title_text,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.08,
                xanchor="center",
                x=0.3,
                font=dict(size=11),
            ),
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
        """绘制市场Regime概率交互柱状图

        Args:
            regime_result: Regime检测结果, 含:
                - probabilities: {regime_name: probability}
                - current_regime: 当前regime名称
                - confirmation_days: 确认天数
                - regime_score: Regime评分
                - transition_signals: 过渡信号列表

        Returns:
            Plotly Figure
        """
        probabilities = _safe_get(regime_result, "probabilities", {})
        current = _safe_get(regime_result, "current_regime", "未知")
        confirmation = _safe_get(regime_result, "confirmation_days", 0)
        regime_score = _safe_get(regime_result, "regime_score", 50)
        transition = _safe_get(regime_result, "transition_signals", [])
        overseas_adj = _safe_get(regime_result, "overseas_adjustment", None)

        if not probabilities:
            probabilities = {"牛市": 0.25, "熊市": 0.15, "震荡": 0.40, "复苏": 0.20}

        regimes = list(probabilities.keys())
        probs = list(probabilities.values())
        bar_colors = [REGIME_COLORS.get(r, COLORS["neutral"]) for r in regimes]

        # 当前regime高亮边框
        line_widths = [3 if r == current else 0 for r in regimes]
        line_colors = [COLORS["danger"] if r == current else "white" for r in regimes]

        fig = go.Figure()

        fig.add_trace(
            go.Bar(
                y=regimes,
                x=probs,
                orientation="h",
                marker=dict(
                    color=bar_colors,
                    opacity=0.85,
                    line=dict(width=line_widths, color=line_colors),
                ),
                text=[f"{p:.1%}" for p in probs],
                textposition="outside",
                textfont=dict(size=14, color=COLORS["text"]),
                hovertemplate="<b>%{y}</b><br>概率: %{x:.1%}<extra></extra>",
                name="概率",
            )
        )

        # 过渡信号注释
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

        # 海外调整注释
        overseas_note = ""
        if overseas_adj:
            ov_dir = _safe_get(overseas_adj, "direction", "N/A")
            ov_delta = _safe_get(overseas_adj, "delta", 0)
            overseas_note = f" | 海外调整: {ov_dir} ({ov_delta:+.1f})"

        _color_text_sec = COLORS["text_secondary"]
        title_text = (
            f"AiStock V8 市场Regime概率分布<br>"
            f"<span style='font-size:13px;color:{_color_text_sec}'>"
            f"当前: <b>{current}</b> | 确认天数: {confirmation} | "
            f"Regime评分: {regime_score:.1f}{overseas_note}</span>"
        )
        _apply_layout(fig, title_text, height=500, showlegend=False)
        _apply_axes(fig)
        fig.update_layout(
            xaxis=dict(
                title="概率",
                tickformat=".0%",
                range=[0, max(probs) * 1.35 if probs else 1.0],
            ),
            yaxis=dict(
                title="",
                tickfont=dict(size=13, color=COLORS["text"]),
            ),
        )

        return fig

    # ═══════════════════════════════════════════════════════════════════════
    # 3. 衍生品信号仪表板
    # ═══════════════════════════════════════════════════════════════════════

    def plot_derivatives_dashboard(
        self,
        derivatives_result: Dict[str, Any],
    ) -> go.Figure:
        """绘制衍生品信号交互仪表板

        Args:
            derivatives_result: 衍生品信号结果, 含:
                - basis_signals: {contract: basis_pct}
                - term_structure: {variety: {month: price}}
                - composite_signal: 综合信号评分
                - signal_level: 信号级别
                - overseas_adjustment: 海外调整

        Returns:
            Plotly Figure
        """
        basis_signals = _safe_get(derivatives_result, "basis_signals", {})
        term_structure = _safe_get(derivatives_result, "term_structure", {})
        commodity_signals = _safe_get(derivatives_result, "commodity_signals", {})
        index_futures_basis = _safe_get(derivatives_result, "index_futures_basis", {})
        industry_sentiment = _safe_get(derivatives_result, "industry_sentiment", {})
        composite_signal = _safe_get(derivatives_result, "composite_signal", 50)
        signal_level = _safe_get(derivatives_result, "signal_level", "normal")
        overseas_adj = _safe_get(derivatives_result, "overseas_adjustment", None)

        # ─── 构建子图网格 ──────────────────────────────────
        has_basis = bool(basis_signals)
        has_term = bool(term_structure)
        has_commodity = bool(commodity_signals)
        has_basis_index = bool(index_futures_basis)

        # 动态计算行列数
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

        fig = make_subplots(
            rows=rows, cols=cols,
            specs=specs,
            subplot_titles=self._derivatives_subplot_titles(
                has_basis, has_term, has_commodity, has_basis_index, subplot_count,
            ),
            vertical_spacing=0.12,
            horizontal_spacing=0.15,
        )

        subplot_idx = 0

        # ─── 子图1: 基差信号柱状图 ──────────────────────
        if has_basis:
            r, c = divmod(subplot_idx, cols)
            r, c = r + 1, c + 1
            contracts = list(basis_signals.keys())
            basis_vals = list(basis_signals.values())
            colors = [COLORS["primary"] if v > 0 else COLORS["danger"] for v in basis_vals]

            fig.add_trace(
                go.Bar(
                    x=contracts,
                    y=basis_vals,
                    marker=dict(color=colors, opacity=0.85),
                    name="基差率",
                    hovertemplate="<b>%{x}</b><br>基差率: %{y:.4f}%<extra></extra>",
                ),
                row=r, col=c,
            )

            # 预警线
            fig.add_hline(y=0, line_dash="dash", line_color=COLORS["text"],
                         line_width=1, row=r, col=c)
            fig.add_hline(y=-1.5, line_dash="dash", line_color=COLORS["warning"],
                         line_width=1, annotation_text="预警", row=r, col=c)
            fig.add_hline(y=-2.0, line_dash="dash", line_color=COLORS["danger"],
                         line_width=1, annotation_text="极端", row=r, col=c)

            fig.update_yaxes(title_text="基差率 (%)", row=r, col=c)
            subplot_idx += 1

        # ─── 子图2: 期限结构 ────────────────────────────
        if has_term:
            r, c = divmod(subplot_idx, cols)
            r, c = r + 1, c + 1
            plot_colors = [COLORS["primary"], COLORS["accent"],
                          COLORS["warning"], COLORS["info"], COLORS["danger"]]

            for i, (variety, months) in enumerate(term_structure.items()):
                if isinstance(months, dict):
                    month_labels = list(months.keys())
                    prices = list(months.values())
                    fig.add_trace(
                        go.Scatter(
                            x=month_labels,
                            y=prices,
                            mode="lines+markers",
                            name=variety,
                            line=dict(color=plot_colors[i % len(plot_colors)], width=2.5),
                            marker=dict(size=8),
                            hovertemplate=f"<b>{variety}</b><br>%{{x}}: %{{y:.2f}}<extra></extra>",
                        ),
                        row=r, col=c,
                    )

            fig.update_yaxes(title_text="价格", row=r, col=c)
            fig.update_xaxes(title_text="合约月份", row=r, col=c)
            subplot_idx += 1

        # ─── 子图3: 商品信号散点图 ─────────────────────
        if has_commodity:
            r, c = divmod(subplot_idx, cols)
            r, c = r + 1, c + 1
            varieties = list(commodity_signals.keys())
            signals = []
            momentums = []
            names = []
            for v in varieties:
                data = commodity_signals[v]
                if hasattr(data, "to_dict"):
                    data = data.to_dict()
                if isinstance(data, dict):
                    signals.append(data.get("signal", 0))
                    momentums.append(data.get("momentum_20d", 0))
                    names.append(data.get("name", v))
                else:
                    signals.append(0)
                    momentums.append(0)
                    names.append(v)

            scatter_colors = [
                COLORS["primary"] if s > 0 else COLORS["danger"] for s in signals
            ]

            fig.add_trace(
                go.Bar(
                    x=varieties,
                    y=signals,
                    marker=dict(color=scatter_colors, opacity=0.85),
                    name="商品信号",
                    hovertemplate="<b>%{x}</b><br>信号: %{y:.1f}<extra></extra>",
                ),
                row=r, col=c,
            )

            fig.add_hline(y=0, line_dash="dash", line_color=COLORS["neutral"],
                         line_width=1, row=r, col=c)
            fig.update_yaxes(title_text="信号强度 (-100~+100)", row=r, col=c)
            subplot_idx += 1

        # ─── 子图4: 股指期货基差 ───────────────────────
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

            fig.add_trace(
                go.Bar(
                    x=if_names,
                    y=basis_pcts,
                    marker=dict(
                        color=[COLORS["primary"] if b > 0 else COLORS["danger"] for b in basis_pcts],
                        opacity=0.85,
                    ),
                    name="股指基差率",
                    hovertemplate="<b>%{x}</b><br>基差率: %{y:.4f}%<extra></extra>",
                ),
                row=r, col=c,
            )

            fig.add_hline(y=0, line_dash="dash", line_color=COLORS["text"],
                         line_width=1, row=r, col=c)
            fig.update_yaxes(title_text="基差率 (%)", row=r, col=c)
            subplot_idx += 1

        # ─── 全局布局 ──────────────────────────────────────
        overseas_note = ""
        if overseas_adj:
            overseas_note = " | 海外: 已整合"

        _color_text_sec = COLORS["text_secondary"]
        title_text = (
            f"AiStock V8 衍生品信号仪表板<br>"
            f"<span style='font-size:13px;color:{_color_text_sec}'>"
            f"综合信号: <b>{composite_signal:.1f}</b> | 级别: {signal_level}{overseas_note}</span>"
        )
        _apply_layout(fig, title_text,
            height=max(500, rows * 380),
            barmode="relative",
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.05,
                xanchor="center",
                x=0.5,
                font=dict(size=11),
            ),
        )

        # 全局轴样式
        _apply_axes(fig)

        return fig

    @staticmethod
    def _derivatives_subplot_titles(has_basis, has_term, has_commodity,
                                     has_basis_index, count):
        titles = []
        if has_basis:
            titles.append("期货基差信号")
        if has_term:
            titles.append("期限结构")
        if has_commodity:
            titles.append("商品品种信号")
        if has_basis_index:
            titles.append("股指期货基差")
        # 补齐
        while len(titles) < count:
            titles.append("")
        return titles

    # ═══════════════════════════════════════════════════════════════════════
    # 4. 风险评估仪表板
    # ═══════════════════════════════════════════════════════════════════════

    def plot_risk_dashboard(
        self,
        risk_result: Dict[str, Any],
    ) -> go.Figure:
        """绘制风险评估交互仪表板

        Args:
            risk_result: 风险评估结果, 含:
                - risk_factors: {factor_name: score / dict}
                - overall_risk_score: 综合风险评分
                - risk_level: 风险级别
                - risk_metrics: {metric: value}
                - warnings: [warning_messages]

        Returns:
            Plotly Figure
        """
        risk_factors = _safe_get(risk_result, "risk_factors", {})
        overall_score = _safe_get(risk_result, "overall_risk_score", 50)
        risk_level = _safe_get(risk_result, "risk_level", "moderate")
        risk_metrics = _safe_get(risk_result, "risk_metrics", {})
        warnings = _safe_get(risk_result, "warnings", [])

        # 解析风险因子
        factor_names = []
        factor_scores = []
        factor_levels = []
        for k, v in risk_factors.items():
            factor_names.append(k)
            if isinstance(v, dict):
                factor_scores.append(v.get("score", v.get("value", 0)))
                factor_levels.append(v.get("level", ""))
            elif hasattr(v, "score"):
                factor_scores.append(v.score)
                factor_levels.append(getattr(v, "level", ""))
            else:
                factor_scores.append(float(v) if v is not None else 0)
                factor_levels.append("")

        # ─── 创建布局 ──────────────────────────────────────
        fig = make_subplots(
            rows=1, cols=2,
            column_widths=[0.5, 0.5],
            specs=[[dict(type="scatterpolar"), dict(type="table")]],
            subplot_titles=["风险因子雷达", "风险指标详情"],
            horizontal_spacing=0.15,
        )

        # ─── 左: 风险因子雷达 ──────────────────────────
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

        _apply_polar(
            fig,
            radial_range=(0, max(factor_scores) * 1.2 if factor_scores else 100),
            radial_tickfont_size=10,
            angular_tickfont_size=11,
        )

        # ─── 右: 指标表 ──────────────────────────────────
        # 表头
        header_vals = ["<b>指标</b>", "<b>数值</b>"]
        cell_vals = [[], []]

        # 综合风险评分 (高亮)
        risk_color = COLORS["primary"] if overall_score >= 60 else (
            COLORS["warning"] if overall_score >= 40 else COLORS["danger"]
        )
        cell_vals[0].append(f"综合风险评分")
        cell_vals[1].append(f"{overall_score:.1f}")

        cell_vals[0].append(f"风险级别")
        cell_vals[1].append(risk_level)

        # 风险因子
        for name, score in zip(factor_names, factor_scores):
            cell_vals[0].append(f"▸ {name}")
            cell_vals[1].append(f"{score:.1f}")

        # 风险指标
        if risk_metrics:
            for k, v in risk_metrics.items():
                cell_vals[0].append(f"◆ {k}")
                if isinstance(v, float):
                    cell_vals[1].append(f"{v:.4f}")
                else:
                    cell_vals[1].append(str(v))

        # 警告
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
                        [COLORS["background"] if i % 2 == 0 else "white"
                         for i in range(len(cell_vals[0]))],
                        [COLORS["background"] if i % 2 == 0 else "white"
                         for i in range(len(cell_vals[0]))],
                    ],
                    font=dict(size=12, color=COLORS["text"]),
                    align="left",
                    height=30,
                ),
                columnwidth=[180, 120],
            ),
            row=1, col=2,
        )

        # ─── 布局 ──────────────────────────────────────────
        warn_text = ""
        if warnings:
            warn_text = f" | ⚠ {len(warnings)}条警告"

        title_text = (
            f"AiStock V8 风险评估仪表板<br>"
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
        """绘制PCR多标的交互对比仪表板

        Args:
            pcr_result: PCR计算结果, 含:
                - etf_pcr: {underlying: PCRResult}
                - cffex_pcr: {variety: PCRResult}
                - commodity_pcr: {variety: PCRResult}
                - composite_pcr: CompositePCRResult
                - divergence_signal: PCRDivergenceSignal

        Returns:
            Plotly Figure
        """
        etf_pcr = _safe_get(pcr_result, "etf_pcr", {})
        cffex_pcr = _safe_get(pcr_result, "cffex_pcr", {})
        commodity_pcr = _safe_get(pcr_result, "commodity_pcr", {})
        composite = _safe_get(pcr_result, "composite_pcr", {})
        divergence = _safe_get(pcr_result, "divergence_signal", {})

        # 解析数据
        etf_underlyings, etf_oi, etf_vol = self._parse_pcr_data(etf_pcr)
        cffex_vars, cffex_oi = self._parse_simple_pcr(cffex_pcr)
        comp_data = _to_dict_safe(composite)
        div_data = _to_dict_safe(divergence)

        # ─── 子图网格 ──────────────────────────────────────
        has_commodity = bool(commodity_pcr)
        n_rows = 3 if has_commodity else 2
        row_heights = [0.35, 0.35, 0.30] if has_commodity else [0.5, 0.5]

        fig = make_subplots(
            rows=n_rows, cols=2,
            row_heights=row_heights,
            vertical_spacing=0.10,
            horizontal_spacing=0.18,
            subplot_titles=self._pcr_subplot_titles(has_commodity),
        )

        # ─── 子图1: ETF PCR对比 ────────────────────────
        if etf_underlyings:
            fig.add_trace(
                go.Bar(
                    x=etf_underlyings,
                    y=etf_oi,
                    name="PCR(OI)",
                    marker=dict(color=COLORS["primary"], opacity=0.85),
                    hovertemplate="<b>%{x}</b><br>PCR(OI): %{y:.4f}<extra></extra>",
                ),
                row=1, col=1,
            )
            fig.add_trace(
                go.Bar(
                    x=etf_underlyings,
                    y=etf_vol,
                    name="PCR(Vol)",
                    marker=dict(color=COLORS["accent"], opacity=0.85),
                    hovertemplate="<b>%{x}</b><br>PCR(Vol): %{y:.4f}<extra></extra>",
                ),
                row=1, col=1,
            )

            # 中性线
            fig.add_hline(y=1.0, line_dash="dash", line_color=COLORS["text"],
                         line_width=1, row=1, col=1,
                         annotation_text="中性", annotation_font_size=10)
            fig.add_hline(y=1.3, line_dash="dot", line_color=COLORS["warning"],
                         line_width=1, row=1, col=1)
            fig.add_hline(y=0.7, line_dash="dot", line_color=COLORS["warning"],
                         line_width=1, row=1, col=1)

        # ─── 子图2: CFFEX PCR ─────────────────────────
        if cffex_vars:
            cffex_colors = [
                COLORS["primary"] if 0.8 <= v <= 1.2 else COLORS["danger"]
                for v in cffex_oi
            ]
            fig.add_trace(
                go.Bar(
                    x=cffex_vars,
                    y=cffex_oi,
                    name="CFFEX PCR(OI)",
                    marker=dict(color=cffex_colors, opacity=0.85),
                    hovertemplate="<b>%{x}</b><br>PCR(OI): %{y:.4f}<extra></extra>",
                ),
                row=1, col=2,
            )
            fig.add_hline(y=1.0, line_dash="dash", line_color=COLORS["text"],
                         line_width=1, row=1, col=2)

        # ─── 子图3: 综合PCR ──────────────────────────
        if isinstance(comp_data, dict):
            labels = ["ETF PCR", "CFFEX PCR", "商品PCR", "综合PCR"]
            values = [
                comp_data.get("etf_pcr", 0),
                comp_data.get("cffex_pcr", 0),
                comp_data.get("commodity_pcr", 0),
                comp_data.get("composite_pcr", 0),
            ]
            comp_colors = [COLORS["primary"], COLORS["accent"],
                          COLORS["warning"], COLORS["info"]]

            fig.add_trace(
                go.Bar(
                    y=labels,
                    x=values,
                    orientation="h",
                    name="综合PCR",
                    marker=dict(color=comp_colors, opacity=0.85),
                    hovertemplate="<b>%{y}</b><br>PCR: %{x:.4f}<extra></extra>",
                ),
                row=2, col=1,
            )
            fig.add_vline(x=1.0, line_dash="dash", line_color=COLORS["text"],
                         line_width=1, row=2, col=1)

            # 信号级别
            signal_level = comp_data.get("signal_level", "normal")
            sig_color = {
                "normal": COLORS["primary"],
                "warning": COLORS["warning"],
                "extreme": COLORS["danger"],
            }.get(signal_level, COLORS["neutral"])

            fig.add_annotation(
                xref="x2", yref="y2",
                x=max(values) * 0.9 if values else 1.5,
                y=labels[-1] if labels else "",
                text=f"信号: {signal_level}",
                showarrow=False,
                font=dict(size=11, color=sig_color),
            )

        # ─── 子图4: 背离信号 ──────────────────────────
        if isinstance(div_data, dict) and div_data.get("divergence_type", "no_divergence") != "no_divergence":
            div_type = div_data.get("divergence_type", "N/A")
            div_risk = div_data.get("risk_level", "low")
            div_mag = div_data.get("divergence_magnitude", 0)
            comm_pcr = div_data.get("commodity_pcr_value", 0)
            idx_pcr = div_data.get("index_pcr_value", 0)

            fig.add_trace(
                go.Bar(
                    x=["商品PCR", "指数PCR"],
                    y=[comm_pcr, idx_pcr],
                    marker=dict(
                        color=[COLORS["warning"], COLORS["primary"]],
                        opacity=0.85,
                    ),
                    name="PCR背离",
                    hovertemplate="<b>%{x}</b><br>PCR: %{y:.4f}<extra></extra>",
                ),
                row=2, col=2,
            )
            fig.add_hline(y=1.0, line_dash="dash", line_color=COLORS["text"],
                         line_width=1, row=2, col=2)

            # 背离信息
            fig.add_annotation(
                xref="x4", yref="paper",
                x=0.5, y=0.95,
                text=f"背离: {div_type}<br>风险: {div_risk} | 幅度: {div_mag:.2f}",
                showarrow=False,
                font=dict(size=11, color=COLORS["danger"]),
                bordercolor=COLORS["grid"],
                borderwidth=1,
                borderpad=6,
                bgcolor="rgba(255,255,255,0.9)",
            )
        else:
            fig.add_annotation(
                xref="x4", yref="y4",
                x=1, y=1,
                text="无显著背离信号",
                showarrow=False,
                font=dict(size=13, color=COLORS["text_secondary"]),
            )

        # ─── 子图5: 商品PCR (如有) ─────────────────────
        if has_commodity:
            comm_vars, comm_oi = self._parse_simple_pcr(commodity_pcr, top_n=15)
            if comm_vars:
                comm_colors = [
                    COLORS["primary"] if 0.8 <= v <= 1.2 else COLORS["danger"]
                    for v in comm_oi
                ]
                fig.add_trace(
                    go.Bar(
                        y=comm_vars,
                        x=comm_oi,
                        orientation="h",
                        name="商品PCR(OI)",
                        marker=dict(color=comm_colors, opacity=0.8),
                        hovertemplate="<b>%{y}</b><br>PCR(OI): %{x:.4f}<extra></extra>",
                    ),
                    row=3, col=1,
                )
                fig.add_vline(x=1.0, line_dash="dash", line_color=COLORS["text"],
                             line_width=1, row=3, col=1)

        # ─── 布局 ──────────────────────────────────────────
        _apply_layout(fig, "AiStock V8 期权PCR仪表板",
            barmode="group",
            height=max(700, n_rows * 280),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.03,
                xanchor="center",
                x=0.5,
                font=dict(size=11),
            ),
        )
        _apply_axes(fig)

        return fig

    @staticmethod
    def _parse_pcr_data(data: Dict) -> Tuple[List, List, List]:
        """解析 PCR 数据 → (underlyings, pcr_oi, pcr_vol)"""
        underlyings = list(data.keys()) if data else []
        pcr_oi, pcr_vol = [], []
        for u in underlyings:
            d = data[u]
            if hasattr(d, "pcr_oi"):
                pcr_oi.append(d.pcr_oi)
                pcr_vol.append(d.pcr_volume)
            elif isinstance(d, dict):
                pcr_oi.append(d.get("pcr_oi", 0))
                pcr_vol.append(d.get("pcr_volume", 0))
            else:
                pcr_oi.append(0)
                pcr_vol.append(0)
        return underlyings, pcr_oi, pcr_vol

    @staticmethod
    def _parse_simple_pcr(data: Dict, top_n: int = 20) -> Tuple[List, List]:
        """解析简单 PCR 数据 → (varieties, pcr_oi)"""
        varieties = list(data.keys())[:top_n] if data else []
        pcr_oi = []
        for v in varieties:
            d = data[v]
            if hasattr(d, "pcr_oi"):
                pcr_oi.append(d.pcr_oi)
            elif isinstance(d, dict):
                pcr_oi.append(d.get("pcr_oi", 0))
            else:
                pcr_oi.append(0)
        return varieties, pcr_oi

    @staticmethod
    def _pcr_subplot_titles(has_commodity: bool) -> List[str]:
        titles = [
            "ETF期权PCR", "中金所期权PCR",
            "综合PCR", "PCR背离信号",
        ]
        if has_commodity:
            titles.extend(["商品期权PCR", ""])
        return titles

    # ═══════════════════════════════════════════════════════════════════════
    # 6. 外盘期货四维信号面板
    # ═══════════════════════════════════════════════════════════════════════

    def plot_overseas_signal_dashboard(
        self,
        overseas_signal: Dict[str, Any],
    ) -> go.Figure:
        """绘制外盘期货四维信号交互面板

        Args:
            overseas_signal: 外盘信号结果, 含:
                - price_score / position_score / macro_score / sentiment_score
                - composite_score, direction, confidence
                - overnight_returns: {symbol: return}
                - sector_impacts: {sector: SectorImpact}
                - price_signals / position_signals (详细)
                - cross_market_spreads (跨市场价差)

        Returns:
            Plotly Figure
        """
        price_score = _safe_get(overseas_signal, "price_score", 50)
        position_score = _safe_get(overseas_signal, "position_score", 50)
        macro_score = _safe_get(overseas_signal, "macro_score", 50)
        sentiment_score = _safe_get(overseas_signal, "sentiment_score", 50)
        composite = _safe_get(overseas_signal, "composite_score", 50)
        direction = _safe_get(overseas_signal, "direction", "neutral")
        confidence = _safe_get(overseas_signal, "confidence", 0)
        overnight = _safe_get(overseas_signal, "overnight_returns", {})
        sectors = _safe_get(overseas_signal, "sector_impacts", {})
        price_signals = _safe_get(overseas_signal, "price_signals", {})
        spreads = _safe_get(overseas_signal, "cross_market_spreads", {})

        # ─── 子图网格 ──────────────────────────────────────
        has_overnight = bool(overnight)
        has_sectors = bool(sectors)
        has_price = bool(price_signals)
        has_spreads = bool(spreads)

        n_cols = 3
        n_rows = 2

        fig = make_subplots(
            rows=n_rows, cols=n_cols,
            vertical_spacing=0.14,
            horizontal_spacing=0.12,
            specs=[
                [dict(type="xy"), dict(type="xy"), dict(type="xy")],
                [dict(type="xy"), dict(type="xy"), dict(type="indicator")],
            ],
            subplot_titles=[
                "四维评分", "外盘隔夜收益", "A股行业传导",
                "品种价格信号", "跨市场价差", "综合评分",
            ],
        )

        # ─── 子图1: 四维评分 ──────────────────────────
        dims = ["价格", "持仓", "宏观", "情绪"]
        dim_scores = [price_score, position_score, macro_score, sentiment_score]
        dim_colors = [COLORS["primary"], COLORS["accent"],
                     COLORS["warning"], COLORS["info"]]

        fig.add_trace(
            go.Bar(
                x=dims,
                y=dim_scores,
                marker=dict(color=dim_colors, opacity=0.85),
                name="四维评分",
                hovertemplate="<b>%{x}</b><br>评分: %{y:.1f}<extra></extra>",
            ),
            row=1, col=1,
        )
        fig.add_hline(y=50, line_dash="dash", line_color=COLORS["neutral"],
                     line_width=1, row=1, col=1)

        # ─── 子图2: 隔夜收益 ──────────────────────────
        if has_overnight:
            symbols = list(overnight.keys())
            returns = list(overnight.values())
            ovn_colors = [COLORS["primary"] if r >= 0 else COLORS["danger"] for r in returns]

            fig.add_trace(
                go.Bar(
                    x=symbols,
                    y=returns,
                    marker=dict(color=ovn_colors, opacity=0.85),
                    name="隔夜收益",
                    hovertemplate="<b>%{x}</b><br>收益率: %{y:.2f}%<extra></extra>",
                ),
                row=1, col=2,
            )
            fig.add_hline(y=0, line_color=COLORS["text"], line_width=1,
                         row=1, col=2)
        else:
            fig.add_annotation(
                text="隔夜收益数据不可用",
                xref="x2", yref="y2", x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=13, color=COLORS["text_secondary"]),
            )

        # ─── 子图3: 行业传导 ──────────────────────────
        if has_sectors:
            sector_names = list(sectors.keys())
            sector_scores = []
            sector_dirs = []
            for s in sector_names:
                sdata = sectors[s]
                if hasattr(sdata, "impact_score"):
                    sector_scores.append(sdata.impact_score)
                    sector_dirs.append(getattr(sdata, "impact_direction", "neutral"))
                elif isinstance(sdata, dict):
                    sector_scores.append(sdata.get("impact_score", 0))
                    sector_dirs.append(sdata.get("impact_direction", "neutral"))
                else:
                    sector_scores.append(0)
                    sector_dirs.append("neutral")

            sec_colors = [
                COLORS["primary"] if s >= 0 else COLORS["danger"]
                for s in sector_scores
            ]

            fig.add_trace(
                go.Bar(
                    y=sector_names,
                    x=sector_scores,
                    orientation="h",
                    marker=dict(color=sec_colors, opacity=0.8),
                    name="行业影响",
                    hovertemplate="<b>%{y}</b><br>影响: %{x:.1f}<extra></extra>",
                ),
                row=1, col=3,
            )
            fig.add_vline(x=0, line_color=COLORS["text"], line_width=1,
                         row=1, col=3)

        # ─── 子图4: 品种价格信号 ──────────────────────
        if has_price:
            ps_names = list(price_signals.keys())
            ps_scores = []
            ps_directions = []
            for p in ps_names:
                pdata = price_signals[p]
                if hasattr(pdata, "composite_score"):
                    ps_scores.append(pdata.composite_score)
                    ps_directions.append(getattr(pdata, "direction", "neutral"))
                elif isinstance(pdata, dict):
                    ps_scores.append(pdata.get("composite_score", 50))
                    ps_directions.append(pdata.get("direction", "neutral"))
                else:
                    ps_scores.append(50)
                    ps_directions.append("neutral")

            ps_colors = [_direction_color(d) for d in ps_directions]

            fig.add_trace(
                go.Bar(
                    x=ps_names,
                    y=ps_scores,
                    marker=dict(color=ps_colors, opacity=0.85),
                    name="品种信号",
                    hovertemplate="<b>%{x}</b><br>评分: %{y:.1f}<extra></extra>",
                ),
                row=2, col=1,
            )
            fig.add_hline(y=50, line_dash="dash", line_color=COLORS["neutral"],
                         line_width=1, row=2, col=1)

        # ─── 子图5: 跨市场价差 ──────────────────────────
        if has_spreads:
            sp_names = list(spreads.keys())
            sp_zscores = []
            for sp in sp_names:
                sdata = spreads[sp]
                if hasattr(sdata, "spread_zscore"):
                    sp_zscores.append(sdata.spread_zscore)
                elif isinstance(sdata, dict):
                    sp_zscores.append(sdata.get("spread_zscore", 0))
                else:
                    sp_zscores.append(0)

            sp_colors = [
                COLORS["primary"] if abs(z) < 1.5 else COLORS["danger"]
                for z in sp_zscores
            ]

            fig.add_trace(
                go.Bar(
                    x=sp_names,
                    y=sp_zscores,
                    marker=dict(color=sp_colors, opacity=0.85),
                    name="价差Z-Score",
                    hovertemplate="<b>%{x}</b><br>Z-Score: %{y:.2f}<extra></extra>",
                ),
                row=2, col=2,
            )
            fig.add_hline(y=0, line_color=COLORS["text"], line_width=1,
                         row=2, col=2)
            fig.add_hline(y=1.5, line_dash="dot", line_color=COLORS["warning"],
                         line_width=1, row=2, col=2)
            fig.add_hline(y=-1.5, line_dash="dot", line_color=COLORS["warning"],
                         line_width=1, row=2, col=2)

        # ─── 子图6: 综合评分仪表盘 ──────────────────────
        gauge_color = _score_to_color(composite)

        fig.add_trace(
            go.Indicator(
                mode="gauge+number",
                value=composite,
                number=dict(
                    font=dict(size=32, color=gauge_color),
                ),
                title=dict(
                    text=f"<b>{direction}</b><br>"
                         f"<span style='font-size:11px'>置信度: {confidence:.0%}</span>",
                    font=dict(size=13),
                ),
                gauge=dict(
                    axis=dict(range=[0, 100], tickwidth=1, tickfont=dict(size=9)),
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
            row=2, col=3,
        )

        # ─── 布局 ──────────────────────────────────────────
        _dir_color = _direction_color(direction)
        title_text = (
            f"AiStock V8 外盘期货四维信号面板<br>"
            f"<span style='font-size:13px;color:{_dir_color}'>"
            f"综合: <b>{composite:.1f}</b> | 方向: {direction} | 置信度: {confidence:.0%}</span>"
        )
        _apply_layout(fig, title_text,
            height=800,
            barmode="relative",
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.04,
                xanchor="center",
                x=0.5,
                font=dict(size=10),
            ),
        )
        _apply_axes(fig)

        return fig

    # ═══════════════════════════════════════════════════════════════════════
    # 7. 宏观信号五维度面板
    # ═══════════════════════════════════════════════════════════════════════

    def plot_macro_dashboard(
        self,
        macro_result: Dict[str, Any],
    ) -> go.Figure:
        """绘制宏观信号五维度交互面板

        Args:
            macro_result: 宏观信号结果, 含:
                - groups: {group_name: GroupResult}
                - composite_macro_score: 综合评分
                - trend_direction: 趋势方向
                - warnings: [warnings]
                - data_quality: {available: N, missing: M}

        Returns:
            Plotly Figure
        """
        groups = _safe_get(macro_result, "groups", {})
        composite_score = _safe_get(macro_result, "composite_macro_score", 50)
        trend = _safe_get(macro_result, "trend_direction", "stable")
        warnings = _safe_get(macro_result, "warnings", [])
        data_quality = _safe_get(macro_result, "data_quality", {})

        # 解析组数据
        group_names_cn = {
            "inflation": "通胀",
            "growth": "增长",
            "liquidity": "流动性",
            "external_risk": "外部风险",
            "market_sentiment": "市场情绪",
        }
        group_colors = {
            "inflation": COLORS["danger"],
            "growth": COLORS["primary"],
            "liquidity": COLORS["accent"],
            "external_risk": COLORS["warning"],
            "market_sentiment": COLORS["info"],
        }

        g_names = []
        g_scores = []
        g_colors = []
        g_directions = []

        for gk, gv in groups.items():
            g_names.append(group_names_cn.get(gk, gk))
            if hasattr(gv, "score"):
                g_scores.append(gv.score)
                g_directions.append(getattr(gv, "direction", "neutral"))
            elif isinstance(gv, dict):
                g_scores.append(gv.get("score", 50))
                g_directions.append(gv.get("direction", "neutral"))
            else:
                g_scores.append(50)
                g_directions.append("neutral")
            g_colors.append(group_colors.get(gk, COLORS["neutral"]))

        # ─── 创建双子图 ────────────────────────────────────
        fig = make_subplots(
            rows=1, cols=2,
            column_widths=[0.45, 0.55],
            specs=[[dict(type="xy"), dict(type="scatterpolar")]],
            subplot_titles=["五维度评分", "宏观雷达图"],
            horizontal_spacing=0.15,
        )

        # ─── 左: 柱状图 ──────────────────────────────────
        fig.add_trace(
            go.Bar(
                x=g_names,
                y=g_scores,
                marker=dict(
                    color=g_colors,
                    opacity=0.85,
                    line=dict(width=2, color=[_direction_color(d) for d in g_directions]),
                ),
                name="组评分",
                hovertemplate="<b>%{x}</b><br>评分: %{y:.1f}<extra></extra>",
            ),
            row=1, col=1,
        )
        fig.add_hline(y=50, line_dash="dash", line_color=COLORS["neutral"],
                     line_width=1, row=1, col=1)

        # ─── 右: 雷达图 ──────────────────────────────────
        if g_names:
            radar_names = g_names + [g_names[0]]
            radar_scores = g_scores + [g_scores[0]]

            fig.add_trace(
                go.Scatterpolar(
                    r=radar_scores,
                    theta=radar_names,
                    fill="toself",
                    fillcolor=COLORS["accent"],
                    opacity=0.2,
                    line=dict(color=COLORS["primary"], width=2.5),
                    marker=dict(size=8, color=g_colors),
                    name="宏观雷达",
                    hovertemplate="<b>%{theta}</b><br>评分: %{r:.1f}<extra></extra>",
                ),
                row=1, col=2,
            )

            _apply_polar(
                fig,
                radial_range=(0, 100),
                radial_tickfont_size=9,
                angular_tickfont_size=12,
            )

        # ─── 布局 ──────────────────────────────────────────
        trend_cn = {"improving": "改善", "deteriorating": "恶化", "stable": "稳定"}
        available = data_quality.get("available", "?") if isinstance(data_quality, dict) else "?"

        _color_text_sec = COLORS["text_secondary"]
        title_text = (
            f"AiStock V8 宏观信号五维度面板<br>"
            f"<span style='font-size:13px;color:{_color_text_sec}'>"
            f"综合: <b>{composite_score:.1f}</b> | "
            f"趋势: {trend_cn.get(trend, trend)} | "
            f"可用指标: {available}</span>"
        )
        _apply_layout(fig, title_text,
            height=550,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.06,
                xanchor="center",
                x=0.5,
                font=dict(size=11),
            ),
        )
        _apply_axes(fig)
        fig.update_yaxes(range=[0, 100], row=1, col=1)

        return fig

    # ═══════════════════════════════════════════════════════════════════════
    # 8. 综合仪表板 (Tab切换)
    # ═══════════════════════════════════════════════════════════════════════

    def plot_composite_dashboard(
        self,
        all_results: Dict[str, Any],
    ) -> go.Figure:
        """绘制综合交互仪表板 (所有模块, 可见性切换)

        Args:
            all_results: 全部管线结果, 含:
                - classification: 分类结果
                - regime: Regime结果
                - pcr: PCR结果
                - derivatives: 衍生品结果
                - overseas: 外盘信号结果
                - risk: 风险评估结果
                - macro: 宏观信号结果

        Returns:
            Plotly Figure (含多个 Trace, 可通过图例切换)
        """
        classification = all_results.get("classification", {})
        regime = all_results.get("regime", {})
        risk = all_results.get("risk", {})

        # ─── 综合概览仪表板 ───────────────────────────────
        fig = make_subplots(
            rows=3, cols=3,
            row_heights=[0.30, 0.40, 0.30],
            vertical_spacing=0.10,
            horizontal_spacing=0.10,
            specs=[
                [
                    dict(type="indicator"),
                    dict(type="indicator"),
                    dict(type="indicator"),
                ],
                [
                    dict(type="scatterpolar"),
                    dict(type="xy"),
                    dict(type="xy"),
                ],
                [
                    dict(type="xy"),
                    dict(type="xy"),
                    dict(type="xy"),
                ],
            ],
            subplot_titles=[
                "市场状态", "综合风险", "Regime",
                "4D雷达", "风险因子", "PCR概览",
                "外盘信号", "衍生品信号", "宏观信号",
            ],
        )

        # ─── Row 1: 三个指标仪表 ──────────────────────

        # 1-1: 市场状态
        comp_score = _safe_get(classification, "composite_score", 50)
        state_label = _safe_get(classification, "state_label", "均衡持有")
        fig.add_trace(
            go.Indicator(
                mode="gauge+number",
                value=comp_score,
                number=dict(font=dict(size=28, color=_score_to_color(comp_score))),
                title=dict(text=f"<b>{state_label}</b>", font=dict(size=14)),
                gauge=dict(
                    axis=dict(range=[0, 100], tickfont=dict(size=9)),
                    bar=dict(color=_score_to_color(comp_score), thickness=0.3),
                    steps=[
                        dict(range=[0, 35], color="#FECACA"),
                        dict(range=[35, 50], color="#FEF08A"),
                        dict(range=[50, 65], color="#D9F99D"),
                        dict(range=[65, 80], color="#86EFAC"),
                        dict(range=[80, 100], color="#2D6A4F"),
                    ],
                ),
                domain=dict(row=0, column=0),
            ),
            row=1, col=1,
        )

        # 1-2: 风险
        risk_score = _safe_get(risk, "overall_risk_score", 50)
        risk_level = _safe_get(risk, "risk_level", "moderate")
        fig.add_trace(
            go.Indicator(
                mode="gauge+number",
                value=risk_score,
                number=dict(font=dict(size=28, color=_score_to_color(risk_score))),
                title=dict(text=f"<b>{risk_level}</b>", font=dict(size=14)),
                gauge=dict(
                    axis=dict(range=[0, 100], tickfont=dict(size=9)),
                    bar=dict(color=_score_to_color(risk_score), thickness=0.3),
                    steps=[
                        dict(range=[0, 30], color="#FECACA"),
                        dict(range=[30, 50], color="#FEF08A"),
                        dict(range=[50, 70], color="#D9F99D"),
                        dict(range=[70, 100], color="#86EFAC"),
                    ],
                ),
                domain=dict(row=0, column=1),
            ),
            row=1, col=2,
        )

        # 1-3: Regime
        regime_score = _safe_get(regime, "regime_score", 50)
        current_regime = _safe_get(regime, "current_regime", "震荡")
        fig.add_trace(
            go.Indicator(
                mode="gauge+number",
                value=regime_score,
                number=dict(font=dict(size=28, color=_score_to_color(regime_score))),
                title=dict(text=f"<b>{current_regime}</b>", font=dict(size=14)),
                gauge=dict(
                    axis=dict(range=[0, 100], tickfont=dict(size=9)),
                    bar=dict(color=_score_to_color(regime_score), thickness=0.3),
                    steps=[
                        dict(range=[0, 35], color="#FECACA"),
                        dict(range=[35, 50], color="#FEF08A"),
                        dict(range=[50, 65], color="#D9F99D"),
                        dict(range=[65, 80], color="#86EFAC"),
                        dict(range=[80, 100], color="#2D6A4F"),
                    ],
                ),
                domain=dict(row=0, column=2),
            ),
            row=1, col=3,
        )

        # ─── Row 2: 4D雷达 + 风险因子 + PCR概览 ──────

        # 2-1: 4D雷达
        dim_keys = ["valuation_score", "momentum_score", "regime_score", "overseas_score"]
        dim_cats = ["估值", "动量", "Regime", "海外"]
        dim_scores = [_safe_get(classification, k, 50) for k in dim_keys]
        dim_clrs = [DIM_COLORS[k] for k in ["valuation", "momentum", "regime", "overseas"]]

        fig.add_trace(
            go.Scatterpolar(
                r=dim_scores + [dim_scores[0]],
                theta=dim_cats + [dim_cats[0]],
                fill="toself",
                fillcolor=COLORS["accent"],
                opacity=0.2,
                line=dict(color=COLORS["primary"], width=2.5),
                marker=dict(size=8, color=dim_clrs),
                name="4D雷达",
                hovertemplate="<b>%{theta}</b>: %{r:.1f}<extra></extra>",
            ),
            row=2, col=1,
        )
        _apply_polar(
            fig,
            radial_range=(0, 100),
            radial_tickfont_size=8,
            angular_tickfont_size=10,
        )

        # 2-2: 风险因子柱状图
        risk_factors = _safe_get(risk, "risk_factors", {})
        if risk_factors:
            rf_names = list(risk_factors.keys())
            rf_scores = []
            for v in risk_factors.values():
                if isinstance(v, dict):
                    rf_scores.append(v.get("score", v.get("value", 0)))
                elif hasattr(v, "score"):
                    rf_scores.append(v.score)
                else:
                    rf_scores.append(float(v) if v is not None else 0)

            fig.add_trace(
                go.Bar(
                    x=rf_names,
                    y=rf_scores,
                    marker=dict(
                        color=[COLORS["danger"] if s > 60 else COLORS["warning"] if s > 40 else COLORS["primary"]
                               for s in rf_scores],
                        opacity=0.8,
                    ),
                    name="风险因子",
                    hovertemplate="<b>%{x}</b><br>%{y:.1f}<extra></extra>",
                ),
                row=2, col=2,
            )
        else:
            fig.add_annotation(
                text="风险因子不可用", xref="x", yref="y",
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=12, color=COLORS["text_secondary"]),
            )

        # 2-3: PCR概览
        pcr = all_results.get("pcr", {})
        composite_pcr = _to_dict_safe(_safe_get(pcr, "composite_pcr", {}))
        if isinstance(composite_pcr, dict) and composite_pcr:
            pcr_labels = ["ETF", "CFFEX", "商品", "综合"]
            pcr_keys = ["etf_pcr", "cffex_pcr", "commodity_pcr", "composite_pcr"]
            pcr_vals = [composite_pcr.get(k, 0) for k in pcr_keys]
            pcr_colors = [COLORS["primary"], COLORS["accent"], COLORS["warning"], COLORS["info"]]

            fig.add_trace(
                go.Bar(
                    x=pcr_labels,
                    y=pcr_vals,
                    marker=dict(color=pcr_colors, opacity=0.85),
                    name="PCR概览",
                    hovertemplate="<b>%{x}</b><br>PCR: %{y:.4f}<extra></extra>",
                ),
                row=2, col=3,
            )
            fig.add_shape(type="line", xref="x2 domain", yref="y2",
                            x0=0, x1=1, y0=1.0, y1=1.0,
                            line=dict(dash="dash", color=COLORS["neutral"], width=1))

        # ─── Row 3: 外盘 + 衍生品 + 宏观 ──────────────

        # 3-1: 外盘信号
        overseas = all_results.get("overseas", {})
        if overseas:
            ov_dims = ["价格", "持仓", "宏观", "情绪"]
            ov_keys = ["price_score", "position_score", "macro_score", "sentiment_score"]
            ov_scores = [_safe_get(overseas, k, 50) for k in ov_keys]
            ov_colors = [COLORS["primary"], COLORS["accent"], COLORS["warning"], COLORS["info"]]

            fig.add_trace(
                go.Bar(
                    x=ov_dims,
                    y=ov_scores,
                    marker=dict(color=ov_colors, opacity=0.85),
                    name="外盘4D",
                    hovertemplate="<b>%{x}</b><br>%{y:.1f}<extra></extra>",
                ),
                row=3, col=1,
            )
            fig.add_shape(type="line", xref="x3 domain", yref="y3",
                            x0=0, x1=1, y0=50, y1=50,
                            line=dict(dash="dash", color=COLORS["neutral"], width=1))
        else:
            fig.add_annotation(
                text="外盘数据不可用", xref="x3", yref="y3",
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=12, color=COLORS["text_secondary"]),
            )

        # 3-2: 衍生品信号
        derivatives = all_results.get("derivatives", {})
        if derivatives:
            deriv_signal = _safe_get(derivatives, "composite_signal", 50)
            deriv_level = _safe_get(derivatives, "signal_level", "normal")
            basis = _safe_get(derivatives, "basis_signals", {})
            if basis:
                b_names = list(basis.keys())[:10]
                b_vals = [basis[k] for k in b_names]
                b_colors = [COLORS["primary"] if v > 0 else COLORS["danger"] for v in b_vals]
                fig.add_trace(
                    go.Bar(
                        x=b_names,
                        y=b_vals,
                        marker=dict(color=b_colors, opacity=0.8),
                        name="基差信号",
                        hovertemplate="<b>%{x}</b><br>%{y:.4f}%<extra></extra>",
                    ),
                    row=3, col=2,
                )
                fig.add_shape(type="line", xref="x4 domain", yref="y4",
                                x0=0, x1=1, y0=0, y1=0,
                                line=dict(color=COLORS["text"], width=1))
            else:
                fig.add_annotation(
                    text=f"衍生品: {deriv_signal:.1f} [{deriv_level}]",
                    xref="x4", yref="y4",
                    x=0.5, y=0.5, showarrow=False,
                    font=dict(size=13, color=COLORS["text"]),
                )

        # 3-3: 宏观信号
        macro = all_results.get("macro", {})
        if macro:
            m_groups = _safe_get(macro, "groups", {})
            group_names_cn = {
                "inflation": "通胀", "growth": "增长",
                "liquidity": "流动性", "external_risk": "外部风险",
                "market_sentiment": "市场情绪",
            }
            group_colors_map = {
                "inflation": COLORS["danger"], "growth": COLORS["primary"],
                "liquidity": COLORS["accent"], "external_risk": COLORS["warning"],
                "market_sentiment": COLORS["info"],
            }
            m_names, m_scores, m_colors = [], [], []
            for gk, gv in m_groups.items():
                m_names.append(group_names_cn.get(gk, gk))
                if hasattr(gv, "score"):
                    m_scores.append(gv.score)
                elif isinstance(gv, dict):
                    m_scores.append(gv.get("score", 50))
                else:
                    m_scores.append(50)
                m_colors.append(group_colors_map.get(gk, COLORS["neutral"]))

            fig.add_trace(
                go.Bar(
                    x=m_names,
                    y=m_scores,
                    marker=dict(color=m_colors, opacity=0.85),
                    name="宏观5D",
                    hovertemplate="<b>%{x}</b><br>%{y:.1f}<extra></extra>",
                ),
                row=3, col=3,
            )
            fig.add_shape(type="line", xref="x5 domain", yref="y5",
                            x0=0, x1=1, y0=50, y1=50,
                            line=dict(dash="dash", color=COLORS["neutral"], width=1))

        # ─── 全局布局 ──────────────────────────────────────
        _color_text_sec = COLORS["text_secondary"]
        title_text = (
            "AiStock V8 市场状态综合仪表板<br>"
            f"<span style='font-size:12px;color:{_color_text_sec}'>"
            f"综合评分: {comp_score:.1f} | 风险: {risk_score:.1f} | "
            f"Regime: {current_regime}</span>"
        )
        _apply_layout(fig, title_text,
            height=1100,
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="center",
                x=0.5,
                font=dict(size=10),
            ),
        )
        _apply_axes(fig)

        return fig

    # ═══════════════════════════════════════════════════════════════════════
    # 一键生成全部图表
    # ═══════════════════════════════════════════════════════════════════════

    def generate_all(
        self,
        all_results: Dict[str, Any],
        save_html: bool = True,
        save_json: bool = False,
    ) -> Dict[str, go.Figure]:
        """一键生成全部交互图表

        Args:
            all_results: 全部管线结果
            save_html:   是否保存为 HTML
            save_json:   是否保存为 Plotly JSON

        Returns:
            {chart_name: Plotly Figure} 字典
        """
        figures: Dict[str, go.Figure] = {}

        # 1. 4D雷达图
        try:
            classification = all_results.get("classification", {})
            if classification:
                fig = self.plot_market_state_4d(classification)
                figures["market_state_4d"] = fig
                if save_html:
                    self.save_html(fig, "market_state_4d")
                if save_json:
                    self.save_json(fig, "market_state_4d")
        except Exception as e:
            logger.error("生成4D雷达图失败: %s", e)

        # 2. Regime概率
        try:
            regime = all_results.get("regime", {})
            if regime:
                fig = self.plot_regime_probability(regime)
                figures["regime_probability"] = fig
                if save_html:
                    self.save_html(fig, "regime_probability")
                if save_json:
                    self.save_json(fig, "regime_probability")
        except Exception as e:
            logger.error("生成Regime概率图失败: %s", e)

        # 3. 衍生品仪表板
        try:
            derivatives = all_results.get("derivatives", {})
            if derivatives:
                fig = self.plot_derivatives_dashboard(derivatives)
                figures["derivatives_dashboard"] = fig
                if save_html:
                    self.save_html(fig, "derivatives_dashboard")
                if save_json:
                    self.save_json(fig, "derivatives_dashboard")
        except Exception as e:
            logger.error("生成衍生品仪表板失败: %s", e)

        # 4. 风险仪表板
        try:
            risk = all_results.get("risk", {})
            if risk:
                fig = self.plot_risk_dashboard(risk)
                figures["risk_dashboard"] = fig
                if save_html:
                    self.save_html(fig, "risk_dashboard")
                if save_json:
                    self.save_json(fig, "risk_dashboard")
        except Exception as e:
            logger.error("生成风险仪表板失败: %s", e)

        # 5. PCR仪表板
        try:
            pcr = all_results.get("pcr", {})
            if pcr:
                fig = self.plot_pcr_dashboard(pcr)
                figures["pcr_dashboard"] = fig
                if save_html:
                    self.save_html(fig, "pcr_dashboard")
                if save_json:
                    self.save_json(fig, "pcr_dashboard")
        except Exception as e:
            logger.error("生成PCR仪表板失败: %s", e)

        # 6. 外盘信号
        try:
            overseas = all_results.get("overseas", {})
            if overseas:
                fig = self.plot_overseas_signal_dashboard(overseas)
                figures["overseas_signal_dashboard"] = fig
                if save_html:
                    self.save_html(fig, "overseas_signal_dashboard")
                if save_json:
                    self.save_json(fig, "overseas_signal_dashboard")
        except Exception as e:
            logger.error("生成外盘信号面板失败: %s", e)

        # 7. 宏观信号
        try:
            macro = all_results.get("macro", {})
            if macro:
                fig = self.plot_macro_dashboard(macro)
                figures["macro_dashboard"] = fig
                if save_html:
                    self.save_html(fig, "macro_dashboard")
                if save_json:
                    self.save_json(fig, "macro_dashboard")
        except Exception as e:
            logger.error("生成宏观信号面板失败: %s", e)

        # 8. 综合仪表板
        try:
            fig = self.plot_composite_dashboard(all_results)
            figures["composite_dashboard"] = fig
            if save_html:
                self.save_html(fig, "composite_dashboard")
            if save_json:
                self.save_json(fig, "composite_dashboard")
        except Exception as e:
            logger.error("生成综合仪表板失败: %s", e)

        logger.info("全部交互图表生成完成: %d 个", len(figures))
        return figures
