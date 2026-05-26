#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AiStock V10 — 市场状态引擎 (MarketStateEngine)

V10 NEW: 子系统入口, 继承 SubsystemBase, 编排所有市场状态组件。

核心职责:
  - 继承 SubsystemBase, 自动注入 config / cache / event_bus
  - 编排: ContractManager + OptionCodeParser + DerivativesSignalEngine + DataLoaderService
  - start() / stop() / run() 生命周期
  - 发布事件: MARKET_STATE_UPDATED

事件:
  - market_state.updated — 每次市场状态计算完成后发布
  - market_state.warning — 到期预警
  - subsystem.started / subsystem.stopped — 继承自 SubsystemBase
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from base_service.service_container import ServiceContainer, SubsystemBase
from subsystems.market_state.core.contract_manager import ContractManager
from subsystems.market_state.core.option_code_parser import OptionCodeParser
from subsystems.market_state.core.derivatives_signal_engine import (
    DerivativesSignalEngine,
    DerivativesResult,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# 事件主题常量
# ═══════════════════════════════════════════════════════════════════════════════

EVENT_MARKET_STATE_UPDATED = "market_state.updated"
EVENT_MARKET_STATE_WARNING = "market_state.warning"


class MarketStateEngine(SubsystemBase):
    """市场状态引擎 — V10 子系统入口

    继承 SubsystemBase, 自动获得:
    - self.config:    ConfigService (子系统隔离配置)
    - self.cache:     CacheService (命名空间隔离)
    - self.event_bus: EventBus (系统间通信)
    - self.logger:    Logger

    编排组件:
    - ContractManager:         动态合约推导 (全配置驱动)
    - OptionCodeParser:        期权代码解析
    - DerivativesSignalEngine: 衍生品信号计算
    - DataLoaderService:       数据加载 (从 ServiceContainer 获取)

    生命周期:
    - start(): 初始化组件, 启动数据流
    - run():   执行一次完整的市场状态计算
    - stop():  清理资源

    Usage:
        container = ServiceContainer()
        # ... 注册 config, cache, event_bus, data_loader ...
        engine = MarketStateEngine(container)
        engine.start()
        result = engine.run()
        engine.stop()
    """

    def __init__(self, container: ServiceContainer) -> None:
        """初始化市场状态引擎

        Args:
            container: ServiceContainer 实例 (提供 config, cache, event_bus 等共享服务)
        """
        super().__init__("market_state", container)

        # 内部组件 (延迟初始化)
        self._contract_manager: Optional[ContractManager] = None
        self._option_parser: Optional[OptionCodeParser] = None
        self._signal_engine: Optional[DerivativesSignalEngine] = None
        self._data_loader: Optional[Any] = None

        # 状态
        self._last_result: Optional[DerivativesResult] = None
        self._is_running: bool = False
        self._run_count: int = 0

        self.logger.info("MarketStateEngine V10 实例化完成")

    # ──────────────────────────────────────────────────────────────
    #  生命周期
    # ──────────────────────────────────────────────────────────────

    def start(self) -> None:
        """启动市场状态子系统

        初始化所有内部组件:
          1. ContractManager (从 ConfigService 加载品种/交割月映射)
          2. OptionCodeParser (期权代码解析)
          3. DerivativesSignalEngine (衍生品信号计算)
          4. DataLoaderService (数据加载, 从容器获取)
        """
        self.logger.info("MarketStateEngine V10 正在启动...")

        # 1. ContractManager
        code_table_path = self.get_config("codes.code_table_path", None)
        if code_table_path is None:
            # 尝试默认路径
            import os
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__)
            ))))
            default_path = os.path.join(project_root, "data", "tdxAPICode180.xlsx")
            if os.path.exists(default_path):
                code_table_path = default_path

        self._contract_manager = ContractManager(
            config=self.config,
            code_table_path=code_table_path,
        )
        self.logger.info("ContractManager 初始化完成 | 代码表: %s", code_table_path or "无")

        # 2. OptionCodeParser
        self._option_parser = OptionCodeParser()
        self.logger.info("OptionCodeParser 初始化完成")

        # 3. DataLoaderService (从容器获取)
        if self._container.has("data_loader"):
            self._data_loader = self._container.get("data_loader")
            self.logger.info("DataLoaderService 已注入")
        else:
            self._data_loader = None
            self.logger.warning("DataLoaderService 未注册, 部分功能可能不可用")

        # 4. DerivativesSignalEngine
        overseas_engine = None
        if self._container.has("overseas_signal_engine"):
            overseas_engine = self._container.get("overseas_signal_engine")

        self._signal_engine = DerivativesSignalEngine(
            data_service=self._data_loader,
            contract_manager=self._contract_manager,
            overseas_signal_engine=overseas_engine,
            config=self.config,
            cache=self.cache,
        )
        self.logger.info("DerivativesSignalEngine 初始化完成")

        self._is_running = True

        # 发布启动事件
        super().start()
        self.logger.info("MarketStateEngine V10 启动完成")

    def stop(self) -> None:
        """停止市场状态子系统"""
        self.logger.info("MarketStateEngine V10 正在停止...")
        self._is_running = False

        # 清理资源
        self._last_result = None
        self._signal_engine = None
        self._contract_manager = None
        self._option_parser = None
        self._data_loader = None

        # 发布停止事件
        super().stop()
        self.logger.info("MarketStateEngine V10 已停止")

    @property
    def is_running(self) -> bool:
        """子系统是否在运行"""
        return self._is_running

    @property
    def last_result(self) -> Optional[DerivativesResult]:
        """最近一次计算结果"""
        return self._last_result

    @property
    def contract_manager(self) -> Optional[ContractManager]:
        """获取 ContractManager 实例"""
        return self._contract_manager

    @property
    def signal_engine(self) -> Optional[DerivativesSignalEngine]:
        """获取 DerivativesSignalEngine 实例"""
        return self._signal_engine

    # ──────────────────────────────────────────────────────────────
    #  核心运行
    # ──────────────────────────────────────────────────────────────

    def run(self) -> Optional[DerivativesResult]:
        """执行一次完整的市场状态计算

        计算流程:
          1. DerivativesSignalEngine.calculate_all() — 衍生品信号全量计算
          2. ContractManager.check_expiry_warnings() — 到期预警
          3. 发布 MARKET_STATE_UPDATED 事件
          4. 缓存结果

        Returns:
            DerivativesResult 或 None (未启动时)
        """
        if not self._is_running:
            self.logger.warning("MarketStateEngine 未启动, 无法执行 run()")
            return None

        start_time = time.time()
        self.logger.info("MarketStateEngine 开始执行第 %d 次计算...", self._run_count + 1)

        try:
            # 1. 衍生品信号全量计算
            result = self._signal_engine.calculate_all()

            # 2. 到期预警
            warnings = self._contract_manager.check_expiry_warnings()
            if warnings:
                self.logger.warning("到期预警: %d 条", len(warnings))
                self.publish_event(EVENT_MARKET_STATE_WARNING, {
                    "warnings": warnings,
                    "timestamp": datetime.now().isoformat(),
                })

            # 3. 缓存结果
            self._last_result = result
            self._run_count += 1

            # 4. 发布更新事件
            elapsed = (time.time() - start_time) * 1000
            self.publish_event(EVENT_MARKET_STATE_UPDATED, {
                "composite_signal": result.composite_signal,
                "composite_direction": result.composite_direction,
                "run_count": self._run_count,
                "elapsed_ms": round(elapsed, 1),
                "timestamp": datetime.now().isoformat(),
            })

            self.logger.info(
                "MarketStateEngine 第 %d 次计算完成 | "
                "综合信号: %.1f [%s] | 耗时: %.0fms",
                self._run_count,
                result.composite_signal,
                result.composite_direction,
                elapsed,
            )

            return result

        except Exception as e:
            self.logger.error("MarketStateEngine 计算异常: %s", e, exc_info=True)
            self.publish_event(EVENT_MARKET_STATE_WARNING, {
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            })
            return None

    # ──────────────────────────────────────────────────────────────
    #  便捷方法
    # ──────────────────────────────────────────────────────────────

    def get_commodity_contracts(self, variety_code: str) -> Optional[Any]:
        """获取商品期货合约对"""
        if self._contract_manager is None:
            return None
        return self._contract_manager.get_commodity_contracts(variety_code=variety_code)

    def get_index_futures_contracts(self, key: str) -> Optional[Any]:
        """获取股指期货合约"""
        if self._contract_manager is None:
            return None
        return self._contract_manager.get_index_futures_contracts(key=key)

    def get_option_contracts(self, underlying: str, month_offset: int = 0) -> Optional[Any]:
        """获取期权合约组"""
        if self._contract_manager is None:
            return None
        return self._contract_manager.get_option_contracts(
            underlying=underlying, month_offset=month_offset,
        )

    def generate_report(self) -> Dict[str, Any]:
        """生成市场状态报告"""
        if self._signal_engine is None:
            return {"error": "MarketStateEngine 未启动"}

        result = self._last_result or self._signal_engine.calculate_all()
        report = self._signal_engine.generate_enhanced_report(result)

        # 附加合约信息
        if self._contract_manager:
            report["contract_summary"] = self._contract_manager.get_contract_summary()
            report["config_updates"] = self._contract_manager.generate_full_config_updates()

        return report

    def refresh_contracts(self, reference_date: Optional[datetime] = None) -> None:
        """刷新合约映射 (日期变更后调用)"""
        if self._contract_manager:
            self._contract_manager.update(reference_date=reference_date)
            self.logger.info("合约映射已刷新")

    def reload_config(self) -> None:
        """热重载配置"""
        if self._contract_manager:
            self._contract_manager.reload_config()
        if self._signal_engine:
            self._signal_engine._commodity_varieties = self._signal_engine._load_commodity_config()
            self._signal_engine._index_futures = self._signal_engine._load_index_futures_config()
            self._signal_engine._weights = self._signal_engine._load_weights()
            self._signal_engine._overseas_fusion_weight = self._signal_engine._load_overseas_fusion_weight()
        self.logger.info("MarketStateEngine 配置热重载完成")
