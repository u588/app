#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AiStock V8 — 市场状态可视化引擎 (StateVisualizer)

基于 matplotlib 生成专业级量化分析图表, 支持中文显示。

图表类型:
  plot_market_state_4d()          — 4D雷达图 (估值/动量/Regime/海外)
  plot_regime_probability()       — Regime概率柱状图
  plot_derivatives_dashboard()    — 期货基差+期限结构
  plot_risk_dashboard()           — 风险因子雷达+指标表
  plot_pcr_dashboard()            — PCR多标的对比
  plot_overseas_signal_dashboard()— 外盘四维信号面板
  plot_composite_dashboard()      — 综合仪表板 (所有模块)

配置来源: system_config.yaml → visualization 节
字体:     Noto Sans SC (中文字体)
输出:     output/visualization/ 目录 (PNG)
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")  # 非交互后端, 服务器环境必须

import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np
from matplotlib.patches import FancyBboxPatch

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# 默认配色方案
# ═══════════════════════════════════════════════════════════════════════════════

# 主色调 (避免蓝/靛蓝色系)
COLORS = {
    "primary": "#2D6A4F",       # 深绿
    "secondary": "#40916C",     # 中绿
    "accent": "#52B788",        # 亮绿
    "warning": "#E9C46A",       # 黄色
    "danger": "#E76F51",        # 红色
    "info": "#264653",          # 深青
    "neutral": "#6B7280",       # 灰色
    "background": "#F8F9FA",    # 浅灰背景
    "grid": "#E5E7EB",          # 网格线
    "text": "#1F2937",          # 主文字
    "text_secondary": "#6B7280",# 次文字
}

# 雷达图维度颜色
DIM_COLORS = {
    "valuation": "#2D6A4F",
    "momentum": "#40916C",
    "regime": "#52B788",
    "overseas": "#E9C46A",
}

# 信号方向颜色
SIGNAL_COLORS = {
    "bullish": "#2D6A4F",
    "neutral": "#6B7280",
    "bearish": "#E76F51",
}

# 默认图表尺寸
DEFAULT_FIGSIZE = (16, 10)
DEFAULT_DPI = 150


# ═══════════════════════════════════════════════════════════════════════════════
# 中文字体配置
# ═══════════════════════════════════════════════════════════════════════════════

def _setup_chinese_font() -> None:
    """配置中文字体 (Noto Sans SC)"""
    font_candidates = [
        "Noto Sans SC",
        "Noto Serif SC",
        "Noto Sans CJK SC",
        "LXGW WenKai",
        "Sarasa Mono SC",
        "SimHei",
        "Microsoft YaHei",
        "WenQuanYi Micro Hei",
        "Arial Unicode MS",
    ]

    from matplotlib.font_manager import fontManager

    available_fonts = {f.name for f in fontManager.ttflist}

    for font_name in font_candidates:
        if font_name in available_fonts:
            plt.rcParams["font.sans-serif"] = [font_name, "DejaVu Sans"]
            plt.rcParams["axes.unicode_minus"] = False
            logger.debug("中文字体配置: %s", font_name)
            return

    # 回退: 使用默认字体, 警告
    plt.rcParams["axes.unicode_minus"] = False
    logger.warning("未找到合适的中文字体, 中文标签可能无法正常显示")


# 初始化字体
_setup_chinese_font()


# ═══════════════════════════════════════════════════════════════════════════════
# StateVisualizer
# ═══════════════════════════════════════════════════════════════════════════════

