"""AiStock V9 市场状态量化系统

核心模块:
  core.contract_manager             — 动态合约代码推导引擎 (V7移植 + code/code_name双码制)
  core.option_code_parser           — 统一期权代码解析器 (3格式)
  core.option_pcr_engine            — 期权PCR计算引擎
  core.overseas_futures_signal_engine — 外盘期货四维信号引擎
  utils.date_utils                  — 交易日历与日期工具
  visualization.state_visualizer    — 可视化图表生成器
"""

__version__ = "9.0.0"
