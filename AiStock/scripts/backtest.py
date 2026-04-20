#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
回测执行入口
"""

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dynamic_price_system.run_backtest import BacktestEngine
from base_services.config_service import ConfigService
from data_services.data_loading_service import DataLoadingService

def prepare_backtest_data(
    start_date: str,
    end_date: str,
    stock_codes: List[str],
    config: ConfigService
) -> tuple:
    """准备回测所需数据"""
    loader = DataLoadingService(
        config_service=config,
        cache_service=None,
        database_reader=None,
        enable_cache=True
    )
    
    # 加载价格数据
    price_data = {}
    for code in stock_codes:
        df = loader.load_stock_daily(code, min_days=500)
        if df is not None and not df.empty:
            # 过滤时间区间
            mask = (df['datetime'] >= start_date) & (df['datetime'] <= end_date)
            price_data[code] = df[mask].copy()
    
    # 生成模拟信号（实际应调用 DynamicPriceEngine 按日计算）
    # 简化版：每周根据最新评分生成信号
    signals = []
    dates = pd.date_range(start_date, end_date, freq='W-FRI')  # 每周五调仓
    
    for date in dates:
        # 此处应调用引擎计算当日信号，简化为随机权重演示
        for code in stock_codes:
            if code in price_data and len(price_data[code]) > 0:
                signals.append({
                    'date': date,
                    'code': code,
                    'signal_type': 'weight',
                    'weight': np.random.uniform(0, 0.15)  # 随机 0~15% 权重
                })
    
    signals_df = pd.DataFrame(signals)
    return signals_df, price_data

def main():
    parser = argparse.ArgumentParser(description='AiStock 回测引擎')
    parser.add_argument('--start', type=str, required=True, help='开始日期 (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, required=True, help='结束日期 (YYYY-MM-DD)')
    parser.add_argument('--stocks', nargs='+', default=None, help='标的代码列表')
    parser.add_argument('--output', type=str, default='output/backtest_result.json', help='结果输出路径')
    args = parser.parse_args()
    
    # 1. 加载配置
    config = ConfigService(system_name='dynamic_price')
    stock_codes = args.stocks or [s['code'] for s in config.get('stocks', [])]
    
    # 2. 准备数据
    print(f"📥 准备回测数据: {args.start} ~ {args.end} | 标的数:{len(stock_codes)}")
    signals_df, price_data = prepare_backtest_data(args.start, args.end, stock_codes, config)
    
    # 3. 执行回测
    print("🔄 执行回测...")
    engine = BacktestEngine(
        initial_capital=1_000_000,
        commission_rate=0.0003,
        slippage_rate=0.001
    )
    
    metrics = engine.run(args.start, args.end, signals_df, price_data)
    
    # 4. 输出结果
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    result = {
        'period': {'start': args.start, 'end': args.end},
        'metrics': metrics,
        'trades': engine.trades[:100],  # 仅保存前 100 笔交易
        'nav_sample': engine.nav_history[::10]  # 每 10 天采样
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"\n📊 回测结果:")
    for k, v in metrics.items():
        print(f"  • {k}: {v}")
    print(f"\n✅ 结果已保存: {output_path}")

if __name__ == '__main__':
    main()