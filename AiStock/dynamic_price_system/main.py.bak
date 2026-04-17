#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
动态价格调整系统 - 主程序入口
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from config.global_settings import LOG_FORMAT, LOG_DATE_FORMAT
# 初始化日志服务（在导入其他模块之前）
from base_services.logger_service import LoggerService, init_logger
from base_services.config_service import ConfigService
from base_services.cache_service import CacheService

from data_services.tdx_adapter import TDXAdapter
from data_services.ak_adapter import AkAdapter
from data_services.database_reader import DatabaseReader  
from data_services.data_loading_service import DataLoadingService

from dynamic_price_system.core.technical_calculator import TechnicalCalculator
from dynamic_price_system.core.fundamental_calculator import FundamentalCalculator
from dynamic_price_system.core.macro_calculator import MacroCalculator
from dynamic_price_system.core.dynamic_price_engine import DynamicPriceEngine
from dynamic_price_system.portfolio.tracker import PortfolioTracker
from dynamic_price_system.portfolio.risk_manager import RiskManager
from dynamic_price_system.utils.export_utils import ExportUtils



config = ConfigService(system_name='dynamic_price')
# 初始化日志
logger_service = init_logger(
    log_dir=Path(config.get('file_paths.log_dir', 'logs')),
    log_level=config.get('system.log_level', 'INFO'),
    enable_console=True,
    enable_file=True,
    use_color=True,
)

# 获取主程序日志器
logger = logger_service.get_logger('main')

logger.info("=" * 60)
logger.info("🚀 动态价格调整系统启动")
logger.info("=" * 60)

# 2. 数据接口
db_reader = DatabaseReader(config.config.get('database').get('DATABASE_ENGINES'), config.config.get('database').get('DB_POOL_CONFIG'))

tdx_config = config.config.get('tdx', {})
tdx = TDXAdapter(tdx_config) if tdx_config.get('use_tdx') else None

external_api = AkAdapter(
    timeout=config.get('external_api.timeout', 30),
    retry_times=config.get('external_api.retry_times', 3)
)
cache_service = CacheService(
    max_size=config.get('cache.max_size', 2000),
    ttl=config.get('cache.ttl', 3600)
)
# 3. 初始化数据加载服务
data_loader = DataLoadingService(
    config_service=config,
    database_reader=db_reader,
    tdx_adapter=tdx,
    cache_service=cache_service,
    external_api=external_api,  # ✅ 注入外部数据接口
    enable_cache=True
)
# LoggerService.init(
#     log_file=str(LOG_DIR / "system.log"),
#     log_format=LOG_FORMAT,
#     date_format=LOG_DATE_FORMAT,
#     level=logging.INFO
# )
# logger = logging.getLogger(__name__)


