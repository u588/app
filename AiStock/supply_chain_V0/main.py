"""
产业链分析系统 - 主入口
功能：CSV标的分析 → 产业链上中下游映射 → 四大关系构建 → pyvis可视化

用法:
    python main.py --csv /path/to/targets.csv [--config-dir /path/to/config] [--output-dir /path/to/output]
    python main.py --csv /path/to/targets.csv --industry 半导体国产化
    python main.py --csv /path/to/targets.csv --relation supply_chain
"""

import argparse
import os
import sys
import json

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.data_loader import DataLoader
from core.industry_analyzer import IndustryAnalyzer
from core.relationship_engine import RelationshipEngine
from core.knowledge_expander import KnowledgeExpander
from visualization.style_manager import StyleManager
from visualization.network_builder import NetworkBuilder
from visualization.renderer import Renderer


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='产业链关系分析可视化系统')
    parser.add_argument('--csv', type=str, required=True, help='CSV标的文件路径')
    parser.add_argument('--config-dir', type=str, default=None, help='YAML配置目录')
    parser.add_argument('--output-dir', type=str, default=None, help='输出目录')
    parser.add_argument('--industry', type=str, default=None, help='筛选指定行业')
    parser.add_argument('--relation', type=str, default=None,
                        choices=['supply_chain', 'competition', 'collaboration', 'verification'],
                        help='筛选指定关系类型')
    return parser.parse_args()


def run_analysis(csv_path: str, config_dir: str = None, output_dir: str = None,
                 industry: str = None, relation_type: str = None):
    """
    运行完整分析流程

    Args:
        csv_path: CSV文件路径
        config_dir: 配置目录
        output_dir: 输出目录
        industry: 行业过滤
        relation_type: 关系类型过滤
    """
    # 默认路径
    base_dir = os.path.dirname(os.path.abspath(__file__))
    if config_dir is None:
        config_dir = os.path.join(base_dir, 'config')
    if output_dir is None:
        output_dir = os.path.join(base_dir, 'output')

    print("=" * 70)
    print("  产业链关系分析可视化系统")
    print("  Supply Chain Relationship Analysis & Visualization")
    print("=" * 70)

    # ========== 1. 数据加载 ==========
    print("\n[Step 1] 数据加载...")
    loader = DataLoader(csv_path, config_dir).load_all()

    # ========== 2. 产业链分析 ==========
    print("\n[Step 2] 产业链上中下游分析...")
    analyzer = IndustryAnalyzer(loader.targets, loader.industry_chain_config)
    chain_structures = analyzer.analyze()

    # 打印产业链摘要
    print("\n产业链分析摘要:")
    print("-" * 60)
    summary = analyzer.get_industry_summary()
    for s in summary:
        print(f"  {s['industry']}: 上游{s['upstream_nodes']}节点 | "
              f"中游{s['midstream_nodes']}节点 | 下游{s['downstream_nodes']}节点 | "
              f"共{s['total_targets']}标的")
    print("-" * 60)

    # ========== 3. 关系构建 ==========
    print("\n[Step 3] 构建四大关系网络...")
    target_level_map = {}
    for industry_name, structure in chain_structures.items():
        for node in structure.all_nodes:
            for t in node.targets:
                target_level_map[t['uid']] = node.level

    rel_engine = RelationshipEngine(
        targets=loader.targets,
        relationships_config=loader.relationships_config,
        chain_structures=chain_structures,
        target_level_map=target_level_map,
    )
    all_edges = rel_engine.build_all()

    # ========== 4. 知识扩充 ==========
    print("\n[Step 4] 专业知识扩充...")
    name_map = {t['标的名称']: t for t in loader.targets}
    expander = KnowledgeExpander(
        targets=loader.targets,
        chain_structures=chain_structures,
        name_map=name_map,
    )
    expanded = expander.expand()

    # 按类型统计扩充关系
    expand_stats = {}
    for r in expanded:
        expand_stats[r.relation_type] = expand_stats.get(r.relation_type, 0) + 1
    print("  扩充关系统计:", expand_stats)

    # ========== 5. 可视化 ==========
    print("\n[Step 5] 构建可视化网络...")

    # 样式管理器
    style_mgr = StyleManager(loader.visualization_config)

    # 网络构建器
    builder = NetworkBuilder(style_mgr)

    # 渲染器
    renderer = Renderer(output_dir, loader.visualization_config)

    # 获取关系统计
    rel_stats = rel_engine.get_statistics()

    # 5.1 全量网络图
    print("  → 生成全量产业链关系网络...")
    industries = [industry] if industry else None
    relation_types = [relation_type] if relation_type else None

    full_net = builder.build_full_network(
        targets=loader.targets,
        chain_structures=chain_structures,
        all_edges=all_edges,
        expanded_relations=expanded,
        relation_types=relation_types,
        industries=industries,
    )
    renderer.render(
        full_net,
        filename="full_chain_network.html",
        title="全量产业链关系网络",
        legend_items=loader.visualization_config.get('legend', {}),
        statistics=rel_stats,
    )

    # 5.2 各行业独立网络图
    print("  → 生成各行业产业链网络...")
    all_industries = loader.get_all_industries()
    for ind in all_industries:
        if industry and ind != industry:
            continue
        ind_net = builder.build_industry_network(
            industry=ind,
            targets=loader.targets,
            chain_structures=chain_structures,
            all_edges=all_edges,
            expanded_relations=expanded,
        )
        renderer.render(
            ind_net,
            filename=f"industry_{ind}.html",
            title=f"{ind} - 产业链关系网络",
            legend_items=loader.visualization_config.get('legend', {}),
            statistics=rel_stats,
        )

    # 5.3 各关系类型独立网络图
    print("  → 生成各关系类型网络...")
    for rtype in ['supply_chain', 'competition', 'collaboration', 'verification']:
        if relation_type and rtype != relation_type:
            continue
        type_labels = {
            'supply_chain': '供应链关系',
            'competition': '竞争关系',
            'collaboration': '协同关系',
            'verification': '验证关系',
        }
        rel_net = builder.build_relationship_network(
            relation_type=rtype,
            targets=loader.targets,
            chain_structures=chain_structures,
            all_edges=all_edges,
            expanded_relations=expanded,
        )
        renderer.render(
            rel_net,
            filename=f"relation_{rtype}.html",
            title=f"{type_labels[rtype]}网络",
            legend_items=loader.visualization_config.get('legend', {}),
            statistics=rel_stats,
        )

    # ========== 6. 输出统计报告 ==========
    print("\n[Step 6] 生成统计报告...")
    _save_statistics_report(output_dir, loader, analyzer, rel_engine, expander)

    print("\n" + "=" * 70)
    print("  分析完成！输出目录:", output_dir)
    print("=" * 70)

    return {
        'chain_structures': chain_structures,
        'all_edges': all_edges,
        'expanded': expanded,
        'output_dir': output_dir,
    }


