#!/usr/bin/env python3
"""
产业链分析系统 - 主入口
功能：读取标的池数据 → 产业链上中下游分析 → 关系构建 → Pyvis + Plotly可视化
"""

import os
import sys
import argparse
import shutil

# 添加项目路径
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)

from modules.config_loader import ConfigLoader
from modules.data_loader import DataLoader
from modules.chain_analyzer import ChainAnalyzer
from modules.relation_builder import RelationBuilder
from modules.visualizer import SupplyChainVisualizer
from modules.plotly_builder import PlotlyBuilder
from modules.dashboard import DashboardBuilder


def copy_outputs_to_dirs(src_dir: str):
    """将输出文件复制到download目录"""
    download_dir = '/home/ts/app/AiStock/supply_chain/download'
    os.makedirs(download_dir, exist_ok=True)
    try:
        for fname in os.listdir(src_dir):
            if fname.endswith('.html'):
                src = os.path.join(src_dir, fname)
                dst = os.path.join(download_dir, fname)
                shutil.copy2(src, dst)
    except Exception as e:
        print(f"  (下载目录复制失败: {e})")


def main():
    parser = argparse.ArgumentParser(description='产业链分析系统')
    parser.add_argument('--mode',
                        choices=['full', 'direction', 'all', 'report', 'plotly', 'dashboard'],
                        default='all',
                        help='运行模式: full/pyvis全景 / direction/单方向 / all/全部 / report/报告 / plotly/Plotly图表 / dashboard/仪表盘')
    parser.add_argument('--direction', type=str, default=None, help='单方向模式下的方向名称')
    parser.add_argument('--no-stocks', action='store_true', help='不展示标的节点（仅赛道级）')
    parser.add_argument('--min-score', type=float, default=4.0, help='标的最低综合评分过滤')
    parser.add_argument('--config-dir', type=str, default=None, help='配置文件目录')
    parser.add_argument('--data-file', type=str, default=None, help='数据文件路径')
    args = parser.parse_args()

    print("=" * 60)
    print("  十大投资方向 · 产业链分析系统")
    print("=" * 60)

    # ===== 1. 初始化配置 =====
    config_dir = args.config_dir or os.path.join(PROJECT_DIR, 'config')
    print(f"\n[1/6] 加载配置 → {config_dir}")
    config = ConfigLoader(config_dir)
    validation = config.validate()
    for name, status in validation.items():
        symbol = "✓" if status is True else "✗"
        print(f"  {symbol} {name}: {status}")

    # ===== 2. 加载数据 =====
    data_file = args.data_file or '/home/ts/app/Ai投研/十大投资方向分类体系标的池（2026.5）.xlsx'
    print(f"\n[2/6] 加载数据 → {data_file}")
    data = DataLoader(data_file)
    data.load()
    summary = data.summary()
    print(f"  一级方向: {summary['total_directions']}个")
    print(f"  二级分类: {summary['total_categories']}个")
    print(f"  三级赛道: {summary['total_tracks']}个")
    print(f"  标的数量: {summary['total_stocks']}只")

    # ===== 3. 产业链分析 =====
    print(f"\n[3/6] 产业链上中下游分析")
    chain = ChainAnalyzer(config, data)
    chain.analyze()
    distribution = chain.get_chain_distribution()
    for dir_name, dist in distribution.items():
        upstream_count = dist['upstream']['stock_count']
        midstream_count = dist['midstream']['stock_count']
        downstream_count = dist['downstream']['stock_count']
        print(f"  {dir_name}: 上游{upstream_count}只 / 中游{midstream_count}只 / 下游{downstream_count}只")

    # ===== 4. 关系构建 =====
    print(f"\n[4/6] 构建供应链/竞争/协同/验证关系")
    rel_builder = RelationBuilder(config, data, chain)
    graph = rel_builder.build()
    stats = graph.stats
    for rt, count in stats.items():
        label = RelationBuilder.TYPE_LABELS.get(rt, rt)
        print(f"  {label}: {count}条")

    # ===== 5. Pyvis网络图可视化 =====
    src_dir = os.path.join(PROJECT_DIR, 'output')
    include_stocks = not args.no_stocks

    if args.mode == 'report':
        report = chain.generate_report()
        print(f"\n{report}")
        return

    if args.mode in ('full', 'all'):
        print(f"\n[5/6] Pyvis网络图可视化")
        visualizer = SupplyChainVisualizer(config, data, chain, rel_builder)
        if args.mode == 'full':
            path = visualizer.create_full_network(include_stocks=include_stocks,
                                                   min_stock_score=args.min_score)
            print(f"  ✓ 全景图: {path}")
        elif args.mode == 'all':
            results = visualizer.generate_all(include_stocks=include_stocks)
            print(f"  共生成 {len(results)} 个Pyvis可视化文件")

    if args.mode == 'direction':
        print(f"\n[5/6] Pyvis方向图")
        visualizer = SupplyChainVisualizer(config, data, chain, rel_builder)
        if not args.direction:
            print("  请指定 --direction 参数")
            return
        path = visualizer.create_direction_network(args.direction)
        print(f"  ✓ {args.direction}: {path}")

    # ===== 6. Plotly交互式图表 =====
    if args.mode in ('plotly', 'dashboard', 'all'):
        print(f"\n[6/6] Plotly交互式图表生成")
        plotly_builder = PlotlyBuilder(config, data, chain, rel_builder)

        if args.mode == 'plotly':
            print("  生成14类独立图表...")
            results = plotly_builder.generate_all()
            print(f"  共生成 {len(results)} 个Plotly图表")

        elif args.mode == 'dashboard':
            dash_builder = DashboardBuilder(config, data, chain, rel_builder)
            results = dash_builder.generate_all_dashboards()
            print(f"  共生成 {len(results)} 个仪表盘")

        elif args.mode == 'all':
            # 独立图表
            print("  生成14类独立图表...")
            chart_results = plotly_builder.generate_all()
            print(f"  共生成 {len(chart_results)} 个Plotly图表")

            # 仪表盘
            dash_builder = DashboardBuilder(config, data, chain, rel_builder)
            dash_results = dash_builder.generate_all_dashboards()
            print(f"  共生成 {len(dash_results)} 个仪表盘")

    # 复制到下载目录
    # copy_outputs_to_dirs(src_dir)

    print("\n" + "=" * 60)
    print("  完成！")
    print("  Pyvis网络图 → output/supply_chain_*.html")
    print("  Plotly图表  → output/plotly_*.html")
    print("  仪表盘      → output/plotly_dashboard_*.html")
    print("=" * 60)


if __name__ == '__main__':
    main()