class DynamicPriceSystem:
    """动态价格调整系统主类"""
    
    def __init__(self, mode: str = "paper_trading"):
        """
        初始化系统
        
        参数:
            mode: 运行模式 (paper_trading/real_trading/backtest)
        """
        logger.info("="*60)
        logger.info(f"🚀 {mode.upper()} 模式启动：三维动态价格调整系统")
        logger.info("="*60)
        
        self.mode = mode
        
        # 1. 加载配置
        logger.info("【步骤 1】加载配置...")
        self.config = ConfigService(
            system_name="dynamic_price",
            config_subdir="dynamic_price"
        )
        
        # 2. 初始化基础服务
        logger.info("【步骤 2】初始化基础服务...")
        self.cache = CacheService(
            max_size=self.config.get('cache.max_size', 2000),
            ttl=self.config.get('cache.ttl', 3600)
        )
        
        db_config = self.config.get('database', {})
        self.db_main = DatabaseService(
            db_config.get('main_db'),
            pool_config=db_config
        )
        self.db_pe = DatabaseService(
            db_config.get('pe_db'),
            pool_config=db_config
        )
        
        # 3. 初始化数据服务
        logger.info("【步骤 3】初始化数据服务...")
        self.data_loader = DataLoader(
            config_service=self.config,
            cache_service=self.cache,
            db_main=self.db_main,
            db_pe=self.db_pe
        )
        
        # 4. 初始化核心引擎
        logger.info("【步骤 4】初始化核心引擎...")
        self.price_engine = DynamicPriceEngine(
            config_service=self.config,
            cache_service=self.cache
        )
        
        # 5. 初始化组合管理
        logger.info("【步骤 5】初始化组合管理...")
        self.portfolio = PortfolioTracker(
            initial_capital=1000000,
            config=self.config
        )
        self.risk_manager = RiskManager(
            config=self.config,
            portfolio=self.portfolio
        )
        
        # 6. 初始化工具
        self.exporter = ExportUtils(output_dir=OUTPUT_DIR)
        
        logger.info("✅ 系统初始化完成")
    
    def run_daily(self):
        """执行每日运行流程"""
        logger.info("\n" + "="*60)
        logger.info("📅 开始每日运行流程")
        logger.info("="*60)
        
        try:
            # 阶段 1: 数据获取
            logger.info("\n【阶段 1】数据获取...")
            stocks_data = self.data_loader.load_all_stocks()
            macro_data = self.data_loader.load_all_macro()
            financial_data = self.data_loader.load_all_financial()
            
            if not stocks_
                logger.error("❌ 数据获取失败，终止运行")
                return
            
            # 阶段 2: 动态价格计算
            logger.info("\n【阶段 2】动态价格计算...")
            results = self.price_engine.calculate_all(
                stocks_data=stocks_data,
                financial_data=financial_data,
                macro_data=macro_data
            )
            
            # 阶段 3: 组合管理 + 风控
            logger.info("\n【阶段 3】组合管理 + 风控...")
            current_prices = {r['code']: r['current_price'] for r in results}
            
            # 检查止损/止盈
            alerts = self.risk_manager.check_alerts(results, current_prices)
            if alerts:
                logger.warning(f"⚠️ 生成 {len(alerts)} 个预警")
            
            # 检查再平衡
            rebalance_actions = self.portfolio.check_rebalance(
                current_prices=current_prices,
                dynamic_prices=results
            )
            if rebalance_actions:
                logger.info(f"📊 生成 {len(rebalance_actions)} 个再平衡建议")
            
            # 阶段 4: 输出报告
            logger.info("\n【阶段 4】输出报告...")
            self.exporter.export_dynamic_prices(results)
            self.exporter.export_portfolio_summary(self.portfolio.get_summary(current_prices))
            
            # 打印摘要
            self._print_summary(results)
            
            logger.info("\n✅ 每日运行流程完成")
            
        except Exception as e:
            logger.error(f"❌ 每日运行失败：{e}", exc_info=True)
        finally:
            self.shutdown()
    
    def _print_summary(self, results):
        """打印运行摘要"""
        logger.info("\n" + "="*60)
        logger.info("📊 运行摘要")
        logger.info("="*60)
        
        # 推荐标的
        recommended = [r for r in results if r['recommendation'] in ['强烈推荐', '推荐']]
        logger.info(f"💡 推荐标的：{len(recommended)}只")
        for r in sorted(recommended, key=lambda x: x['profit_loss_ratio'], reverse=True)[:5]:
            logger.info(f"   {r['code']} {r['recommendation']} | 盈亏比{r['profit_loss_ratio']}")
        
        # 缓存统计
        cache_stats = self.cache.get_stats()
        logger.info(f"💾 缓存命中率：{cache_stats['hit_rate']:.1%}")
        
        # 数据库健康
        if self.db_main.health_check():
            logger.info("🗄️ 数据库连接：正常")
        else:
            logger.warning("⚠️ 数据库连接：异常")
    
    def shutdown(self):
        """优雅关闭"""
        logger.info("🛑 系统关闭中...")
        self.db_main.close()
        self.db_pe.close()
        self.cache.compact()
        logger.info("✅ 系统已关闭")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='三维动态价格调整系统')
    parser.add_argument('--mode', choices=['paper', 'real', 'backtest'], default='paper',
                       help='运行模式')
    
    args = parser.parse_args()
    
    system = DynamicPriceSystem(mode=args.mode)
    
    try:
        system.run_daily()
    except KeyboardInterrupt:
        logger.info("⌨️ 用户中断")
    finally:
        system.shutdown()


if __name__ == '__main__':
    main()