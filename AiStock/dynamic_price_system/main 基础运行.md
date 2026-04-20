##### 模拟盘模式（默认）
python dynamic_price_system/main.py

##### 指定标的 + 导出 PNG
python dynamic_price_system/main.py --stocks 600938 601899 --export png

##### 跳过可视化（提升批量计算性能）
python dynamic_price_system/main.py --skip-viz

##### 回测模式（需配合 run_backtest.py 或传入 --date）
python dynamic_price_system/main.py --mode backtest --date 2026-03-15