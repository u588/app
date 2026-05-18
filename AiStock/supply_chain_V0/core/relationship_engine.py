"""
关系构建引擎
根据配置规则自动构建供应链/竞争/协同/验证四种关系网络
"""

from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from itertools import combinations


@dataclass
class RelationEdge:
    """关系边"""
    source: str       # 源标的名称
    source_uid: str   # 源标的UID
    target: str       # 目标标的名称
    target_uid: str   # 目标标的UID
    relation_type: str  # supply_chain / competition / collaboration / verification
    label: str        # 关系标签
    weight: int       # 关系权重 1-5
    description: str  # 关系描述
    is_cross_industry: bool = False  # 是否跨行业

    @property
    def edge_id(self) -> str:
        """边的唯一标识"""
        return f"{self.source_uid}--{self.relation_type}--{self.target_uid}"


class RelationshipEngine:
    """关系构建引擎"""

    def __init__(
        self,
        targets: List[Dict],
        relationships_config: Dict,
        chain_structures: Dict,
        target_level_map: Dict[str, str] = None,
    ):
        """
        初始化关系构建引擎

        Args:
            targets: 标的数据列表
            relationships_config: 关系YAML配置
            chain_structures: 产业链结构字典
            target_level_map: 标的→层级映射
        """
        self.targets = targets
        self.config = relationships_config
        self.chain_structures = chain_structures
        self.target_level_map = target_level_map or {}

        # 构建名称→标的映射
        self._name_map: Dict[str, Dict] = {}
        self._uid_map: Dict[str, Dict] = {}
        for t in targets:
            self._name_map[t['标的名称']] = t
            self._uid_map[t['uid']] = t

        # 存储所有关系边
        self._edges: Dict[str, List[RelationEdge]] = {
            'supply_chain': [],
            'competition': [],
            'collaboration': [],
            'verification': [],
        }

    def build_all(self) -> Dict[str, List[RelationEdge]]:
        """
        构建所有四种关系

        Returns:
            以关系类型为key的边列表字典
        """
        self._build_supply_chain()
        self._build_competition()
        self._build_collaboration()
        self._build_verification()

        for rtype, edges in self._edges.items():
            print(f"[RelationshipEngine] {rtype}: {len(edges)} 条关系")

        return self._edges

    def _build_supply_chain(self):
        """构建供应链关系"""
        sc_config = self.config.get('supply_chain', {})

        # 行业内供应链
        intra = sc_config.get('intra_industry', {})
        for industry, rules in intra.items():
            for rule in rules:
                from_track = rule.get('from', '')
                to_track = rule.get('to', '')
                self._add_supply_chain_edge(
                    from_track, to_track, rule, industry, is_cross=False
                )

        # 跨行业供应链
        cross = sc_config.get('cross_industry', [])
        for rule in cross:
            from_industry = rule.get('from_industry', '')
            from_track = rule.get('from_track', '')
            to_industry = rule.get('to_industry', '')
            to_track = rule.get('to_track', '')
            self._add_cross_supply_chain_edge(
                from_industry, from_track, to_industry, to_track, rule
            )

    def _add_supply_chain_edge(
        self,
        from_track: str,
        to_track: str,
        rule: Dict,
        industry: str,
        is_cross: bool = False
    ):
        """添加行业内供应链边（智能过滤：优先大市值，限制每条规则最多连接数）"""
        from_targets = self._get_targets_by_track_str(industry, from_track)
        to_targets = self._get_targets_by_track_str(industry, to_track)

        # 智能过滤：按市值规模排序，优先大市值标的
        from_targets = self._rank_targets(from_targets)
        to_targets = self._rank_targets(to_targets)

        # 限制边数量：每条规则最多生成 MAX_PER_RULE 条边
        MAX_PER_RULE = 15
        count = 0
        for src in from_targets:
            if count >= MAX_PER_RULE:
                break
            for dst in to_targets:
                if count >= MAX_PER_RULE:
                    break
                # 至少一方是大/中市值才建立连接（避免小-小连接过多）
                both_small = (src['市值规模'] == '小' and dst['市值规模'] == '小')
                if both_small:
                    continue
                edge = RelationEdge(
                    source=src['标的名称'],
                    source_uid=src['uid'],
                    target=dst['标的名称'],
                    target_uid=dst['uid'],
                    relation_type='supply_chain',
                    label=rule.get('label', '供应'),
                    weight=rule.get('weight', 3),
                    description=rule.get('description', ''),
                    is_cross_industry=is_cross,
                )
                self._edges['supply_chain'].append(edge)
                count += 1

    def _add_cross_supply_chain_edge(
        self,
        from_industry: str,
        from_track: str,
        to_industry: str,
        to_track: str,
        rule: Dict
    ):
        """添加跨行业供应链边（智能过滤：优先大市值，限制边数）"""
        from_targets = self._get_targets_by_track_str(from_industry, from_track)
        to_targets = self._get_targets_by_track_str(to_industry, to_track)

        # 智能过滤：只保留大/中市值标的的跨行业连接
        from_targets = self._rank_targets(from_targets)
        to_targets = self._rank_targets(to_targets)

        MAX_PER_RULE = 10
        count = 0
        for src in from_targets:
            if count >= MAX_PER_RULE:
                break
            for dst in to_targets:
                if count >= MAX_PER_RULE:
                    break
                # 跨行业连接至少一方是大市值
                has_big = (src['市值规模'] == '大' or dst['市值规模'] == '大')
                if not has_big:
                    continue
                edge = RelationEdge(
                    source=src['标的名称'],
                    source_uid=src['uid'],
                    target=dst['标的名称'],
                    target_uid=dst['uid'],
                    relation_type='supply_chain',
                    label=rule.get('label', '跨行业供应'),
                    weight=rule.get('weight', 3),
                    description=rule.get('description', ''),
                    is_cross_industry=True,
                )
                self._edges['supply_chain'].append(edge)
                count += 1

    @staticmethod
    def _rank_targets(targets: List[Dict]) -> List[Dict]:
        """按市值规模排序：大→中→小，同等规模按政策契合度+投资确定性排序"""
        cap_order = {'大': 3, '中': 2, '小': 1}
        return sorted(
            targets,
            key=lambda x: (
                cap_order.get(x.get('市值规模', '小'), 1),
                x.get('政策契合度', 0) + x.get('投资确定性', 0),
            ),
            reverse=True,
        )

    def _build_competition(self):
        """构建竞争关系"""
        comp_config = self.config.get('competition', {})

        # 自动生成同赛道竞争
        rules = comp_config.get('rules', [])
        for rule in rules:
            if rule.get('auto_generate') and rule.get('dimension') == '同三级赛道':
                self._auto_generate_same_track_competition(rule)

        # 手动竞争关系
        manual = comp_config.get('manual', [])
        for item in manual:
            target_names = item.get('targets', [])
            weight = item.get('weight', 3)
            label = item.get('label', '竞争')
            description = item.get('description', '')

            # 两两配对
            for i, name1 in enumerate(target_names):
                for name2 in target_names[i + 1:]:
                    t1 = self._name_map.get(name1)
                    t2 = self._name_map.get(name2)
                    if t1 and t2:
                        edge = RelationEdge(
                            source=name1,
                            source_uid=t1['uid'],
                            target=name2,
                            target_uid=t2['uid'],
                            relation_type='competition',
                            label=label,
                            weight=weight,
                            description=description,
                        )
                        self._edges['competition'].append(edge)

    def _auto_generate_same_track_competition(self, rule: Dict):
        """自动生成同三级赛道的竞争关系"""
        weight = rule.get('weight', 3)

        # 按赛道分组
        track_groups: Dict[str, List[Dict]] = {}
        for t in self.targets:
            key = f"{t['一级方向']}|{t['二级分类']}|{t['三级赛道']}"
            if key not in track_groups:
                track_groups[key] = []
            track_groups[key].append(t)

        # 每组内两两配对（限制同组最多生成C(n,2)条边）
        for key, group in track_groups.items():
            if len(group) < 2:
                continue
            parts = key.split('|')
            industry, category, track = parts[0], parts[1], parts[2]

            # 对大组只取市值规模大的标的（避免边爆炸）
            sorted_group = sorted(group, key=lambda x: {'大': 3, '中': 2, '小': 1}.get(x['市值规模'], 0), reverse=True)
            if len(sorted_group) > 6:
                sorted_group = sorted_group[:6]

            for i, t1 in enumerate(sorted_group):
                for t2 in sorted_group[i + 1:]:
                    edge = RelationEdge(
                        source=t1['标的名称'],
                        source_uid=t1['uid'],
                        target=t2['标的名称'],
                        target_uid=t2['uid'],
                        relation_type='competition',
                        label=f"{track}竞争",
                        weight=weight,
                        description=f"同属{industry}/{category}/{track}赛道，互为竞争对手",
                    )
                    self._edges['competition'].append(edge)

    def _build_collaboration(self):
        """构建协同关系"""
        collab_config = self.config.get('collaboration', {})
        manual = collab_config.get('manual', [])

        for item in manual:
            target_names = item.get('targets', [])
            weight = item.get('weight', 3)
            label = item.get('label', '协同')
            description = item.get('description', '')

            for i, name1 in enumerate(target_names):
                for name2 in target_names[i + 1:]:
                    t1 = self._name_map.get(name1)
                    t2 = self._name_map.get(name2)
                    if t1 and t2:
                        cross = t1['一级方向'] != t2['一级方向']
                        edge = RelationEdge(
                            source=name1,
                            source_uid=t1['uid'],
                            target=name2,
                            target_uid=t2['uid'],
                            relation_type='collaboration',
                            label=label,
                            weight=weight,
                            description=description,
                            is_cross_industry=cross,
                        )
                        self._edges['collaboration'].append(edge)

    def _build_verification(self):
        """构建验证关系"""
        ver_config = self.config.get('verification', {})
        manual = ver_config.get('manual', [])

        for item in manual:
            from_name = item.get('from', '')
            to_name = item.get('to', '')
            weight = item.get('weight', 3)
            label = item.get('label', '验证')
            description = item.get('description', '')

            t1 = self._name_map.get(from_name)
            t2 = self._name_map.get(to_name)
            if t1 and t2:
                edge = RelationEdge(
                    source=from_name,
                    source_uid=t1['uid'],
                    target=to_name,
                    target_uid=t2['uid'],
                    relation_type='verification',
                    label=label,
                    weight=weight,
                    description=description,
                )
                self._edges['verification'].append(edge)

    def _get_targets_by_track_str(self, industry: str, track_str: str) -> List[Dict]:
        """
        根据赛道字符串（如"设备材料→刻蚀薄膜"）查找对应标的

        Args:
            industry: 一级方向
            track_str: 格式为"二级分类→三级赛道"的字符串

        Returns:
            匹配的标的列表
        """
        parts = track_str.split('→')
        category = parts[0] if len(parts) > 0 else ''
        track = parts[1] if len(parts) > 1 else ''

        result = []
        for t in self.targets:
            if t['一级方向'] != industry:
                continue
            if category and t['二级分类'] != category:
                continue
            if track and t['三级赛道'] != track:
                continue
            result.append(t)
        return result

    def get_edges_by_type(self, relation_type: str) -> List[RelationEdge]:
        """按类型获取关系边"""
        return self._edges.get(relation_type, [])

    def get_edges_for_target(self, target_name: str) -> Dict[str, List[RelationEdge]]:
        """获取某标的的所有关系"""
        result = {rt: [] for rt in self._edges}
        for rt, edges in self._edges.items():
            for edge in edges:
                if edge.source == target_name or edge.target == target_name:
                    result[rt].append(edge)
        return result

    @property
    def all_edges(self) -> Dict[str, List[RelationEdge]]:
        """获取所有关系边"""
        return self._edges

    def get_statistics(self) -> Dict:
        """获取关系统计信息"""
        stats = {}
        for rt, edges in self._edges.items():
            cross_count = sum(1 for e in edges if e.is_cross_industry)
            stats[rt] = {
                'total': len(edges),
                'cross_industry': cross_count,
                'intra_industry': len(edges) - cross_count,
                'avg_weight': sum(e.weight for e in edges) / len(edges) if edges else 0,
            }
        return stats