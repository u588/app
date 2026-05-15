"""
网络图构建模块
负责将分析结果转换为pyvis网络图
"""

from typing import Dict, List, Optional, Set
from pyvis.network import Network
from .style_manager import StyleManager


class NetworkBuilder:
    """网络图构建器"""

    def __init__(self, style_manager: StyleManager):
        """
        初始化网络图构建器

        Args:
            style_manager: 样式管理器
        """
        self.style = style_manager
        self._added_nodes: Set[str] = set()  # 防止重复添加节点
        self._added_edges: Set[str] = set()  # 防止重复添加边

    def build_full_network(
        self,
        targets: List[Dict],
        chain_structures: Dict,
        all_edges: Dict[str, List],
        expanded_relations: List,
        relation_types: Optional[List[str]] = None,
        industries: Optional[List[str]] = None,
    ) -> Network:
        """
        构建完整的产业链关系网络图

        Args:
            targets: 标的数据列表
            chain_structures: 产业链结构
            all_edges: 所有关系边
            expanded_relations: 扩充关系列表
            relation_types: 要展示的关系类型过滤
            industries: 要展示的行业过滤

        Returns:
            pyvis Network对象
        """
        global_config = self.style.get_global_config()
        net = Network(
            height=global_config.get('height', '900px'),
            width=global_config.get('width', '100%'),
            bgcolor=global_config.get('background', '#0a0e27'),
            font_color='#E0E0E0',
            directed=global_config.get('directed', True),
            notebook=global_config.get('notebook', True),
            cdn_resources='remote',
        )

        self._added_nodes = set()
        self._added_edges = set()

        # 过滤行业
        filtered_targets = targets
        if industries:
            filtered_targets = [t for t in targets if t['一级方向'] in industries]

        # 过滤关系类型
        active_types = relation_types or ['supply_chain', 'competition', 'collaboration', 'verification']

        # 1. 添加标的节点
        self._add_target_nodes(net, filtered_targets, chain_structures)

        # 2. 添加行业分组节点
        self._add_industry_group_nodes(net, filtered_targets)

        # 3. 添加关系边
        for rtype in active_types:
            edges = all_edges.get(rtype, [])
            self._add_edges(net, edges, rtype, industries)

        # 4. 添加扩充关系边
        for r in expanded_relations:
            if r.relation_type in active_types:
                if industries:
                    src_target = self._get_target_by_uid(targets, r.source_uid)
                    if src_target and src_target['一级方向'] not in industries:
                        continue
                self._add_single_edge(
                    net, r.source_uid, r.target_uid,
                    r.relation_type, r.label, r.weight, r.description
                )

        # 5. 配置物理引擎
        physics = self.style.get_physics_config()
        if physics.get('enabled', True):
            bh = physics.get('barnesHut', {})
            net.barnes_hut(
                gravity=bh.get('gravitationalConstant', -8000),
                central_gravity=bh.get('centralGravity', 0.3),
                spring_length=bh.get('springLength', 200),
                spring_strength=bh.get('springConstant', 0.04),
                damping=bh.get('damping', 0.09),
                overlap=bh.get('avoidOverlap', 0.5),
            )

        # 6. 添加交互控件
        interaction = self.style.get_interaction_config()
        if interaction.get('navigation_buttons', True):
            net.show_buttons(filter_=['physics', 'nodes', 'edges'])

        return net

    def build_industry_network(
        self,
        industry: str,
        targets: List[Dict],
        chain_structures: Dict,
        all_edges: Dict[str, List],
        expanded_relations: List,
    ) -> Network:
        """
        构建单个行业的产业链网络图

        Args:
            industry: 一级方向名称
            targets: 标的数据列表
            chain_structures: 产业链结构
            all_edges: 所有关系边
            expanded_relations: 扩充关系列表

        Returns:
            pyvis Network对象
        """
        return self.build_full_network(
            targets=targets,
            chain_structures=chain_structures,
            all_edges=all_edges,
            expanded_relations=expanded_relations,
            industries=[industry],
        )

    def build_relationship_network(
        self,
        relation_type: str,
        targets: List[Dict],
        chain_structures: Dict,
        all_edges: Dict[str, List],
        expanded_relations: List,
    ) -> Network:
        """
        构建单类关系的网络图

        Args:
            relation_type: 关系类型
            targets: 标的数据列表
            chain_structures: 产业链结构
            all_edges: 所有关系边
            expanded_relations: 扩充关系列表

        Returns:
            pyvis Network对象
        """
        return self.build_full_network(
            targets=targets,
            chain_structures=chain_structures,
            all_edges=all_edges,
            expanded_relations=expanded_relations,
            relation_types=[relation_type],
        )

    def _add_target_nodes(
        self,
        net: Network,
        targets: List[Dict],
        chain_structures: Dict,
    ):
        """添加标的节点"""
        # 构建uid→level映射
        level_map = {}
        for industry_name, structure in chain_structures.items():
            for node in structure.all_nodes:
                for t in node.targets:
                    level_map[t['uid']] = node.level

        for target in targets:
            uid = target['uid']
            if uid in self._added_nodes:
                continue

            chain_level = level_map.get(uid, 'midstream')
            node_style = self.style.get_node_style(
                industry=target['一级方向'],
                chain_level=chain_level,
                market_cap=target['市值规模'],
                target_name=target['标的名称'],
                code=target['代码'],
                description=target.get('入选说明', ''),
                policy_score=target.get('政策契合度', 0),
                certainty_score=target.get('投资确定性', 0),
                score=target.get('综合评分', 0.0),
                target_priority=target.get('标的优先级', 0),
                config_advice=target.get('配置建议', ''),
                invest_style=target.get('投资风格', ''),
                core_ratio=target.get('核心业务占比', 0),
                category=target.get('二级分类', ''),
                track=target.get('三级赛道', ''),
                track_priority=target.get('赛道优先级', ''),
                policy_cycle=target.get('政策周期', ''),
            )

            net.add_node(
                uid,
                label=node_style.pop('label'),
                title=node_style.pop('title'),
                **node_style,
            )
            self._added_nodes.add(uid)

    def _add_industry_group_nodes(self, net: Network, targets: List[Dict]):
        """添加行业分组虚拟节点（用于视觉分组）"""
        industries_seen = set()
        for t in targets:
            industry = t['一级方向']
            if industry in industries_seen:
                continue
            industries_seen.add(industry)

            colors = self.style.get_industry_color(industry)
            group_id = f"group_{industry}"

            net.add_node(
                group_id,
                label=industry,
                color={
                    'background': colors['primary'],
                    'border': colors['border'],
                    'highlight': {'background': colors['highlight'], 'border': colors['border']},
                },
                size=50,
                shape='text',
                font={
                    'size': 18,
                    'color': colors['primary'],
                    'face': 'Microsoft YaHei, Noto Sans SC, sans-serif',
                    'strokeWidth': 4,
                    'strokeColor': '#0a0e27',
                    'bold': True,
                },
                level=0,
                fixed=True,
                physics=False,
            )
            self._added_nodes.add(group_id)

    def _add_edges(
        self,
        net: Network,
        edges: List,
        relation_type: str,
        industries: Optional[List[str]] = None,
    ):
        """添加关系边"""
        edge_style = self.style.get_edge_style(relation_type)

        for edge in edges:
            # 行业过滤
            if industries:
                src_target = self._get_target_by_uid_from_edge(edge, 'source_uid')
                if src_target and src_target['一级方向'] not in industries:
                    continue

            # 确保节点存在
            if edge.source_uid not in self._added_nodes or edge.target_uid not in self._added_nodes:
                continue

            self._add_single_edge(
                net, edge.source_uid, edge.target_uid,
                relation_type, edge.label, edge.weight, edge.description,
                edge_style,
            )

    def _add_single_edge(
        self,
        net: Network,
        source_uid: str,
        target_uid: str,
        relation_type: str,
        label: str,
        weight: int,
        description: str,
        edge_style: Optional[Dict] = None,
    ):
        """添加单条边"""
        edge_id = f"{source_uid}--{relation_type}--{target_uid}"
        if edge_id in self._added_edges:
            return

        if edge_style is None:
            edge_style = self.style.get_edge_style(relation_type)

        # 边宽根据权重调整
        adjusted_width = edge_style.get('width', 2) * (weight / 3)

        # 构建悬停提示
        type_labels = {
            'supply_chain': '供应链',
            'competition': '竞争',
            'collaboration': '协同',
            'verification': '验证',
        }
        tooltip = (
            f"<b>[{type_labels.get(relation_type, '')}]</b> {label}<br>"
            f"<hr style='margin:3px 0;border-color:{edge_style.get('color', {}).get('color', '#888')}'>"
            f"<b>关系强度</b>: {'●' * weight}{'○' * (5 - weight)}<br>"
            f"<b>说明</b>: {description}"
        )

        try:
            net.add_edge(
                source_uid,
                target_uid,
                label=label,
                title=tooltip,
                width=adjusted_width,
                color=edge_style.get('color', {}),
                dashes=edge_style.get('dashes', False),
                smooth=edge_style.get('smooth', {'type': 'continuous'}),
                arrows=edge_style.get('arrows', {}),
                font=edge_style.get('font', {}),
                hoverWidth=edge_style.get('hoverWidth', adjusted_width + 2),
                selectionWidth=edge_style.get('selectionWidth', adjusted_width + 2),
            )
            self._added_edges.add(edge_id)
        except Exception as e:
            # 静默跳过边添加异常
            pass

    @staticmethod
    def _get_target_by_uid(targets: List[Dict], uid: str) -> Optional[Dict]:
        """根据UID查找标的"""
        for t in targets:
            if t['uid'] == uid:
                return t
        return None

    @staticmethod
    def _get_target_by_uid_from_edge(edge, uid_field: str) -> Optional[Dict]:
        """从边对象获取标的信息（通过全局映射）"""
        # 这个方法在调用处已通过其他方式处理
        return None
