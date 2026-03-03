# A股市场状态量化系统 V6.0

## 📊 系统概述

V6.0微服务化架构系统，基于四维一体决策框架（股票+期权+期货+商品+宏观），提供18大核心图表可视化分析。

## ✨ 核心特性

- ✅ **完全微服务化**：11个独立业务服务，无循环依赖
- ✅ **18大图表完整实现**：修复Plotly序列化错误，强制Python原生类型
- ✅ **配置热更新**：YAML配置动态加载，支持版本回滚
- ✅ **服务熔断/限流**：API网关提供生产级保护
- ✅ **跨市场联动**：新增A股/港股/美股/汇率/美债分析
- ✅ **行业轮动矩阵**：新增20日行业收益率分析
- ✅ **股指期货基差**：新增IF/IH/IC/IM四大股指基差分析

## 🚀 快速开始

### 安装依赖

```bash
pip install -r requirements/base.txt
pip install -r requirements/dev.txt  # Jupyter开发环境

```

### 初始化项目

``` bash

cd scripts
bash setup_project_structure.sh

```

### Jupyter开发

```bash

cd notebooks
jupyter notebook example_integration_v6.ipynb

```

### 生成可视化报告

``` python

from main_system.market_state_system_v6 import MarketStateSystemV6_0

system = MarketStateSystemV6_0('./config/system_config_v6.yaml')
result = system.run()
system.show_in_jupyter()  # 生成18大图表

```

### 项目结构

``` text

market_state_system_v6/
├── config/                  # 配置文件（YAML）
├── services/                # 11个业务微服务
├── infrastructure/          # 通信层+基础服务
├── main_system/             # 主系统协调层
├── utils/                   # 工具函数
├── notebooks/               # Jupyter开发示例
├── reports/                 # 可视化报告输出
├── logs/                    # 系统日志
├── cache/                   # 运行时缓存
└── ...

```