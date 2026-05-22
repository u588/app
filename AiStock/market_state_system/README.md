/home/ts/app/AiStock/
│
├── config/                              # 【多系统共用配置层】
│   ├── market_state_system/
│   │   └── system_config.yaml           # V7完整配置(443行,20个顶级节)
│   ├── global_settings.py               # 全局常量(85行)
│   └── .env                             # 环境变量(27行)
│
├── base_services/                        # 【多系统公用服务层】
│   ├── __init__.py
│   ├── config_service.py                # ConfigService(323行): YAML热重载+多系统隔离
│   ├── cache_service.py                 # CacheService(133行): LRU+TTL+统计
│   └── logger_service.py                # LoggerService(662行): 彩色/JSON/轮转
│
├── data_service/                         # 【数据接入层】
│   ├── __init__.py
│   ├── data_loader_service.py           # DataLoadingService(345行): 三类市场路由+缓存协调
│   ├── database_reader.py              # DatabaseReader(142行): PostgreSQL只读+连接池
│   ├── tdx_adapter.py                  # TDXAdapter(628行): 三类市场分离+自动重连
│   └── ak_adapter.py                   # AKAdapter(378行): 外盘期货+AkShare集成
│
├── market_state_system/                 # 【市场状态量化系统】
│   ├── __init__.py
│   ├── config/                          # 系统专属配置(符号链接或独立)
│   ├── core/                            # 核心计算引擎
│   │   ├── __init__.py
│   │   ├── contract_manager.py          # ContractManager(1321行): 动态合约推导
│   │   ├── derivatives_signal_engine.py # DerivativesSignalEngine(266行): 衍生品信号
│   │   ├── market_regime_engine.py      # MarketRegimeEngine(379行): Regime检测
│   │   ├── market_state_classifier.py   # MarketStateClassifier(494行): 3D状态分类
│   │   └── risk_assessment_engine.py    # RiskAssessmentEngine(362行): 风险评估+PCR
│   ├── visualization/                   # 可视化服务层
│   │   ├── __init__.py
│   │   └── state_visualizer.py          # StateVisualizer(275行): 4种图表
│   └── utils/                           # 工具层
│       ├── __init__.py
│       └── date_utils.py                # 日期工具(151行): 交割日/交易日判断
│
├── main.py                              # 系统入口(437行): 完整6步流水线
├── logs/                                # 日志目录
├── data/                                # 本地数据缓存
└── output/
    ├── analysis_results/                 # 分析结果存储
    └── visualization/                    # 可视化输出