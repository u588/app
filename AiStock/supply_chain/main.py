#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
十五五战略投资产业链图谱系统 - 主入口
模块解耦设计 | YAML配置 | Plotly专业可视化
"""

import sys
from pathlib import Path

# 添加src到路径
sys.path.insert(0, str(Path(__file__).parent))

from src.data_loader import DataLoader
from src.relationship_builder import RelationshipBuilder
from src.visualizer import ChainVisualizer

def main():
    """系统主流程"""
    print("🚀 启动十五五产业链图谱分析系统...")
    
    # 1. 初始化配置
    config_path = Path('config/config.yaml')
    
    # 2. 加载数据
    print("📊 加载标的数据...")
    loader = DataLoader(config_path)
    df = loader.load_targets()
    nodes = loader.build_node_metadata(df)
    print(f"   ✓ 加载 {len([n for n in nodes if n.get('level')==4])} 个标的公司")
    print(f"   ✓ 构建 {len([n for n in nodes if n.get('level')<4])} 个层级节点")
    
    # 3. 构建关系
    print("🔗 构建产业链关系...")
    builder = RelationshipBuilder(config_path)
    edges = builder.build_all_relationships(df)
    
    # 统计关系类型
    from collections import Counter
    edge_types = Counter(e['type'] for e in edges)
    for etype, count in edge_types.items():
        print(f"   ✓ {etype}: {count} 条")
    
    # 4. 生成可视化
    print("🎨 生成专业图谱...")
    viz = ChainVisualizer(config_path)
    fig = viz.create_network_graph(nodes, edges, layout_type='force_atlas2')
    
    # 5. 保存输出
    print("💾 保存结果...")
    viz.save_figure(fig, 'industry_chain_map', format='html')
    viz.save_figure(fig, 'industry_chain_map', format='png')
    
    print("\n✨ 系统执行完成！")
    print("📁 输出文件: supply_chain/output/")
    print("🔍 打开 industry_chain_map.html 查看交互式图谱")

if __name__ == '__main__':
    main()