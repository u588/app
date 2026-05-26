#!/usr/bin/env python3
"""
AiStock V10 — 系统主入口

启动流程:
  1. 初始化日志服务
  2. 初始化服务容器
  3. 注册共享服务 (ConfigService, CacheService, EventBus, LoggerService)
  4. 注册数据服务 (TDXAdapter, AKAdapter, DatabaseReader, DataLoaderService)
  5. 加载子系统 (market_state, price_quant, ...)
  6. 注册信号处理
  7. 运行管线
  8. 关闭

特性:
  - 配置驱动: 改 codes.yaml 一处 → 全局生效
  - 子系统隔离: 各子系统独立配置/缓存/事件
  - 热重载: YAML 变更自动传播
"""
from __future__ import annotations

import os
import signal
import sys
import time
import logging
from pathlib import Path
from typing import Dict, Any, Optional

# 确保项目根目录在 sys.path
PROJECT_ROOT = Path(__file__).parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from base_service.config_service import ConfigService
from base_service.cache_service import CacheService
from base_service.event_bus import EventBus, Topics
from base_service.service_container import ServiceContainer
from base_service.logger_service import LoggerService


def bootstrap(config_dir: str = "config/yaml") -> ServiceContainer:
    """V10 引导启动 — 8步管线"""
    
    # Step 1: 日志服务
    logger_svc = LoggerService(config_dir=config_dir)
    logger_svc.initialize()
    logger = logging.getLogger("aistock.main")
    logger.info("=" * 60)
    logger.info("AiStock V10 启动中...")
    logger.info("=" * 60)
    
    # Step 2: 服务容器
    container = ServiceContainer()
    container.register_singleton("logger_service", logger_svc)
    
    # Step 3: 共享服务
    # 3a. EventBus (最先注册, 其他服务可能需要它)
    event_bus = EventBus(history_size=200)
    container.register_singleton("event_bus", event_bus)
    logger.info("[3/8] EventBus 已注册")
    
    # 3b. ConfigService (依赖 EventBus)
    config_service = ConfigService(
        config_dir=config_dir,
        enable_hot_reload=True,
        hot_reload_interval=5.0,
        event_bus=event_bus,
    )
    config_service.load_all()
    container.register_singleton("config", config_service)
    logger.info("[3/8] ConfigService 已注册 (已加载 %d 个YAML)", len(config_service._configs))
    
    # 3c. CacheService
    cache_config = config_service.get_section("cache")
    cache_service = CacheService(
        default_ttl=cache_config.get("default_ttl", 300),
        default_max_size=cache_config.get("max_size", 500),
    )
    container.register_singleton("cache", cache_service)
    logger.info("[3/8] CacheService 已注册")
    
    # Step 4: 数据服务
    _register_data_services(container, config_service)
    
    # Step 5: 子系统
    _register_subsystems(container, config_service)
    
    # Step 6: 信号处理
    _register_signal_handlers(container, logger)
    
    # Step 7: 打印系统摘要
    _print_summary(container, config_service, logger)
    
    logger.info("=" * 60)
    logger.info("AiStock V10 启动完成!")
    logger.info("=" * 60)
    
    return container


def _register_data_services(container: ServiceContainer, config: ConfigService) -> None:
    """注册数据服务"""
    logger = logging.getLogger("aistock.main")
    
    # TDXAdapter
    from data_service.tdx_adapter import TDXAdapter
    tdx = TDXAdapter(config_service=config)
    container.register_singleton("tdx_adapter", tdx)
    logger.info("[4/8] TDXAdapter 已注册 (标准:%s:%d, 扩展:%s:%d)",
                tdx._std_host, tdx._std_port, tdx._ext_host, tdx._ext_port)
    
    # AKAdapter
    from data_service.ak_adapter import AKAdapter
    ak = AKAdapter(config_service=config)
    container.register_singleton("ak_adapter", ak)
    logger.info("[4/8] AKAdapter 已注册")
    
    # DatabaseReader
    from data_service.database_reader import DatabaseReader
    db = DatabaseReader(config_service=config)
    container.register_singleton("db_reader", db)
    logger.info("[4/8] DatabaseReader 已注册")
    
    # DataLoaderService
    from data_service.data_loader_service import DataLoaderService
    data_loader = DataLoaderService(
        tdx_adapter=tdx,
        ak_adapter=ak,
        db_reader=db,
        config_service=config,
    )
    container.register_singleton("data_loader", data_loader)
    logger.info("[4/8] DataLoaderService 已注册 (索引:%d 期货:%d 期权标的:%d)",
                len(config.get_index_codes()),
                len(config.get_futures_codes()),
                len(config.get_option_underlyings()))


