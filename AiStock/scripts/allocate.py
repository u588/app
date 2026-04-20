#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
资产配置脚本：根据动态价格计算结果生成目标权重
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
import yaml

# 路径注入
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dynamic_price_system.core.dynamic_price_engine import DynamicPriceEngine
from base_services.config_service import ConfigService
from base_services.cache_service import CacheService

def load_portfolio_config(config_path: str) -> dict:
    """加载组合配置"""
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def calculate_target_weights(
    results: list,
    config: dict
) -> dict:
    """
    根据计算结果计算目标权重
    
    参数:
        results: DynamicPriceEngine 计算结果列表
        config: 组合配置字典
    
    返回:
        {code: weight} 目标权重字典
    """
    portfolio_cfg = config.get('portfolio', {})
    weighting_cfg = config.get('weighting', {})
    
    # 1. 筛选符合条件的标的
    min_pl = portfolio_cfg.get('min_pl_ratio', 2.0)
    min_score = portfolio_cfg.get('min_fundamental_score', 60)
    
    candidates = [
        r for r in results 
        if r['scores']['pl_ratio'] >= min_pl 
        and r['scores']['fundamental_score'] >= min_score
    ]
    
    if not candidates:
        print("⚠️ 无符合条件的标的，返回空组合")
        return {}
    
    # 2. 计算综合得分（可配置权重）
    score_weights = weighting_cfg.get('score_weights', {
        'pl_ratio': 0.5, 'fundamental_score': 0.3, 'macro_factor': 0.2
    })
    
    for r in candidates:
        # 标准化各指标到 0-1 区间
        pl_norm = min(r['scores']['pl_ratio'] / 5.0, 1.0)  # 假设最大盈亏比 5
        fin_norm = r['scores']['fundamental_score'] / 100
        macro_norm = min((r['factors']['macro'] - 0.9) / 0.2, 1.0)  # 0.9~1.1 → 0~1
        
        r['composite_score'] = (
            pl_norm * score_weights['pl_ratio'] +
            fin_norm * score_weights['fundamental_score'] +
            macro_norm * score_weights['macro_factor']
        )
    
    # 3. 按综合得分分配权重
    total_score = sum(r['composite_score'] for r in candidates)
    raw_weights = {
        r['code']: r['composite_score'] / total_score 
        for r in candidates
    }
    
    # 4. 应用约束：单标的/单板块上限
    max_single = portfolio_cfg.get('max_position_single', 0.15)
    max_sector = portfolio_cfg.get('max_position_sector', 0.30)
    
    # 按板块聚合
    sector_weights = {}
    for r in candidates:
        sector = r['sector']
        sector_weights[sector] = sector_weights.get(sector, 0) + raw_weights[r['code']]
    
    # 板块约束调整
    for sector, weight in sector_weights.items():
        if weight > max_sector:
            scale = max_sector / weight
            for r in candidates:
                if r['sector'] == sector:
                    raw_weights[r['code']] *= scale
    
    # 单标的约束调整
    for code in list(raw_weights.keys()):
        if raw_weights[code] > max_single:
            raw_weights[code] = max_single
    
    # 5. 归一化权重
    total = sum(raw_weights.values())
    if total > 0:
        target_weights = {k: v/total for k, v in raw_weights.items()}
    else:
        target_weights = {}
    
    return target_weights

def main():
    """主函数：执行资产配置"""
    # 1. 加载配置
    config = ConfigService(system_name='dynamic_price')
    portfolio_config = load_portfolio_config(
        PROJECT_ROOT / 'config' / 'dynamic_price' / 'portfolio_config.yaml'
    )
    
    # 2. 初始化服务
    cache = CacheService(max_size=2000, ttl=3600)
    engine = DynamicPriceEngine(config_service=config)
    
    # 3. 加载数据并计算
    from data_services.data_loading_service import DataLoadingService
    loader = DataLoadingService(
        config_service=config,
        cache_service=cache,
        database_reader=None,  # 按需注入
        enable_cache=True
    )
    
    # 加载宏观数据
    macro_codes = ['brent_crude', 'comex_gold', 'pmi', 'm2_growth']
    macro_data = loader.load_all_macro_indicators(macro_codes)
    
    # 批量计算动态价格
    stock_configs = config.get('stocks', [])
    batch_inputs = []
    for sc in stock_configs:
        code = sc['code']
        stock_data = loader.load_stock_daily(code, min_days=200)
        if stock_data is None or stock_data.empty:
            continue
        batch_inputs.append({
            'code': code,
            'sector': sc['sector'],
            'stock_data': stock_data,
            'financial_data': {},  # 按需加载财务数据
            'macro_data': macro_data,
            'stock_params': sc.get('params', {})
        })
    
    results = engine.calculate_batch(batch_inputs)
    
    # 4. 计算目标权重
    target_weights = calculate_target_weights(results, portfolio_config)
    
    # 5. 输出结果
    print("\n📋 目标组合权重:")
    for code, weight in sorted(target_weights.items(), key=lambda x: -x[1]):
        stock = next((s for s in stock_configs if s['code'] == code), {})
        print(f"  • {code} {stock.get('name', '')}: {weight:.1%} | "
              f"板块:{stock.get('sector')} | "
              f"盈亏比:{next((r['scores']['pl_ratio'] for r in results if r['code']==code), 0):.1f}x")
    
    # 6. 保存配置（供交易模块使用）
    import json
    output_path = PROJECT_ROOT / 'output' / 'target_weights.json'
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump({
            'timestamp': pd.Timestamp.now().isoformat(),
            'weights': target_weights,
            'total_positions': len(target_weights)
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 配置已保存: {output_path}")

if __name__ == '__main__':
    main()