class StateVisualizer:
    """AiStock V8 市场状态可视化引擎

    基于 matplotlib 生成专业级量化分析图表。

    Args:
        output_dir:     输出目录, 默认为项目根目录下 output/visualization/
        config:         ConfigService 实例, 读取 visualization 配置节
        figsize:        默认图表尺寸 (宽, 高)
        dpi:            默认DPI

    Example:
        >>> from base_services import ConfigService
        >>> viz = StateVisualizer(config=ConfigService())
        >>> viz.plot_market_state_4d(classification_result)
        >>> viz.plot_composite_dashboard(all_results)
    """

    def __init__(
        self,
        output_dir: Optional[str] = None,
        config: Any = None,
        figsize: Tuple[int, int] = DEFAULT_FIGSIZE,
        dpi: int = DEFAULT_DPI,
    ) -> None:
        # 确定项目根目录
        project_root = Path(__file__).resolve().parent.parent.parent

        # 输出目录
        if output_dir:
            self._output_dir = Path(output_dir)
        else:
            self._output_dir = project_root / "output" / "visualization"

        self._output_dir.mkdir(parents=True, exist_ok=True)

        self._config = config
        self._figsize = figsize
        self._dpi = dpi

        # 从配置读取覆盖参数
        self._load_config()

        logger.info(
            "StateVisualizer 初始化 | 输出目录: %s | 尺寸: %s | DPI: %d",
            self._output_dir, self._figsize, self._dpi,
        )

    # ─── 配置加载 ──────────────────────────────────────────

    def _load_config(self) -> None:
        """从 system_config.yaml 加载可视化配置"""
        if self._config is None:
            return

        try:
            viz_cfg = self._config.get_section("visualization")
            if viz_cfg:
                self._figsize = tuple(viz_cfg.get("figsize", self._figsize))
                self._dpi = viz_cfg.get("dpi", self._dpi)

                custom_colors = viz_cfg.get("colors", {})
                if custom_colors:
                    COLORS.update(custom_colors)

        except Exception as e:
            logger.warning("可视化配置加载失败, 使用默认值: %s", e)

    # ─── 工具方法 ──────────────────────────────────────────

    def _save_fig(self, fig: plt.Figure, name: str) -> str:
        """保存图表到输出目录

        Args:
            fig:  matplotlib Figure
            name: 文件名 (不含扩展名)

        Returns:
            保存路径
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{name}_{timestamp}.png"
        filepath = self._output_dir / filename

        fig.savefig(
            str(filepath),
            dpi=self._dpi,
            bbox_inches="tight",
            facecolor=fig.get_facecolor(),
            edgecolor="none",
        )
        plt.close(fig)

        logger.info("图表已保存: %s", filepath)
        return str(filepath)

    @staticmethod
    def _get_direction_color(direction: str) -> str:
        """获取方向对应的颜色"""
        d = direction.lower()
        if "bull" in d or d in ("up", "long", "positive"):
            return SIGNAL_COLORS["bullish"]
        elif "bear" in d or d in ("down", "short", "negative"):
            return SIGNAL_COLORS["bearish"]
        return SIGNAL_COLORS["neutral"]

    @staticmethod
    def _score_to_label(score: float) -> str:
        """评分转标签"""
        if score >= 80:
            return "强进攻"
        elif score >= 65:
            return "积极配置"
        elif score >= 50:
            return "均衡持有"
        elif score >= 35:
            return "防御观望"
        else:
            return "战略防御"

    @staticmethod
    def _score_to_color(score: float) -> str:
        """评分转颜色"""
        if score >= 65:
            return COLORS["primary"]
        elif score >= 50:
            return COLORS["warning"]
        else:
            return COLORS["danger"]

    # ═══════════════════════════════════════════════════════════════════════
    # 1. 市场状态4D雷达图
    # ═══════════════════════════════════════════════════════════════════════

    def plot_market_state_4d(
        self,
        classification_result: Dict[str, Any],
    ) -> str:
        """绘制4D雷达图 — 估值/动量/Regime/海外

        Args:
            classification_result: 市场状态分类结果, 含:
                - valuation_score:  估值维度评分 (0-100)
                - momentum_score:   动量维度评分 (0-100)
                - regime_score:     Regime维度评分 (0-100)
                - overseas_score:   海外维度评分 (0-100)
                - composite_score:  综合评分 (0-100)
                - state_label:      状态标签
                - direction:        方向

        Returns:
            保存的文件路径
        """
        categories = ["估值", "动量", "Regime", "海外"]
        scores = [
            classification_result.get("valuation_score", 50),
            classification_result.get("momentum_score", 50),
            classification_result.get("regime_score", 50),
            classification_result.get("overseas_score", 50),
        ]

        composite = classification_result.get("composite_score", 50)
        label = classification_result.get("state_label", "均衡持有")
        direction = classification_result.get("direction", "neutral")

        # ─── 绘图 ──────────────────────────────────────
        fig = plt.figure(figsize=(10, 10), facecolor=COLORS["background"])

        # 雷达图
        ax_radar = fig.add_subplot(111, polar=True)

        N = len(categories)
        angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
        scores_plot = scores + scores[:1]
        angles += angles[:1]

        # 背景网格
        ax_radar.set_facecolor(COLORS["background"])
        ax_radar.spines["polar"].set_color(COLORS["grid"])
        ax_radar.grid(color=COLORS["grid"], linewidth=0.5, alpha=0.7)

        # 绘制区域
        color = self._score_to_color(composite)
        ax_radar.fill(angles, scores_plot, color=color, alpha=0.15)
        ax_radar.plot(angles, scores_plot, color=color, linewidth=2.5, marker="o",
                      markersize=8, markerfacecolor="white", markeredgewidth=2,
                      markeredgecolor=color)

        # 维度标签
        ax_radar.set_xticks(angles[:-1])
        ax_radar.set_xticklabels(
            [f"{cat}\n{score:.0f}" for cat, score in zip(categories, scores)],
            fontsize=13, fontweight="bold", color=COLORS["text"],
        )

        # 径向刻度
        ax_radar.set_ylim(0, 100)
        ax_radar.set_yticks([20, 40, 60, 80, 100])
        ax_radar.set_yticklabels(["20", "40", "60", "80", "100"],
                                 fontsize=9, color=COLORS["text_secondary"])

        # 标题与状态标签
        direction_color = self._get_direction_color(direction)
        ax_radar.set_title(
            f"AiStock V8 市场状态4D雷达\n"
            f"综合评分: {composite:.1f} | 状态: {label}",
            fontsize=16, fontweight="bold", color=COLORS["text"],
            pad=30,
        )

        # 状态标签
        fig.text(
            0.5, 0.02,
            f"◆ {label} | 方向: {direction} | "
            f"估值={scores[0]:.0f} 动量={scores[1]:.0f} "
            f"Regime={scores[2]:.0f} 海外={scores[3]:.0f}",
            ha="center", fontsize=11, color=direction_color,
            fontweight="bold",
        )

        return self._save_fig(fig, "market_state_4d")

    # ═══════════════════════════════════════════════════════════════════════
    # 2. Regime概率柱状图
    # ═══════════════════════════════════════════════════════════════════════

    def plot_regime_probability(
        self,
        regime_result: Dict[str, Any],
    ) -> str:
        """绘制市场Regime概率柱状图

        Args:
            regime_result: Regime检测结果, 含:
                - probabilities: {regime_name: probability}
                - current_regime: 当前regime名称
                - confirmation_days: 确认天数

        Returns:
            保存的文件路径
        """
        probabilities = regime_result.get("probabilities", {})
        current = regime_result.get("current_regime", "unknown")
        confirmation = regime_result.get("confirmation_days", 0)

        if not probabilities:
            # 使用默认值
            probabilities = {
                "牛市": 0.25,
                "熊市": 0.15,
                "震荡": 0.40,
                "复苏": 0.20,
            }

        regimes = list(probabilities.keys())
        probs = list(probabilities.values())

        # ─── 绘图 ──────────────────────────────────────
        fig, ax = plt.subplots(figsize=(12, 7), facecolor=COLORS["background"])
        ax.set_facecolor(COLORS["background"])

        # 颜色映射
        regime_colors = {
            "牛市": COLORS["primary"],
            "熊市": COLORS["danger"],
            "震荡": COLORS["warning"],
            "复苏": COLORS["accent"],
            "bull": COLORS["primary"],
            "bear": COLORS["danger"],
            "volatile": COLORS["warning"],
            "recovery": COLORS["accent"],
        }

        bar_colors = [regime_colors.get(r, COLORS["neutral"]) for r in regimes]

        bars = ax.barh(regimes, probs, color=bar_colors, height=0.6,
                       edgecolor="white", linewidth=1.5, alpha=0.85)

        # 在条形上标注概率
        for bar, prob in zip(bars, probs):
            width = bar.get_width()
            ax.text(
                width + 0.01, bar.get_y() + bar.get_height() / 2,
                f"{prob:.1%}",
                ha="left", va="center",
                fontsize=12, fontweight="bold", color=COLORS["text"],
            )

        # 标记当前regime
        for i, r in enumerate(regimes):
            if r == current:
                ax.barh(r, probabilities[r], color=bar_colors[i],
                        height=0.6, edgecolor=COLORS["danger"],
                        linewidth=3, alpha=0.95)

        ax.set_xlim(0, max(probs) * 1.3 if probs else 1.0)
        ax.set_xlabel("概率", fontsize=12, color=COLORS["text"])
        ax.set_title(
            f"AiStock V8 市场Regime概率分布\n"
            f"当前Regime: {current} | 确认天数: {confirmation}",
            fontsize=14, fontweight="bold", color=COLORS["text"],
        )
        ax.tick_params(axis="y", labelsize=12, colors=COLORS["text"])
        ax.tick_params(axis="x", labelsize=10, colors=COLORS["text_secondary"])
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["bottom"].set_color(COLORS["grid"])
        ax.spines["left"].set_color(COLORS["grid"])

        return self._save_fig(fig, "regime_probability")

    # ═══════════════════════════════════════════════════════════════════════
    # 3. 衍生品仪表板 (基差+期限结构)
    # ═══════════════════════════════════════════════════════════════════════

    def plot_derivatives_dashboard(
        self,
        derivatives_result: Dict[str, Any],
    ) -> str:
        """绘制衍生品信号仪表板 — 期货基差+期限结构

        Args:
            derivatives_result: 衍生品信号结果, 含:
                - basis_signals: {contract: basis_pct}
                - term_structure: {variety: {month: price}}
                - composite_signal: 综合信号评分
                - signal_level: 信号级别

        Returns:
            保存的文件路径
        """
        basis_signals = derivatives_result.get("basis_signals", {})
        term_structure = derivatives_result.get("term_structure", {})
        composite_signal = derivatives_result.get("composite_signal", 50)
        signal_level = derivatives_result.get("signal_level", "normal")

        fig = plt.figure(figsize=self._figsize, facecolor=COLORS["background"])
        gs = gridspec.GridSpec(2, 2, figure=fig, hspace=0.35, wspace=0.3)

        # ─── 子图1: 基差信号柱状图 ──────────────────
        ax1 = fig.add_subplot(gs[0, :], facecolor=COLORS["background"])
        if basis_signals:
            contracts = list(basis_signals.keys())
            basis_vals = list(basis_signals.values())

            colors = [
                COLORS["primary"] if v > 0 else COLORS["danger"]
                for v in basis_vals
            ]

            ax1.bar(contracts, basis_vals, color=colors, alpha=0.8,
                    edgecolor="white", linewidth=0.8)
            ax1.axhline(y=0, color=COLORS["text"], linewidth=0.8, linestyle="--")
            ax1.axhline(y=-1.5, color=COLORS["warning"], linewidth=1,
                        linestyle="--", label="基差预警线")
            ax1.axhline(y=-2.0, color=COLORS["danger"], linewidth=1,
                        linestyle="--", label="基差极端线")

            ax1.set_ylabel("基差率 (%)", fontsize=11, color=COLORS["text"])
            ax1.set_title("期货基差信号", fontsize=13, fontweight="bold",
                          color=COLORS["text"])
            ax1.legend(fontsize=9, loc="upper right")
            ax1.tick_params(axis="x", rotation=45, labelsize=9)
        else:
            ax1.text(0.5, 0.5, "基差数据不可用", ha="center", va="center",
                     fontsize=14, color=COLORS["text_secondary"],
                     transform=ax1.transAxes)
            ax1.set_title("期货基差信号", fontsize=13, fontweight="bold",
                          color=COLORS["text"])

        # ─── 子图2: 期限结构 ────────────────────────
        ax2 = fig.add_subplot(gs[1, 0], facecolor=COLORS["background"])
        if term_structure:
            for i, (variety, months) in enumerate(term_structure.items()):
                if isinstance(months, dict):
                    month_labels = list(months.keys())
                    prices = list(months.values())
                    color_idx = i % 4
                    plot_colors = [COLORS["primary"], COLORS["accent"],
                                   COLORS["warning"], COLORS["info"]]
                    ax2.plot(month_labels, prices, marker="o", linewidth=2,
                             color=plot_colors[color_idx], label=variety)

            ax2.set_xlabel("合约月份", fontsize=10, color=COLORS["text"])
            ax2.set_ylabel("价格", fontsize=10, color=COLORS["text"])
            ax2.set_title("期限结构", fontsize=13, fontweight="bold",
                          color=COLORS["text"])
            ax2.legend(fontsize=9, loc="best")
        else:
            ax2.text(0.5, 0.5, "期限结构数据不可用", ha="center", va="center",
                     fontsize=14, color=COLORS["text_secondary"],
                     transform=ax2.transAxes)
            ax2.set_title("期限结构", fontsize=13, fontweight="bold",
                          color=COLORS["text"])

        # ─── 子图3: 综合信号 ────────────────────────
        ax3 = fig.add_subplot(gs[1, 1], facecolor=COLORS["background"])

        # 仪表盘式显示
        signal_color = self._score_to_color(composite_signal)
        ax3.barh(["衍生品信号"], [composite_signal], color=signal_color,
                 height=0.4, alpha=0.85, edgecolor="white")
        ax3.set_xlim(0, 100)

        # 分区标注
        for x, lbl in [(25, "强防御"), (37.5, "防御"), (50, "均衡"),
                        (62.5, "积极"), (75, "进攻"), (87.5, "强进攻")]:
            ax3.axvline(x=x, color=COLORS["grid"], linewidth=0.5, alpha=0.5)
            ax3.text(x, 0.3, lbl, ha="center", fontsize=7,
                     color=COLORS["text_secondary"])

        ax3.text(composite_signal + 1, 0, f"{composite_signal:.1f}",
                 va="center", fontsize=14, fontweight="bold",
                 color=signal_color)
        ax3.set_title(
            f"综合信号: {composite_signal:.1f} | 级别: {signal_level}",
            fontsize=13, fontweight="bold", color=COLORS["text"],
        )
        ax3.set_yticks([])

        fig.suptitle(
            "AiStock V8 衍生品信号仪表板",
            fontsize=16, fontweight="bold", color=COLORS["text"], y=0.98,
        )

        return self._save_fig(fig, "derivatives_dashboard")

    # ═══════════════════════════════════════════════════════════════════════
    # 4. 风险仪表板 (雷达+指标表)
    # ═══════════════════════════════════════════════════════════════════════

    def plot_risk_dashboard(
        self,
        risk_result: Dict[str, Any],
    ) -> str:
        """绘制风险评估仪表板 — 风险因子雷达+指标表

        Args:
            risk_result: 风险评估结果, 含:
                - risk_factors: {factor_name: score}
                - overall_risk_score: 综合风险评分 (0-100, 100最安全)
                - risk_level: 风险级别
                - risk_metrics: {metric_name: value}
                - warnings: [warning_messages]

        Returns:
            保存的文件路径
        """
        risk_factors = risk_result.get("risk_factors", {})
        overall_score = risk_result.get("overall_risk_score", 50)
        risk_level = risk_result.get("risk_level", "moderate")
        risk_metrics = risk_result.get("risk_metrics", {})
        warnings = risk_result.get("warnings", [])

        fig = plt.figure(figsize=self._figsize, facecolor=COLORS["background"])
        gs = gridspec.GridSpec(1, 2, figure=fig, wspace=0.4, width_ratios=[1, 1])

        # ─── 左: 风险因子雷达 ──────────────────────
        ax_radar = fig.add_subplot(gs[0, 0], polar=True)

        if risk_factors:
            factors = list(risk_factors.keys())
            scores = list(risk_factors.values())

            N = len(factors)
            angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
            scores_plot = scores + scores[:1]
            angles += angles[:1]

            ax_radar.fill(angles, scores_plot, color=COLORS["danger"], alpha=0.15)
            ax_radar.plot(angles, scores_plot, color=COLORS["danger"], linewidth=2)

            ax_radar.set_xticks(angles[:-1])
            ax_radar.set_xticklabels(factors, fontsize=9, color=COLORS["text"])
            ax_radar.set_ylim(0, 100)

        ax_radar.set_title(
            "风险因子雷达",
            fontsize=13, fontweight="bold", color=COLORS["text"], pad=20,
        )

        # ─── 右: 指标表 ────────────────────────────
        ax_table = fig.add_subplot(gs[0, 1])
        ax_table.axis("off")

        # 综合风险评分
        risk_color = COLORS["primary"] if overall_score >= 60 else (
            COLORS["warning"] if overall_score >= 40 else COLORS["danger"]
        )
        ax_table.text(
            0.5, 0.95, f"综合风险评分: {overall_score:.1f}",
            ha="center", va="top", fontsize=18, fontweight="bold",
            color=risk_color, transform=ax_table.transAxes,
        )
        ax_table.text(
            0.5, 0.88, f"风险级别: {risk_level}",
            ha="center", va="top", fontsize=13, color=COLORS["text"],
            transform=ax_table.transAxes,
        )

        # 指标表
        if risk_metrics:
            table_data = [
                [k, f"{v:.4f}" if isinstance(v, float) else str(v)]
                for k, v in risk_metrics.items()
            ]
            table = ax_table.table(
                cellText=table_data,
                colLabels=["指标", "数值"],
                cellLoc="center",
                loc="center",
                bbox=[0.1, 0.05, 0.8, 0.75],
            )
            table.auto_set_font_size(False)
            table.set_fontsize(10)
            table.auto_set_column_width([0, 1])

            # 表头样式
            for key, cell in table.get_celld().items():
                if key[0] == 0:
                    cell.set_facecolor(COLORS["primary"])
                    cell.set_text_props(color="white", fontweight="bold")
                else:
                    cell.set_facecolor(COLORS["background"]
                                       if key[0] % 2 == 0 else "white")

        # 警告信息
        if warnings:
            warn_text = "\n".join(f"⚠ {w}" for w in warnings[:5])
            ax_table.text(
                0.5, 0.0, warn_text,
                ha="center", va="bottom", fontsize=9,
                color=COLORS["danger"], transform=ax_table.transAxes,
                style="italic",
            )

        fig.suptitle(
            "AiStock V8 风险评估仪表板",
            fontsize=16, fontweight="bold", color=COLORS["text"], y=0.98,
        )

        return self._save_fig(fig, "risk_dashboard")

    # ═══════════════════════════════════════════════════════════════════════
    # 5. PCR仪表板
    # ═══════════════════════════════════════════════════════════════════════

    def plot_pcr_dashboard(
        self,
        pcr_result: Dict[str, Any],
    ) -> str:
        """绘制PCR多标的对比仪表板

        Args:
            pcr_result: PCR计算结果, 含:
                - etf_pcr: {underlying: PCRResult}
                - cffex_pcr: {variety: PCRResult}
                - commodity_pcr: {variety: PCRResult}
                - composite_pcr: CompositePCRResult
                - divergence_signal: PCRDivergenceSignal

        Returns:
            保存的文件路径
        """
        etf_pcr = pcr_result.get("etf_pcr", {})
        cffex_pcr = pcr_result.get("cffex_pcr", {})
        composite = pcr_result.get("composite_pcr", {})
        divergence = pcr_result.get("divergence_signal", {})

        fig = plt.figure(figsize=self._figsize, facecolor=COLORS["background"])
        gs = gridspec.GridSpec(2, 2, figure=fig, hspace=0.4, wspace=0.35)

        # ─── 子图1: ETF PCR对比 ─────────────────────
        ax1 = fig.add_subplot(gs[0, 0], facecolor=COLORS["background"])
        if etf_pcr:
            underlyings = list(etf_pcr.keys())
            pcr_oi_vals = []
            pcr_vol_vals = []
            for u in underlyings:
                data = etf_pcr[u]
                if hasattr(data, "pcr_oi"):
                    pcr_oi_vals.append(data.pcr_oi)
                    pcr_vol_vals.append(data.pcr_volume)
                elif isinstance(data, dict):
                    pcr_oi_vals.append(data.get("pcr_oi", 0))
                    pcr_vol_vals.append(data.get("pcr_volume", 0))
                else:
                    pcr_oi_vals.append(0)
                    pcr_vol_vals.append(0)

            x = np.arange(len(underlyings))
            width = 0.35
            ax1.bar(x - width / 2, pcr_oi_vals, width, label="PCR(OI)",
                    color=COLORS["primary"], alpha=0.85)
            ax1.bar(x + width / 2, pcr_vol_vals, width, label="PCR(Vol)",
                    color=COLORS["accent"], alpha=0.85)

            ax1.axhline(y=1.0, color=COLORS["text"], linewidth=0.8,
                        linestyle="--", label="中性线")
            ax1.axhline(y=1.3, color=COLORS["warning"], linewidth=0.8,
                        linestyle="--", alpha=0.7)
            ax1.axhline(y=0.7, color=COLORS["warning"], linewidth=0.8,
                        linestyle="--", alpha=0.7)

            ax1.set_xticks(x)
            ax1.set_xticklabels(underlyings, fontsize=9, rotation=45)
            ax1.set_ylabel("PCR", fontsize=10, color=COLORS["text"])
            ax1.set_title("ETF期权PCR", fontsize=12, fontweight="bold",
                          color=COLORS["text"])
            ax1.legend(fontsize=8)

        # ─── 子图2: CFFEX PCR对比 ───────────────────
        ax2 = fig.add_subplot(gs[0, 1], facecolor=COLORS["background"])
        if cffex_pcr:
            varieties = list(cffex_pcr.keys())
            cffex_oi = []
            for v in varieties:
                data = cffex_pcr[v]
                if hasattr(data, "pcr_oi"):
                    cffex_oi.append(data.pcr_oi)
                elif isinstance(data, dict):
                    cffex_oi.append(data.get("pcr_oi", 0))
                else:
                    cffex_oi.append(0)

            colors_cffex = [
                COLORS["primary"] if v >= 0.8 and v <= 1.2 else COLORS["danger"]
                for v in cffex_oi
            ]
            ax2.bar(varieties, cffex_oi, color=colors_cffex, alpha=0.85)
            ax2.axhline(y=1.0, color=COLORS["text"], linewidth=0.8,
                        linestyle="--")
            ax2.set_ylabel("PCR(OI)", fontsize=10, color=COLORS["text"])
            ax2.set_title("中金所期权PCR", fontsize=12, fontweight="bold",
                          color=COLORS["text"])

        # ─── 子图3: 综合PCR ─────────────────────────
        ax3 = fig.add_subplot(gs[1, 0], facecolor=COLORS["background"])
        if composite:
            comp_data = composite
            if hasattr(comp_data, "to_dict"):
                comp_data = comp_data.to_dict()
            if isinstance(comp_data, dict):
                labels = ["ETF PCR", "CFFEX PCR", "商品PCR", "综合PCR"]
                values = [
                    comp_data.get("etf_pcr", 0),
                    comp_data.get("cffex_pcr", 0),
                    comp_data.get("commodity_pcr", 0),
                    comp_data.get("composite_pcr", 0),
                ]
                colors_comp = [COLORS["primary"], COLORS["accent"],
                               COLORS["warning"], COLORS["info"]]
                ax3.barh(labels, values, color=colors_comp, height=0.5, alpha=0.85)
                ax3.axvline(x=1.0, color=COLORS["text"], linewidth=0.8,
                            linestyle="--")
                ax3.set_xlabel("PCR值", fontsize=10, color=COLORS["text"])
                ax3.set_title("综合PCR", fontsize=12, fontweight="bold",
                              color=COLORS["text"])

                # 信号级别标注
                signal_level = comp_data.get("signal_level", "normal")
                signal_color = {
                    "normal": COLORS["primary"],
                    "warning": COLORS["warning"],
                    "extreme": COLORS["danger"],
                }.get(signal_level, COLORS["neutral"])
                ax3.text(0.98, 0.02, f"信号级别: {signal_level}",
                         ha="right", va="bottom", fontsize=10,
                         fontweight="bold", color=signal_color,
                         transform=ax3.transAxes)

        # ─── 子图4: 背离信号 ────────────────────────
        ax4 = fig.add_subplot(gs[1, 1], facecolor=COLORS["background"])
        if divergence:
            div_data = divergence
            if hasattr(div_data, "to_dict"):
                div_data = div_data.to_dict()
            if isinstance(div_data, dict):
                div_type = div_data.get("divergence_type", "no_divergence")
                div_risk = div_data.get("risk_level", "low")
                div_mag = div_data.get("divergence_magnitude", 0)
                comm_pcr = div_data.get("commodity_pcr_value", 0)
                idx_pcr = div_data.get("index_pcr_value", 0)

                # 商品 vs 指数 PCR 对比
                ax4.bar(
                    ["商品PCR", "指数PCR"], [comm_pcr, idx_pcr],
                    color=[COLORS["warning"], COLORS["primary"]],
                    alpha=0.85, width=0.5,
                )
                ax4.axhline(y=1.0, color=COLORS["text"], linewidth=0.8,
                            linestyle="--")

                div_label_color = COLORS["danger"] if div_type != "no_divergence" \
                    else COLORS["primary"]
                ax4.text(
                    0.5, 0.95,
                    f"背离类型: {div_type}\n风险级别: {div_risk}\n"
                    f"幅度: {div_mag:.2f}",
                    ha="center", va="top", fontsize=10,
                    color=div_label_color, transform=ax4.transAxes,
                    bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                              edgecolor=COLORS["grid"], alpha=0.9),
                )
                ax4.set_title("PCR背离信号", fontsize=12, fontweight="bold",
                              color=COLORS["text"])
        else:
            ax4.text(0.5, 0.5, "无背离信号数据", ha="center", va="center",
                     fontsize=14, color=COLORS["text_secondary"],
                     transform=ax4.transAxes)

        fig.suptitle(
            "AiStock V8 期权PCR仪表板",
            fontsize=16, fontweight="bold", color=COLORS["text"], y=0.98,
        )

        return self._save_fig(fig, "pcr_dashboard")

    # ═══════════════════════════════════════════════════════════════════════
    # 6. 外盘信号面板
    # ═══════════════════════════════════════════════════════════════════════

    def plot_overseas_signal_dashboard(
        self,
        overseas_signal: Dict[str, Any],
    ) -> str:
        """绘制外盘期货四维信号面板

        Args:
            overseas_signal: 外盘信号结果, 含:
                - price_score: 价格维度评分
                - position_score: 持仓维度评分
                - macro_score: 宏观维度评分
                - sentiment_score: 情绪维度评分
                - composite_score: 综合评分
                - direction: 方向
                - overnight_returns: {symbol: return}
                - sector_impacts: {sector: impact}

        Returns:
            保存的文件路径
        """
        price_score = overseas_signal.get("price_score", 50)
        position_score = overseas_signal.get("position_score", 50)
        macro_score = overseas_signal.get("macro_score", 50)
        sentiment_score = overseas_signal.get("sentiment_score", 50)
        composite = overseas_signal.get("composite_score", 50)
        direction = overseas_signal.get("direction", "neutral")
        overnight = overseas_signal.get("overnight_returns", {})
        sectors = overseas_signal.get("sector_impacts", {})

        fig = plt.figure(figsize=self._figsize, facecolor=COLORS["background"])
        gs = gridspec.GridSpec(2, 3, figure=fig, hspace=0.4, wspace=0.35)

        # ─── 子图1: 四维评分柱状图 ──────────────────
        ax1 = fig.add_subplot(gs[0, 0], facecolor=COLORS["background"])
        dims = ["价格", "持仓", "宏观", "情绪"]
        dim_scores = [price_score, position_score, macro_score, sentiment_score]
        dim_colors = [COLORS["primary"], COLORS["accent"],
                      COLORS["warning"], COLORS["info"]]

        ax1.bar(dims, dim_scores, color=dim_colors, alpha=0.85, width=0.6)
        ax1.axhline(y=50, color=COLORS["text"], linewidth=0.8, linestyle="--",
                     label="中性线")
        ax1.set_ylim(0, 100)
        ax1.set_ylabel("评分", fontsize=10, color=COLORS["text"])
        ax1.set_title("四维评分", fontsize=12, fontweight="bold",
                      color=COLORS["text"])

        # 综合评分标注
        dir_color = self._get_direction_color(direction)
        ax1.text(0.98, 0.95, f"综合: {composite:.1f}\n方向: {direction}",
                 ha="right", va="top", fontsize=9, fontweight="bold",
                 color=dir_color, transform=ax1.transAxes,
                 bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                           edgecolor=COLORS["grid"]))

        # ─── 子图2: 隔夜收益 ────────────────────────
        ax2 = fig.add_subplot(gs[0, 1:], facecolor=COLORS["background"])
        if overnight:
            symbols = list(overnight.keys())
            returns = list(overnight.values())

            colors_ovn = [
                COLORS["primary"] if r >= 0 else COLORS["danger"]
                for r in returns
            ]
            ax2.bar(symbols, returns, color=colors_ovn, alpha=0.8, width=0.6)
            ax2.axhline(y=0, color=COLORS["text"], linewidth=0.8)
            ax2.set_ylabel("隔夜收益率 (%)", fontsize=10, color=COLORS["text"])
            ax2.set_title("外盘隔夜收益", fontsize=12, fontweight="bold",
                          color=COLORS["text"])
            ax2.tick_params(axis="x", rotation=45, labelsize=8)
        else:
            ax2.text(0.5, 0.5, "隔夜收益数据不可用", ha="center", va="center",
                     fontsize=14, color=COLORS["text_secondary"],
                     transform=ax2.transAxes)

        # ─── 子图3: A股行业影响 ─────────────────────
        ax3 = fig.add_subplot(gs[1, :], facecolor=COLORS["background"])
        if sectors:
            sector_names = list(sectors.keys())
            sector_scores = []
            for s in sector_names:
                sdata = sectors[s]
                if hasattr(sdata, "impact_score"):
                    sector_scores.append(sdata.impact_score)
                elif isinstance(sdata, dict):
                    sector_scores.append(sdata.get("impact_score", 0))
                else:
                    sector_scores.append(0)

            colors_sec = [
                COLORS["primary"] if s >= 0 else COLORS["danger"]
                for s in sector_scores
            ]

            ax3.barh(sector_names, sector_scores, color=colors_sec,
                     alpha=0.8, height=0.5)
            ax3.axvline(x=0, color=COLORS["text"], linewidth=0.8)
            ax3.set_xlabel("影响评分", fontsize=10, color=COLORS["text"])
            ax3.set_title("外盘→A股行业传导", fontsize=12, fontweight="bold",
                          color=COLORS["text"])
            ax3.tick_params(axis="y", labelsize=9)
        else:
            ax3.text(0.5, 0.5, "行业传导数据不可用", ha="center", va="center",
                     fontsize=14, color=COLORS["text_secondary"],
                     transform=ax3.transAxes)

        fig.suptitle(
            "AiStock V8 外盘期货四维信号面板",
            fontsize=16, fontweight="bold", color=COLORS["text"], y=0.98,
        )

        return self._save_fig(fig, "overseas_signal_dashboard")

    # ═══════════════════════════════════════════════════════════════════════
    # 7. 综合仪表板
    # ═══════════════════════════════════════════════════════════════════════

    def plot_composite_dashboard(
        self,
        all_results: Dict[str, Any],
    ) -> str:
        """绘制综合仪表板 — 整合所有模块结果

        Args:
            all_results: 全部结果字典, 含:
                - classification: 市场状态分类结果
                - regime: Regime检测结果
                - derivatives: 衍生品信号结果
                - risk: 风险评估结果
                - pcr: PCR计算结果
                - overseas: 外盘信号结果
                - macro: 宏观信号结果

        Returns:
            保存的文件路径
        """
        classification = all_results.get("classification", {})
        regime = all_results.get("regime", {})
        derivatives = all_results.get("derivatives", {})
        risk = all_results.get("risk", {})
        pcr = all_results.get("pcr", {})
        overseas = all_results.get("overseas", {})
        macro = all_results.get("macro", {})

        fig = plt.figure(figsize=(20, 14), facecolor=COLORS["background"])
        gs = gridspec.GridSpec(
            3, 4, figure=fig,
            hspace=0.45, wspace=0.35,
            height_ratios=[1.2, 1, 1],
        )

        # ─── 顶部: 市场状态概览 ────────────────────
        ax_overview = fig.add_subplot(gs[0, :2])
        ax_overview.axis("off")

        composite_score = classification.get("composite_score", 50)
        label = classification.get("state_label", "均衡持有")
        direction = classification.get("direction", "neutral")

        # 评分与状态
        score_color = self._score_to_color(composite_score)
        ax_overview.text(
            0.5, 0.75, f"{composite_score:.1f}",
            ha="center", va="center", fontsize=48, fontweight="bold",
            color=score_color, transform=ax_overview.transAxes,
        )
        ax_overview.text(
            0.5, 0.35, label,
            ha="center", va="center", fontsize=24, fontweight="bold",
            color=score_color, transform=ax_overview.transAxes,
        )
        ax_overview.text(
            0.5, 0.10, f"方向: {direction}",
            ha="center", va="center", fontsize=14,
            color=self._get_direction_color(direction),
            transform=ax_overview.transAxes,
        )
        ax_overview.set_title(
            "市场状态概览", fontsize=14, fontweight="bold",
            color=COLORS["text"],
        )

        # ─── 顶部: 4D雷达图 ────────────────────────
        ax_radar = fig.add_subplot(gs[0, 2:], polar=True)
        categories = ["估值", "动量", "Regime", "海外"]
        scores = [
            classification.get("valuation_score", 50),
            classification.get("momentum_score", 50),
            classification.get("regime_score", 50),
            classification.get("overseas_score", 50),
        ]
        N = len(categories)
        angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
        scores_plot = scores + scores[:1]
        angles += angles[:1]

        ax_radar.fill(angles, scores_plot, color=score_color, alpha=0.15)
        ax_radar.plot(angles, scores_plot, color=score_color, linewidth=2,
                      marker="o", markersize=6)
        ax_radar.set_xticks(angles[:-1])
        ax_radar.set_xticklabels(
            [f"{c}\n{s:.0f}" for c, s in zip(categories, scores)],
            fontsize=9,
        )
        ax_radar.set_ylim(0, 100)
        ax_radar.set_title("4D雷达", fontsize=14, fontweight="bold",
                           color=COLORS["text"], pad=20)

        # ─── 中左: Regime概率 ──────────────────────
        ax_regime = fig.add_subplot(gs[1, 0], facecolor=COLORS["background"])
        probs = regime.get("probabilities", {})
        if probs:
            r_labels = list(probs.keys())
            r_vals = list(probs.values())
            r_colors = [COLORS["primary"], COLORS["danger"],
                        COLORS["warning"], COLORS["accent"]]
            ax_regime.barh(r_labels, r_vals, color=r_colors[:len(r_labels)],
                           height=0.5, alpha=0.8)
        ax_regime.set_title("Regime概率", fontsize=12, fontweight="bold",
                            color=COLORS["text"])

        # ─── 中: PCR概况 ───────────────────────────
        ax_pcr = fig.add_subplot(gs[1, 1], facecolor=COLORS["background"])
        comp_pcr = pcr.get("composite_pcr", {})
        if comp_pcr:
            if hasattr(comp_pcr, "to_dict"):
                comp_pcr = comp_pcr.to_dict()
            if isinstance(comp_pcr, dict):
                pcr_labels = ["ETF", "CFFEX", "商品", "综合"]
                pcr_values = [
                    comp_pcr.get("etf_pcr", 0),
                    comp_pcr.get("cffex_pcr", 0),
                    comp_pcr.get("commodity_pcr", 0),
                    comp_pcr.get("composite_pcr", 0),
                ]
                ax_pcr.bar(pcr_labels, pcr_values,
                           color=[COLORS["primary"], COLORS["accent"],
                                  COLORS["warning"], COLORS["info"]],
                           alpha=0.85, width=0.5)
                ax_pcr.axhline(y=1.0, color=COLORS["text"], linewidth=0.8,
                               linestyle="--")
        ax_pcr.set_title("综合PCR", fontsize=12, fontweight="bold",
                         color=COLORS["text"])

        # ─── 中右: 外盘信号 ────────────────────────
        ax_overseas = fig.add_subplot(gs[1, 2:], facecolor=COLORS["background"])
        ov_scores = [
            overseas.get("price_score", 50),
            overseas.get("position_score", 50),
            overseas.get("macro_score", 50),
            overseas.get("sentiment_score", 50),
        ]
        ov_labels = ["价格", "持仓", "宏观", "情绪"]
        ov_colors = [COLORS["primary"], COLORS["accent"],
                     COLORS["warning"], COLORS["info"]]
        ax_overseas.bar(ov_labels, ov_scores, color=ov_colors, alpha=0.85,
                        width=0.5)
        ax_overseas.axhline(y=50, color=COLORS["text"], linewidth=0.8,
                            linestyle="--")
        ax_overseas.set_ylim(0, 100)
        ax_overseas.set_title(
            f"外盘信号: {overseas.get('composite_score', 50):.1f}",
            fontsize=12, fontweight="bold", color=COLORS["text"],
        )

        # ─── 底左: 风险评估 ────────────────────────
        ax_risk = fig.add_subplot(gs[2, :2], facecolor=COLORS["background"])
        risk_score = risk.get("overall_risk_score", 50)
        risk_level = risk.get("risk_level", "moderate")
        risk_color = COLORS["primary"] if risk_score >= 60 else (
            COLORS["warning"] if risk_score >= 40 else COLORS["danger"]
        )
        ax_risk.barh(["风险评分"], [risk_score], color=risk_color,
                     height=0.3, alpha=0.85)
        ax_risk.set_xlim(0, 100)
        ax_risk.text(risk_score + 1, 0, f"{risk_score:.1f}",
                     va="center", fontsize=14, fontweight="bold",
                     color=risk_color)
        ax_risk.set_title(
            f"风险评估 | 级别: {risk_level}",
            fontsize=12, fontweight="bold", color=COLORS["text"],
        )
        ax_risk.set_yticks([])

        # ─── 底右: 衍生品信号 ─────────────────────
        ax_deriv = fig.add_subplot(gs[2, 2:], facecolor=COLORS["background"])
        deriv_score = derivatives.get("composite_signal", 50)
        deriv_level = derivatives.get("signal_level", "normal")
        deriv_color = self._score_to_color(deriv_score)
        ax_deriv.barh(["衍生品信号"], [deriv_score], color=deriv_color,
                      height=0.3, alpha=0.85)
        ax_deriv.set_xlim(0, 100)
        ax_deriv.text(deriv_score + 1, 0, f"{deriv_score:.1f}",
                      va="center", fontsize=14, fontweight="bold",
                      color=deriv_color)
        ax_deriv.set_title(
            f"衍生品信号 | 级别: {deriv_level}",
            fontsize=12, fontweight="bold", color=COLORS["text"],
        )
        ax_deriv.set_yticks([])

        fig.suptitle(
            f"AiStock V8 综合仪表板 | "
            f"综合评分: {composite_score:.1f} | {label}",
            fontsize=18, fontweight="bold", color=COLORS["text"], y=0.99,
        )

        return self._save_fig(fig, "composite_dashboard")
