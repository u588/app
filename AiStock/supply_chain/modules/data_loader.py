"""
数据加载器 - 读取Excel标的池数据并构建结构化数据模型
"""

import os
import pandas as pd
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field


@dataclass
class Stock:
    """标的实体"""
    name: str
    code: str
    direction: str        # 一级方向
    category: str         # 二级分类
    track: str            # 三级赛道
    policy_cycle: str     # 政策周期（近期/中期/远期）——标的级别    
    size_class: str       # 规模分类
    style: str            # 投资风格
    policy_fit: int       # 政策契合度
    certainty: int        # 投资确定性
    core_ratio: int       # 核心业务占比
    score: float          # 综合评分
    priority: int         # 标的优先级
    suggestion: str       # 配置建议
    description: str      # 优化入选说明

    @property
    def id(self) -> str:
        return f"stock_{self.name}"


@dataclass
class Track:
    """赛道实体"""
    name: str
    direction: str
    category: str
    track_priority: str
    track_priority_desc: str
    independent_value: int
    independent_value_desc: str
    stocks: List[Stock] = field(default_factory=list)

    @property
    def id(self) -> str:
        return f"track_{self.name}"


@dataclass
class Category:
    """二级分类实体"""
    name: str
    direction: str
    category_priority: str
    tracks: List[Track] = field(default_factory=list)

    @property
    def id(self) -> str:
        return f"cat_{self.name}"


@dataclass
class Direction:
    """一级方向实体"""
    name: str
    direction_priority: str
    policy_cycle: str
    categories: List[Category] = field(default_factory=list)

    @property
    def id(self) -> str:
        return f"dir_{self.name}"


class DataLoader:
    """Excel数据加载与结构化处理"""

    COLUMN_MAP = {
        '一级方向': 'direction',
        '方向\n优先级': 'direction_priority',
        '二级分类': 'category',
        '分类\n优先级': 'category_priority',
        '政策周期': 'policy_cycle',
        '三级赛道': 'track',
        '赛道\n优先级': 'track_priority',
        '赛道优先级说明': 'track_priority_desc',
        '赛道独立\n价值评级': 'independent_value',
        '独立价值说明': 'independent_value_desc',
        '名称': 'name',
        '代码': 'code',
        '规模\n分类': 'size_class',
        '投资风格': 'style',
        '政策\n契合度': 'policy_fit',
        '投资\n确定性': 'certainty',
        '核心业\n务占比': 'core_ratio',
        '综合\n评分': 'score',
        '标的\n优先级': 'priority',
        '配置建议': 'suggestion',
        '优化入选说明': 'description',
    }

    def __init__(self, filepath: str = None):
        if filepath is None:
            filepath = '/home/ts/app/Ai投研/十大投资方向分类体系标的池（2026.5）.xlsx'
        self.filepath = filepath
        self._df: Optional[pd.DataFrame] = None
        self._directions: Dict[str, Direction] = {}
        self._stocks: Dict[str, Stock] = {}

    def load(self) -> pd.DataFrame:
        """加载Excel数据"""
        self._df = pd.read_excel(self.filepath,converters={'代码': str})
        self._df.columns = [self.COLUMN_MAP.get(c, c) for c in self._df.columns]
        return self._df

    @property
    def dataframe(self) -> pd.DataFrame:
        if self._df is None:
            self.load()
        return self._df

    def build_structure(self) -> Dict[str, Direction]:
        """构建层级化数据结构"""
        if self._df is None:
            self.load()

        df = self._df

        for _, row in df.iterrows():
            dir_name = str(row['direction'])
            cat_name = str(row['category'])
            track_name = str(row['track'])

            # 一级方向
            if dir_name not in self._directions:
                self._directions[dir_name] = Direction(
                    name=dir_name,
                    direction_priority=str(row.get('direction_priority', '')),
                    policy_cycle=str(row.get('policy_cycle', '')),
                )

            direction = self._directions[dir_name]

            # 二级分类
            category = None
            for c in direction.categories:
                if c.name == cat_name:
                    category = c
                    break
            if category is None:
                category = Category(
                    name=cat_name,
                    direction=dir_name,
                    category_priority=str(row.get('category_priority', '')),
                )
                direction.categories.append(category)

            # 三级赛道
            track = None
            for t in category.tracks:
                if t.name == track_name:
                    track = t
                    break
            if track is None:
                track = Track(
                    name=track_name,
                    direction=dir_name,
                    category=cat_name,
                    track_priority=str(row.get('track_priority', '')),
                    track_priority_desc=str(row.get('track_priority_desc', '')),
                    independent_value=int(row.get('independent_value', 0)) if pd.notna(row.get('independent_value')) else 0,
                    independent_value_desc=str(row.get('independent_value_desc', '')),
                )
                category.tracks.append(track)

            # 标的
            stock = Stock(
                name=str(row['name']),
                code=str(row['code']),
                direction=dir_name,
                category=cat_name,
                track=track_name,
                policy_cycle=str(row.get('policy_cycle', '')),
                size_class=str(row.get('size_class', '')),
                style=str(row.get('style', '')),
                policy_fit=int(row['policy_fit']) if pd.notna(row.get('policy_fit')) else 0,
                certainty=int(row['certainty']) if pd.notna(row.get('certainty')) else 0,
                core_ratio=int(row['core_ratio']) if pd.notna(row.get('core_ratio')) else 0,
                score=float(row['score']) if pd.notna(row.get('score')) else 0.0,
                priority=int(row['priority']) if pd.notna(row.get('priority')) else 0,
                suggestion=str(row.get('suggestion', '')),
                description=str(row.get('description', '')),
            )
            track.stocks.append(stock)
            self._stocks[stock.name] = stock

        return self._directions

    def get_directions(self) -> Dict[str, Direction]:
        if not self._directions:
            self.build_structure()
        return self._directions

    def get_stocks(self) -> Dict[str, Stock]:
        if not self._stocks:
            self.build_structure()
        return self._stocks

    def get_stock_by_track(self, track_name: str) -> List[Stock]:
        """获取指定赛道的所有标的"""
        return [s for s in self._stocks.values() if s.track == track_name]

    def get_all_tracks(self) -> List[Track]:
        """获取所有赛道"""
        tracks = []
        for d in self.get_directions().values():
            for c in d.categories:
                tracks.extend(c.tracks)
        return tracks

    def get_direction_for_track(self, track_name: str) -> str:
        """获取赛道所属一级方向"""
        for d in self.get_directions().values():
            for c in d.categories:
                for t in c.tracks:
                    if t.name == track_name:
                        return d.name
        return ""

    def get_category_for_track(self, track_name: str) -> str:
        """获取赛道所属二级分类"""
        for d in self.get_directions().values():
            for c in d.categories:
                for t in c.tracks:
                    if t.name == track_name:
                        return c.name
        return ""

    def summary(self) -> Dict[str, Any]:
        """数据摘要"""
        dirs = self.get_directions()
        total_stocks = len(self._stocks)
        total_tracks = sum(len(c.tracks) for d in dirs.values() for c in d.categories)
        total_categories = sum(len(d.categories) for d in dirs.values())

        dir_stats = {}
        for name, d in dirs.items():
            stock_count = sum(len(t.stocks) for c in d.categories for t in c.tracks)
            track_count = sum(len(c.tracks) for c in d.categories)
            dir_stats[name] = {
                'stock_count': stock_count,
                'track_count': track_count,
                'priority': d.direction_priority,
            }

        return {
            'total_directions': len(dirs),
            'total_categories': total_categories,
            'total_tracks': total_tracks,
            'total_stocks': total_stocks,
            'direction_stats': dir_stats,
        }