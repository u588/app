"""
产业链分析器 - 基于YAML配置对赛道进行上中下游分类
分析产业链层级结构和价值分布
"""

from typing import Dict, List, Any, Tuple
from dataclasses import dataclass, field
from .config_loader import ConfigLoader
from .data_loader import DataLoader, Direction, Track, Stock


@dataclass
class ChainNode:
    """产业链节点"""
    name: str
    level: str           # upstream / midstream / downstream
    direction: str
    category: str
    stocks: List[Stock] = field(default_factory=list)
    tracks: List[str] = field(default_factory=list)

    @property
    def level_label(self) -> str:
        labels = {'upstream': '上游', 'midstream': '中游', 'downstream': '下游'}
        return labels.get(self.level, self.level)

    @property
    def stock_count(self) -> int:
        return len(self.stocks)

    @property
    def avg_score(self) -> float:
        if not self.stocks:
            return 0.0
        return sum(s.score for s in self.stocks) / len(self.stocks)


@dataclass
class DirectionChain:
    """一级方向的产业链结构"""
    direction: str
    upstream: List[ChainNode] = field(default_factory=list)
    midstream: List[ChainNode] = field(default_factory=list)
    downstream: List[ChainNode] = field(default_factory=list)

    @property
    def total_stocks(self) -> int:
        return sum(n.stock_count for n in self.upstream + self.midstream + self.downstream)

    @property
    def all_nodes(self) -> List[ChainNode]:
        return self.upstream + self.midstream + self.downstream

    def get_level_summary(self, level: str) -> Dict[str, Any]:
        nodes = getattr(self, level, [])
        return {
            'track_count': len(nodes),
            'stock_count': sum(n.stock_count for n in nodes),
            'avg_score': sum(n.avg_score for n in nodes) / max(len(nodes), 1),
            'tracks': [n.name for n in nodes],
        }


