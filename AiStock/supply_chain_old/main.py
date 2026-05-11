#!/usr/bin/env python3
import sys
import os
from pathlib import Path
import argparse
import pandas as pd
# 1. 路径配置 (核心修复)
# try:
#     # 获取当前脚本 main.py 的绝对路径
#     PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
# except NameError:
#     # 兼容交互式环境 (如 Python Shell / Jupyter)，回退到当前工作目录
#     PROJECT_ROOT = os.getcwd()

# # 将项目根目录插入到 sys.path 的最前面
# if PROJECT_ROOT not in sys.path:
#     sys.path.insert(0, PROJECT_ROOT)
#     print(f"INFO: Added project root to sys.path: {PROJECT_ROOT}")

# 2. 导入业务模块 (现在 src 可以被识别了)
from src.core.loader import ConfigLoader
from src.visualizers.sankey import SankeyVisualizer
from src.visualizers.radar import RadarVisualizer
from src.visualizers.timeline import TimelineVisualizer
from src.dashboard.assembler import DashboardAssembler
from src.exporters.io_manager import IOManager
from src.utils.helpers import setup_logging


def main():
    parser = argparse.ArgumentParser(description="十五五产业链图谱生成器")
    parser.add_argument("--config", default="config/supply_chain_config.yaml")
    parser.add_argument("--output-dir", default="output")
    args = parser.parse_args()

    logger = setup_logging()
    logger.info("🚀 启动十五五产业链可视化引擎...")

    # 1. 加载配置
    loader = ConfigLoader(args.config)
    cfg_bundle = loader.load()
    data = cfg_bundle["data"]
    settings = cfg_bundle["settings"]

    # 2. 初始化组件
    io = IOManager(args.output_dir)
    theme = data.get("visual_style", {})
    sankey = SankeyVisualizer(theme)
    radar = RadarVisualizer(theme)
    timeline = TimelineVisualizer(theme)

    # 3. 生成子图
    figures = []
    chain_keys = list(data["supply_chains"].keys())
    titles = ["十大方向综合评估", "时间线规划"] + [data["supply_chains"][k]["name"] for k in chain_keys]
    
    figures.append(radar.render(data))
    figures.append(timeline.render(data["timeline"]))
    for k in chain_keys:
        figures.append(sankey.render(data["supply_chains"][k]))

    # 4. 组装仪表盘
    cols = 2
    rows = (len(figures) + cols - 1) // cols
    
    # 修复 specs 生成逻辑：明确指定每个位置的图表类型，避免未定义变量报错
    specs = []
    for r in range(rows):
        row_specs = []
        for c in range(cols):
            if r == 0 and c == 0:
                row_specs.append({"type": "scatterpolar"}) # 雷达图
            elif r == 0 and c == 1:
                row_specs.append({"type": "bar"})          # 时间线
            else:
                row_specs.append({"type": "sankey"})       # 产业链桑基图
        specs.append(row_specs)
        
    assembler = DashboardAssembler(specs, titles)
    dashboard = assembler.compose(figures)

    # 5. 导出
    io.save_html(dashboard, "全景仪表盘")
    
    # 导出指标表
    indicators = []
    for chain, inds in data["global_indicators"].items():
        chain_name = data["supply_chains"].get(chain, {}).get("name", chain)
        for ind in inds:
            indicators.append({
                "方向": chain_name,
                "指标": ind["name"],
                "当前值": ind.get("current", "-"),
                "2030目标": ind["target"]
            })
    io.save_excel(pd.DataFrame(indicators), "关键指标对比")

    logger.info("✅ 生成完成！产物已保存至: %s", Path(args.output_dir).absolute())

if __name__ == "__main__":
    main()