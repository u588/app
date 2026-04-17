#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DynamicPriceSystem 主程序入口
职责：服务编排、流程控制、异常处理、参数解析
架构：严格遵循依赖注入与配置驱动原则，业务逻辑全部下沉至 Service 层
"""

import sys
import os
import argparse
import logging
import json
from pathlib import Path
from datetime import datetime

# ==================== 路径注入 ====================
# 假设 main.py 位于 AiStock/dynamic_price_system/
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

# ==================== 参数解析 ====================
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AiStock 动态价格计算系统")
    parser.add_argument("--mode", choices=["paper", "real", "backtest"], default="paper",
                        help="运行模式: paper(模拟)/real(实盘)/backtest(回测)")
    parser.add_argument("--date", type=str, default=None,
                        help="指定计算日期 (YYYY-MM-DD)，默认当日")
    parser.add_argument("--stocks", nargs="+", default=None,
                        help="指定股票代码列表 (默认全量 18 只)")
    parser.add_argument("--export", choices=["html", "excel", "png", "json"], default="html",
                        help="可视化导出格式")
    parser.add_argument("--skip-viz", action="store_true",
                        help="跳过可视化生成（提升批量计算性能）")
    return parser.parse_args()


# ==================== 核心运行器 ====================
class DynamicPriceRunner:
    """动态价格系统主流程编排器"""
    
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.logger = logging.getLogger("MainRunner")
        self.services = {}
        self._init_logging()
        self._init_services()
    
    def _init_logging(self):
        """初始化日志配置（可替换为自定义 LoggerService）"""
        log_dir = PROJECT_ROOT / "logs" / "dynamic_price"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        fmt = '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        handlers = [
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_dir / f"system_{datetime.now().strftime('%Y%m%d')}.log", encoding='utf-8')
        ]
        logging.basicConfig(level=logging.INFO, format=fmt, handlers=handlers)
    
    def _init_services(self):
        """初始化所有业务服务（依赖注入）"""
        self.logger.info("🔧 初始化核心服务...")
        
        # 1. 配置服务
        from base_services.config_service import ConfigService
        self.services['config'] = ConfigService(system_name='dynamic_price')
        
        # 2. 缓存服务
        from base_services.cache_service import CacheService
        cache_cfg = self.services['config'].get('cache', {})
        self.services['cache'] = CacheService(
            max_size=cache_cfg.get('max_size', 2000),
            ttl=cache_cfg.get('ttl', 300)
        )
        
        # 3. 数据库服务
        from data_services.database_reader import DatabaseReader
        db_cfg = self.services['config'].get('database', {})
        self.services['db'] = DatabaseReader(
            engines=db_cfg.get('engines', {}),
            pool_config=db_cfg.get('pool_config', {})
        )
        
        # 4. 数据源适配器
        from data_services.tdx_adapter import TDXAdapter
        from data_services.ak_adapter import AKAdapter
        tdx_cfg = self.services['config'].get('tdx', {})
        self.services['tdx'] = TDXAdapter(tdx_cfg) if tdx_cfg.get('use_tdx') else None
        self.services['ak'] = AKAdapter()
        
        # 5. 数据加载服务
        from data_services.data_loading_service import DataLoadingService
        self.services['loader'] = DataLoadingService(
            config_service=self.services['config'],
            cache_service=self.services['cache'],
            database_reader=self.services['db'],
            tdx_adapter=self.services['tdx'],
            ak_adapter=self.services['ak'],
            enable_cache=True
        )
        
        # 6. 三维价格引擎
        from dynamic_price_system.core.dynamic_price_engine import DynamicPriceEngine
        self.services['engine'] = DynamicPriceEngine(config_service=self.services['config'])
        
        # 7. 组合与风控
        from dynamic_price_system.portfolio.tracker import PortfolioTracker
        from dynamic_price_system.portfolio.risk_manager import RiskManager
        initial_capital = self.services['config'].get('portfolio.initial_capital', 1_000_000)
        self.services['portfolio'] = PortfolioTracker(initial_capital=initial_capital, config=self.services['config'])
        self.services['risk'] = RiskManager(config=self.services['config'], portfolio=self.services['portfolio'])
        
        # 8. 可视化服务
        if not self.args.skip_viz:
            try:
                from visualization.services.visualization_service import VisualizationService
                viz_cfg_path = PROJECT_ROOT / "config" / "dynamic_price" / "chart_config.yaml"
                self.services['viz'] = VisualizationService(
                    config_path=str(viz_cfg_path) if viz_cfg_path.exists() else None
                )
            except Exception as e:
                self.logger.warning(f"⚠️ 可视化服务初始化失败: {e}，后续将跳过图表生成")
                self.services['viz'] = None
        else:
            self.services['viz'] = None
            
        self.logger.info("✅ 服务初始化完成")
    
    def run(self):
        """执行主流程"""
        self.logger.info(f"🚀 启动动态价格系统 | 模式: {self.args.mode} | 时间: {datetime.now().isoformat()}")
        start_time = datetime.now()
        
        try:
            # 1. 确定标的池
            target_stocks = self._resolve_stock_universe()
            self.logger.info(f"📋 标的池: {len(target_stocks)} 只 -> {[s['code'] for s in target_stocks]}")
            
            # 2. 加载宏观数据
            macro_codes = ['brent_crude', 'comex_gold', 'lme_copper', 'pmi', 'm2_growth', 'usd_cny']
            self.logger.info("🌍 加载宏观指标数据...")
            macro_data = self.services['loader'].load_all_macro_indicators(macro_codes)
            
            # 3. 批量加载行情 & 财务数据
            self.logger.info("📥 加载标的行情与财务数据...")
            stock_data_map = {}
            financial_data_map = {}
            valid_stocks = []
            
            for stock in target_stocks:
                code = stock['code']
                try:
                    stock_data_map[code] = self.services['loader'].load_stock_daily(code, min_days=200)
                    if stock_data_map[code] is None or stock_data_map[code].empty:
                        self.logger.warning(f"⚠️ 行情数据不足跳过: {code}")
                        continue
                    
                    fin_df = self.services['loader'].load_stock_financials(code)
                    financial_data_map[code] = fin_df.to_dict(orient='records')[0] if not fin_df.empty else {}
                    valid_stocks.append(stock)
                except Exception as e:
                    self.logger.error(f"❌ 加载 {code} 数据失败: {e}")
            
            if not valid_stocks:
                self.logger.error("❌ 无有效标的数据，流程终止")
                return
            
            # 4. 执行三维价格计算
            self.logger.info("🧮 执行动态价格计算...")
            calc_inputs = [
                {
                    'code': s['code'], 'name': s['name'], 'sector': s['sector'],
                    'stock_data': stock_data_map[s['code']],
                    'financial_data': financial_data_map[s['code']],
                    'macro_data': macro_data,
                    'params': s.get('params', {})
                } for s in valid_stocks
            ]
            batch_results = self.services['engine'].calculate_batch(calc_inputs)
            self.logger.info(f"✅ 计算完成: 成功 {len(batch_results)}/{len(calc_inputs)} 只")
            
            if not batch_results:
                self.logger.warning("⚠️ 无有效计算结果，流程终止")
                return
            
            # 5. 组合更新与风控检查
            self.logger.info("🛡️ 执行组合更新与风控检查...")
            current_prices = {r['code']: r['prices']['current'] for r in batch_results}
            
            if hasattr(self.services['portfolio'], 'mark_to_market'):
                self.services['portfolio'].mark_to_market(current_prices)
            elif hasattr(self.services['portfolio'], 'update_prices'):
                self.services['portfolio'].update_prices(current_prices)
            
            risk_alerts = self.services['risk'].check_alerts(batch_results)
            if risk_alerts:
                for alert in risk_alerts:
                    self.logger.warning(f"⚠️ 风控预警: {alert.get('code')} | {alert.get('message')}")
            
            # 6. 可视化与导出
            if self.services['viz']:
                self.logger.info("📊 生成可视化图表...")
                try:
                    viz_output = self.services['viz'].visualize_batch_results(
                        batch_results, output_format=self.args.export
                    )
                    if viz_output:
                        self.logger.info(f"📁 可视化导出: {viz_output}")
                except Exception as e:
                    self.logger.error(f"❌ 可视化生成失败: {e}")
            
            # 7. 持久化结果
            self._persist_results(batch_results)
            
            # 8. 性能统计
            duration = (datetime.now() - start_time).total_seconds()
            cache_stats = self.services['cache'].get_stats()
            self.logger.info(f"⏱️ 执行耗时: {duration:.2f}s | 缓存命中率: {cache_stats['hit_rate']:.1%}")
            self.logger.info("🏁 流程执行完毕")
            
        except KeyboardInterrupt:
            self.logger.info("⌨️ 用户中断执行")
        except Exception as e:
            self.logger.error(f"❌ 系统运行异常: {e}", exc_info=True)
            raise
        finally:
            self._cleanup()
    
    def _resolve_stock_universe(self) -> list:
        """解析目标标的池"""
        all_stocks = self.services['config'].get('stocks', [])
        if self.args.stocks:
            filtered = [s for s in all_stocks if s['code'] in self.args.stocks]
            if not filtered:
                self.logger.warning(f"⚠️ 未找到指定标的: {self.args.stocks}，回退至全量")
                return all_stocks
            return filtered
        return all_stocks
    
    def _persist_results(self, results: list):
        """持久化计算结果（JSON + 可选数据库）"""
        output_dir = PROJECT_ROOT / "output" / "results"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_path = output_dir / f"dynamic_prices_{ts}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2, default=str)
        self.logger.info(f"💾 结果已保存: {json_path}")
        
        # 可扩展：写入 PostgreSQL / CSV / 消息队列
        # if hasattr(self.services['db'], 'insert_batch'):
        #     self.services['db'].insert_batch('dynamic_prices', results)
    
    def _cleanup(self):
        """优雅关闭所有服务资源"""
        self.logger.info("🧹 清理服务资源...")
        for name, svc in self.services.items():
            if hasattr(svc, 'close'):
                try:
                    svc.close()
                except Exception as e:
                    self.logger.debug(f"清理 {name} 失败: {e}")
        self.logger.info("✅ 资源清理完成")


# ==================== 入口函数 ====================
def main():
    args = parse_args()
    runner = DynamicPriceRunner(args)
    runner.run()


if __name__ == '__main__':
    main()