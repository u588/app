#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Plotly专业可视化模块
支持：力导向布局/分层布局/交互筛选/中文悬浮
"""

import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots
import networkx as nx
from typing import List, Dict, Optional
import yaml
import json
from pathlib import Path

# 注册中文字体支持
pio.templates.default = "plotly_white"

class ChainVisualizer:
    """产业链图谱专业可视化器"""
    
    def __init__(self, config_path: str):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        self.viz_config = self.config['visualization']
        
    def create_network_graph(
        self, 
        nodes: List[Dict], 
        edges: List[Dict],
        layout_type: str = 'force_atlas2'
    ) -> go.Figure:
        """创建交互式网络图谱"""
        
        # 构建NetworkX图用于布局计算
        G = nx.DiGraph()
        
        # 添加节点
        node_positions = {}
        for node in nodes:
            G.add_node(node['id'])
            # 初始位置：按层级分层
            if 'level' in node:
                node_positions[node['id']] = (
                    hash(node['label']) % 100 - 50,  # x
                    -node['level'] * 150              # y: 层级越高越靠上
                )
        
        # 添加边
        for edge in edges:
            G.add_edge(edge['source'], edge['target'], 
                      weight=edge.get('weight', 1.0),
                      type=edge['type'])
        
        # 计算布局
        if layout_type == 'force_atlas2':
            pos = self._force_atlas2_layout(G, node_positions)
        elif layout_type == 'hierarchical':
            pos = nx.drawing.nx_agraph.graphviz_layout(G, prog='dot')
        else:
            pos = nx.spring_layout(G, k=2, iterations=50, seed=42)
        
        # 构建Plotly节点trace
        node_trace = self._build_node_trace(nodes, pos)
        
        # 构建边trace（按类型分组）
        edge_traces = self._build_edge_traces(edges, pos)
        
        # 创建主图
        fig = go.Figure(
            data=[node_trace] + edge_traces,
            layout=self._build_layout()
        )
        
        # 添加交互控件
        fig = self._add_interactive_controls(fig, nodes, edges)
        
        return fig
    
    def _force_atlas2_layout(self, G: nx.Graph, init_pos: Dict) -> Dict:
        """简化版ForceAtlas2力导向布局"""
        pos = init_pos.copy()
        nodes = list(G.nodes())
        
        # 迭代优化位置
        for _ in range(50):
            displacements = {n: [0, 0] for n in nodes}
            
            # 排斥力：节点间相互排斥
            for i, n1 in enumerate(nodes):
                for n2 in nodes[i+1:]:
                    dx = pos[n1][0] - pos[n2][0]
                    dy = pos[n1][1] - pos[n2][1]
                    dist = max((dx**2 + dy**2)**0.5, 1)
                    force = 100 / (dist ** 2)
                    displacements[n1][0] += dx / dist * force
                    displacements[n1][1] += dy / dist * force
                    displacements[n2][0] -= dx / dist * force
                    displacements[n2][1] -= dy / dist * force
            
            # 吸引力：边连接节点相互吸引
            for n1, n2 in G.edges():
                dx = pos[n2][0] - pos[n1][0]
                dy = pos[n2][1] - pos[n1][1]
                dist = max((dx**2 + dy**2)**0.5, 1)
                force = dist * 0.01 * G[n1][n2].get('weight', 1)
                displacements[n1][0] += dx / dist * force
                displacements[n1][1] += dy / dist * force
                displacements[n2][0] -= dx / dist * force
                displacements[n2][1] -= dy / dist * force
            
            # 更新位置
            for n in nodes:
                pos[n] = (
                    pos[n][0] + displacements[n][0] * 0.1,
                    pos[n][1] + displacements[n][1] * 0.1
                )
        
        return pos
    
    def _build_node_trace(self, nodes: List[Dict], pos: Dict) -> go.Scatter:
        """构建节点散点轨迹"""
        x, y, text, sizes, colors, custom_data = [], [], [], [], [], []
        
        for node in nodes:
            nid = node['id']
            if nid in pos:
                x.append(pos[nid][0])
                y.append(pos[nid][1])
                text.append(node['label'])
                sizes.append(node.get('size', 20))
                colors.append(node.get('color', '#3498db'))
                custom_data.append([
                    node.get('code', ''),
                    node.get('market_cap', ''),
                    node.get('score', 0),
                    node.get('hover_text', '')
                ])
        
        return go.Scatter(
            x=x, y=y,
            mode='markers+text',
            marker=dict(
                size=sizes,
                color=colors,
                line=dict(width=2, color='white'),
                opacity=0.9
            ),
            text=text,
            textposition="bottom center",
            textfont=dict(
                family=self.viz_config['font_family'],
                size=self.viz_config['node_label_font_size'],
                color='#2c3e50'
            ),
            customdata=custom_data,
            hovertemplate=(
                "<b>%{text}</b><br>"
                "代码: %{customdata[0]}<br>"
                "市值: %{customdata[1]}<br>"
                "评分: %{customdata[2]:.1f}<br>"
                "%{customdata[3]}<extra></extra>"
            ),
            name='标的公司',
            hoverlabel=dict(
                bgcolor='white',
                font_size=12,
                font_family=self.viz_config['font_family']
            )
        )
    
    def _build_edge_traces(self, edges: List[Dict], pos: Dict) -> List[go.Scatter]:
        """按关系类型分组构建边轨迹"""
        traces = []
        edge_groups = {}
        
        # 按关系类型分组
        for edge in edges:
            etype = edge['type']
            if etype not in edge_groups:
                edge_groups[etype] = {'x': [], 'y': [], 'text': []}
                
            src, tgt = edge['source'], edge['target']
            if src in pos and tgt in pos:
                x0, y0 = pos[src]
                x1, y1 = pos[tgt]
                # 使用 None 断点实现多段线合并绘制，提升渲染性能
                edge_groups[etype]['x'].extend([x0, x1, None])
                edge_groups[etype]['y'].extend([y0, y1, None])
                edge_groups[etype]['text'].append(edge['hover_text'])
                
        # 关系类型中文字典
        type_names = {
            'supply_chain': '🔗 供应链',
            'competition': '⚔️ 竞争',
            'synergy': '🤝 协同',
            'validation': '✅ 验证',
            'hierarchy': '📁 归属'
        }
        
        for etype, data in edge_groups.items():
            config = self.config['relationship_rules'].get(etype, {})
            traces.append(go.Scatter(
                x=data['x'], y=data['y'],
                mode='lines',
                line=dict(
                    color=config.get('color', '#95a5a6'),
                    width=config.get('width', 1),
                    dash=config.get('dash', 'solid')
                    # ✅ 已移除 line 内部的 opacity
                ),
                opacity=self.viz_config.get('edge_alpha', 0.6), # ✅ 移至 trace 顶层
                hovertext=data['text'],
                hoverinfo='text',
                name=type_names.get(etype, etype),
                showlegend=True
            ))
        return traces
    
    def _build_layout(self) -> go.Layout:
        """构建专业图表布局"""
        return go.Layout(
            title=dict(
                text=self.config['system']['name'],
                font=dict(
                    family=self.viz_config['font_family'],
                    size=self.viz_config['title_font_size'],
                    color='#2c3e50'
                ),
                x=0.5, xanchor='center'
            ),
            width=self.viz_config['width'],
            height=self.viz_config['height'],
            showlegend=self.viz_config['show_legend'],
            legend=dict(
                orientation='h',
                yanchor='bottom',
                y=0.02,
                xanchor='center',
                x=0.5,
                font=dict(family=self.viz_config['font_family'], size=10)
            ),
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            plot_bgcolor='white',
            paper_bgcolor='white',
            hovermode='closest',
            dragmode='pan'
        )
    
    def _add_interactive_controls(self, fig: go.Figure, nodes, edges) -> go.Figure:
        """添加筛选/搜索/导出等交互控件"""
        # 添加关系类型筛选下拉框
        fig.update_layout(
            updatemenus=[
                dict(
                    buttons=[
                        dict(
                            args=[{'visible': [True] * len(fig.data)}],
                            label="显示全部",
                            method="restyle"
                        ),
                        dict(
                            args=[{'visible': [True] + [False] * (len(fig.data)-1)}],
                            label="仅标的",
                            method="restyle"
                        ),
                        dict(
                            args=[{'visible': [True, True] + [False] * (len(fig.data)-2)}],
                            label="标的+供应链",
                            method="restyle"
                        )
                    ],
                    direction="down",
                    pad={"r": 10, "t": 10},
                    showactive=True,
                    x=0.15, xanchor="left", y=1.15, yanchor="top"
                )
            ]
        )
        return fig
    
    def save_figure(self, fig: go.Figure, output_path: str, format='html'):
        """保存可视化结果"""
        output_dir = Path(self.config['system']['root_dir']) / self.config['system']['output_dir']
        output_dir.mkdir(parents=True, exist_ok=True)
        
        save_path = output_dir / f"{output_path}.{format}"
        
        if format == 'html':
            fig.write_html(save_path, include_plotlyjs='cdn')
        elif format == 'png':
            fig.write_image(save_path, width=1920, height=1200, scale=2)
        elif format == 'json':
            json_data = fig.to_plotly_json()
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 图谱已保存: {save_path}")
        return save_path