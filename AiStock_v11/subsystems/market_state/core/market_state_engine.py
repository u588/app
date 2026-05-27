#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AiStock V11 — 市场状态引擎 (MarketStateEngine)

V11 核心变更:
  - 6分量模型: commodity + term_structure + index_basis
    + fund_flow + option_pcr + macro_valuation
  - 新增 FundFlowEngine / OptionPCREngine / MacroValuationEngine
  - 行业情绪和海外信号降级为辅助信息 (不计入6分量权重)

核心职责:
  - 继承 SubsystemBase, 自动注入 config / cache / event_bus
  - 编排: ContractManager + OptionCodeParser + DerivativesSignalEngine
    + FundFlowEngine + OptionPCREngine + MacroValuationEngine + DataLoaderService
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
from subsystems.market_state.core.fund_flow_engine import FundFlowEngine
from subsystems.market_state.core.option_pcr_engine import OptionPCREngine
from subsystems.market_state.core.macro_valuation_engine import MacroValuationEngine
from subsystems.market_state.core.style_rotation_engine import StyleRotationEngine

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# 事件主题常量
# ═══════════════════════════════════════════════════════════════════════════════

EVENT_MARKET_STATE_UPDATED = "market_state.updated"
EVENT_MARKET_STATE_WARNING = "market_state.warning"