def _save_statistics_report(output_dir: str, loader, analyzer, rel_engine, expander):
    """保存统计报告"""
    report_path = os.path.join(output_dir, 'analysis_report.txt')

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("=" * 70 + "\n")
        f.write("  产业链关系分析报告\n")
        f.write("=" * 70 + "\n\n")

        # 标的统计
        f.write("一、标的统计\n")
        f.write("-" * 40 + "\n")
        f.write(f"标的总数: {len(loader.targets)}\n")
        for ind in loader.get_all_industries():
            targets = loader.get_targets_by_industry(ind)
            f.write(f"  {ind}: {len(targets)}个标的\n")

        # 产业链分析
        f.write("\n二、产业链层级分布\n")
        f.write("-" * 40 + "\n")
        for s in analyzer.get_industry_summary():
            f.write(f"  {s['industry']}: 上游{s['upstream_nodes']} | "
                    f"中游{s['midstream_nodes']} | 下游{s['downstream_nodes']} | "
                    f"标的{s['total_targets']}\n")

        # 关系统计
        f.write("\n三、关系网络统计\n")
        f.write("-" * 40 + "\n")
        stats = rel_engine.get_statistics()
        for rtype, info in stats.items():
            f.write(f"  {rtype}: 总计{info['total']}条 | "
                    f"行业内{info['intra_industry']} | 跨行业{info['cross_industry']} | "
                    f"平均权重{info['avg_weight']:.1f}\n")

        # 知识扩充统计
        f.write("\n四、知识扩充统计\n")
        f.write("-" * 40 + "\n")
        f.write(f"  扩充关系总数: {len(expander.expanded_relations)}\n")
        for rtype in ['supply_chain', 'competition', 'collaboration']:
            count = len(expander.get_expanded_by_type(rtype))
            f.write(f"  {rtype}: {count}条\n")

    print(f"  统计报告已保存: {report_path}")


if __name__ == '__main__':
    args = parse_args()
    result = run_analysis(
        csv_path=args.csv,
        config_dir=args.config_dir,
        output_dir=args.output_dir,
        industry=args.industry,
        relation_type=args.relation,
    )