#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
state_visualizer：市场状态可视化模块
提供 3D 散点图、概率柱状图、衍生品仪表盘、风险仪表盘
"""

import os
from datetime import datetime
from typing import Dict, Optional

import matplotlib
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np

# ── 字体设置 ──────────────────────────────────────────────────────────────────
_font_path = '/usr/share/fonts/truetype/chinese/NotoSansSC[wght].ttf'
if os.path.exists(_font_path):
    fm.fontManager.addfont(_font_path)

plt.rcParams['font.sans-serif'] = ['Noto Sans SC', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# ── 配色 ──────────────────────────────────────────────────────────────────────
_CMAP_STATE = {
    '极度低估': '#2ecc71',
    '低估':     '#58d68d',
    '合理':     '#f39c12',
    '高估':     '#e67e22',
    '极度高估': '#e74c3c',
}
_REGIME_COLORS = ['#3498db', '#2ecc71', '#e74c3c', '#9b59b6', '#f39c12', '#1abc9c']


class StateVisualizer:
    """市场状态独立可视化器，无业务层依赖，仅接收 Dict 结果"""

    def __init__(self, config: Dict):
        self.config = config
        self.output_dir: str = config.get('output_dir', './output/visualization/')
        os.makedirs(self.output_dir, exist_ok=True)

    # ── 工具方法 ──────────────────────────────────────────────────────────────
    @staticmethod
    def _resolve_save_path(save_path: Optional[str], default_name: str) -> str:
        if save_path:
            directory = os.path.dirname(save_path)
            if directory:
                os.makedirs(directory, exist_ok=True)
            return save_path
        return default_name

    @staticmethod
    def _empty_figure(title: str, save_path: str):
        """空数据时生成占位图"""
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.text(0.5, 0.5, '暂无数据', ha='center', va='center',
                fontsize=18, color='#999999', transform=ax.transAxes)
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.axis('off')
        fig.tight_layout()
        fig.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close(fig)

    # ── 3D 市场状态散点图 ────────────────────────────────────────────────────
    def plot_market_state_3d(self,
                             classification_result: Dict,
                             save_path: Optional[str] = None) -> str:
        """三维散点图：估值 / 动量 / 体制得分"""
        default = os.path.join(self.output_dir, 'market_state_3d.png')
        path = self._resolve_save_path(save_path, default)

        states = classification_result.get('states', [])
        if not states:
            self._empty_figure('市场状态三维分布', path)
            return path

        fig = plt.figure(figsize=(12, 9))
        ax = fig.add_subplot(111, projection='3d')

        for state_info in states:
            name = state_info.get('state', '未知')
            val = state_info.get('valuation_score', 0)
            mom = state_info.get('momentum_score', 0)
            reg = state_info.get('regime_score', 0)
            color = _CMAP_STATE.get(name, '#95a5a6')
            ax.scatter(val, mom, reg, c=color, s=120, label=name, edgecolors='k', linewidths=0.5)

        ax.set_xlabel('估值得分', fontsize=11)
        ax.set_ylabel('动量得分', fontsize=11)
        ax.set_zlabel('体制得分', fontsize=11)
        ax.set_title('市场状态三维分布', fontsize=14, fontweight='bold')
        ax.legend(loc='upper left', fontsize=9)
        fig.tight_layout()
        fig.savefig(path, dpi=150, bbox_inches='tight')
        plt.close(fig)
        return path

    # ── 体制概率柱状图 ────────────────────────────────────────────────────────
    def plot_regime_probability(self,
                                regime_result: Dict,
                                save_path: Optional[str] = None) -> str:
        """柱状图：各体制概率"""
        default = os.path.join(self.output_dir, 'regime_probability.png')
        path = self._resolve_save_path(save_path, default)

        probabilities = regime_result.get('regime_probabilities', {})
        if not probabilities:
            self._empty_figure('体制概率分布', path)
            return path

        labels = list(probabilities.keys())
        values = [probabilities[k] for k in labels]
        colors = [_REGIME_COLORS[i % len(_REGIME_COLORS)] for i in range(len(labels))]

        fig, ax = plt.subplots(figsize=(10, 6))
        bars = ax.bar(labels, values, color=colors, edgecolor='white', linewidth=0.8)

        for bar, val in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01,
                    f'{val:.1%}', ha='center', va='bottom', fontsize=10)

        ax.set_ylabel('概率', fontsize=11)
        ax.set_title('体制概率分布', fontsize=14, fontweight='bold')
        ax.set_ylim(0, min(max(values) * 1.3, 1.05))
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f'{y:.0%}'))
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        fig.tight_layout()
        fig.savefig(path, dpi=150, bbox_inches='tight')
        plt.close(fig)
        return path

    # ── 衍生品仪表盘 ─────────────────────────────────────────────────────────
    def plot_derivatives_dashboard(self,
                                   derivatives_result: Dict,
                                   save_path: Optional[str] = None) -> str:
        """组合面板：期限结构 + 基差"""
        default = os.path.join(self.output_dir, 'derivatives_dashboard.png')
        path = self._resolve_save_path(save_path, default)

        term_data = derivatives_result.get('term_structure', {})
        basis_data = derivatives_result.get('basis_analysis', {})

        if not term_data and not basis_data:
            self._empty_figure('衍生品信号仪表盘', path)
            return path

        fig = plt.figure(figsize=(16, 7))
        gs = gridspec.GridSpec(1, 2, width_ratios=[1, 1], wspace=0.35)

        # ── 期限结构 ──────────────────────────────────────────────────────────
        ax1 = fig.add_subplot(gs[0])
        if term_data:
            contracts = list(term_data.keys())
            prices = [term_data[c].get('price', 0) if isinstance(term_data[c], dict) else term_data[c]
                      for c in contracts]
            ax1.plot(contracts, prices, 'o-', color='#3498db', linewidth=2, markersize=7)
            ax1.fill_between(range(len(contracts)), prices, alpha=0.15, color='#3498db')
            ax1.set_xlabel('合约', fontsize=10)
            ax1.set_ylabel('价格', fontsize=10)
        else:
            ax1.text(0.5, 0.5, '无期限结构数据', ha='center', va='center',
                     transform=ax1.transAxes, fontsize=12, color='#999')
        ax1.set_title('期限结构', fontsize=13, fontweight='bold')
        ax1.spines['top'].set_visible(False)
        ax1.spines['right'].set_visible(False)

        # ── 基差分析 ──────────────────────────────────────────────────────────
        ax2 = fig.add_subplot(gs[1])
        if basis_data:
            names = list(basis_data.keys())
            basis_vals = [basis_data[n].get('basis', 0) if isinstance(basis_data[n], dict) else basis_data[n]
                          for n in names]
            bar_colors = ['#e74c3c' if v < 0 else '#2ecc71' for v in basis_vals]
            ax2.bar(names, basis_vals, color=bar_colors, edgecolor='white', linewidth=0.6)
            ax2.axhline(0, color='#555555', linewidth=0.8, linestyle='--')
            ax2.set_xlabel('品种', fontsize=10)
            ax2.set_ylabel('基差', fontsize=10)
        else:
            ax2.text(0.5, 0.5, '无基差数据', ha='center', va='center',
                     transform=ax2.transAxes, fontsize=12, color='#999')
        ax2.set_title('基差分析', fontsize=13, fontweight='bold')
        ax2.spines['top'].set_visible(False)
        ax2.spines['right'].set_visible(False)

        fig.suptitle('衍生品信号仪表盘', fontsize=15, fontweight='bold', y=1.02)
        fig.tight_layout()
        fig.savefig(path, dpi=150, bbox_inches='tight')
        plt.close(fig)
        return path

    # ── 风险仪表盘 ───────────────────────────────────────────────────────────
    def plot_risk_dashboard(self,
                            risk_result: Dict,
                            save_path: Optional[str] = None) -> str:
        """风险指标仪表盘：综合得分 + 风险因子雷达 + 指标摘要"""
        default = os.path.join(self.output_dir, 'risk_dashboard.png')
        path = self._resolve_save_path(save_path, default)

        if not risk_result:
            self._empty_figure('风险评估仪表盘', path)
            return path

        fig = plt.figure(figsize=(16, 7))
        gs = gridspec.GridSpec(1, 3, width_ratios=[1, 1.3, 1], wspace=0.4)

        # ── 综合风险评分 ──────────────────────────────────────────────────────
        ax1 = fig.add_subplot(gs[0])
        overall = risk_result.get('overall_risk_score', 0)
        risk_level = risk_result.get('risk_level', '未知')
        level_color = {'低': '#2ecc71', '中低': '#58d68d', '中': '#f39c12',
                       '中高': '#e67e22', '高': '#e74c3c'}.get(risk_level, '#95a5a6')

        theta = np.linspace(0, 2 * np.pi, 100)
        r_max = 100
        ax1.plot(r_max * np.cos(theta), r_max * np.sin(theta), color='#ddd', linewidth=1)
        ax1.fill(r_max * np.cos(theta), r_max * np.sin(theta), color='#f9f9f9')
        fill_theta = np.linspace(0, 2 * np.pi * (overall / r_max), 100)
        ax1.fill(overall * np.cos(fill_theta), overall * np.sin(fill_theta),
                 color=level_color, alpha=0.35)
        ax1.text(0, 0, f'{overall:.0f}\n{risk_level}', ha='center', va='center',
                 fontsize=18, fontweight='bold', color=level_color)
        ax1.set_xlim(-r_max * 1.2, r_max * 1.2)
        ax1.set_ylim(-r_max * 1.2, r_max * 1.2)
        ax1.set_aspect('equal')
        ax1.axis('off')
        ax1.set_title('综合风险评分', fontsize=13, fontweight='bold')

        # ── 风险因子雷达图 ────────────────────────────────────────────────────
        ax2 = fig.add_subplot(gs[1], polar=True)
        factors = risk_result.get('risk_factors', {})
        if factors:
            labels = list(factors.keys())
            values = [factors[k] if isinstance(factors[k], (int, float)) else 0 for k in labels]
            n = len(labels)
            angles = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
            values_closed = values + [values[0]]
            angles_closed = angles + [angles[0]]
            ax2.plot(angles_closed, values_closed, 'o-', color='#3498db', linewidth=2)
            ax2.fill(angles_closed, values_closed, alpha=0.2, color='#3498db')
            ax2.set_xticks(angles)
            ax2.set_xticklabels(labels, fontsize=9)
            ax2.set_title('风险因子雷达', fontsize=13, fontweight='bold', pad=20)
        else:
            ax2.set_title('风险因子雷达\n(无数据)', fontsize=13, fontweight='bold')

        # ── 指标摘要表 ────────────────────────────────────────────────────────
        ax3 = fig.add_subplot(gs[2])
        metrics = risk_result.get('risk_metrics', {})
        if metrics:
            rows = list(metrics.keys())
            vals = [f'{metrics[k]:.2f}' if isinstance(metrics[k], (int, float)) else str(metrics[k])
                    for k in rows]
            table = ax3.table(cellText=[[v] for v in vals],
                              rowLabels=rows,
                              colLabels=['数值'],
                              loc='center',
                              cellLoc='center')
            table.auto_set_font_size(False)
            table.set_fontsize(9)
            table.scale(1, 1.5)
        else:
            ax3.text(0.5, 0.5, '无风险指标数据', ha='center', va='center',
                     transform=ax3.transAxes, fontsize=12, color='#999')
        ax3.axis('off')
        ax3.set_title('风险指标摘要', fontsize=13, fontweight='bold')

        fig.suptitle('风险评估仪表盘', fontsize=15, fontweight='bold', y=1.02)
        fig.tight_layout()
        fig.savefig(path, dpi=150, bbox_inches='tight')
        plt.close(fig)
        return path
