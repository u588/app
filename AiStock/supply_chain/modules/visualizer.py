"""
Pyvis可视化引擎 - 生成交互式产业链关系网络图
支持多层级、多关系类型的专业可视化
"""

import os
import json
from typing import Dict, List, Any, Optional, Set

from pyvis.network import Network

from .config_loader import ConfigLoader
from .data_loader import DataLoader, Direction, Category, Track, Stock
from .chain_analyzer import ChainAnalyzer, DirectionChain, ChainNode
from .relation_builder import RelationBuilder, RelationGraph, Relation


class SupplyChainVisualizer:
    """产业链Pyvis可视化引擎"""

    def __init__(self, config: ConfigLoader, data: DataLoader,
                 chain_analyzer: ChainAnalyzer, relation_builder: RelationBuilder):
        self.config = config
        self.data = data
        self.chain = chain_analyzer
        self.relations = relation_builder
        self._vis_config = config.load('visual')
        self._chain_config = config.load('industry_chain')

    def _get_direction_color(self, direction: str) -> str:
        colors = self._vis_config.get('direction_colors', {})
        return colors.get(direction, '#888888')

    def _get_level_color(self, level: str) -> str:
        colors = self._vis_config.get('chain_level_colors', {})
        return colors.get(level, '#888888')

    def _get_level_label(self, level: str) -> str:
        labels = self._vis_config.get('chain_level_labels', {})
        return labels.get(level, level)

    def _get_edge_style(self, relation_type: str) -> Dict:
        styles = self._vis_config.get('edge_styles', {})
        return styles.get(relation_type, {})

    def _hex_to_rgba(self, hex_color: str, alpha: float = 1.0) -> str:
        """将hex颜色转为rgba"""
        hex_color = hex_color.lstrip('#')
        r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        return f"rgba({r},{g},{b},{alpha})"

    def _make_node_tooltip(self, node_type: str, data: Dict) -> str:
        """生成节点悬停提示（HTML格式，由MutationObserver渲染）"""
        if node_type == 'direction':
            return (
                f"<b>{data['name']}</b>"
                f"<div class='tt-divider'></div>"
                f"<div class='tt-row'><span class='tt-label'>优先级：</span><span class='tt-val'>{data.get('priority', '')}</span></div>"
                f"<div class='tt-row'><span class='tt-label'>政策周期：</span><span class='tt-val'>{data.get('policy_cycle', '')}</span></div>"
                f"<div class='tt-row'><span class='tt-label'>标的数量：</span><span class='tt-val'>{data.get('stock_count', 0)}</span></div>"
                f"<div class='tt-row'><span class='tt-label'>赛道数量：</span><span class='tt-val'>{data.get('track_count', 0)}</span></div>"
            )
        elif node_type == 'track':
            level_label = self._get_level_label(data.get('level', ''))
            return (
                f"<b>{data['name']}</b>"
                f"<div class='tt-divider'></div>"
                f"<div class='tt-row'><span class='tt-label'>所属方向：</span><span class='tt-val'>{data.get('direction', '')}</span></div>"
                f"<div class='tt-row'><span class='tt-label'>所属分类：</span><span class='tt-val'>{data.get('category', '')}</span></div>"
                f"<div class='tt-row'><span class='tt-label'>产业链层级：</span><span class='tt-val'>{level_label}</span></div>"
                f"<div class='tt-row'><span class='tt-label'>标的数量：</span><span class='tt-val'>{data.get('stock_count', 0)}</span></div>"
                f"<div class='tt-row'><span class='tt-label'>平均评分：</span><span class='tt-val'>{data.get('avg_score', 0):.2f}</span></div>"
            )
        elif node_type == 'stock':
            return (
                f"<b>{data['name']}</b> <span style='color:#8899aa'>({data.get('code', '')})</span>"
                f"<div class='tt-divider'></div>"
                f"<div class='tt-row'><span class='tt-label'>所属方向：</span><span class='tt-val'>{data.get('direction', '')}</span></div>"
                f"<div class='tt-row'><span class='tt-label'>所属赛道：</span><span class='tt-val'>{data.get('track', '')}</span></div>"
                f"<div class='tt-row'><span class='tt-label'>规模：</span><span class='tt-val'>{data.get('size_class', '')}</span></div>"
                f"<div class='tt-row'><span class='tt-label'>投资风格：</span><span class='tt-val'>{data.get('style', '')}</span></div>"
                f"<div class='tt-row'><span class='tt-label'>综合评分：</span><span class='tt-val' style='color:#f0c040'>{data.get('score', 0)}</span></div>"
                f"<div class='tt-row'><span class='tt-label'>标的优先级：</span><span class='tt-val'>S{data.get('priority', 0)}</span></div>"
                f"<div class='tt-row'><span class='tt-label'>配置建议：</span><span class='tt-val'>{data.get('suggestion', '')}</span></div>"
                f"<div class='tt-divider'></div>"
                f"<i>{data.get('description', '')}</i>"
            )
        return ""

    def create_full_network(self, output_path: str = None,
                            include_stocks: bool = True,
                            min_stock_score: float = 4.0) -> str:
        """
        创建完整产业链关系网络可视化
        包含：一级方向 → 二级分类 → 三级赛道 → 标的 四层节点
        以及四种关系：供应链 / 竞争 / 协同 / 验证
        """
        if output_path is None:
            output_dir = self._vis_config.get('global', {}).get('output_dir', 'output')
            output_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                output_dir,
                'supply_chain_full.html'
            )

        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        net = Network(
            height='100vh',
            width='100%',
            bgcolor=self._vis_config.get('global', {}).get('background', '#0a0e1a'),
            font_color=self._vis_config.get('global', {}).get('font_color', '#e0e0e0'),
            directed=True,
            notebook=False,
        )

        # 设置物理引擎
        physics = self._vis_config.get('physics', {})
        bh_params = physics.get('barnesHut', {})
        net.barnes_hut(**bh_params)

        # ===== 1. 添加一级方向节点 =====
        directions = self.data.get_directions()
        dir_style = self._vis_config.get('node_styles', {}).get('direction', {})

        for dir_name, direction in directions.items():
            stock_count = sum(
                len(t.stocks) for c in direction.categories for t in c.tracks
            )
            track_count = sum(len(c.tracks) for c in direction.categories)
            color = self._get_direction_color(dir_name)

            net.add_node(
                dir_name,
                label=dir_name,
                shape=dir_style.get('shape', 'diamond'),
                size=dir_style.get('size', 50),
                color={
                    'background': color,
                    'border': '#ffffff',
                    'highlight': {'background': color, 'border': '#ffff00'},
                    'hover': {'background': color, 'border': '#ffffff'},
                },
                borderWidth=dir_style.get('border_width', 3),
                font={
                    'size': dir_style.get('font_size', 18),
                    'color': dir_style.get('font_color', '#ffffff'),
                    'face': 'Microsoft YaHei, Noto Sans SC, sans-serif',
                    'bold': True,
                },
                title=self._make_node_tooltip('direction', {
                    'name': dir_name,
                    'priority': direction.direction_priority,
                    'policy_cycle': direction.policy_cycle,
                    'stock_count': stock_count,
                    'track_count': track_count,
                }),
                group='direction',
                level=0,
            )

        # ===== 2. 添加二级分类节点 =====
        cat_style = self._vis_config.get('node_styles', {}).get('category', {})

        for dir_name, direction in directions.items():
            dir_color = self._get_direction_color(dir_name)
            for cat in direction.categories:
                cat_id = f"cat_{cat.name}"
                stock_count = sum(len(t.stocks) for t in cat.tracks)

                net.add_node(
                    cat_id,
                    label=cat.name,
                    shape=cat_style.get('shape', 'hexagon'),
                    size=cat_style.get('size', 35),
                    color={
                        'background': self._hex_to_rgba(dir_color, 0.7),
                        'border': dir_color,
                        'highlight': {'background': self._hex_to_rgba(dir_color, 0.9), 'border': '#ffff00'},
                    },
                    borderWidth=cat_style.get('border_width', 2),
                    font={
                        'size': cat_style.get('font_size', 14),
                        'color': cat_style.get('font_color', '#ffffff'),
                        'face': 'Microsoft YaHei, Noto Sans SC, sans-serif',
                    },
                    title=f"<b>{cat.name}</b><br>所属方向: {dir_name}<br>标的数量: {stock_count}",
                    group='category',
                    level=1,
                )

                # 方向→分类 边
                net.add_edge(
                    dir_name, cat_id,
                    color={'color': self._hex_to_rgba(dir_color, 0.3)},
                    width=1,
                    arrows={'enabled': False},
                    smooth={'type': 'curvedCCW', 'roundness': 0.1},
                )

        # ===== 3. 添加三级赛道节点（含上中下游标识） =====
        track_style = self._vis_config.get('node_styles', {}).get('track', {})
        chains = self.chain.get_chains()

        for dir_name, chain in chains.items():
            dir_color = self._get_direction_color(dir_name)

            for level in ['upstream', 'midstream', 'downstream']:
                level_color = self._get_level_color(level)
                level_label = self._get_level_label(level)
                nodes = getattr(chain, level)

                for node in nodes:
                    track_id = f"track_{node.name}"
                    # 混合方向色+层级色
                    border_color = level_color

                    # 边框宽度根据标的数量
                    bw = max(1, min(3, node.stock_count // 3))

                    net.add_node(
                        track_id,
                        label=f"[{level_label}]{node.name}",
                        shape=track_style.get('shape', 'dot'),
                        size=track_style.get('size', 25) + node.stock_count,
                        color={
                            'background': self._hex_to_rgba(dir_color, 0.5),
                            'border': border_color,
                            'highlight': {
                                'background': self._hex_to_rgba(dir_color, 0.8),
                                'border': '#ffff00',
                            },
                        },
                        borderWidth=bw,
                        font={
                            'size': track_style.get('font_size', 12),
                            'color': track_style.get('font_color', '#e0e0e0'),
                            'face': 'Microsoft YaHei, Noto Sans SC, sans-serif',
                        },
                        title=self._make_node_tooltip('track', {
                            'name': node.name,
                            'direction': dir_name,
                            'category': node.category,
                            'level': level,
                            'stock_count': node.stock_count,
                            'avg_score': node.avg_score,
                            'independent_value': max(
                                (s.score for s in node.stocks), default=0
                            ) // 1,
                        }),
                        group=f'track_{level}',
                        level=2,
                    )

                    # 分类→赛道 边
                    cat_id = f"cat_{node.category}"
                    net.add_edge(
                        cat_id, track_id,
                        color={'color': self._hex_to_rgba(dir_color, 0.2)},
                        width=0.5,
                        arrows={'enabled': False},
                        smooth={'type': 'curvedCCW', 'roundness': 0.1},
                    )

        # ===== 4. 添加标的节点 =====
        if include_stocks:
            stock_style = self._vis_config.get('node_styles', {}).get('stock', {})
            stocks = self.data.get_stocks()

            for stock_name, stock in stocks.items():
                if stock.score < min_stock_score:
                    continue

                track_id = f"track_{stock.track}"
                dir_color = self._get_direction_color(stock.direction)

                # 规模映射节点大小：大盘/中盘/小盘 明显区分
                size_map = {'大盘': 22, '中盘': 14, '小盘': 8}
                node_size = size_map.get(stock.size_class, 10)
                # 规模映射边框粗细
                bw_map = {'大盘': 2, '中盘': 1, '小盘': 1}
                node_bw = bw_map.get(stock.size_class, 1)

                # 优先级映射颜色亮度
                priority_alpha = 0.3 + 0.14 * stock.priority

                net.add_node(
                    stock_name,
                    label=stock_name,
                    shape='dot',
                    size=node_size,
                    color={
                        'background': self._hex_to_rgba(dir_color, priority_alpha),
                        'border': self._hex_to_rgba(dir_color, 0.8),
                        'highlight': {
                            'background': self._hex_to_rgba(dir_color, 0.9),
                            'border': '#ffff00',
                        },
                    },
                    borderWidth=node_bw,
                    font={
                        'size': stock_style.get('font_size', 9),
                        'color': stock_style.get('font_color', '#b0b0b0'),
                        'face': 'Microsoft YaHei, Noto Sans SC, sans-serif',
                    },
                    title=self._make_node_tooltip('stock', {
                        'name': stock.name,
                        'code': stock.code,
                        'direction': stock.direction,
                        'track': stock.track,
                        'size_class': stock.size_class,
                        'style': stock.style,
                        'score': stock.score,
                        'priority': stock.priority,
                        'suggestion': stock.suggestion,
                        'description': stock.description,
                    }),
                    group='stock',
                    level=3,
                )

                # 赛道→标的 边
                net.add_edge(
                    track_id, stock_name,
                    color={'color': self._hex_to_rgba(dir_color, 0.15)},
                    width=0.3,
                    arrows={'enabled': False},
                    smooth={'type': 'continuous'},
                )

        # ===== 5. 添加四种关系边 =====
        graph = self.relations.get_graph()

        for relation in graph.relations:
            # 确定节点ID
            if relation.source_type == 'track':
                source_id = f"track_{relation.source}"
            else:
                source_id = relation.source

            if relation.target_type == 'track':
                target_id = f"track_{relation.target}"
            else:
                target_id = relation.target

            # 检查节点是否存在
            node_ids = set(net.get_nodes())
            if source_id not in node_ids or target_id not in node_ids:
                continue

            # 获取关系样式
            style = self._get_edge_style(relation.relation_type)

            # 构建边属性
            edge_color = style.get('color', '#888888')
            edge_width = style.get('width', 1.0) * (relation.weight / 10.0 + 0.3)
            arrows_cfg = style.get('arrows', {})
            smooth_cfg = style.get('smooth', {'type': 'continuous'})
            dashes = style.get('dashes', False)

            # 边标签
            edge_label = relation.label if relation.weight >= 7 else ''

            net.add_edge(
                source_id, target_id,
                color={'color': edge_color, 'opacity': min(1.0, relation.weight / 10.0 + 0.2)},
                width=edge_width,
                arrows=arrows_cfg,
                smooth=smooth_cfg,
                dashes=dashes,
                label=edge_label,
                font={
                    'size': 8,
                    'color': edge_color,
                    'face': 'Microsoft YaHei, Noto Sans SC, sans-serif',
                    'align': 'middle',
                    'strokeWidth': 2,
                    'strokeColor': '#0a0e1a',
                },
                title=f"[{self.relations.TYPE_LABELS.get(relation.relation_type, '')}] {relation.label}<br>{relation.description}",
                value=relation.weight,
            )

        # ===== 6. 设置交互选项 =====
        net.show_buttons(filter_=['physics', 'nodes', 'edges'])

        # 保存
        net.save_graph(output_path)

        # ===== 7. 后处理：注入自定义图例和样式 =====
        self._post_process_html(output_path)

        return output_path

    def create_direction_network(self, direction: str, output_path: str = None) -> str:
        """
        创建单个方向的产业链关系网络
        更详细地展示该方向的上中下游和关系
        """
        if output_path is None:
            output_dir = self._vis_config.get('global', {}).get('output_dir', 'output')
            safe_name = direction.replace('/', '_')
            output_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                output_dir,
                f'supply_chain_{safe_name}.html'
            )

        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        net = Network(
            height='100vh',
            width='100%',
            bgcolor=self._vis_config.get('global', {}).get('background', '#0a0e1a'),
            font_color=self._vis_config.get('global', {}).get('font_color', '#e0e0e0'),
            directed=True,
            notebook=False,
        )

        physics = self._vis_config.get('physics', {})
        bh_params = physics.get('barnesHut', {})
        net.barnes_hut(**bh_params)

        chains = self.chain.get_chains()
        chain = chains.get(direction)
        if not chain:
            raise ValueError(f"未找到方向: {direction}")

        dir_color = self._get_direction_color(direction)

        # 添加方向中心节点
        net.add_node(
            direction,
            label=direction,
            shape='diamond',
            size=60,
            color={'background': dir_color, 'border': '#ffffff'},
            borderWidth=3,
            font={'size': 20, 'color': '#ffffff', 'face': 'Microsoft YaHei, Noto Sans SC, sans-serif', 'bold': True},
            title=f"<b>{direction}</b><br>共{chain.total_stocks}只标的",
            group='direction',
        )

        # 添加上中下游层级节点
        level_labels = {'upstream': '上游', 'midstream': '中游', 'downstream': '下游'}
        level_positions = {'upstream': -300, 'midstream': 0, 'downstream': 300}

        for level in ['upstream', 'midstream', 'downstream']:
            level_color = self._get_level_color(level)
            level_label = level_labels[level]
            level_id = f"level_{level}"

            net.add_node(
                level_id,
                label=level_label,
                shape='box',
                size=40,
                color={'background': self._hex_to_rgba(level_color, 0.3), 'border': level_color},
                borderWidth=2,
                font={'size': 16, 'color': level_color, 'face': 'Microsoft YaHei, Noto Sans SC, sans-serif', 'bold': True},
                group='level',
            )

            net.add_edge(
                direction, level_id,
                color={'color': self._hex_to_rgba(level_color, 0.4)},
                width=2,
                arrows={'enabled': True, 'scale_factor': 0.5},
            )

        # 添加赛道节点
        nodes = chain.all_nodes
        for node in nodes:
            track_id = f"track_{node.name}"
            level_color = self._get_level_color(node.level)

            net.add_node(
                track_id,
                label=node.name,
                shape='dot',
                size=20 + node.stock_count * 2,
                color={
                    'background': self._hex_to_rgba(dir_color, 0.5),
                    'border': level_color,
                },
                borderWidth=2,
                font={'size': 14, 'color': '#e0e0e0', 'face': 'Microsoft YaHei, Noto Sans SC, sans-serif'},
                title=self._make_node_tooltip('track', {
                    'name': node.name,
                    'direction': direction,
                    'category': node.category,
                    'level': node.level,
                    'stock_count': node.stock_count,
                    'avg_score': node.avg_score,
                }),
                group=f'track_{node.level}',
            )

            level_id = f"level_{node.level}"
            net.add_edge(
                level_id, track_id,
                color={'color': self._hex_to_rgba(level_color, 0.3)},
                width=1,
                arrows={'enabled': False},
            )

        # 添加标的节点
        stocks = self.data.get_stocks()
        for node in nodes:
            for stock in node.stocks:
                track_id = f"track_{node.name}"

                # 规模映射节点大小：大盘/中盘/小盘 明显区分
                dir_size_map = {'大盘': 26, '中盘': 16, '小盘': 9}
                dir_size = dir_size_map.get(stock.size_class, 12)
                dir_bw_map = {'大盘': 2, '中盘': 1, '小盘': 1}
                dir_bw = dir_bw_map.get(stock.size_class, 1)

                net.add_node(
                    stock.name,
                    label=stock.name,
                    shape='dot',
                    size=dir_size,
                    color={
                        'background': self._hex_to_rgba(dir_color, 0.4 + 0.1 * stock.priority),
                        'border': self._hex_to_rgba(dir_color, 0.8),
                    },
                    borderWidth=dir_bw,
                    font={'size': 10, 'color': '#c0c0c0', 'face': 'Microsoft YaHei, Noto Sans SC, sans-serif'},
                    title=self._make_node_tooltip('stock', {
                        'name': stock.name,
                        'code': stock.code,
                        'direction': stock.direction,
                        'track': stock.track,
                        'size_class': stock.size_class,
                        'style': stock.style,
                        'score': stock.score,
                        'priority': stock.priority,
                        'suggestion': stock.suggestion,
                        'description': stock.description,
                    }),
                    group='stock',
                )

                net.add_edge(
                    track_id, stock.name,
                    color={'color': self._hex_to_rgba(dir_color, 0.15)},
                    width=0.5,
                    arrows={'enabled': False},
                )

        # 添加关系边
        graph = self.relations.get_graph()
        for relation in graph.relations:
            source_id = f"track_{relation.source}" if relation.source_type == 'track' else relation.source
            target_id = f"track_{relation.target}" if relation.target_type == 'track' else relation.target

            # 只展示与当前方向相关的关系
            all_track_names = set(n.name for n in nodes)
            all_stock_names = set(s.name for n in nodes for s in n.stocks)

            source_in = (relation.source in all_track_names or relation.source in all_stock_names)
            target_in = (relation.target in all_track_names or relation.target in all_stock_names)

            if not (source_in or target_in):
                continue

            node_ids = set(net.get_nodes())
            if source_id not in node_ids or target_id not in node_ids:
                continue

            style = self._get_edge_style(relation.relation_type)
            edge_color = style.get('color', '#888888')

            net.add_edge(
                source_id, target_id,
                color={'color': edge_color, 'opacity': 0.7},
                width=style.get('width', 1.5),
                arrows=style.get('arrows', {'enabled': True}),
                smooth=style.get('smooth', {'type': 'curvedCCW', 'roundness': 0.2}),
                dashes=style.get('dashes', False),
                label=relation.label if relation.weight >= 6 else '',
                font={
                    'size': 9,
                    'color': edge_color,
                    'face': 'Microsoft YaHei, Noto Sans SC, sans-serif',
                    'strokeWidth': 2,
                    'strokeColor': '#0a0e1a',
                },
                title=f"[{self.relations.TYPE_LABELS.get(relation.relation_type, '')}] {relation.description}",
            )

        net.save_graph(output_path)

        # 后处理：注入图例和样式
        self._post_process_html(output_path)

        return output_path

    def _inject_legend(self, net: Network) -> None:
        """注入自定义HTML图例"""
        direction_colors = self._vis_config.get('direction_colors', {})
        level_colors = self._vis_config.get('chain_level_colors', {})
        edge_styles = self._vis_config.get('edge_styles', {})

        # 构建图例HTML
        legend_html = """
        <div id="custom-legend" style="
            position: absolute; top: 10px; left: 10px; z-index: 1000;
            background: rgba(10,14,26,0.92); border: 1px solid #333;
            border-radius: 8px; padding: 12px; font-size: 12px;
            color: #e0e0e0; max-height: 90vh; overflow-y: auto;
            font-family: 'Microsoft YaHei', 'Noto Sans SC', sans-serif;
            box-shadow: 0 4px 20px rgba(0,0,0,0.5);
        ">
            <div style="font-size:14px;font-weight:bold;margin-bottom:8px;border-bottom:1px solid #444;padding-bottom:6px;">
                十大投资方向 · 产业链图谱
            </div>
        """

        # 方向颜色图例
        legend_html += '<div style="margin-bottom:6px;font-weight:bold;">一级方向</div>'
        for name, color in direction_colors.items():
            legend_html += f'<div style="margin:2px 0;"><span style="display:inline-block;width:12px;height:12px;background:{color};border-radius:2px;margin-right:6px;vertical-align:middle;"></span>{name}</div>'

        # 产业链层级图例
        legend_html += '<div style="margin-top:8px;margin-bottom:6px;font-weight:bold;">产业链层级</div>'
        level_labels = {'upstream': '上游（原材料/基础供给）', 'midstream': '中游（制造/集成/平台）', 'downstream': '下游（应用/终端/服务）'}
        for level, color in level_colors.items():
            label = level_labels.get(level, level)
            legend_html += f'<div style="margin:2px 0;"><span style="display:inline-block;width:12px;height:12px;background:{color};border-radius:50%;margin-right:6px;vertical-align:middle;"></span>{label}</div>'

        # 关系类型图例
        legend_html += '<div style="margin-top:8px;margin-bottom:6px;font-weight:bold;">关系类型</div>'
        rel_type_info = {
            'supply_chain': ('供应链', '#3498db', '━━▶'),
            'competition': ('竞争', '#e74c3c', '- - ↔'),
            'synergy': ('协同', '#2ecc71', '━━▶'),
            'validation': ('验证', '#f39c12', '-·- ▶'),
        }
        for rt, (label, color, symbol) in rel_type_info.items():
            legend_html += f'<div style="margin:2px 0;"><span style="color:{color};margin-right:6px;font-weight:bold;">{symbol}</span><span style="color:{color};">{label}</span></div>'

        # 节点形状图例
        legend_html += '<div style="margin-top:8px;margin-bottom:6px;font-weight:bold;">节点形状</div>'
        legend_html += '<div style="margin:2px 0;">◆ 一级方向</div>'
        legend_html += '<div style="margin:2px 0;">⬡ 二级分类</div>'
        legend_html += '<div style="margin:2px 0;">● 赛道（含上中下游标识）</div>'
        # 标的规模图例
        legend_html += '<div style="margin-top:8px;margin-bottom:6px;font-weight:bold;">标的规模（节点大小）</div>'
        legend_html += '<div style="margin:2px 0;display:flex;align-items:center;"><span style="display:inline-block;width:18px;height:18px;background:rgba(100,140,200,0.5);border:2px solid rgba(100,140,200,0.8);border-radius:50%;margin-right:8px;"></span>大盘</div>'
        legend_html += '<div style="margin:2px 0;display:flex;align-items:center;"><span style="display:inline-block;width:12px;height:12px;background:rgba(100,140,200,0.5);border:1px solid rgba(100,140,200,0.8);border-radius:50%;margin-right:8px;"></span>中盘</div>'
        legend_html += '<div style="margin:2px 0;display:flex;align-items:center;"><span style="display:inline-block;width:7px;height:7px;background:rgba(100,140,200,0.5);border:1px solid rgba(100,140,200,0.8);border-radius:50%;margin-right:8px;"></span>小盘</div>'

        legend_html += """
            <div style="margin-top:10px;font-size:10px;color:#888;border-top:1px solid #333;padding-top:6px;">
                交互：滚轮缩放 · 拖拽移动 · 悬停查看详情<br>
                点击节点高亮关联 · 右侧面板调整参数
            </div>
        </div>
        """

        # 注入到网络（已废弃，由_post_process_html替代）
        net.html = net.html.replace('</body>', f'{legend_html}</body>')

    def _inject_custom_css(self, net: Network) -> None:
        """注入自定义CSS样式"""
        custom_css = """
        <style>
            body {
                margin: 0;
                padding: 0;
                overflow: hidden;
                font-family: 'Microsoft YaHei', 'Noto Sans SC', sans-serif;
            }
            #mynetwork {
                width: 100vw;
                height: 100vh;
                border: none;
            }
            .vis-tooltip {
                background: rgba(10,14,26,0.95) !important;
                color: #e0e0e0 !important;
                border: 1px solid #444 !important;
                border-radius: 6px !important;
                padding: 10px !important;
                font-size: 12px !important;
                font-family: 'Microsoft YaHei', 'Noto Sans SC', sans-serif !important;
                max-width: 350px !important;
                box-shadow: 0 4px 15px rgba(0,0,0,0.5) !important;
            }
            .vis-tooltip b {
                color: #fff;
                font-size: 14px;
            }
            .vis-tooltip i {
                color: #aaa;
                font-size: 11px;
            }
        </style>
        """
        net.html = net.html.replace('</head>', f'{custom_css}</head>')

    def _post_process_html(self, filepath: str) -> None:
        """后处理已保存的HTML文件，注入图例、自定义CSS和HTML tooltip修复"""
        with open(filepath, 'r', encoding='utf-8') as f:
            html = f.read()

        # 注入自定义CSS
        custom_css = """
        <style>
            body {
                margin: 0;
                padding: 0;
                overflow: hidden;
                font-family: 'Microsoft YaHei', 'Noto Sans SC', sans-serif;
            }
            #mynetwork {
                width: 100vw;
                height: 100vh;
                border: none;
            }
            .vis-tooltip {
                background: rgba(10,14,26,0.95) !important;
                color: #e0e0e0 !important;
                border: 1px solid #444 !important;
                border-radius: 6px !important;
                padding: 10px !important;
                font-size: 12px !important;
                font-family: 'Microsoft YaHei', 'Noto Sans SC', sans-serif !important;
                max-width: 400px !important;
                box-shadow: 0 4px 15px rgba(0,0,0,0.5) !important;
                line-height: 1.6 !important;
            }
            .vis-tooltip b {
                color: #ffffff;
                font-size: 14px;
            }
            .vis-tooltip i {
                color: #aaaaaa;
                font-size: 11px;
            }
            .vis-tooltip .tt-row {
                margin: 1px 0;
            }
            .vis-tooltip .tt-label {
                color: #8899aa;
            }
            .vis-tooltip .tt-val {
                color: #e0e0e0;
            }
            .vis-tooltip .tt-divider {
                border-top: 1px solid #333;
                margin: 4px 0;
            }
        </style>
        """
        html = html.replace('</head>', f'{custom_css}</head>')

        # 注入tooltip修复JS：通过hook network的hoverNode事件 + 监听tooltip DOM变化
        # 核心问题：vis.js每次hover都设置tooltip.textContent，不会触发innerHTML
        # 方案：监听tooltip元素的characterData/childList变化，自动将textContent转innerHTML
        tooltip_fix_js = """
        <script>
        (function() {
            // 全局tooltip修复函数
            function fixTooltip() {
                var tooltip = document.querySelector('.vis-tooltip');
                if (!tooltip) return;
                var raw = tooltip.textContent || '';
                // 检测是否包含HTML标签（说明vis.js把它当纯文本设入了）
                if (raw.indexOf('<') !== -1 && raw.indexOf('>') !== -1) {
                    tooltip.innerHTML = raw;
                }
            }

            // 方案1：对tooltip元素本身做MutationObserver（监听后续textContent变化）
            var tooltipObsSetup = false;
            function setupTooltipObserver() {
                if (tooltipObsSetup) return;
                var tooltip = document.querySelector('.vis-tooltip');
                if (!tooltip) return;
                tooltipObsSetup = true;
                var obs = new MutationObserver(function() {
                    // vis.js更新textContent后会触发，转成innerHTML
                    fixTooltip();
                });
                obs.observe(tooltip, { childList: true, characterData: true, subtree: true });
            }

            // 方案2：首次创建tooltip时捕获（body级Observer）
            var bodyObs = new MutationObserver(function(mutations) {
                for (var i = 0; i < mutations.length; i++) {
                    for (var j = 0; j < mutations[i].addedNodes.length; j++) {
                        var node = mutations[i].addedNodes[j];
                        if (node.classList && node.classList.contains('vis-tooltip')) {
                            fixTooltip();
                            setupTooltipObserver();
                            return;
                        }
                    }
                }
            });
            bodyObs.observe(document.body, { childList: true, subtree: true });

            // 方案3：mousemove兜底 — 确保每次鼠标移动后tooltip都是HTML渲染
            var _fixTimer = null;
            document.getElementById('mynetwork').addEventListener('mousemove', function() {
                if (_fixTimer) clearTimeout(_fixTimer);
                _fixTimer = setTimeout(function() {
                    setupTooltipObserver();
                    fixTooltip();
                }, 8);
            });

            // 方案4：在network创建后绑定hoverNode事件
            function hookNetworkEvents() {
                var container = document.getElementById('mynetwork');
                // vis-network实例挂载在container上或通过vis全局
                var net = container._network || (window.network);
                if (!net) {
                    // 尝试从vis.Network已创建的实例获取
                    // pyvis会在drawGraph()里创建network但不暴露给全局
                    // 所以用DOM方式更可靠
                    return;
                }
                net.on('hoverNode', function() {
                    setTimeout(fixTooltip, 5);
                    setTimeout(setupTooltipObserver, 5);
                });
                net.on('hoverEdge', function() {
                    setTimeout(fixTooltip, 5);
                });
            }
            // 延迟hook，等network创建完成
            setTimeout(hookNetworkEvents, 1000);
            setTimeout(hookNetworkEvents, 3000);
        })();
        </script>
        """

        # 在 </body> 前注入tooltip修复JS
        html = html.replace('</body>', f'{tooltip_fix_js}</body>')

        # 注入图例
        direction_colors = self._vis_config.get('direction_colors', {})
        level_colors = self._vis_config.get('chain_level_colors', {})

        legend_html = """
        <div id="custom-legend" style="
            position: absolute; top: 10px; left: 10px; z-index: 1000;
            background: rgba(10,14,26,0.92); border: 1px solid #333;
            border-radius: 8px; padding: 12px; font-size: 12px;
            color: #e0e0e0; max-height: 90vh; overflow-y: auto;
            font-family: 'Microsoft YaHei', 'Noto Sans SC', sans-serif;
            box-shadow: 0 4px 20px rgba(0,0,0,0.5);
        ">
            <div style="font-size:14px;font-weight:bold;margin-bottom:8px;border-bottom:1px solid #444;padding-bottom:6px;">
                十大投资方向 · 产业链图谱
            </div>
        """

        legend_html += '<div style="margin-bottom:6px;font-weight:bold;">一级方向</div>'
        for name, color in direction_colors.items():
            legend_html += f'<div style="margin:2px 0;"><span style="display:inline-block;width:12px;height:12px;background:{color};border-radius:2px;margin-right:6px;vertical-align:middle;"></span>{name}</div>'

        legend_html += '<div style="margin-top:8px;margin-bottom:6px;font-weight:bold;">产业链层级</div>'
        level_labels = {'upstream': '上游（原材料/基础供给）', 'midstream': '中游（制造/集成/平台）', 'downstream': '下游（应用/终端/服务）'}
        for level, color in level_colors.items():
            label = level_labels.get(level, level)
            legend_html += f'<div style="margin:2px 0;"><span style="display:inline-block;width:12px;height:12px;background:{color};border-radius:50%;margin-right:6px;vertical-align:middle;"></span>{label}</div>'

        legend_html += '<div style="margin-top:8px;margin-bottom:6px;font-weight:bold;">关系类型</div>'
        rel_type_info = {
            'supply_chain': ('供应链', '#3498db', '━━▶'),
            'competition': ('竞争', '#e74c3c', '- - ↔'),
            'synergy': ('协同', '#2ecc71', '━━▶'),
            'validation': ('验证', '#f39c12', '-·- ▶'),
        }
        for rt, (label, color, symbol) in rel_type_info.items():
            legend_html += f'<div style="margin:2px 0;"><span style="color:{color};margin-right:6px;font-weight:bold;">{symbol}</span><span style="color:{color};">{label}</span></div>'

        legend_html += '<div style="margin-top:8px;margin-bottom:6px;font-weight:bold;">节点形状</div>'
        legend_html += '<div style="margin:2px 0;">◆ 一级方向</div>'
        legend_html += '<div style="margin:2px 0;">⬡ 二级分类</div>'
        legend_html += '<div style="margin:2px 0;">● 赛道（含上中下游标识）</div>'
        # 标的规模图例 — 用不同大小的圆直观展示
        legend_html += '<div style="margin-top:8px;margin-bottom:6px;font-weight:bold;">标的规模（节点大小）</div>'
        legend_html += '<div style="margin:2px 0;display:flex;align-items:center;"><span style="display:inline-block;width:18px;height:18px;background:rgba(100,140,200,0.5);border:2px solid rgba(100,140,200,0.8);border-radius:50%;margin-right:8px;flex-shrink:0;"></span>大盘</div>'
        legend_html += '<div style="margin:2px 0;display:flex;align-items:center;"><span style="display:inline-block;width:12px;height:12px;background:rgba(100,140,200,0.5);border:1px solid rgba(100,140,200,0.8);border-radius:50%;margin-right:8px;flex-shrink:0;"></span>中盘</div>'
        legend_html += '<div style="margin:2px 0;display:flex;align-items:center;"><span style="display:inline-block;width:7px;height:7px;background:rgba(100,140,200,0.5);border:1px solid rgba(100,140,200,0.8);border-radius:50%;margin-right:8px;flex-shrink:0;"></span>小盘</div>'

        legend_html += """
            <div style="margin-top:10px;font-size:10px;color:#888;border-top:1px solid #333;padding-top:6px;">
                交互：滚轮缩放 · 拖拽移动 · 悬停查看详情<br>
                点击节点高亮关联 · 右侧面板调整参数
            </div>
        </div>
        """

        html = html.replace('</body>', f'{legend_html}</body>')

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html)

    def generate_all(self, include_stocks: bool = True) -> Dict[str, str]:
        """生成所有可视化文件"""
        results = {}

        # 全景图
        print("[可视化] 生成全景产业链图...")
        results['full'] = self.create_full_network(include_stocks=include_stocks)
        print(f"  → 已保存: {results['full']}")

        # 各方向独立图
        directions = self.data.get_directions()
        for dir_name in directions:
            print(f"[可视化] 生成 {dir_name} 方向产业链图...")
            try:
                results[dir_name] = self.create_direction_network(dir_name)
                print(f"  → 已保存: {results[dir_name]}")
            except Exception as e:
                print(f"  ✗ {dir_name} 生成失败: {e}")

        return results