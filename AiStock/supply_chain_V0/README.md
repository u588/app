#### 文件系统

/home/ts/app/AiStock/supply_chain
├── config/                          # YAML配置层
│   ├── industry_chain.yaml          # 产业链上中下游定义（10个行业×3层级）
│   ├── relationships.yaml           # 四大关系规则（供应链/竞争/协同/验证）
│   └── visualization.yaml           # 可视化样式配置（暗色主题/颜色/物理引擎）
├── core/                            # 核心分析层
│   ├── data_loader.py               # 数据加载器（CSV+YAML）
│   ├── industry_analyzer.py         # 产业链分析引擎（上中下游映射）
│   ├── relationship_engine.py       # 关系构建引擎（四大关系自动+手动构建）
│   └── knowledge_expander.py        # 知识扩充器（5种扩充策略）
├── visualization/                   # 可视化层
│   ├── style_manager.py             # 样式管理器（行业颜色/层级形状/边样式）
│   ├── network_builder.py           # 网络构建器（pyvis图构建）
│   └── renderer.py                  # 渲染器（HTML注入图例/统计/交互控件）
├── output/                          # 输出目录
└── main.py                          # 主入口

##### 全量分析

python main.py --csv /home/ts/app/AiStock/supply_chain/data/targets.csv

##### 单行业

python main.py --csv ... --industry 半导体国产化

##### 单关系类型

python main.py --csv ... --relation supply_chain