class ChainAnalyzer:
    """产业链分析引擎"""

    def __init__(self, config: ConfigLoader, data: DataLoader):
        self.config = config
        self.data = data
        self._chain_config: Dict = {}
        self._chains: Dict[str, DirectionChain] = {}

    def analyze(self) -> Dict[str, DirectionChain]:
        """执行产业链分析"""
        self._chain_config = self.config.load('industry_chain')
        directions = self.data.get_directions()
        stocks_map = self.data.get_stocks()

        for dir_name, direction in directions.items():
            chain_config = self._chain_config.get(dir_name, {})
            if not chain_config:
                continue

            dir_chain = DirectionChain(direction=dir_name)

            for level in ['upstream', 'midstream', 'downstream']:
                track_names = chain_config.get(level, [])
                for track_name in track_names:
                    # 查找赛道对象
                    track_obj = None
                    for cat in direction.categories:
                        for t in cat.tracks:
                            if t.name == track_name:
                                track_obj = t
                                break

                    if track_obj is None:
                        # 跨方向赛道
                        node = ChainNode(
                            name=track_name,
                            level=level,
                            direction=dir_name,
                            category=self.data.get_category_for_track(track_name),
                            stocks=self.data.get_stock_by_track(track_name),
                            tracks=[track_name],
                        )
                    else:
                        node = ChainNode(
                            name=track_name,
                            level=level,
                            direction=dir_name,
                            category=track_obj.category,
                            stocks=track_obj.stocks,
                            tracks=[track_name],
                        )

                    getattr(dir_chain, level).append(node)

            self._chains[dir_name] = dir_chain

        return self._chains

    def get_chains(self) -> Dict[str, DirectionChain]:
        if not self._chains:
            self.analyze()
        return self._chains

    def get_track_level(self, direction: str, track: str) -> str:
        """获取赛道的产业链层级"""
        chains = self.get_chains()
        chain = chains.get(direction)
        if not chain:
            return 'unknown'

        for level in ['upstream', 'midstream', 'downstream']:
            for node in getattr(chain, level):
                if node.name == track:
                    return level
        return 'unknown'

    def get_chain_distribution(self) -> Dict[str, Dict[str, Any]]:
        """获取各方向的上中下游分布"""
        chains = self.get_chains()
        distribution = {}

        for dir_name, chain in chains.items():
            distribution[dir_name] = {
                'upstream': chain.get_level_summary('upstream'),
                'midstream': chain.get_level_summary('midstream'),
                'downstream': chain.get_level_summary('downstream'),
                'total_stocks': chain.total_stocks,
            }

        return distribution

    def get_cross_direction_tracks(self) -> List[Dict[str, Any]]:
        """识别跨方向共享赛道（一个赛道出现在多个方向的产业链中）"""
        track_dirs: Dict[str, List[str]] = {}
        chains = self.get_chains()

        for dir_name, chain in chains.items():
            for level in ['upstream', 'midstream', 'downstream']:
                for node in getattr(chain, level):
                    if node.name not in track_dirs:
                        track_dirs[node.name] = []
                    track_dirs[node.name].append(dir_name)

        return [
            {'track': t, 'directions': list(set(dirs))}
            for t, dirs in track_dirs.items() if len(set(dirs)) > 1
        ]

    def get_value_chain_analysis(self, direction: str) -> Dict[str, Any]:
        """获取指定方向的产业链价值分析"""
        chains = self.get_chains()
        chain = chains.get(direction)
        if not chain:
            return {}

        result = {
            'direction': direction,
            'upstream': {
                'tracks': [],
                'total_stocks': 0,
                'avg_score': 0,
                'top_stocks': [],
            },
            'midstream': {
                'tracks': [],
                'total_stocks': 0,
                'avg_score': 0,
                'top_stocks': [],
            },
            'downstream': {
                'tracks': [],
                'total_stocks': 0,
                'avg_score': 0,
                'top_stocks': [],
            },
        }

        for level in ['upstream', 'midstream', 'downstream']:
            nodes = getattr(chain, level)
            level_data = result[level]
            all_stocks = []

            for node in nodes:
                level_data['tracks'].append({
                    'name': node.name,
                    'stock_count': node.stock_count,
                    'avg_score': round(node.avg_score, 2),
                })
                all_stocks.extend(node.stocks)

            level_data['total_stocks'] = len(all_stocks)
            level_data['avg_score'] = round(
                sum(s.score for s in all_stocks) / max(len(all_stocks), 1), 2
            )
            # Top 5 标的
            sorted_stocks = sorted(all_stocks, key=lambda s: s.score, reverse=True)[:5]
            level_data['top_stocks'] = [
                {'name': s.name, 'code': s.code, 'score': s.score}
                for s in sorted_stocks
            ]

        return result

    def generate_report(self) -> str:
        """生成产业链分析文字报告"""
        chains = self.get_chains()
        lines = []
        lines.append("=" * 60)
        lines.append("十大投资方向 · 产业链上中下游分析报告")
        lines.append("=" * 60)

        for dir_name, chain in chains.items():
            lines.append(f"\n{'─' * 50}")
            lines.append(f"▶ {dir_name}（共{chain.total_stocks}只标的）")
            lines.append(f"{'─' * 50}")

            for level in ['upstream', 'midstream', 'downstream']:
                nodes = getattr(chain, level)
                level_label = {'upstream': '上游', 'midstream': '中游', 'downstream': '下游'}[level]
                if not nodes:
                    continue

                all_stocks = []
                for node in nodes:
                    all_stocks.extend(node.stocks)

                lines.append(f"\n  【{level_label}】{len(nodes)}个赛道 / {len(all_stocks)}只标的")
                for node in nodes:
                    top3 = sorted(node.stocks, key=lambda s: s.score, reverse=True)[:3]
                    top3_str = "、".join(f"{s.name}({s.score})" for s in top3)
                    lines.append(f"    · {node.name}（{node.stock_count}只）→ 代表: {top3_str}")

        return "\n".join(lines)