# supply_chain/main.py
import sys
from pathlib import Path
from src.loader import ChainConfigLoader
from src.builder import GraphDataBuilder
from src.visualizer import SankeyRenderer

def main():
    project_root = Path(__file__).parent
    config_file = project_root / "config" / "chain_config.yaml"
    output_file = project_root / "output" / "industry_target_network.html"

    try:
        print("📦 加载产业链与标的拓扑配置...")
        config = ChainConfigLoader(config_file).load()

        print("🔗 构建节点索引与关系链路...")
        graph_data = GraphDataBuilder.build(config)
        if not graph_data["links"]["source"]:
            raise ValueError("未解析到有效链路，请检查 links 字段配置。")

        print("🎨 渲染 Plotly 交互式图谱...")
        SankeyRenderer().render(graph_data, output_file)
        
    except Exception as e:
        print(f"❌ 执行中断: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()