"""
Plotly仪表盘整合模块
将多个图表组合为单一交互式仪表盘页面
"""

import os
from plotly.subplots import make_subplots
import plotly.graph_objects as go
from typing import Dict, List

from .config_loader import ConfigLoader
from .data_loader import DataLoader
from .chain_analyzer import ChainAnalyzer
from .relation_builder import RelationBuilder
from .plotly_builder import PlotlyBuilder


class DashboardBuilder:
    """组合仪表盘构建器"""

    def __init__(self, config: ConfigLoader, data: DataLoader,
                 chain: ChainAnalyzer, relations: RelationBuilder):
        self.config = config
        self.data = data
        self.chain = chain
        self.relations = relations
        self._cfg = config.load('plotly_charts')
        self._theme = self._cfg.get('theme', {})
        self.plotly = PlotlyBuilder(config, data, chain, relations)

    def build_overview_dashboard(self, output_path: str = None) -> str:
        """构建全景总览仪表盘（6图组合）"""
        if output_path is None:
            output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'output')
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, 'plotly_dashboard_overview.html')

        # 创建子图布局: 2行3列
        fig = make_subplots(
            rows=2, cols=3,
            specs=[
                [{"type": "sunburst"}, {"type": "xy"}, {"type": "xy"}],
                [{"type": "xy"}, {"type": "xy"}, {"type": "pie"}],
            ],
            subplot_titles=(
                "产业链层级结构", "上中下游标的分布", "评分箱线图",
                "规模×风格分布", "政策周期矩阵", "配置建议分布"
            ),
            horizontal_spacing=0.08,
            vertical_spacing=0.12,
        )

        # --- 1. Sunburst (1,1) ---
        sb = self.plotly.chart_sunburst()
        for trace in sb.data:
            fig.add_trace(trace, row=1, col=1)

        # --- 2. 上中下游柱状图 (1,2) ---
        chain_bar = self.plotly.chart_chain_value_distribution()
        for trace in chain_bar.data:
            fig.add_trace(trace, row=1, col=2)

        # --- 3. 箱线图 (1,3) ---
        box = self.plotly.chart_boxplot_scores()
        for trace in box.data:
            trace.showlegend = False
            fig.add_trace(trace, row=1, col=3)

        # --- 4. 规模×风格 (2,1) ---
        ss = self.plotly.chart_size_style_distribution()
        for trace in ss.data:
            fig.add_trace(trace, row=2, col=1)

        # --- 5. 政策周期热力图 (2,2) ---
        hm = self.plotly.chart_policy_cycle_matrix()
        for trace in hm.data:
            fig.add_trace(trace, row=2, col=2)

        # --- 6. 配置建议环形图 (2,3) ---
        donut = self.plotly.chart_suggestion_donut()
        for trace in donut.data:
            fig.add_trace(trace, row=2, col=3)

        # 统一样式
        fig.update_layout(
            title=dict(text="十大投资方向 · 产业链全景总览仪表盘",
                       font=dict(size=22, color='#fff'), x=0.5, xanchor='center'),
            paper_bgcolor=self._theme.get('paper_bgcolor', '#0e1425'),
            plot_bgcolor=self._theme.get('plot_bgcolor', '#0e1425'),
            font=dict(family=self._theme.get('font_family', ''),
                      color=self._theme.get('font_color', '#e0e0e0')),
            height=900,
            showlegend=True,
            legend=dict(font=dict(size=9)),
        )

        # 坐标轴样式
        for i in range(1, 7):
            try:
                fig.update_xaxes(gridcolor=self._theme.get('grid_color', 'rgba(255,255,255,0.06)'),
                                 row=(i-1)//3+1, col=(i-1)%3+1)
                fig.update_yaxes(gridcolor=self._theme.get('grid_color', 'rgba(255,255,255,0.06)'),
                                 row=(i-1)//3+1, col=(i-1)%3+1)
            except Exception:
                pass

        fig.write_html(output_path, include_plotlyjs='cdn', full_html=True)
        return output_path

    def build_scoring_dashboard(self, output_path: str = None) -> str:
        """构建评分分析仪表盘"""
        if output_path is None:
            output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'output')
            output_path = os.path.join(output_dir, 'plotly_dashboard_scoring.html')

        fig = make_subplots(
            rows=2, cols=3,
            specs=[
                [{"type": "xy"}, {"type": "xy"}, {"type": "polar"}],
                [{"type": "xy"}, {"type": "xy"}, {"type": "xy"}],
            ],
            subplot_titles=(
                "Top20标的排名", "评分箱线图", "优先级雷达图",
                "核心业务占比×评分", "赛道评分热力图", "小提琴图"
            ),
            horizontal_spacing=0.08,
            vertical_spacing=0.12,
        )

        # 1. Top20
        top = self.plotly.chart_top20_stocks()
        for trace in top.data:
            trace.showlegend = False
            fig.add_trace(trace, row=1, col=1)

        # 2. 箱线图
        box = self.plotly.chart_boxplot_scores()
        for trace in box.data:
            trace.showlegend = False
            fig.add_trace(trace, row=1, col=2)

        # 3. 雷达图
        radar = self.plotly.chart_priority_radar()
        for trace in radar.data:
            fig.add_trace(trace, row=1, col=3)

        # 4. 核心占比×评分
        core = self.plotly.chart_core_ratio_vs_score()
        for trace in core.data:
            fig.add_trace(trace, row=2, col=1)

        # 5. 热力图
        hm = self.plotly.chart_track_heatmap()
        for trace in hm.data:
            fig.add_trace(trace, row=2, col=2)

        # 6. 小提琴图
        violin = self.plotly.chart_value_rating_distribution()
        for trace in violin.data:
            trace.showlegend = False
            fig.add_trace(trace, row=2, col=3)

        fig.update_layout(
            title=dict(text="综合评分深度分析仪表盘",
                       font=dict(size=22, color='#fff'), x=0.5, xanchor='center'),
            paper_bgcolor=self._theme.get('paper_bgcolor', '#0e1425'),
            plot_bgcolor=self._theme.get('plot_bgcolor', '#0e1425'),
            font=dict(family=self._theme.get('font_family', ''),
                      color=self._theme.get('font_color', '#e0e0e0')),
            height=900,
            legend=dict(font=dict(size=9)),
        )

        fig.write_html(output_path, include_plotlyjs='cdn', full_html=True)
        return output_path

    def build_relation_dashboard(self, output_path: str = None) -> str:
        """构建关系分析仪表盘"""
        if output_path is None:
            output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'output')
            output_path = os.path.join(output_dir, 'plotly_dashboard_relations.html')

        fig = make_subplots(
            rows=2, cols=2,
            specs=[[{"type": "xy"}, {"type": "xy"}],
                   [{"type": "xy"}, {"type": "xy"}]],
            subplot_titles=(
                "赛道级关系类型分布", "政策契合度×投资确定性",
                "Treemap评分分布", "关系类型统计",
            ),
            horizontal_spacing=0.1,
            vertical_spacing=0.12,
        )

        # 1. 关系分布
        rel = self.plotly.chart_relation_stats()
        for trace in rel.data:
            fig.add_trace(trace, row=1, col=1)

        # 2. 政策×确定性
        pv = self.plotly.chart_policy_vs_certainty()
        for trace in pv.data:
            fig.add_trace(trace, row=1, col=2)

        # 3. Treemap
        tm = self.plotly.chart_treemap()
        for trace in tm.data:
            fig.add_trace(trace, row=2, col=1)

        # 4. 配置建议
        donut = self.plotly.chart_suggestion_donut()
        for trace in donut.data:
            fig.add_trace(trace, row=2, col=2)

        fig.update_layout(
            title=dict(text="产业链关系与政策分析仪表盘",
                       font=dict(size=22, color='#fff'), x=0.5, xanchor='center'),
            paper_bgcolor=self._theme.get('paper_bgcolor', '#0e1425'),
            plot_bgcolor=self._theme.get('plot_bgcolor', '#0e1425'),
            font=dict(family=self._theme.get('font_family', ''),
                      color=self._theme.get('font_color', '#e0e0e0')),
            height=800,
            legend=dict(font=dict(size=9)),
        )

        fig.write_html(output_path, include_plotlyjs='cdn', full_html=True)
        return output_path

    def generate_all_dashboards(self, output_dir: str = None) -> Dict[str, str]:
        """生成全部仪表盘"""
        if output_dir is None:
            output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'output')

        results = {}
        print("[仪表盘] 生成全景总览仪表盘...")
        results['overview'] = self.build_overview_dashboard(
            os.path.join(output_dir, 'plotly_dashboard_overview.html'))
        print(f"  ✓ → {results['overview']}")

        print("[仪表盘] 生成评分分析仪表盘...")
        results['scoring'] = self.build_scoring_dashboard(
            os.path.join(output_dir, 'plotly_dashboard_scoring.html'))
        print(f"  ✓ → {results['scoring']}")

        print("[仪表盘] 生成关系分析仪表盘...")
        results['relations'] = self.build_relation_dashboard(
            os.path.join(output_dir, 'plotly_dashboard_relations.html'))
        print(f"  ✓ → {results['relations']}")

        return results