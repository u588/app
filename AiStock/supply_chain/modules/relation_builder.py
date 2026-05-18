"""
关系构建器 - 基于YAML配置构建四种关系网络
供应链(supply_chain) / 竞争(competition) / 协同(synergy) / 验证(validation)
"""

from typing import Dict, List, Any, Tuple, Set
from dataclasses import dataclass, field
from .config_loader import ConfigLoader
from .data_loader import DataLoader
from .chain_analyzer import ChainAnalyzer


@dataclass
class Relation:
    """关系实体"""
    source: str          # 源节点名称
    target: str          # 目标节点名称
    relation_type: str   # supply_chain / competition / synergy / validation
    weight: float        # 权重 1-10
    label: str           # 关系标签
    description: str     # 关系描述
    source_type: str     # track / stock
    target_type: str     # track / stock

    @property
    def id(self) -> str:
        return f"{self.relation_type}:{self.source}→{self.target}"


@dataclass
class RelationGraph:
    """关系图"""
    relations: List[Relation] = field(default_factory=list)

    def add(self, relation: Relation) -> None:
        self.relations.append(relation)

    def get_by_type(self, relation_type: str) -> List[Relation]:
        return [r for r in self.relations if r.relation_type == relation_type]

    def get_by_source(self, source: str) -> List[Relation]:
        return [r for r in self.relations if r.source == source]

    def get_by_target(self, target: str) -> List[Relation]:
        return [r for r in self.relations if r.target == target]

    def get_between(self, node_a: str, node_b: str) -> List[Relation]:
        return [
            r for r in self.relations
            if (r.source == node_a and r.target == node_b) or
               (r.source == node_b and r.target == node_a)
        ]

    @property
    def node_set(self) -> Set[str]:
        nodes = set()
        for r in self.relations:
            nodes.add(r.source)
            nodes.add(r.target)
        return nodes

    @property
    def stats(self) -> Dict[str, int]:
        stats = {}
        for r in self.relations:
            stats[r.relation_type] = stats.get(r.relation_type, 0) + 1
        return stats


