#!/usr/bin/env python3
"""
产业链分析系统 - 主入口
功能：读取标的池数据 → 产业链上中下游分析 → 关系构建 → Pyvis可视化
"""

import os
import sys
import argparse

# 添加项目路径
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)

from modules.config_loader import ConfigLoader
from modules.data_loader import DataLoader
from modules.chain_analyzer import ChainAnalyzer
from modules.relation_builder import RelationBuilder
from modules.visualizer import SupplyChainVisualizer


def main():
    parser = argparse.ArgumentParser(description='产业链分析系统')
    parser.add_argument('--mode', choices=['full', 'direction', 'all', 'report'],
                        default='all', help='运行模式: full(全景图) / direction(单方向) / all(全部) / report(仅报告)')
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
    print(f"\n[1/5] 加载配置 → {config_dir}")
    config = ConfigLoader(config_dir)
    validation = config.validate()
    for name, status in validation.items():
        symbol = "✓" if status is True else "✗"
        print(f"  {symbol} {name}: {status}")

    # ===== 2. 加载数据 =====
    data_file = args.data_file or '/home/ts/app/Ai投研/十大投资方向分类体系标的池（2026.5）.xlsx'
    print(f"\n[2/5] 加载数据 → {data_file}")
    data = DataLoader(data_file)
    data.load()
    summary = data.summary()
    print(f"  一级方向: {summary['total_directions']}个")
    print(f"  二级分类: {summary['total_categories']}个")
    print(f"  三级赛道: {summary['total_tracks']}个")
    print(f"  标的数量: {summary['total_stocks']}只")

    # ===== 3. 产业链分析 =====
    print(f"\n[3/5] 产业链上中下游分析")
    chain = ChainAnalyzer(config, data)
    chain.analyze()
    distribution = chain.get_chain_distribution()

    for dir_name, dist in distribution.items():
        upstream_count = dist['upstream']['stock_count']
        midstream_count = dist['midstream']['stock_count']
        downstream_count = dist['downstream']['stock_count']
        print(f"  {dir_name}: 上游{upstream_count}只 / 中游{midstream_count}只 / 下游{downstream_count}只")

    # ===== 4. 关系构建 =====
    print(f"\n[4/5] 构建供应链/竞争/协同/验证关系")
    rel_builder = RelationBuilder(config, data, chain)
    graph = rel_builder.build()
    stats = graph.stats
    for rt, count in stats.items():
        label = RelationBuilder.TYPE_LABELS.get(rt, rt)
        print(f"  {label}: {count}条")

    track_summary = rel_builder.get_track_relation_summary()
    stock_summary = rel_builder.get_stock_relation_summary()
    print(f"\n  赛道级关系:")
    for rt, info in track_summary.items():
        print(f"    {RelationBuilder.TYPE_LABELS.get(rt, rt)}: {info['count']}条, 平均权重={info['avg_weight']}")
    print(f"\n  标的级关系:")
    for rt, info in stock_summary.items():
        print(f"    {RelationBuilder.TYPE_LABELS.get(rt, rt)}: {info['count']}条")

    # ===== 5. 可视化 =====
    include_stocks = not args.no_stocks

    if args.mode == 'report':
        report = chain.generate_report()
        print(f"\n{report}")
        return

    print(f"\n[5/5] Pyvis可视化生成")
    visualizer = SupplyChainVisualizer(config, data, chain, rel_builder)

    if args.mode == 'full':
        path = visualizer.create_full_network(include_stocks=include_stocks,
                                               min_stock_score=args.min_score)
        print(f"  ✓ 全景图: {path}")

    elif args.mode == 'direction':
        if not args.direction:
            print("  请指定 --direction 参数")
            return
        path = visualizer.create_direction_network(args.direction)
        print(f"  ✓ {args.direction}: {path}")

    elif args.mode == 'all':
        results = visualizer.generate_all(include_stocks=include_stocks)
        print(f"\n  共生成 {len(results)} 个可视化文件:")
        for name, path in results.items():
            print(f"    {name}: {path}")

    # 同时复制到目标路径
    target_dir = '/home/ts/app/AiStock/supply_chain/output'
    src_dir = os.path.join(PROJECT_DIR, 'output')
    try:
        os.makedirs(target_dir, exist_ok=True)
        for fname in os.listdir(src_dir):
            if fname.endswith('.html'):
                src = os.path.join(src_dir, fname)
                dst = os.path.join(target_dir, fname)
                import shutil
                shutil.copy2(src, dst)
                print(f"  → 已同步到目标路径: {dst}")
    except Exception as e:
        print(f"  (目标路径同步跳过: {e})")

    # 同时复制到download目录
    download_dir = '/home/ts/app/AiStock/supply_chain/download'
    os.makedirs(download_dir, exist_ok=True)
    try:
        for fname in os.listdir(src_dir):
            if fname.endswith('.html'):
                src = os.path.join(src_dir, fname)
                dst = os.path.join(download_dir, fname)
                import shutil
                shutil.copy2(src, dst)
                print(f"  → 已复制到下载目录: {dst}")
    except Exception as e:
        print(f"  (下载目录复制失败: {e})")

    print("\n" + "=" * 60)
    print("  完成！请在浏览器中打开HTML文件查看交互式产业链图谱")
    print("=" * 60)


if __name__ == '__main__':
    main()