#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
宏观经济分析系统 - 主运行脚本
================================
组装各子系统模块，执行完整的宏观经济数据分析流程：
  1. 数据获取（公用 data_service + 系统特有 data_service）
  2. 多维度分析（macro_analysis_system/analysis）
  3. 可视化生成（公用 visualization + 系统特有 visualization）
  4. 结果输出（output/）

Usage:
    python scripts/run_macro_analysis.py
    # 或从 AiStock 根目录:
    python -m macro_analysis_system.scripts.run_macro_analysis
"""

import sys
import os

# 将 AiStock 项目根目录加入 Python 路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from base_services.config_service import ConfigService
from base_services.cache_service import CacheService
from base_services.logger_service import LoggerService
from data_services.database_reader import DatabaseReader
from data_services.tdx_adapter import TDXAdapter
# from macro_analysis_system.data_service.data_loader_service import DataLoaderService
from data_services.data_loading_service import DataLoadingService
from macro_analysis_system.analysis.macro_analyzer import MacroAnalyzer
from macro_analysis_system.analysis.result_repository import ResultRepository
from macro_analysis_system.analysis.filter_engine import FilterEngine
from macro_analysis_system.analysis.summary_generator import SummaryGenerator
from macro_analysis_system.analysis.cache_manager import AnalysisCacheManager
from visualization.config.theme_config import get_default_theme
from macro_analysis_system.visualization.macro_chart_engine import MacroChartEngine
from macro_analysis_system.visualization.report_service import ReportService


def main():
    """主程序入口"""
    print("=" * 60)
    print("    中国宏观经济数据分析与可视化系统")
    print("=" * 60)

    # ---- 1. 初始化基础服务 ----
    config = ConfigService(system_name='macro_analysis')
    cache = CacheService(max_size=2000,ttl= 300)
    log_service = LoggerService()
    logger = log_service.get_logger('main')

    # ---- 2. 初始化数据层 ----
    db_cfg = config.get('database', {})
    db_server = DatabaseReader(
            db_config=db_cfg.get('DATABASE_ENGINES', {}),
            pool_config=db_cfg.get('DB_POOL_CONFIG', {})
        )
    tdx_cfg = config.get('tdx', {})

    tdx_adapter = TDXAdapter(tdx_cfg) if tdx_cfg.get('use_tdx') else None
    data_loader = DataLoadingService(
            config_service=config,
            cache_service=cache,
            database_reader=db_server,
            tdx_adapter=tdx_adapter,
            enable_cache=True
        )

    # ---- 3. 执行分析 ----
    logger.info("开始宏观数据分析...")
    analyzer = MacroAnalyzer(data_loader=data_loader)
    outlook = analyzer.run_full_analysis()

    # ---- 4. 输出分析结果 ----
    print(f"\n{'='*40}")
    print(f"  综合评分: {outlook['total_score']:.0f}")
    print(f"  经济状态: {outlook['status']}")
    print(f"  经济展望: {outlook['outlook'][:60]}...")
    print(f"{'='*40}")

    print("\n各维度评分:")
    for key, score in outlook['category_scores'].items():
        bar = '█' * int(score / 5) + '░' * (20 - int(score / 5))
        print(f"  {key:20s} [{bar}] {score:.0f}")

    # 信号过滤与汇总
    filter_engine = FilterEngine()
    signals = filter_engine.extract_signals(analyzer.analysis)
    summary = filter_engine.get_summary(signals)

    print(f"\n信号统计: 正面{summary['positive']} / 负面{summary['negative']} / 中性{summary['neutral']}")

    summary_gen = SummaryGenerator()
    text_summary = summary_gen.generate_text(outlook, analyzer.analysis, include_signals=True)
    print(text_summary)

    # ---- 5. 生成可视化 ----
    print(f"\n[2/3] 正在生成可视化图表...")
    theme = get_default_theme()
    chart_engine = MacroChartEngine(
        data=analyzer.data,
        analysis=analyzer.analysis,
        theme=theme,
    )
    figures = chart_engine.generate_all(outlook)
    print(f"  已生成 {len(figures)} 个图表")

    # ---- 6. 生成报告 ----
    print(f"\n[3/3] 正在生成HTML报告...")
    report_service = ReportService(chart_engine=chart_engine)
    output_dir = os.path.join(PROJECT_ROOT, 'output', 'visualization')
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, 'macro_analysis_report.html')
    report_service.save_html(output_path, outlook, analyzer.analysis, figures)

    # ---- 7. 保存分析结果 ----
    repo = ResultRepository()
    repo.save('macro_analysis', outlook, analyzer.analysis, analyzer.get_latest_snapshot())

    # ---- 8. 关闭连接 ----
    tdx_adapter.disconnect()

    print(f"\n{'='*60}")
    print(f"  分析完成！")
    print(f"  HTML报告: {output_path}")
    print(f"  综合评分: {outlook['total_score']:.0f} | 状态: {outlook['status']}")
    print(f"{'='*60}")

    return outlook


if __name__ == '__main__':
    main()