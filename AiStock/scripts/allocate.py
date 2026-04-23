#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
资产配置脚本：根据动态价格计算结果生成目标权重（优化版）
✅ 支持命令行参数覆盖配置
✅ 优雅停机 + 线程安全
✅ 详细调试日志 + 诊断报告
"""

import sys
import argparse
import logging
import json
import signal
from pathlib import Path
from datetime import datetime
from contextlib import contextmanager

# 路径注入
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from base_services.config_service import ConfigService
from base_services.cache_service import CacheService
from dynamic_price_system.core.dynamic_price_engine import DynamicPriceEngine


# 配置日志
def setup_logging(level: str = "INFO"):
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    return logging.getLogger("Allocate")

logger = setup_logging()

@contextmanager
def graceful_shutdown(services):
    """确保服务优雅关闭"""
    try:
        yield
    except KeyboardInterrupt:
        logger.info("⌨️ 用户中断，正在清理...")
    finally:
        for svc in reversed(services):  # 反向关闭（依赖顺序）
            if hasattr(svc, 'close'):
                try:
                    svc.close()
                except Exception as e:
                    logger.debug(f"清理 {type(svc).__name__} 失败: {e}")
        sys.exit(0)

def parse_args():
    parser = argparse.ArgumentParser(description="AiStock 资产配置")
    parser.add_argument("--mode", choices=["paper", "real"], default="paper")
    parser.add_argument("--stocks", nargs="+", help="指定标的代码")
    parser.add_argument("--min-pl", type=float, help="覆盖最小盈亏比阈值")
    parser.add_argument("--min-score", type=int, help="覆盖最小基本面评分")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG","INFO","WARNING"])
    parser.add_argument("--dry-run", action="store_true", help="仅输出不保存")
    return parser.parse_args()

def load_portfolio_config(config_service, args) -> dict:
    """加载并合并命令行覆盖的配置"""
    cfg = config_service.config.get('portfolio', {}).copy()
    weighting = config_service.config.get('weighting', {}).copy()
    
    # 命令行覆盖
    if args.min_pl is not None:
        cfg['min_pl_ratio'] = args.min_pl
        logger.info(f"🔄 覆盖 min_pl_ratio={args.min_pl}")
    if args.min_score is not None:
        cfg['min_fundamental_score'] = args.min_score
        logger.info(f"🔄 覆盖 min_fundamental_score={args.min_score}")
    
    return {'portfolio': cfg, 'weighting': weighting}

def calculate_target_weights(results: list, config: dict) -> dict:
    """计算目标权重（增强调试版）"""
    portfolio_cfg = config['portfolio']
    weighting_cfg = config['weighting']
    
    min_pl = portfolio_cfg.get('min_pl_ratio', 2.0)
    min_score = portfolio_cfg.get('min_fundamental_score', 60)
    
    # 🔍 调试日志
    logger.info(f"🔍 筛选条件: pl≥{min_pl}, score≥{min_score} | 总标的: {len(results)}")
    for r in results:
        code = r['code']
        pl = r['scores']['pl_ratio']
        fin = r['scores']['fundamental']
        ok = pl >= min_pl and fin >= min_score
        logger.debug(f"  {'✅' if ok else '❌'} {code}: pl={pl:.2f}, fin={fin:.1f}")
    
    candidates = [r for r in results if r['scores']['pl_ratio'] >= min_pl and r['scores']['fundamental'] >= min_score]
    
    if not candidates:
        # 🔍 诊断原因
        reasons = []
        if not results:
            reasons.append("计算结果为空")
        else:
            low_pl = [r['code'] for r in results if r['scores']['pl_ratio'] < min_pl]
            low_fin = [r['code'] for r in results if r['scores']['fundamental'] < min_score]
            if low_pl: reasons.append(f"盈亏比不足: {low_pl}")
            if low_fin: reasons.append(f"基本面不足: {low_fin}")
        logger.warning(f"⚠️ 无符合条件的标的 | 原因: {'; '.join(reasons)}")
        return {}
    
    logger.info(f"✅ 通过筛选: {len(candidates)} 只标的")
    
    # 2. 计算综合得分（可配置权重）
    score_weights = weighting_cfg.get('score_weights', {
        'pl_ratio': 0.5, 'fundamental_score': 0.3, 'macro_factor': 0.2
    })
    
    for r in candidates:
        # 标准化各指标到 0-1 区间
        pl_norm = min(r['scores']['pl_ratio'] / 5.0, 1.0)  # 假设最大盈亏比 5
        fin_norm = r['scores']['fundamental'] / 100
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

    total_score = sum(r['scores']['pl_ratio'] for r in candidates)
    
    return {r['code']: r['scores']['pl_ratio']/total_score for r in candidates}

def main():
    args = parse_args()
    global logger
    logger = setup_logging(args.log_level)
    
    logger.info(f"🚀 启动资产配置 | 模式:{args.mode} | 时间:{datetime.now().isoformat()}")
    
    # 初始化服务（禁用热重载避免线程警告）
    config = ConfigService(system_name='dynamic_price', enable_hot_reload=False)
    cache = CacheService(max_size=2000, ttl=3600)

    # 3. 加载数据并计算
        # 3. 数据库服务
    from data_services.database_reader import DatabaseReader
    db_cfg = config.get('database', {})
    db = DatabaseReader(
        db_config=db_cfg.get('DATABASE_ENGINES', {}),
        pool_config=db_cfg.get('DB_POOL_CONFIG', {})
    )
    
    # 4. 数据源适配器
    from data_services.tdx_adapter import TDXAdapter
    from data_services.ak_adapter import AKAdapter
    tdx_cfg = config.get('tdx', {})
    tdx = TDXAdapter(tdx_cfg) if tdx_cfg.get('use_tdx') else None
    ak = AKAdapter()    

        # 5. 数据加载服务
    from data_services.data_loading_service import DataLoadingService
        
    services = [config, cache]  # 注册清理列表
    
    with graceful_shutdown(services):
        # 加载配置
        portfolio_config = load_portfolio_config(config, args)
        
        # 初始化数据加载
        loader = DataLoadingService(
            config_service=config,
            cache_service=cache,
            database_reader=db,  # 按需注入
            tdx_adapter=tdx,
            ak_adapter=ak,
            enable_cache=True
        )
        services.append(loader)
        
        # 加载宏观数据
        macro_codes = ['brent_crude', 'comex_gold', 'pmi', 'm2_growth', 'cpi','ppi', 'china_10y_bond','lme_nickel', 'usd_cny','eua_carbon','lme_copper']
        logger.info("🌍 加载宏观数据...")
        macro_data = loader.load_all_macro_indicators(macro_codes)
        
        # 确定标的池
        all_stocks = config.get('stocks', [])
        target_stocks = [s for s in all_stocks if not args.stocks or s['code'] in args.stocks]
        logger.info(f"📋 标的池: {len(target_stocks)} 只")
        
        # 批量计算动态价格
        logger.info("🧮 执行动态价格计算...")
        engine = DynamicPriceEngine(config_service=config)
        batch_inputs = []
        
        for sc in target_stocks:
            code = sc['code']
            try:
                stock_data = loader.load_stock_daily(code, min_days=250)
                financial_data = loader.load_stock_financials(code).to_dict(orient='records')[0]
                if stock_data is None or stock_data.empty:
                    logger.warning(f"⚠️ 跳过 {code}: 行情数据不足")
                    continue
                batch_inputs.append({
                    'code': code,
                    'name': sc.get('name', ''), 
                    'sector': sc['sector'],
                    'stock_data': stock_data,
                    'financial_data': financial_data,  # 按需加载
                    'macro_data': macro_data,
                    'stock_params': sc.get('params', {})
                })
            except Exception as e:
                logger.error(f"❌ 加载 {code} 失败: {e}")
        
        if not batch_inputs:
            logger.error("❌ 无有效输入数据，流程终止")
            return
        
        results = engine.calculate_batch(batch_inputs)
        logger.info(f"✅ 计算完成: {len(results)}/{len(batch_inputs)} 成功")
        # print(results)
        # 计算权重
        target_weights = calculate_target_weights(results, portfolio_config)
        # print(target_weights)
        # 输出结果
        print("\n📋 目标组合权重:")
        if target_weights:
            for code, weight in sorted(target_weights.items(), key=lambda x: -x[1]):
                stock = next((s for s in all_stocks if s['code'] == code), {})
                print(f"  • {code} {stock.get('name', '')}: {weight:.1%}")
        else:
            print("  (空组合)")
        
        # 保存结果
        if not args.dry_run:
            output_path = PROJECT_ROOT / 'output' / 'target_weights.json'
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'timestamp': datetime.now().isoformat(),
                    'weights': target_weights,
                    'total_positions': len(target_weights),
                    'args': vars(args)
                }, f, ensure_ascii=False, indent=2)
            logger.info(f"✅ 配置已保存: {output_path}")
        else:
            logger.info("🧪 [DRY-RUN] 跳过保存")

if __name__ == '__main__':
    main()