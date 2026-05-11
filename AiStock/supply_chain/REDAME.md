fifteen_five_supply_chain/
── config/
│   ├── supply_chain_config.yaml   # 产业链数据与指标配置
│   └── app_settings.yaml          # 应用级设置（主题/输出路径/日志）
├── src/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   └── loader.py              # 配置加载与Schema校验
│   ├── visualizers/
│   │   ├── __init__.py
│   │   ├── base.py                # 公共主题/布局基类
│   │   ├── sankey.py              # 桑基图（产业链流向）
│   │   ├── radar.py               # 雷达图（方向对比）
│   │   └── timeline.py            # 时间线/甘特图
│   ├── dashboard/
│   │   ├── __init__.py
│   │   └── assembler.py           # 子图网格编排
│   ├── exporters/
│   │   ├── __init__.py
│   │   └── io_manager.py          # HTML/Excel/PNG 导出
│   └── utils/
│       ├── __init__.py
│       └── helpers.py             # 路径/日志/类型工具
├── output/                        # 自动生成的产物目录
├── pyproject.toml                 # 项目元数据
├── requirements.txt               # 依赖声明
├── main.py                        # CLI 入口
└── README.md                      # 使用说明