class RelationBuilder:
    """关系构建引擎"""

    # 关系类型中文映射
    TYPE_LABELS = {
        'supply_chain': '供应链',
        'competition': '竞争',
        'synergy': '协同',
        'validation': '验证',
    }

    def __init__(self, config: ConfigLoader, data: DataLoader, chain_analyzer: ChainAnalyzer):
        self.config = config
        self.data = data
        self.chain_analyzer = chain_analyzer
        self._graph = RelationGraph()

    def build(self) -> RelationGraph:
        """构建完整关系图"""
        self._build_track_relations()
        self._build_stock_relations()
        self._build_auto_competition()
        return self._graph

    def get_graph(self) -> RelationGraph:
        if not self._graph.relations:
            self.build()
        return self._graph

    def _build_track_relations(self) -> None:
        """从YAML配置构建赛道级关系"""
        rel_config = self.config.load('relations')

        # 供应链关系
        for item in rel_config.get('supply_chain', []):
            self._graph.add(Relation(
                source=item['from'],
                target=item['to'],
                relation_type='supply_chain',
                weight=item.get('weight', 5),
                label=item.get('label', ''),
                description=item.get('label', ''),
                source_type='track',
                target_type='track',
            ))

        # 竞争关系（赛道内）
        for item in rel_config.get('competition', []):
            if item.get('type') == 'intra_track':
                # 同赛道竞争：为赛道内每对标的生成竞争关系
                track_name = item['from']
                stocks = self.data.get_stock_by_track(track_name)
                self._add_intra_track_competition(stocks, item)

        # 协同关系
        for item in rel_config.get('synergy', []):
            self._graph.add(Relation(
                source=item['from'],
                target=item['to'],
                relation_type='synergy',
                weight=item.get('weight', 5),
                label=item.get('label', ''),
                description=item.get('description', ''),
                source_type='track',
                target_type='track',
            ))

        # 验证关系
        for item in rel_config.get('validation', []):
            self._graph.add(Relation(
                source=item['from'],
                target=item['to'],
                relation_type='validation',
                weight=item.get('weight', 5),
                label=item.get('label', ''),
                description=item.get('description', ''),
                source_type='track',
                target_type='track',
            ))

    def _add_intra_track_competition(self, stocks: list, config_item: dict) -> None:
        """为赛道内标的生成竞争关系（取前N个核心标的）"""
        # 按综合评分排序，取前6个标的生成竞争对
        sorted_stocks = sorted(stocks, key=lambda s: s.score, reverse=True)
        top_stocks = sorted_stocks[:6]

        weight = config_item.get('weight', 5)
        description = config_item.get('description', '')

        for i in range(len(top_stocks)):
            for j in range(i + 1, len(top_stocks)):
                self._graph.add(Relation(
                    source=top_stocks[i].name,
                    target=top_stocks[j].name,
                    relation_type='competition',
                    weight=weight,
                    label=f"{top_stocks[i].name}↔{top_stocks[j].name}",
                    description=description,
                    source_type='stock',
                    target_type='stock',
                ))

    def _build_stock_relations(self) -> None:
        """从YAML配置构建标的级关系"""
        stock_config = self.config.load('stock_relations')

        # 标的间供应链
        for item in stock_config.get('stock_supply_chain', []):
            self._graph.add(Relation(
                source=item['from'],
                target=item['to'],
                relation_type='supply_chain',
                weight=item.get('weight', 5),
                label=item.get('label', ''),
                description=item.get('label', ''),
                source_type='stock',
                target_type='stock',
            ))

        # 标的间竞争
        for item in stock_config.get('stock_competition', []):
            self._graph.add(Relation(
                source=item['from'],
                target=item['to'],
                relation_type='competition',
                weight=item.get('weight', 5),
                label=item.get('label', ''),
                description=item.get('label', ''),
                source_type='stock',
                target_type='stock',
            ))

        # 标的间协同
        for item in stock_config.get('stock_synergy', []):
            self._graph.add(Relation(
                source=item['from'],
                target=item['to'],
                relation_type='synergy',
                weight=item.get('weight', 5),
                label=item.get('label', ''),
                description=item.get('label', ''),
                source_type='stock',
                target_type='stock',
            ))

        # 标的间验证
        for item in stock_config.get('stock_validation', []):
            self._graph.add(Relation(
                source=item['from'],
                target=item['to'],
                relation_type='validation',
                weight=item.get('weight', 5),
                label=item.get('label', ''),
                description=item.get('label', ''),
                source_type='stock',
                target_type='stock',
            ))

    def _build_auto_competition(self) -> None:
        """自动推断：同赛道内未在YAML中定义的高分标的竞争关系"""
        existing_pairs = set()
        for r in self._graph.relations:
            if r.relation_type == 'competition' and r.source_type == 'stock':
                pair = tuple(sorted([r.source, r.target]))
                existing_pairs.add(pair)

        tracks = self.data.get_all_tracks()
        for track in tracks:
            if len(track.stocks) < 2:
                continue
            sorted_stocks = sorted(track.stocks, key=lambda s: s.score, reverse=True)
            top = sorted_stocks[:4]

            for i in range(len(top)):
                for j in range(i + 1, len(top)):
                    pair = tuple(sorted([top[i].name, top[j].name]))
                    if pair not in existing_pairs:
                        self._graph.add(Relation(
                            source=top[i].name,
                            target=top[j].name,
                            relation_type='competition',
                            weight=4,
                            label=f"{top[i].name}↔{top[j].name}",
                            description=f"同赛道({track.name})竞争",
                            source_type='stock',
                            target_type='stock',
                        ))
                        existing_pairs.add(pair)

    def get_track_relation_summary(self) -> Dict[str, Any]:
        """赛道级关系统计"""
        graph = self.get_graph()
        track_relations = [
            r for r in graph.relations
            if r.source_type == 'track' and r.target_type == 'track'
        ]

        summary = {}
        for r in track_relations:
            rt = r.relation_type
            if rt not in summary:
                summary[rt] = {'count': 0, 'avg_weight': 0, 'pairs': []}
            summary[rt]['count'] += 1
            summary[rt]['pairs'].append(f"{r.source}→{r.target}")

        for rt in summary:
            rels = [r for r in track_relations if r.relation_type == rt]
            summary[rt]['avg_weight'] = round(
                sum(r.weight for r in rels) / len(rels), 2
            )

        return summary

    def get_stock_relation_summary(self) -> Dict[str, Any]:
        """标的级关系统计"""
        graph = self.get_graph()
        stock_relations = [
            r for r in graph.relations
            if r.source_type == 'stock' and r.target_type == 'stock'
        ]

        summary = {}
        for r in stock_relations:
            rt = r.relation_type
            if rt not in summary:
                summary[rt] = {'count': 0, 'top_weight': []}
            summary[rt]['count'] += 1
            if r.weight >= 7:
                summary[rt]['top_weight'].append(
                    f"{r.source}→{r.target}(w={r.weight})"
                )

        return summary