"""
Plotly交互式可视化构建器
10+种专业图表，覆盖产业链全景分析
"""

import os
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from typing import Dict, List, Any, Optional

from .config_loader import ConfigLoader
from .data_loader import DataLoader, Stock
from .chain_analyzer import ChainAnalyzer
from .relation_builder import RelationBuilder


class PlotlyBuilder:
    """Plotly交互式图表构建引擎"""

    def __init__(self, config: ConfigLoader, data: DataLoader,
                 chain: ChainAnalyzer, relations: RelationBuilder):
        self.config = config
        self.data = data
        self.chain = chain
        self.relations = relations
        self._cfg = config.load('plotly_charts')
        self._theme = self._cfg.get('theme', {})
        self._dir_colors = self._cfg.get('direction_colors', {})
        self._chain_colors = self._cfg.get('chain_colors', {})
        self._size_colors = self._cfg.get('size_colors', {})
        self._style_colors = self._cfg.get('style_colors', {})
        self._cycle_colors = self._cfg.get('cycle_colors', {})

    def _base_layout(self, title: str = "", **kwargs) -> Dict:
        """基础布局参数"""
        m = self._theme.get('margin', {})
        return dict(
            title=dict(text=title, font=dict(size=self._theme.get('title_font_size', 18),
                                              color=self._theme.get('font_color', '#e0e0e0'),
                                              family=self._theme.get('font_family', '')),
                       x=0.5, xanchor='center'),
            paper_bgcolor=self._theme.get('paper_bgcolor', '#0e1425'),
            plot_bgcolor=self._theme.get('plot_bgcolor', '#0e1425'),
            font=dict(family=self._theme.get('font_family', ''),
                      color=self._theme.get('font_color', '#e0e0e0'),
                      size=self._theme.get('label_font_size', 12)),
            margin=dict(l=m.get('l', 60), r=m.get('r', 30), t=m.get('t', 60), b=m.get('b', 50)),
            **kwargs,
        )

    def _axis_style(self, **kwargs) -> Dict:
        """坐标轴样式"""
        base = dict(
            gridcolor=self._theme.get('grid_color', 'rgba(255,255,255,0.06)'),
            zerolinecolor=self._theme.get('grid_color', 'rgba(255,255,255,0.06)'),
            tickfont=dict(size=self._theme.get('tick_font_size', 11)),
        )
        # merge kwargs, allowing overrides
        base.update(kwargs)
        return base

    # ================================================================
    # 图表1: 产业链层级Sunburst（方向→分类→赛道）
    # 悬浮只显示标的数量及平均评分
    # ================================================================
    def chart_sunburst(self) -> go.Figure:
        directions = self.data.get_directions()

        ids, labels, parents, values, colors, hover_texts = [], [], [], [], [], []

        for dir_name, direction in directions.items():
            # ── 方向层 ──
            dir_id = f"dir_{dir_name}"
            dir_stocks = [s for c in direction.categories for t in c.tracks for s in t.stocks]
            dir_count = len(dir_stocks)
            dir_avg = sum(s.score for s in dir_stocks) / max(dir_count, 1)

            ids.append(dir_id)
            labels.append(dir_name)
            parents.append("")
            values.append(dir_count)
            colors.append(self._dir_colors.get(dir_name, '#888'))
            hover_texts.append(f"标的数: {dir_count}<br>平均评分: {dir_avg:.2f}")

            for cat in direction.categories:
                # ── 分类层 ──
                cat_id = f"{dir_id}_cat_{cat.name}"
                cat_stocks = [s for t in cat.tracks for s in t.stocks]
                cat_count = len(cat_stocks)
                cat_avg = sum(s.score for s in cat_stocks) / max(cat_count, 1)

                ids.append(cat_id)
                labels.append(cat.name)
                parents.append(dir_id)
                values.append(cat_count)
                colors.append(self._dir_colors.get(dir_name, '#888'))
                hover_texts.append(f"标的数: {cat_count}<br>平均评分: {cat_avg:.2f}")

                for track in cat.tracks:
                    # ── 赛道层（最细粒度） ──
                    track_id = f"{cat_id}_trk_{track.name}"
                    track_count = len(track.stocks)
                    track_avg = sum(s.score for s in track.stocks) / max(track_count, 1)

                    ids.append(track_id)
                    labels.append(track.name)
                    parents.append(cat_id)
                    values.append(track_count)
                    colors.append(self._dir_colors.get(dir_name, '#888'))
                    hover_texts.append(f"标的数: {track_count}<br>平均评分: {track_avg:.2f}")

        fig = go.Figure(go.Sunburst(
            ids=ids, labels=labels, parents=parents, values=values,
            marker=dict(colors=colors, line=dict(width=1, color='#1a1a2e')),
            textinfo="label",
            textfont=dict(size=10, color='#fff'),
            hovertemplate='<b>%{label}</b><br>%{customdata}<extra></extra>',
            customdata=hover_texts,
            branchvalues='total',
            maxdepth=3,
        ))
        fig.update_layout(**self._base_layout("产业链层级结构 · Sunburst全景（方向→分类→赛道）"))
        return fig

    # ================================================================
    # 图表2: Treemap（方向→分类→赛道→标的 评分色阶）
    # ================================================================
    def chart_treemap(self) -> go.Figure:
        directions = self.data.get_directions()

        ids, labels, parents, values, colors_list = [], [], [], [], []
        for dir_name, direction in directions.items():
            # ── 方向层 ──
            dir_id = f"dir_{dir_name}"
            dir_stocks = [s for c in direction.categories for t in c.tracks for s in t.stocks]
            dir_total = sum(s.score * 100 for s in dir_stocks)

            ids.append(dir_id)
            labels.append(f"<b>{dir_name}</b>")
            parents.append("")
            values.append(dir_total)
            colors_list.append(self._dir_colors.get(dir_name, '#888'))

            for cat in direction.categories:
                # ── 分类层 ──
                cat_id = f"{dir_id}_cat_{cat.name}"
                cat_stocks = [s for t in cat.tracks for s in t.stocks]
                cat_total = sum(s.score * 100 for s in cat_stocks)

                ids.append(cat_id)
                labels.append(cat.name)
                parents.append(dir_id)
                values.append(cat_total)
                colors_list.append(self._dir_colors.get(dir_name, '#888'))

                for track in cat.tracks:
                    # ── 赛道层 ──
                    track_id = f"{cat_id}_trk_{track.name}"
                    track_total = sum(s.score * 100 for s in track.stocks)

                    ids.append(track_id)
                    labels.append(track.name)
                    parents.append(cat_id)
                    values.append(track_total)
                    colors_list.append(self._dir_colors.get(dir_name, '#888'))

                    for stock in track.stocks:
                        # ── 标的层 ──
                        stock_id = f"{track_id}_stk_{stock.name}"
                        ids.append(stock_id)
                        labels.append(f"{stock.name}<br>{stock.code}<br>{stock.score}")
                        parents.append(track_id)
                        values.append(stock.score * 100)
                        colors_list.append(stock.score)

        fig = go.Figure(go.Treemap(
            ids=ids, labels=labels, parents=parents, values=values,
            marker=dict(
                colors=colors_list,
                colorscale=self._cfg.get('score_colorscale', 'RdYlGn'),
                cmid=4.0,
                line=dict(width=1, color='#1a1a2e'),
            ),
            textfont=dict(size=10),
            hovertemplate='<b>%{label}</b><br>评分: %{color:.2f}<extra></extra>',
            branchvalues='total',
            maxdepth=4,
        ))
        fig.update_layout(**self._base_layout("标的评分分布 · Treemap色阶图（方向→分类→赛道→标的）"))
        return fig

    # ================================================================
    # 图表3: 各方向评分箱线图
    # ================================================================
    def chart_boxplot_scores(self) -> go.Figure:
        stocks = self.data.get_stocks()
        dir_stocks: Dict[str, List[float]] = {}
        for s in stocks.values():
            dir_stocks.setdefault(s.direction, []).append(s.score)

        fig = go.Figure()
        dir_order = sorted(dir_stocks.keys(), key=lambda d: -sum(dir_stocks[d]) / len(dir_stocks[d]))
        for dir_name in dir_order:
            fig.add_trace(go.Box(
                y=dir_stocks[dir_name],
                name=dir_name,
                marker_color=self._dir_colors.get(dir_name, '#888'),
                boxmean='sd',
                hovertemplate='%{text}<br>评分: %{y:.2f}<extra></extra>',
                text=[s for s in dir_stocks[dir_name]],
            ))

        fig.update_layout(
            **self._base_layout("各方向综合评分分布 · 箱线图"),
            showlegend=False,
            yaxis=self._axis_style(title='综合评分'),
            xaxis=self._axis_style(title=''),
        )
        return fig

    # ================================================================
    # 图表4: 政策契合度 vs 投资确定性 散点气泡图
    # ================================================================
    def chart_policy_vs_certainty(self) -> go.Figure:
        stocks = list(self.data.get_stocks().values())

        fig = go.Figure()
        for dir_name in self._dir_colors:
            dir_stocks = [s for s in stocks if s.direction == dir_name]
            if not dir_stocks:
                continue
            fig.add_trace(go.Scatter(
                x=[s.policy_fit for s in dir_stocks],
                y=[s.certainty for s in dir_stocks],
                mode='markers+text',
                marker=dict(
                    size=[s.score * 6 for s in dir_stocks],
                    color=self._dir_colors.get(dir_name, '#888'),
                    opacity=0.75,
                    line=dict(width=1, color='rgba(255,255,255,0.3)'),
                ),
                text=[s.name for s in dir_stocks],
                textposition='top center',
                textfont=dict(size=8),
                name=dir_name,
                hovertemplate='<b>%{text}</b><br>政策契合度: %{x}<br>投资确定性: %{y}<br>评分: %{marker.size:.1f}<extra></extra>',
                customdata=[s.score for s in dir_stocks],
            ))

        fig.update_layout(
            **self._base_layout("政策契合度 × 投资确定性 · 气泡图（气泡=综合评分）"),
            xaxis=self._axis_style(title='政策契合度', dtick=1, range=[3.5, 5.5]),
            yaxis=self._axis_style(title='投资确定性', dtick=1, range=[2.5, 5.5]),
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1,
                        font=dict(size=10)),
        )
        return fig

    # ================================================================
    # 图表5: 规模×风格 堆叠柱状图（按方向）
    # ================================================================
    def chart_size_style_distribution(self) -> go.Figure:
        stocks = list(self.data.get_stocks().values())
        directions = list(self._dir_colors.keys())

        # 规模×风格 组合
        combos = [('大盘', '龙头稳健型'), ('中盘', '龙头稳健型'), ('中盘', '中小盘弹性型'), ('小盘', '中小盘弹性型'), ('小盘', '龙头稳健型'), ('大盘', '中小盘弹性型')]
        combo_colors = ['#e74c3c', '#f39c12', '#e67e22', '#3498db', '#9b59b6', '#95a5a6']

        fig = go.Figure()
        for (sz, st), color in zip(combos, combo_colors):
            counts = []
            for d in directions:
                c = sum(1 for s in stocks if s.direction == d and s.size_class == sz and s.style == st)
                counts.append(c)
            if any(counts):
                fig.add_trace(go.Bar(
                    name=f"{sz}·{st}",
                    x=directions, y=counts,
                    marker_color=color,
                    hovertemplate='%{x}<br>' + f'{sz}·{st}' + ': %{y}只<extra></extra>',
                ))

        fig.update_layout(
            **self._base_layout("规模 × 投资风格分布 · 堆叠柱状图"),
            barmode='stack',
            xaxis=self._axis_style(title='', tickangle=30),
            yaxis=self._axis_style(title='标的数量'),
            legend=dict(font=dict(size=10), orientation='h', yanchor='bottom', y=1.05),
        )
        return fig

    # ================================================================
    # 图表6: 产业链上中下游价值分布（分组柱状图）
    # ================================================================
    def chart_chain_value_distribution(self) -> go.Figure:
        chains = self.chain.get_chains()

        fig = go.Figure()
        for level, color in self._chain_colors.items():
            counts, avgs, dirs = [], [], []
            for dir_name, chain in chains.items():
                nodes = getattr(chain, {'上游': 'upstream', '中游': 'midstream', '下游': 'downstream'}[level])
                all_stocks = [s for n in nodes for s in n.stocks]
                counts.append(len(all_stocks))
                avgs.append(sum(s.score for s in all_stocks) / max(len(all_stocks), 1))
                dirs.append(dir_name)

            fig.add_trace(go.Bar(
                name=f"{level}（均分{sum(avgs)/max(len(avgs),1):.2f}）",
                x=dirs, y=counts,
                marker_color=color,
                customdata=avgs,
                hovertemplate='%{x} · ' + level + '<br>标的数: %{y}<br>平均评分: %{customdata:.2f}<extra></extra>',
            ))

        fig.update_layout(
            **self._base_layout("上中下游标的分布 · 分组柱状图"),
            barmode='group',
            xaxis=self._axis_style(title='', tickangle=30),
            yaxis=self._axis_style(title='标的数量'),
            legend=dict(font=dict(size=10)),
        )
        return fig

    # ================================================================
    # 图表7: 标的优先级雷达图（各方向S2-S5分布）
    # ================================================================
    def chart_priority_radar(self) -> go.Figure:
        stocks = list(self.data.get_stocks().values())
        directions = list(self._dir_colors.keys())
        priorities = [2, 3, 4, 5]

        fig = go.Figure()
        for dir_name in directions:
            dir_stocks = [s for s in stocks if s.direction == dir_name]
            counts = [sum(1 for s in dir_stocks if s.priority == p) for p in priorities]
            if any(counts):
                fig.add_trace(go.Scatterpolar(
                    r=counts,
                    theta=[f'S{p}' for p in priorities],
                    fill='toself',
                    fillcolor=self._dir_colors.get(dir_name, '#888'),
                    line=dict(color=self._dir_colors.get(dir_name, '#888')),
                    opacity=0.35,
                    name=dir_name,
                    hovertemplate='%{theta}: %{r}只<extra></extra>',
                ))

        fig.update_layout(
            **self._base_layout("标的优先级分布 · 雷达图"),
            polar=dict(
                bgcolor=self._theme.get('paper_bgcolor', '#0e1425'),
                radialaxis=dict(gridcolor=self._theme.get('grid_color', 'rgba(255,255,255,0.06)'),
                                tickfont=dict(size=10)),
                angularaxis=dict(gridcolor=self._theme.get('grid_color', 'rgba(255,255,255,0.06)'),
                                 tickfont=dict(size=11)),
            ),
            legend=dict(font=dict(size=10), orientation='h', yanchor='bottom', y=-0.15),
        )
        return fig

    # ================================================================
    # 图表8: 核心业务占比 vs 综合评分 散点图（按方向着色）
    # ================================================================
    def chart_core_ratio_vs_score(self) -> go.Figure:
        stocks = list(self.data.get_stocks().values())

        fig = go.Figure()
        for dir_name in self._dir_colors:
            dir_stocks = [s for s in stocks if s.direction == dir_name]
            if not dir_stocks:
                continue
            fig.add_trace(go.Scatter(
                x=[s.core_ratio for s in dir_stocks],
                y=[s.score for s in dir_stocks],
                mode='markers+text',
                marker=dict(
                    size=10,
                    color=self._dir_colors.get(dir_name, '#888'),
                    opacity=0.7,
                    symbol=['circle' if s.size_class == '大盘' else 'diamond' if s.size_class == '中盘' else 'square' for s in dir_stocks],
                ),
                text=[s.name for s in dir_stocks],
                textposition='top center',
                textfont=dict(size=7),
                name=dir_name,
                hovertemplate='<b>%{text}</b><br>核心业务占比: %{x}%<br>综合评分: %{y:.2f}<extra></extra>',
            ))

        fig.update_layout(
            **self._base_layout("核心业务占比 × 综合评分 · 散点图"),
            xaxis=self._axis_style(title='核心业务占比 (%)'),
            yaxis=self._axis_style(title='综合评分'),
            legend=dict(font=dict(size=9), orientation='h', yanchor='bottom', y=1.02),
        )
        return fig

    # ================================================================
    # 图表9: 各赛道综合评分热力图
    # ================================================================
    def chart_track_heatmap(self) -> go.Figure:
        chains = self.chain.get_chains()
        tracks_data = []
        for dir_name, chain in chains.items():
            for level in ['upstream', 'midstream', 'downstream']:
                for node in getattr(chain, level):
                    tracks_data.append({
                        'direction': dir_name,
                        'track': node.name,
                        'level': {'upstream': '上游', 'midstream': '中游', 'downstream': '下游'}[level],
                        'avg_score': node.avg_score,
                        'stock_count': node.stock_count,
                    })

        # 按方向分组
        directions = list(self._dir_colors.keys())
        track_names = [t['track'] for t in tracks_data]

        # Build matrix: rows=tracks, cols=directions (sparse)
        unique_tracks = sorted(set(t['track'] for t in tracks_data))
        unique_dirs = directions

        import numpy as np
        z = np.full((len(unique_tracks), len(unique_dirs)), np.nan)
        text = np.full((len(unique_tracks), len(unique_dirs)), '', dtype=object)
        for t in tracks_data:
            ri = unique_tracks.index(t['track'])
            ci = unique_dirs.index(t['direction'])
            z[ri, ci] = t['avg_score']
            text[ri, ci] = f"{t['avg_score']:.2f}<br>({t['stock_count']}只)"

        fig = go.Figure(go.Heatmap(
            z=z, x=unique_dirs, y=unique_tracks,
            text=text, texttemplate='%{text}',
            colorscale=self._cfg.get('score_colorscale', 'RdYlGn'),
            zmid=4.0,
            zmin=3.0, zmax=5.0,
            hovertemplate='%{y} · %{x}<br>均分: %{z:.2f}<extra></extra>',
            textfont=dict(size=8),
            xgap=2, ygap=2,
        ))

        fig.update_layout(
            **self._base_layout("各赛道综合评分 · 热力图"),
            xaxis=self._axis_style(title='', tickangle=30),
            yaxis=self._axis_style(title='', tickfont=dict(size=9)),
            height=max(600, len(unique_tracks) * 16),
        )
        return fig

    # ================================================================
    # 图表10: Top20标的评分排名 水平柱状图
    # ================================================================
    def chart_top20_stocks(self) -> go.Figure:
        stocks = sorted(self.data.get_stocks().values(), key=lambda s: s.score, reverse=True)[:20]

        fig = go.Figure(go.Bar(
            y=[f"{s.name}<br>({s.track})" for s in stocks],
            x=[s.score for s in stocks],
            orientation='h',
            marker_color=[self._dir_colors.get(s.direction, '#888') for s in stocks],
            text=[f"{s.score:.2f}" for s in stocks],
            textposition='outside',
            textfont=dict(size=10, color='#e0e0e0'),
            hovertemplate='<b>%{y}</b><br>评分: %{x:.2f}<extra></extra>',
        ))

        fig.update_layout(
            **self._base_layout("Top20标的综合评分排名"),
            yaxis=dict(autorange='reversed', tickfont=dict(size=10)),
            xaxis=self._axis_style(title='综合评分', range=[3.5, 5.3]),
            height=600,
        )
        return fig

    # ================================================================
    # 图表15: 政策周期→一级方向→配置建议→标的 Sankey图
    # ================================================================
    def chart_policy_sankey(self) -> go.Figure:
        stocks = list(self.data.get_stocks().values())
        directions_data = self.data.get_directions()

        # ── 1. 构建所有唯一节点 ──
        # 层级: 政策周期 → 一级方向 → 配置建议 → 标的
        cycles = []       # 政策周期
        dir_names = []    # 一级方向
        suggestions = []  # 配置建议
        stock_names = []  # 标的

        for s in stocks:
            pc = self._get_stock_policy_cycle(s)
            if pc not in cycles:
                cycles.append(pc)
            if s.direction not in dir_names:
                dir_names.append(s.direction)
            if s.suggestion not in suggestions:
                suggestions.append(s.suggestion)
            if s.name not in stock_names:
                stock_names.append(s.name)

        # 确保周期按 近期→中期→远期 排序
        cycle_order = {'近期': 0, '中期': 1, '远期': 2}
        cycles.sort(key=lambda x: cycle_order.get(x, 9))

        # ── 2. 构建节点标签与颜色 ──
        node_labels = cycles + dir_names + suggestions + stock_names
        cycle_color_map = {'近期': '#2ecc71', '中期': '#f39c12', '远期': '#e74c3c'}
        # rgba半透明颜色（Sankey link不支持8位hex）
        def hex_to_rgba(hex_color, alpha=0.4):
            h = hex_color.lstrip('#')
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            return f'rgba({r},{g},{b},{alpha})'

        sug_color_list = ['#e74c3c', '#f39c12', '#3498db', '#2ecc71', '#9b59b6', '#1abc9c']

        node_colors = []
        # 政策周期节点
        for c in cycles:
            node_colors.append(cycle_color_map.get(c, '#888'))
        # 一级方向节点
        for d in dir_names:
            node_colors.append(self._dir_colors.get(d, '#888'))
        # 配置建议节点
        for i, sg in enumerate(suggestions):
            node_colors.append(sug_color_list[i % len(sug_color_list)])
        # 标的节点（使用方向颜色，低透明度）
        for s in stocks:
            node_colors.append(self._dir_colors.get(s.direction, '#888'))

        # ── 3. 计算节点索引偏移 ──
        n_cycles = len(cycles)
        n_dirs = len(dir_names)
        n_sugs = len(suggestions)

        def cycle_idx(name): return cycles.index(name)
        def dir_idx(name): return n_cycles + dir_names.index(name)
        def sug_idx(name): return n_cycles + n_dirs + suggestions.index(name)
        def stock_idx(name): return n_cycles + n_dirs + n_sugs + stock_names.index(name)

        # ── 4. 统计连边（政策周期→方向→建议→标的） ──
        # 用字典聚合相同连边
        link_dict = {}  # (src, tgt) → value

        # 层1: 政策周期 → 一级方向
        for s in stocks:
            pc = self._get_stock_policy_cycle(s)
            key = (cycle_idx(pc), dir_idx(s.direction))
            link_dict[key] = link_dict.get(key, 0) + 1

        # 记录层1/层2/层3的分界，用于着色
        n_link1 = len(link_dict)
        link1_end = n_link1

        # 层2: 一级方向 → 配置建议
        for s in stocks:
            key = (dir_idx(s.direction), sug_idx(s.suggestion))
            link_dict[key] = link_dict.get(key, 0) + 1

        link2_end = len(link_dict)

        # 层3: 配置建议 → 标的
        for s in stocks:
            key = (sug_idx(s.suggestion), stock_idx(s.name))
            link_dict[key] = link_dict.get(key, 0) + 1

        # ── 5. 拆分连边列表 ──
        all_keys = list(link_dict.keys())
        all_values = list(link_dict.values())
        all_sources = [k[0] for k in all_keys]
        all_targets = [k[1] for k in all_keys]

        # 着色
        all_colors = []
        for i, (src, tgt) in enumerate(all_keys):
            if i < link1_end:
                # 层1: 使用政策周期颜色
                pc_name = cycles[[c for c in range(n_cycles) if cycle_idx(cycles[c]) == src][0]]
                all_colors.append(hex_to_rgba(cycle_color_map.get(pc_name, '#888'), 0.4))
            elif i < link2_end:
                # 层2: 使用方向颜色
                dir_name = dir_names[[d for d in range(n_dirs) if dir_idx(dir_names[d]) == src][0]]
                all_colors.append(hex_to_rgba(self._dir_colors.get(dir_name, '#888'), 0.4))
            else:
                # 层3: 使用建议颜色，低透明度
                sug_name = suggestions[[sg for sg in range(n_sugs) if sug_idx(suggestions[sg]) == src][0]]
                sug_i = suggestions.index(sug_name)
                all_colors.append(hex_to_rgba(sug_color_list[sug_i % len(sug_color_list)], 0.25))

        # ── 6. 构建hover信息 ──
        all_hover = []
        for (src, tgt), val in zip(all_keys, all_values):
            src_label = node_labels[src]
            tgt_label = node_labels[tgt]
            all_hover.append(f"{src_label} → {tgt_label}<br>标的数: {val}")

        fig = go.Figure(go.Sankey(
            arrangement='snap',
            node=dict(
                pad=12,
                thickness=20,
                line=dict(color='#1a1a2e', width=1),
                label=node_labels[:n_cycles + n_dirs + n_sugs],  # 标的不显示标签（太多）
                color=node_colors[:n_cycles + n_dirs + n_sugs],
                hovertemplate='<b>%{label}</b><br>标的数: %{value}<extra></extra>',
            ),
            link=dict(
                source=all_sources,
                target=all_targets,
                value=all_values,
                color=all_colors,
                hovertemplate='%{customdata}<extra></extra>',
                customdata=all_hover,
            ),
        ))

        fig.update_layout(
            **self._base_layout("政策周期 → 一级方向 → 配置建议 → 标的 · Sankey流向图",
                                height=700),
        )
        return fig

    # ================================================================
    # 图表11: 关系类型统计 柱状图
    # ================================================================
    def chart_relation_stats(self) -> go.Figure:
        graph = self.relations.get_graph()
        rel_colors = self._cfg.get('relation_colors', {})

        # 按方向×关系类型统计赛道级关系
        track_rels = [r for r in graph.relations if r.source_type == 'track']
        directions = list(self._dir_colors.keys())
        rel_types = ['supply_chain', 'competition', 'synergy', 'validation']
        rel_labels = {'supply_chain': '供应链', 'competition': '竞争', 'synergy': '协同', 'validation': '验证'}

        fig = go.Figure()
        for rt in rel_types:
            counts = []
            for d in directions:
                c = sum(1 for r in track_rels if r.relation_type == rt and
                        (r.source in [n.name for ch in [self.chain.get_chains().get(d)] if ch for lv in ['upstream', 'midstream', 'downstream'] for n in getattr(ch, lv)] or
                         r.target in [n.name for ch in [self.chain.get_chains().get(d)] if ch for lv in ['upstream', 'midstream', 'downstream'] for n in getattr(ch, lv)]))
                counts.append(c)
            fig.add_trace(go.Bar(
                name=rel_labels.get(rt, rt),
                x=directions, y=counts,
                marker_color=rel_colors.get(rt, '#888'),
                hovertemplate='%{x} · ' + rel_labels.get(rt, rt) + ': %{y}条<extra></extra>',
            ))

        fig.update_layout(
            **self._base_layout("赛道级关系类型分布 · 堆叠柱状图"),
            barmode='stack',
            xaxis=self._axis_style(title='', tickangle=30),
            yaxis=self._axis_style(title='关系数量'),
            legend=dict(font=dict(size=10)),
        )
        return fig

    # ================================================================
    # 图表12: 政策周期×方向 矩阵图
    # ================================================================
    def chart_policy_cycle_matrix(self) -> go.Figure:
        stocks = list(self.data.get_stocks().values())
        directions = list(self._dir_colors.keys())
        cycles = ['近期', '中期', '远期']

        import numpy as np
        z = np.zeros((len(directions), len(cycles)))
        text_arr = np.full((len(directions), len(cycles)), '', dtype=object)

        for i, d in enumerate(directions):
            for j, c in enumerate(cycles):
                dir_stocks = [s for s in stocks if s.direction == d and
                              self._get_stock_policy_cycle(s) == c]
                z[i, j] = len(dir_stocks)
                avg = sum(s.score for s in dir_stocks) / max(len(dir_stocks), 1)
                text_arr[i, j] = f"{len(dir_stocks)}只<br>均分{avg:.2f}"

        fig = go.Figure(go.Heatmap(
            z=z, x=cycles, y=directions,
            text=text_arr, texttemplate='%{text}',
            colorscale='Blues',
            textfont=dict(size=11),
            hovertemplate='%{y} · %{x}<br>标的数: %{z}<extra></extra>',
        ))

        fig.update_layout(
            **self._base_layout("政策周期 × 方向 · 矩阵图"),
            xaxis=self._axis_style(title='政策周期'),
            yaxis=self._axis_style(title=''),
        )
        return fig

    def _get_stock_policy_cycle(self, stock: Stock) -> str:
        """获取标的的政策周期——直接从标的级别读取"""
        return stock.policy_cycle if stock.policy_cycle else '近期'

    # ================================================================
    # 图表13: 配置建议分布 环形图
    # ================================================================
    def chart_suggestion_donut(self) -> go.Figure:
        stocks = list(self.data.get_stocks().values())
        suggestions = {}
        for s in stocks:
            suggestions.setdefault(s.suggestion, []).append(s)

        labels = list(suggestions.keys())
        values = [len(v) for v in suggestions.values()]
        avg_scores = [sum(s.score for s in v) / len(v) for v in suggestions.values()]

        fig = go.Figure(go.Pie(
            labels=labels, values=values,
            hole=0.55,
            marker=dict(colors=['#e74c3c', '#f39c12', '#3498db', '#2ecc71'][:len(labels)],
                        line=dict(width=2, color='#0e1425')),
            textinfo='label+percent',
            textfont=dict(size=11, color='#fff'),
            hovertemplate='<b>%{label}</b><br>数量: %{value}只<br>占比: %{percent}<extra></extra>',
        ))

        # 中心文字
        fig.add_annotation(text=f"共{len(stocks)}只", x=0.5, y=0.5,
                           font=dict(size=16, color='#fff'), showarrow=False)

        fig.update_layout(
            **self._base_layout("配置建议分布 · 环形图"),
            showlegend=True,
            legend=dict(font=dict(size=10)),
        )
        return fig

    # ================================================================
    # 图表14: 各方向赛道独立价值评级分布
    # ================================================================
    def chart_value_rating_distribution(self) -> go.Figure:
        stocks = list(self.data.get_stocks().values())
        directions = list(self._dir_colors.keys())

        fig = go.Figure()
        for dir_name in directions:
            dir_stocks = [s for s in stocks if s.direction == dir_name]
            if not dir_stocks:
                continue
            # 按赛道聚合
            tracks = {}
            for s in dir_stocks:
                tracks.setdefault(s.track, []).append(s)

            # 赛道独立价值评级
            track_scores = {}
            for t_name, t_stocks in tracks.items():
                track_scores[t_name] = max(s.score for s in t_stocks)

            fig.add_trace(go.Violin(
                y=list(track_scores.values()),
                name=dir_name,
                box_visible=True,
                meanline_visible=True,
                line_color=self._dir_colors.get(dir_name, '#888'),
                fillcolor=self._dir_colors.get(dir_name, '#888'),
                opacity=0.6,
                hovertemplate='%{y:.2f}<extra></extra>',
            ))

        fig.update_layout(
            **self._base_layout("各方向赛道评分分布 · 小提琴图"),
            yaxis=self._axis_style(title='赛道最高评分'),
            showlegend=False,
        )
        return fig

    # ================================================================
    # 保存单个图表
    # ================================================================
    def save_chart(self, fig: go.Figure, filename: str, output_dir: str = None) -> str:
        if output_dir is None:
            output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'output')
        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, filename)
        fig.write_html(filepath, include_plotlyjs='cdn', full_html=True)
        return filepath

    # ================================================================
    # 生成全部图表
    # ================================================================
    def generate_all(self, output_dir: str = None) -> Dict[str, str]:
        if output_dir is None:
            output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'output')
        os.makedirs(output_dir, exist_ok=True)

        results = {}
        charts = [
            ('01_sunburst', '产业链层级结构', self.chart_sunburst),
            ('02_treemap', '标的评分Treemap', self.chart_treemap),
            ('03_boxplot', '评分箱线图', self.chart_boxplot_scores),
            ('04_policy_vs_certainty', '政策契合度×确定性', self.chart_policy_vs_certainty),
            ('05_size_style', '规模×风格分布', self.chart_size_style_distribution),
            ('06_chain_value', '上中下游价值分布', self.chart_chain_value_distribution),
            ('07_radar', '优先级雷达图', self.chart_priority_radar),
            ('08_core_ratio_vs_score', '核心占比×评分', self.chart_core_ratio_vs_score),
            ('09_heatmap', '赛道评分热力图', self.chart_track_heatmap),
            ('10_top20', 'Top20标的排名', self.chart_top20_stocks),
            ('11_relations', '关系类型统计', self.chart_relation_stats),
            ('12_policy_matrix', '政策周期矩阵', self.chart_policy_cycle_matrix),
            ('13_suggestion_donut', '配置建议环形图', self.chart_suggestion_donut),
            ('14_violin', '评分分布小提琴图', self.chart_value_rating_distribution),
            ('15_sankey', '政策周期Sankey流向', self.chart_policy_sankey),
        ]

        for idx, (name, desc, chart_fn) in enumerate(charts, 1):
            print(f"  [{idx}/{len(charts)}] {desc}...", end=' ')
            try:
                fig = chart_fn()
                filepath = self.save_chart(fig, f'plotly_{name}.html', output_dir)
                results[name] = filepath
                print(f'✓ → {filepath}')
            except Exception as e:
                print(f'✗ {e}')
                import traceback
                traceback.print_exc()

        return results
