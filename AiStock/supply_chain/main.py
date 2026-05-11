#!/usr/bin/env python3
import argparse
from pathlib import Path
import pandas as pd

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
    specs = [[{"type": "scatterpolar" if i==0 else "bar" if i==1 else "sankey"} 
              for _ in range(cols)] for _ in range(rows)]
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