def _register_subsystems(container: ServiceContainer, config: ConfigService) -> None:
    """注册子系统"""
    logger = logging.getLogger("aistock.main")
    
    subsystems_config = config.get("system.subsystems", [])
    for sub_cfg in subsystems_config:
        name = sub_cfg.get("name", "")
        enabled = sub_cfg.get("enabled", False)
        
        if not enabled:
            logger.info("[5/8] 子系统 [%s] 已禁用, 跳过", name)
            continue
        
        if name == "market_state":
            from subsystems.market_state.core.market_state_engine import MarketStateEngine
            engine = MarketStateEngine(container)
            container.register_singleton(f"subsystem.{name}", engine)
            logger.info("[5/8] 子系统 [market_state] 已注册")
        elif name == "price_quant":
            from subsystems.price_quant.engine import PriceQuantEngine
            engine = PriceQuantEngine(container)
            container.register_singleton(f"subsystem.{name}", engine)
            logger.info("[5/8] 子系统 [price_quant] 已注册")
        else:
            logger.warning("[5/8] 未知子系统: %s", name)


def _register_signal_handlers(container: ServiceContainer, logger: logging.Logger) -> None:
    """注册信号处理"""
    def shutdown_handler(signum, frame):
        logger.info("收到终止信号 (%d), 正在关闭...", signum)
        _shutdown(container)
        sys.exit(0)
    
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)
    logger.info("[6/8] 信号处理器已注册")


def _shutdown(container: ServiceContainer) -> None:
    """关闭所有服务"""
    logger = logging.getLogger("aistock.main")
    
    # 停止子系统
    for svc_name in container.list_services():
        if svc_name.startswith("subsystem."):
            try:
                sub = container.get(svc_name)
                if hasattr(sub, 'stop'):
                    sub.stop()
            except Exception as e:
                logger.error("子系统停止异常 [%s]: %s", svc_name, e)
    
    # 停止 ConfigService 热重载
    try:
        config = container.get("config")
        config.stop()
    except Exception:
        pass
    
    # 关闭 TDX 连接
    try:
        tdx = container.get("tdx_adapter")
        tdx.close()
    except Exception:
        pass
    
    logger.info("AiStock V10 已关闭")


def _print_summary(container: ServiceContainer, config: ConfigService, logger: logging.Logger) -> None:
    """打印系统摘要"""
    logger.info("[7/8] 系统摘要:")
    logger.info("  版本: %s", config.get("system.version", "10.0"))
    logger.info("  模式: %s", config.get("system.mode", "production"))
    logger.info("  已注册服务: %s", ", ".join(container.list_services()))
    
    # 验证关键配置
    futures = config.get_futures_codes()
    if futures:
        sample = futures[0]
        logger.info("  期货代码示例: %s (%s) ← codes.yaml", sample.get("code"), sample.get("name"))
    
    indices = config.get_index_codes()
    if indices:
        sample = indices[0]
        logger.info("  指数代码示例: %s (%s) ← codes.yaml", sample.get("code"), sample.get("name"))


def run_pipeline(container: ServiceContainer) -> Dict[str, Any]:
    """运行完整管线"""
    logger = logging.getLogger("aistock.main")
    logger.info("[8/8] 开始运行管线...")
    
    result = {}
    
    # Step 1: 加载数据
    logger.info("── Step 1: 数据加载 ──")
    try:
        data_loader = container.get("data_loader")
        data = data_loader.load_all()
        result["data"] = data
        logger.info("数据加载完成, %d 个段", len([k for k in data.keys() if not k.startswith("_")]))
    except Exception as e:
        logger.error("数据加载失败: %s", e)
        result["data_error"] = str(e)
    
    # Step 2: 运行子系统
    logger.info("── Step 2: 子系统计算 ──")
    for svc_name in container.list_services():
        if svc_name.startswith("subsystem."):
            try:
                sub = container.get(svc_name)
                if hasattr(sub, 'run'):
                    sub_result = sub.run()
                    result[svc_name] = sub_result
                    logger.info("子系统 [%s] 计算完成", svc_name)
            except Exception as e:
                logger.error("子系统 [%s] 计算失败: %s", svc_name, e)
    
    return result


# ═══════════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════════

def main():
    """主入口"""
    config_dir = os.environ.get("AISTOCK_CONFIG_DIR", "config/yaml")
    container = bootstrap(config_dir=config_dir)
    
    # 运行管线
    result = run_pipeline(container)
    
    # 清理
    _shutdown(container)
    
    return result


if __name__ == "__main__":
    main()