class MarketStateEngine(SubsystemBase):
    """市场状态引擎 — V11 7分量模型

    继承 SubsystemBase, 自动获得:
    - self.config:    ConfigService (子系统隔离配置)
    - self.cache:     CacheService (命名空间隔离)
    - self.event_bus: EventBus (系统间通信)
    - self.logger:    Logger

    编排组件:
    - ContractManager:         动态合约推导 (全配置驱动)
    - OptionCodeParser:        期权代码解析
    - DerivativesSignalEngine: 衍生品信号计算 (3个原有分量 + 辅助信号)
    - FundFlowEngine:          基金资金流信号 (V11 NEW)
    - OptionPCREngine:         期权PCR信号 (V11 NEW)
    - MacroValuationEngine:    宏观估值信号 (V11 NEW)
    - StyleRotationEngine:     行业/风格/规模轮动信号 (V11 NEW)
    - DataLoaderService:       数据加载 (从 ServiceContainer 获取)

    生命周期:
    - start(): 初始化组件, 启动数据流
    - run():   执行一次完整的市场状态计算 (7分量)
    - stop():  清理资源
    """

    def __init__(self, container: ServiceContainer) -> None:
        """初始化市场状态引擎

        Args:
            container: ServiceContainer 实例
        """
        super().__init__("market_state", container)

        # 内部组件 (延迟初始化)
        self._contract_manager: Optional[ContractManager] = None
        self._option_parser: Optional[OptionCodeParser] = None
        self._signal_engine: Optional[DerivativesSignalEngine] = None
        self._fund_flow_engine: Optional[FundFlowEngine] = None
        self._option_pcr_engine: Optional[OptionPCREngine] = None
        self._macro_valuation_engine: Optional[MacroValuationEngine] = None
        self._style_rotation_engine: Optional[StyleRotationEngine] = None
        self._data_loader: Optional[Any] = None
        self._tdx_adapter: Optional[Any] = None
        self._db_reader: Optional[Any] = None

        # 状态
        self._last_result: Optional[DerivativesResult] = None
        self._is_running: bool = False
        self._run_count: int = 0

        self.logger.info("MarketStateEngine V11.1 实例化完成")

    # ──────────────────────────────────────────────────────────────
    #  生命周期
    # ──────────────────────────────────────────────────────────────

    def start(self) -> None:
        """启动市场状态子系统

        初始化所有内部组件:
          1. ContractManager (从 ConfigService 加载品种/交割月映射)
          2. OptionCodeParser (期权代码解析)
          3. DataLoaderService (数据加载, 从容器获取)
          4. DerivativesSignalEngine (衍生品信号计算)
          5. FundFlowEngine (基金资金流信号, V11 NEW)
          6. OptionPCREngine (期权PCR信号, V11 NEW)
          7. MacroValuationEngine (宏观估值信号, V11 NEW)
          8. StyleRotationEngine (行业/风格/规模轮动信号, V11 NEW)
        """
        self.logger.info("MarketStateEngine V11.1 正在启动...")

        # 1. ContractManager
        code_table_path = self.get_config("codes.code_table_path", None)
        if code_table_path is None:
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

        # 3. DataLoaderService + TDXAdapter + DatabaseReader (从容器获取)
        if self._container.has("data_loader"):
            self._data_loader = self._container.get("data_loader")
            self.logger.info("DataLoaderService 已注入")
        else:
            self._data_loader = None
            self.logger.warning("DataLoaderService 未注册, 部分功能可能不可用")

        if self._container.has("tdx_adapter"):
            self._tdx_adapter = self._container.get("tdx_adapter")
        else:
            self._tdx_adapter = None
            self.logger.warning("TDXAdapter 未注册, 资金流/宏观引擎将不可用")

        if self._container.has("db_reader"):
            self._db_reader = self._container.get("db_reader")
        else:
            self._db_reader = None
            self.logger.debug("DatabaseReader 未注册, 估值信号将不可用")

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

        # 5. FundFlowEngine (V11 NEW)
        self._fund_flow_engine = FundFlowEngine(
            data_service=self._tdx_adapter or self._data_loader,
            config=self.config,
            cache=self.cache,
        )
        self.logger.info("FundFlowEngine V11 初始化完成")

        # 6. OptionPCREngine (V11 NEW)
        self._option_pcr_engine = OptionPCREngine(
            data_service=self._data_loader,
            config=self.config,
            cache=self.cache,
        )
        self.logger.info("OptionPCREngine V11 初始化完成")

        # 7. MacroValuationEngine (V11 NEW)
        self._macro_valuation_engine = MacroValuationEngine(
            tdx_adapter=self._tdx_adapter,
            db_reader=self._db_reader,
            config=self.config,
            cache=self.cache,
        )
        self.logger.info("MacroValuationEngine V11 初始化完成")

        # 8. StyleRotationEngine (V11 NEW)
        self._style_rotation_engine = StyleRotationEngine(
            tdx_adapter=self._tdx_adapter,
            config=self.config,
            cache=self.cache,
        )
        self.logger.info("StyleRotationEngine V11 初始化完成")

        self._is_running = True

        # 发布启动事件
        super().start()
        self.logger.info("MarketStateEngine V11.1 启动完成 (7分量模型)")

    def stop(self) -> None:
        """停止市场状态子系统"""
        self.logger.info("MarketStateEngine V11 正在停止...")
        self._is_running = False

        # 清理资源
        self._last_result = None
        self._signal_engine = None
        self._fund_flow_engine = None
        self._option_pcr_engine = None
        self._macro_valuation_engine = None
        self._style_rotation_engine = None
        self._contract_manager = None
        self._option_parser = None
        self._data_loader = None
        self._tdx_adapter = None
        self._db_reader = None

        # 发布停止事件
        super().stop()
        self.logger.info("MarketStateEngine V11.1 已停止")

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

    @property
    def fund_flow_engine(self) -> Optional[FundFlowEngine]:
        """获取 FundFlowEngine 实例"""
        return self._fund_flow_engine

    @property
    def option_pcr_engine(self) -> Optional[OptionPCREngine]:
        """获取 OptionPCREngine 实例"""
        return self._option_pcr_engine

    @property
    def macro_valuation_engine(self) -> Optional[MacroValuationEngine]:
        """获取 MacroValuationEngine 实例"""
        return self._macro_valuation_engine

    @property
    def style_rotation_engine(self) -> Optional[StyleRotationEngine]:
        """获取 StyleRotationEngine 实例"""
        return self._style_rotation_engine

    # ──────────────────────────────────────────────────────────────
    #  核心运行
    # ──────────────────────────────────────────────────────────────

    def run(self) -> Optional[DerivativesResult]:
        """执行一次完整的市场状态计算 (V11 7分量模型)

        计算流程:
          1. FundFlowEngine.calculate()    → 基金资金流信号
          2. OptionPCREngine.calculate()   → 期权PCR信号
          3. MacroValuationEngine.calculate() → 宏观估值信号
          4. StyleRotationEngine.calculate()  → 行业/风格/规模轮动信号
          5. DerivativesSignalEngine.calculate_all() — 衍生品信号全量计算 + 7分量合成
          6. ContractManager.check_expiry_warnings() — 到期预警
          7. 发布 MARKET_STATE_UPDATED 事件
          8. 缓存结果

        Returns:
            DerivativesResult 或 None (未启动时)
        """
        if not self._is_running:
            self.logger.warning("MarketStateEngine 未启动, 无法执行 run()")
            return None

        start_time = time.time()
        self.logger.info("MarketStateEngine V11 开始执行第 %d 次计算 (6分量)...", self._run_count + 1)

        try:
            # 1. 基金资金流信号 (V11 NEW)
            fund_flow_signal = None
            if self._fund_flow_engine is not None:
                try:
                    fund_flow_signal = self._fund_flow_engine.calculate()
                except Exception as e:
                    self.logger.warning("FundFlowEngine 计算异常: %s", e)

            # 2. 期权PCR信号 (V11 NEW)
            option_pcr_signal = None
            if self._option_pcr_engine is not None:
                try:
                    option_pcr_signal = self._option_pcr_engine.calculate()
                except Exception as e:
                    self.logger.warning("OptionPCREngine 计算异常: %s", e)

            # 3. 宏观估值信号 (V11 NEW)
            macro_valuation_signal = None
            if self._macro_valuation_engine is not None:
                try:
                    macro_valuation_signal = self._macro_valuation_engine.calculate()
                except Exception as e:
                    self.logger.warning("MacroValuationEngine 计算异常: %s", e)

            # 4. 风格轮动信号 (V11 NEW)
            style_rotation_signal = None
            if self._style_rotation_engine is not None:
                try:
                    style_rotation_signal = self._style_rotation_engine.calculate()
                except Exception as e:
                    self.logger.warning("StyleRotationEngine 计算异常: %s", e)

            # 5. 衍生品信号全量计算 (含7分量合成)
            result = self._signal_engine.calculate_all(
                fund_flow_signal=fund_flow_signal,
                option_pcr_signal=option_pcr_signal,
                macro_valuation_signal=macro_valuation_signal,
                style_rotation_signal=style_rotation_signal,
            )

            # 6. 到期预警
            warnings = self._contract_manager.check_expiry_warnings()
            if warnings:
                self.logger.warning("到期预警: %d 条", len(warnings))
                self.publish_event(EVENT_MARKET_STATE_WARNING, {
                    "warnings": warnings,
                    "timestamp": datetime.now().isoformat(),
                })

            # 7. 缓存结果
            self._last_result = result
            self._run_count += 1

            # 8. 发布更新事件
            elapsed = (time.time() - start_time) * 1000
            self.publish_event(EVENT_MARKET_STATE_UPDATED, {
                "composite_signal": result.composite_signal,
                "composite_direction": result.composite_direction,
                "model": "7-component",
                "run_count": self._run_count,
                "elapsed_ms": round(elapsed, 1),
                "timestamp": datetime.now().isoformat(),
            })

            self.logger.info(
                "MarketStateEngine V11.1 第 %d 次计算完成 | "
                "综合信号: %.1f [%s] | 模型: 7分量 | 耗时: %.0fms",
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
        if self._fund_flow_engine:
            self._fund_flow_engine._weights = self._fund_flow_engine._load_weights()
            self._fund_flow_engine._indicators = self._fund_flow_engine._load_indicators()
        if self._option_pcr_engine:
            self._option_pcr_engine._weights = self._option_pcr_engine._load_weights()
            self._option_pcr_engine._thresholds = self._option_pcr_engine._load_thresholds()
            self._option_pcr_engine._underlyings = self._option_pcr_engine._load_underlyings()
        if self._macro_valuation_engine:
            self._macro_valuation_engine._weights = self._macro_valuation_engine._load_weights()
            self._macro_valuation_engine._indicators = self._macro_valuation_engine._load_indicators()
            self._macro_valuation_engine._valuation_codes = self._macro_valuation_engine._load_valuation_codes()
        if self._style_rotation_engine:
            self._style_rotation_engine._weights = self._style_rotation_engine._load_weights()
            self._style_rotation_engine._industry_indices = self._style_rotation_engine._load_industry_indices()
            self._style_rotation_engine._style_indices = self._style_rotation_engine._load_style_indices()
            self._style_rotation_engine._size_indices = self._style_rotation_engine._load_size_indices()
            self._style_rotation_engine._alert_thresholds = self._style_rotation_engine._load_alert_thresholds()
        self.logger.info("MarketStateEngine V11.1 配置热重载完成")
