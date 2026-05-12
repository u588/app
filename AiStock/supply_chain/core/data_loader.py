"""
数据加载模块
负责CSV数据读取、清洗、标准化，以及YAML配置加载
"""

import csv
import os
from typing import List, Dict, Optional
import yaml


class DataLoader:
    """数据加载器，负责读取CSV标的文件和YAML配置文件"""

    def __init__(self, csv_path: str, config_dir: str):
        """
        初始化数据加载器

        Args:
            csv_path: CSV标的文件路径
            config_dir: YAML配置文件目录
        """
        self.csv_path = csv_path
        self.config_dir = config_dir
        self._targets: List[Dict] = []
        self._industry_chain_config: Dict = {}
        self._relationships_config: Dict = {}
        self._visualization_config: Dict = {}

    @property
    def targets(self) -> List[Dict]:
        """获取标的列表"""
        return self._targets

    @property
    def industry_chain_config(self) -> Dict:
        """获取产业链配置"""
        return self._industry_chain_config

    @property
    def relationships_config(self) -> Dict:
        """获取关系配置"""
        return self._relationships_config

    @property
    def visualization_config(self) -> Dict:
        """获取可视化配置"""
        return self._visualization_config

    def load_all(self) -> 'DataLoader':
        """加载所有数据，返回self以支持链式调用"""
        self._load_csv()
        self._load_configs()
        return self

    def _load_csv(self):
        """读取CSV标的文件，处理BOM和编码问题"""
        targets = []
        with open(self.csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # 标准化字段名（去除空白和BOM标记）
                cleaned = {}
                for k, v in row.items():
                    key = k.strip().replace('\ufeff', '')
                    cleaned[key] = v.strip() if v else ''
                # 类型转换
                target = self._normalize_target(cleaned)
                if target:
                    targets.append(target)
        self._targets = targets
        print(f"[DataLoader] 已加载 {len(targets)} 个标的")

    def _normalize_target(self, raw: Dict) -> Optional[Dict]:
        """
        标准化单个标的数据

        Args:
            raw: 原始字典数据

        Returns:
            标准化后的标的字典，数据不完整返回None
        """
        try:
            return {
                '一级方向': raw.get('一级方向', ''),
                '二级分类': raw.get('二级分类', ''),
                '三级赛道': raw.get('三级赛道', ''),
                '市值规模': raw.get('市值规模', '小'),
                '标的名称': raw.get('标的名称', ''),
                '代码': raw.get('代码', ''),
                '入选说明': raw.get('入选说明', ''),
                '政策契合度': int(raw.get('政策契合度', 0)),
                '投资确定性': int(raw.get('投资确定性', 0)),
                # 唯一标识
                'uid': f"{raw.get('代码', '')}_{raw.get('标的名称', '')}",
            }
        except (ValueError, TypeError) as e:
            print(f"[DataLoader] 标的数据异常: {raw.get('标的名称', 'unknown')}, 错误: {e}")
            return None

    def _load_configs(self):
        """加载所有YAML配置文件"""
        configs = {
            'industry_chain': 'industry_chain.yaml',
            'relationships': 'relationships.yaml',
            'visualization': 'visualization.yaml',
        }
        for attr, filename in configs.items():
            filepath = os.path.join(self.config_dir, filename)
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                setattr(self, f'_{attr}_config', config or {})
                print(f"[DataLoader] 已加载配置: {filename}")
            else:
                print(f"[DataLoader] 警告: 配置文件不存在 {filepath}")

    def get_targets_by_industry(self, industry: str) -> List[Dict]:
        """按一级方向筛选标的"""
        return [t for t in self._targets if t['一级方向'] == industry]

    def get_targets_by_track(self, industry: str, category: str, track: str) -> List[Dict]:
        """按三级赛道筛选标的"""
        return [
            t for t in self._targets
            if t['一级方向'] == industry
            and t['二级分类'] == category
            and t['三级赛道'] == track
        ]

    def get_target_by_name(self, name: str) -> Optional[Dict]:
        """按标的名称查找"""
        for t in self._targets:
            if t['标的名称'] == name:
                return t
        return None

    def get_target_by_code(self, code: str) -> Optional[Dict]:
        """按代码查找"""
        for t in self._targets:
            if t['代码'] == code:
                return t
        return None

    def get_all_industries(self) -> List[str]:
        """获取所有一级方向列表"""
        seen = []
        for t in self._targets:
            if t['一级方向'] not in seen:
                seen.append(t['一级方向'])
        return seen

    def get_tracks_by_industry(self, industry: str) -> Dict[str, List[str]]:
        """获取某一级方向下的二级分类→三级赛道映射"""
        result = {}
        for t in self._targets:
            if t['一级方向'] == industry:
                cat = t['二级分类']
                track = t['三级赛道']
                if cat not in result:
                    result[cat] = []
                if track not in result[cat]:
                    result[cat].append(track)
        return result