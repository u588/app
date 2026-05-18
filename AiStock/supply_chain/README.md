supply_chain/
├── config/                          # YAML配置文件
│   ├── industry_chain.yaml          # 产业链上中下游分类配置
│   ├── relations.yaml               # 赛道级4种关系配置（供应链/竞争/协同/验证）
│   ├── stock_relations.yaml          # 标的级4种关系配置
│   └── visual.yaml                  # 可视化参数配置
├── modules/                         # 解耦Python模块
│   ├── config_loader.py             # YAML配置加载器
│   ├── data_loader.py               # Excel数据加载与结构化
│   ├── chain_analyzer.py            # 产业链上中下游分析引擎
│   ├── relation_builder.py          # 四种关系构建引擎
│   └── visualizer.py                # Pyvis可视化引擎
├── main.py                          # 主入口（支持命令行参数）
└── output/                          # 生成的交互式HTML文件