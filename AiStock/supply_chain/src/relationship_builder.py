#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
产业链关系构建引擎
自动识别：供应链/竞争/协同/验证 四类关系
"""

import pandas as pd
from typing import List, Dict, Set
from itertools import combinations
import yaml

class RelationshipBuilder:
    """产业链关系智能构建器"""
    
    def __init__(self, config_path: str):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        self.rules = self.config['relationship_rules']
        
    def build_all_relationships(self, df: pd.DataFrame) -> List[Dict]:
        """构建全量关系边"""
        edges = []
        
        # 1. 产业链上下游关系（核心逻辑）
        edges.extend(self._build_supply_chain_edges(df))
        
        # 2. 同赛道竞争关系
        edges.extend(self._build_competition_edges(df))
        
        # 3. 跨赛道协同关系
        edges.extend(self._build_synergy_edges(df))
        
        # 4. 技术验证/认证关系
        edges.extend(self._build_validation_edges(df))
        
        # 5. 层级归属关系（方向→分类→赛道→标的）
        edges.extend(self._build_hierarchy_edges(df))
        
        return edges
    
    def _build_supply_chain_edges(self, df: pd.DataFrame) -> List[Dict]:
        """
        供应链上下游关系构建
        规则：设备材料→晶圆制造→封装测试→终端应用
        """
        edges = []
        supply_map = {
            '设备材料': ['晶圆制造', '先进封装'],
            '晶圆制造': ['先进封装', '第三代半导体'],
            '先进封装': ['人工智能', '消费电子'],
            '算力芯片': ['大模型基座', '算力基建'],
            '光伏技术': ['储能电池', '电网'],
            '稀土开采': ['永磁材料', '电机'],
        }
        
        for _, row in df.iterrows():
            category = row['二级分类']
            if category in supply_map:
                for downstream in supply_map[category]:
                    # 查找下游赛道标的
                    downstream_targets = df[
                        (df['三级赛道'].str.contains(downstream, case=False, na=False)) |
                        (df['二级分类'] == downstream)
                    ]
                    for _, dt in downstream_targets.iterrows():
                        edges.append({
                            'source': row['node_id'],
                            'target': dt['node_id'],
                            'type': 'supply_chain',
                            'weight': 0.8,
                            'color': self.rules['supply_chain']['color'],
                            'width': self.rules['supply_chain']['width'],
                            'dash': self.rules['supply_chain']['dash'],
                            'hover_text': f"供应链: {row['标的名称']} → {dt['标的名称']}"
                        })
        return edges
    
    def _build_competition_edges(self, df: pd.DataFrame) -> List[Dict]:
        """同赛道+同市值规模竞争关系"""
        edges = []
        # 按赛道+市值分组
        groups = df.groupby(['三级赛道', '市值规模'])
        
        for (track, cap), group in groups:
            if len(group) < 2:
                continue
            # 同组内两两建立竞争关系
            for (i, row_i), (j, row_j) in combinations(group.iterrows(), 2):
                edges.append({
                    'source': row_i['node_id'],
                    'target': row_j['node_id'],
                    'type': 'competition',
                    'weight': 0.5,
                    'color': self.rules['competition']['color'],
                    'width': self.rules['competition']['width'],
                    'dash': self.rules['competition']['dash'],
                    'hover_text': f"竞争关系: {row_i['标的名称']} ⇄ {row_j['标的名称']}<br>赛道: {track}"
                })
        return edges
    
    def _build_synergy_edges(self, df: pd.DataFrame) -> List[Dict]:
        """跨赛道技术/客户协同关系"""
        edges = []
        synergy_pairs = [
            ('刻蚀薄膜', '光刻硅片', '设备协同'),
            ('SiC/GaN', '功率半导体', '材料协同'),
            ('算力芯片', '光液冷', '散热协同'),
            ('大模型基座', '数据资产', '数据协同'),
            ('储能系统', '光伏技术', '光储协同'),
            ('航空发动机', '碳纤维复材', '材料协同'),
            ('关节减速器', '微特电机', '驱动协同'),
        ]
        
        for track1, track2, desc in synergy_pairs:
            targets1 = df[df['三级赛道'].str.contains(track1, na=False)]
            targets2 = df[df['三级赛道'].str.contains(track2, na=False)]
            
            if targets1.empty or targets2.empty:
                continue
                
            # 同一级方向内建立协同
            for _, t1 in targets1.iterrows():
                for _, t2 in targets2.iterrows():
                    if t1['一级方向'] == t2['一级方向']:
                        edges.append({
                            'source': t1['node_id'],
                            'target': t2['node_id'],
                            'type': 'synergy',
                            'weight': 0.6,
                            'color': self.rules['synergy']['color'],
                            'width': self.rules['synergy']['width'],
                            'dash': self.rules['synergy']['dash'],
                            'hover_text': f"协同关系: {desc}<br>{t1['标的名称']} ↔ {t2['标的名称']}"
                        })
        return edges
    
    def _build_validation_edges(self, df: pd.DataFrame) -> List[Dict]:
        """技术验证/认证关系（设备→产线验证）"""
        edges = []
        # 设备厂商→晶圆厂验证关系
        equipment = df[df['二级分类'] == '设备材料']
        foundries = df[df['三级赛道'] == '成熟制程']
        
        for _, eq in equipment.iterrows():
            for _, fy in foundries.iterrows():
                # 简化逻辑：同方向内设备→制造建立验证关系
                if eq['一级方向'] == fy['一级方向']:
                    edges.append({
                        'source': eq['node_id'],
                        'target': fy['node_id'],
                        'type': 'validation',
                        'weight': 0.4,
                        'color': self.rules['validation']['color'],
                        'width': self.rules['validation']['width'],
                        'dash': self.rules['validation']['dash'],
                        'hover_text': f"验证关系: {eq['标的名称']} → {fy['标的名称']}<br>产线认证/技术验证"
                    })
        return edges
    
    def _build_hierarchy_edges(self, df: pd.DataFrame) -> List[Dict]:
        """构建层级归属关系边"""
        edges = []
        
        for _, row in df.iterrows():
            # 标的 → 三级赛道
            edges.append({
                'source': row['node_id'],
                'target': f"TRK_{row['三级赛道']}",
                'type': 'hierarchy',
                'weight': 1.0,
                'color': '#95a5a6',
                'width': 0.8,
                'dash': 'solid',
                'hover_text': f"归属: {row['标的名称']} → {row['三级赛道']}"
            })
        
        # 赛道 → 分类 → 方向（去重）
        track_cat = df.groupby('三级赛道')['二级分类'].first()
        for track, cat in track_cat.items():
            edges.append({
                'source': f"TRK_{track}",
                'target': f"CAT_{cat}",
                'type': 'hierarchy',
                'weight': 1.0,
                'color': '#7f8c8d',
                'width': 1.2,
                'dash': 'solid',
                'hover_text': f"归属: {track} → {cat}"
            })
        
        cat_dir = df.groupby('二级分类')['一级方向'].first()
        for cat, direction in cat_dir.items():
            edges.append({
                'source': f"CAT_{cat}",
                'target': f"DIR_{direction}",
                'type': 'hierarchy',
                'weight': 1.0,
                'color': '#34495e',
                'width': 1.5,
                'dash': 'solid',
                'hover_text': f"归属: {cat} → {direction}"
            })
        
        return edges