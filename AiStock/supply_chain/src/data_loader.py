#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据加载与解析模块
负责读取原始数据、清洗、标准化处理
"""

import pandas as pd
import yaml
from pathlib import Path
from typing import Dict, List, Optional
import re

class DataLoader:
    """产业链数据加载器"""
    
    def __init__(self, config_path: str):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        self.root_dir = Path(self.config['system']['root_dir'])
        
    def load_targets(self) -> pd.DataFrame:
        """加载原始标的数据"""
        raw_path = self.root_dir / self.config['data']['raw_file']
        
        # 解析用户提供的表格数据（模拟CSV读取）
        df = pd.read_csv(
            raw_path, 
            encoding=self.config['data']['encoding'],
            delimiter=self.config['data']['delimiter'],
            dtype={'代码': str, '排序': int}
        )
        
        # 数据清洗与标准化
        df = self._clean_data(df)
        return df
    
    def _clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """数据清洗：去重、类型转换、字段标准化"""
        # 去除空白行
        df = df.dropna(how='all')
        
        # 代码字段标准化（去除空格）
        df['代码'] = df['代码'].astype(str).str.strip()
        
        # 市值规模映射为数值排序
        cap_order = {'大': 3, '中': 2, '小': 1}
        df['cap_rank'] = df['市值规模'].map(cap_order)
        
        # 政策契合度+投资确定性综合评分
        df['composite_score'] = (
            df['政策契合度'] * 0.6 + df['投资确定性'] * 0.4
        )
        
        # 生成唯一节点ID
        df['node_id'] = df.apply(
            lambda x: f"{x['一级方向']}_{x['二级分类']}_{x['标的名称']}", 
            axis=1
        )
        
        return df
    
    def build_node_metadata(self, df: pd.DataFrame) -> List[Dict]:
        """构建节点元数据列表（Plotly格式）"""
        nodes = []
        cap_config = self.config['data']['market_cap_map']
        
        for _, row in df.iterrows():
            node = {
                'id': row['node_id'],
                'label': row['标的名称'],
                'code': row['代码'],
                'level': 4,  # 标的层级
                'track': row['三级赛道'],
                'category': row['二级分类'],
                'direction': row['一级方向'],
                'market_cap': row['市值规模'],
                'size': cap_config[row['市值规模']]['size'],
                'color': cap_config[row['市值规模']]['color'],
                'hover_text': self._build_hover_text(row),
                'score': row['composite_score']
            }
            nodes.append(node)
        
        # 添加产业链层级节点（方向/分类/赛道）
        nodes.extend(self._build_hierarchy_nodes(df))
        return nodes
    
    def _build_hover_text(self, row: pd.Series) -> str:
        """构建悬浮提示文本（支持中文+富信息）"""
        return (
            f"<b>{row['标的名称']}</b> ({row['代码']})<br>"
            f"📍 {row['一级方向']} → {row['二级分类']} → {row['三级赛道']}<br>"
            f"📊 市值: {row['市值规模']} | 综合评分: {row['composite_score']:.1f}<br>"
            f"✅ 政策契合: {row['政策契合度']}/5 | 确定性: {row['投资确定性']}/5<br>"
            f"📝 {row['入选说明']}"
        )
    
    def _build_hierarchy_nodes(self, df: pd.DataFrame) -> List[Dict]:
        """构建产业链层级虚拟节点"""
        hierarchy_nodes = []
        level_config = self.config['chain_hierarchy']
        
        # 一级方向节点
        for direction in df['一级方向'].unique():
            hierarchy_nodes.append({
                'id': f"DIR_{direction}",
                'label': direction,
                'level': 1,
                'size': level_config[0]['node_size'],
                'color': '#2c3e50',
                'hover_text': f"<b>{direction}</b><br>战略投资方向",
                'type': 'direction'
            })
        
        # 二级分类节点
        for _, group in df.groupby(['一级方向', '二级分类']):
            direction, category = group['一级方向'].iloc[0], group['二级分类'].iloc[0]
            hierarchy_nodes.append({
                'id': f"CAT_{category}",
                'label': category,
                'level': 2,
                'parent': f"DIR_{direction}",
                'size': level_config[1]['node_size'],
                'color': '#3498db',
                'hover_text': f"<b>{category}</b><br>所属: {direction}",
                'type': 'category'
            })
        
        # 三级赛道节点
        for _, group in df.groupby(['二级分类', '三级赛道']):
            category, track = group['二级分类'].iloc[0], group['三级赛道'].iloc[0]
            hierarchy_nodes.append({
                'id': f"TRK_{track}",
                'label': track,
                'level': 3,
                'parent': f"CAT_{category}",
                'size': level_config[2]['node_size'],
                'color': '#9b59b6',
                'hover_text': f"<b>{track}</b><br>所属: {category}",
                'type': 'track'
            })
        
        return hierarchy_nodes