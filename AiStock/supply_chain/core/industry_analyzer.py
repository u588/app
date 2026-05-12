"""
产业链分析引擎
负责将标的映射到产业链上中下游层级，构建产业链结构
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class ChainNode:
    """产业链节点"""
    node_id: str
    name: str
    level: str  # upstream / midstream / downstream
    industry: str  # 一级方向
    category: str  # 二级分类
    track: str     # 三级赛道
    targets: List[Dict] = field(default_factory=list)
    description: str = ""

    @property
    def label(self) -> str:
        if self.track:
            return f"{self.track}"
        return f"{self.category}"


@dataclass
class ChainStructure:
    """产业链结构"""
    industry: str
    display_name: str
    upstream: List[ChainNode] = field(default_factory=list)
    midstream: List[ChainNode] = field(default_factory=list)
    downstream: List[ChainNode] = field(default_factory=list)

    @property
    def all_nodes(self) -> List[ChainNode]:
        return self.upstream + self.midstream + self.downstream


class IndustryAnalyzer:
    """产业链分析引擎"""

    def __init__(self, targets: List[Dict], chain_config: Dict):
        """
        初始化产业链分析引擎

        Args:
            targets: 标的数据列表
            chain_config: 产业链YAML配置
        """
        self.targets = targets
        self.chain_config = chain_config.get('industry_chain', {})
        self._chain_structures: Dict[str, ChainStructure] = {}
        self._target_level_map: Dict[str, str] = {}  # uid → level

    def analyze(self) -> Dict[str, ChainStructure]:
        """
        执行产业链分析，返回各一级方向的产业链结构

        Returns:
            以一级方向为key的产业链结构字典
        """
        for industry_name, config in self.chain_config.items():
            structure = self._build_chain_structure(industry_name, config)
            self._chain_structures[industry_name] = structure
            # 构建标的→层级映射
            for node in structure.all_nodes:
                for target in node.targets:
                    self._target_level_map[target['uid']] = node.level
            print(f"[IndustryAnalyzer] {industry_name}: "
                  f"上游{len(structure.upstream)} 中游{len(structure.midstream)} "
                  f"下游{len(structure.downstream)} 节点")
        return self._chain_structures

    def _build_chain_structure(self, industry_name: str, config: Dict) -> ChainStructure:
        """
        构建单个一级方向的产业链结构

        Args:
            industry_name: 一级方向名称
            config: 该方向的YAML配置

        Returns:
            ChainStructure对象
        """
        structure = ChainStructure(
            industry=industry_name,
            display_name=config.get('display_name', industry_name),
        )

        for level_name in ['upstream', 'midstream', 'downstream']:
            level_configs = config.get(level_name, [])
            for lc in level_configs:
                category = lc.get('二级分类', '')
                tracks = lc.get('三级赛道', [])
                description = lc.get('description', '')

                if tracks:
                    # 有明确三级赛道，按赛道创建节点
                    for track in tracks:
                        node = self._create_chain_node(
                            industry_name, category, track, level_name, description
                        )
                        self._add_node_to_structure(structure, node, level_name)
                else:
                    # 无三级赛道（如"应用场景"），按二级分类创建节点
                    node = self._create_chain_node(
                        industry_name, category, '', level_name, description
                    )
                    self._add_node_to_structure(structure, node, level_name)

        return structure

    def _create_chain_node(
        self,
        industry: str,
        category: str,
        track: str,
        level: str,
        description: str
    ) -> ChainNode:
        """创建产业链节点，并关联对应标的"""
        # 构建节点ID
        if track:
            node_id = f"{industry}_{category}_{track}"
        else:
            node_id = f"{industry}_{category}"

        # 查找属于此节点的标的
        matched_targets = []
        for t in self.targets:
            if t['一级方向'] != industry:
                continue
            if t['二级分类'] != category:
                continue
            if track and t['三级赛道'] != track:
                continue
            if not track:
                # 无三级赛道时匹配所有该二级分类的标的
                matched_targets.append(t)
            else:
                matched_targets.append(t)

        return ChainNode(
            node_id=node_id,
            name=track or category,
            level=level,
            industry=industry,
            category=category,
            track=track,
            targets=matched_targets,
            description=description,
        )

    @staticmethod
    def _add_node_to_structure(structure: ChainStructure, node: ChainNode, level: str):
        """将节点添加到产业链结构的对应层级"""
        if level == 'upstream':
            structure.upstream.append(node)
        elif level == 'midstream':
            structure.midstream.append(node)
        elif level == 'downstream':
            structure.downstream.append(node)

    def get_target_level(self, target_uid: str) -> str:
        """获取标的在产业链中的层级"""
        return self._target_level_map.get(target_uid, 'unknown')

    def get_chain_structure(self, industry: str) -> Optional[ChainStructure]:
        """获取指定一级方向的产业链结构"""
        return self._chain_structures.get(industry)

    @property
    def chain_structures(self) -> Dict[str, ChainStructure]:
        """获取所有产业链结构"""
        return self._chain_structures

    def get_industry_summary(self) -> List[Dict]:
        """获取产业链分析摘要"""
        summary = []
        for name, struct in self._chain_structures.items():
            total_targets = sum(len(n.targets) for n in struct.all_nodes)
            summary.append({
                'industry': name,
                'upstream_nodes': len(struct.upstream),
                'midstream_nodes': len(struct.midstream),
                'downstream_nodes': len(struct.downstream),
                'total_targets': total_targets,
            })
        return summary