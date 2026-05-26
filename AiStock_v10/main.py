#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AiStock V9.1 — 主入口 (Main Entry Point)

V9.1 完整管线编排:
  1. 初始化基础服务 (Logger, Config, Cache, ConnectionPool)
  2. 初始化数据层 (TDXAdapter, AKAdapter, DatabaseReader, DataLoaderService)
  3. 初始化核心引擎 (含V9.1 ContractManager动态合约推导)
  4. 执行9步分析管线
  5. 生成报告 (JSON)
  6. 生成可视化图表
  7. 输出汇总摘要

V9.1 关键改进:
  - 完整移植V7 ContractManager: 80+品种交割月规则 + 日期驱动动态推导
  - xlsx代码表code列与TDX接口code参数严格对齐
  - code/code_name双码制: TDX API用code, OptionCodeParser用code_name
  - 合约到期自动滚动 + 预警

CLI 参数:
  --config              自定义配置文件路径
  --mode                运行模式: production / development / backtest
  --skip-overseas       跳过外盘数据 (离线测试)
  --skip-visualization  跳过可视化生成

Usage:
  python main.py
  python main.py --config ./custom_config.yaml --mode development
  python main.py --skip-overseas --skip-visualization
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

# ─── 项目根目录 ──────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent

# 将项目根目录加入 sys.path
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ═══════════════════════════════════════════════════════════════════════════════
# 管线步骤计时器
# ═══════════════════════════════════════════════════════════════════════════════

class PipelineTimer:
    """管线步骤计时器"""

    def __init__(self) -> None:
        self._records: list[dict[str, Any]] = []

    def record(self, step: str, elapsed_ms: float, status: str = "ok") -> None:
        self._records.append({
            "step": step,
            "elapsed_ms": round(elapsed_ms, 1),
            "status": status,
        })

    def to_list(self) -> list[dict[str, Any]]:
        return self._records

    def total_ms(self) -> float:
        return sum(r["elapsed_ms"] for r in self._records)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. 基础服务初始化
# ═══════════════════════════════════════════════════════════════════════════════

def init_base_services(
    config_path: Optional[str] = None,
    mode: str = "production",
) -> Dict[str, Any]:
    """初始化基础服务层

    Returns:
        {
            'logger_service': LoggerService,
            'config': ConfigService,
            'cache': CacheService,
            'connection_pool': TDXConnectionPool,
            'logger': logging.Logger,
        }
    """
    from base_services import LoggerService, ConfigService, CacheService, TDXConnectionPool

    # LoggerService
    log_level_map = {
        "production": 20,    # INFO
        "development": 10,   # DEBUG
        "backtest": 30,      # WARNING
    }
    console_level = log_level_map.get(mode, 20)

    logger_service = LoggerService(
        console_level=console_level,
        project_root=str(PROJECT_ROOT),
    )
    logger = logger_service.get_logger("main")

    logger.info("=" * 70)
    logger.info("AiStock V9.1 市场状态量化系统 启动")
    logger.info("运行模式: %s", mode)
    logger.info("=" * 70)

    # ConfigService
    if config_path:
        config = ConfigService(config_path=config_path)
        logger.info("使用自定义配置: %s", config_path)
    else:
        config = ConfigService()
        logger.info("使用默认配置: %s", config.config_path)

    # 覆盖运行模式
    config.set("system.mode", mode)

    # CacheService
    cache_max_size = config.get("cache.max_size", 2000, value_type=int)
    cache_default_ttl = config.get("cache.default_ttl", 3600, value_type=int)
    cache = CacheService(max_size=cache_max_size, default_ttl=cache_default_ttl)
    logger.info("CacheService 初始化: max_size=%d, default_ttl=%ds", cache_max_size, cache_default_ttl)

    # TDXConnectionPool
    std_host = config.get("tdx.standard.host", "180.153.18.170")
    std_port = config.get("tdx.standard.port", 7709, value_type=int)
    ext_host = config.get("tdx.extension.host", "180.153.18.176")
    ext_port = config.get("tdx.extension.port", 7721, value_type=int)
    pool_size = config.get("tdx.parallel_workers", 3, value_type=int)

    connection_pool = TDXConnectionPool(
        pool_size=pool_size,
        standard_host=std_host,
        standard_port=std_port,
        extension_host=ext_host,
        extension_port=ext_port,
    )
    logger.info(
        "TDXConnectionPool 初始化: pool_size=%d | 标准=%s:%d | 扩展=%s:%d",
        pool_size, std_host, std_port, ext_host, ext_port,
    )

    return {
        "logger_service": logger_service,
        "config": config,
        "cache": cache,
        "connection_pool": connection_pool,
        "logger": logger,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 2. 数据层初始化
# ═══════════════════════════════════════════════════════════════════════════════

def init_data_layer(
    services: Dict[str, Any],
    skip_overseas: bool = False,
) -> Dict[str, Any]:
    """初始化数据访问层

    Returns:
        {
            'tdx_adapter': TDXAdapter,
            'ak_adapter': AKAdapter,
            'db_reader': DatabaseReader,
            'data_loader': DataLoaderService,
        }
    """
    config = services["config"]
    cache = services["cache"]
    logger = services["logger"]

    # TDXAdapter (双端口)
    from data_service import TDXAdapter, AKAdapter, DatabaseReader, DataLoaderService

    std_host = config.get("tdx.standard.host", "180.153.18.170")
    std_port = config.get("tdx.standard.port", 7709, value_type=int)
    ext_host = config.get("tdx.extension.host", "180.153.18.176")
    ext_port = config.get("tdx.extension.port", 7721, value_type=int)
    pool_size = config.get("tdx.parallel_workers", 3, value_type=int)

    tdx_adapter = TDXAdapter(
        std_host=std_host,
        std_port=std_port,
        ext_host=ext_host,
        ext_port=ext_port,
        pool_size=pool_size,
    )
    logger.info("TDXAdapter 初始化 (双端口模式: %s:%d / %s:%d)",
                std_host, std_port, ext_host, ext_port)

    # AKAdapter
    ak_adapter = AKAdapter(
        rate_limit_interval=0.5,
        retry_count=2,
        retry_delay=1.0,
        cache_ttl=300.0,
    )
    logger.info("AKAdapter 初始化 (海外期货29品种 + 辅助数据)")

    # DatabaseReader — 从 global_settings 获取数据库配置
    try:
        from config.global_settings import DATABASE_ENGINES
        db_config = DATABASE_ENGINES.get("index_pe_db", {})
        # global_settings 中 index_pe_db 是 URL 字符串, 需转为 dict
        if isinstance(db_config, str):
            db_config = {"url": db_config}
    except ImportError:
        db_config = None

    db_reader = DatabaseReader(
        db_config=db_config,
        engine_name="index_pe_db",
        fallback_on_error=True,
    )
    logger.info("DatabaseReader 初始化 (fallback=True)")

    # DataLoaderService
    data_loader = DataLoaderService(
        tdx_adapter=tdx_adapter,
        ak_adapter=ak_adapter,
        db_reader=db_reader,
    )
    logger.info("DataLoaderService 初始化 (7段数据编排)")

    return {
        "tdx_adapter": tdx_adapter,
        "ak_adapter": ak_adapter,
        "db_reader": db_reader,
        "data_loader": data_loader,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 3. 核心引擎初始化
# ═══════════════════════════════════════════════════════════════════════════════

def init_core_engines(
    services: Dict[str, Any],
    data_layer: Dict[str, Any],
    skip_overseas: bool = False,
) -> Dict[str, Any]:
    """初始化核心分析引擎

    Returns:
        {
            'contract_manager': ContractManager,
            'option_code_parser': OptionCodeParser,
            'option_pcr_engine': OptionPCREngine,
            'overseas_engine': OverseasFuturesSignalEngine | None,
            'derivatives_engine': DerivativesSignalEngine,
            'macro_engine': MacroSignalEngine,
            'regime_engine': MarketRegimeEngine,
            'state_classifier': MarketStateClassifier,
            'risk_engine': RiskAssessmentEngine,
        }
    """
    config = services["config"]
    cache = services["cache"]
    logger = services["logger"]

    engines: Dict[str, Any] = {}

    # ─── OptionCodeParser ─────────────────────────────
    try:
        from market_state_system.core.option_code_parser import OptionCodeParser

        option_code_parser = OptionCodeParser()
        engines["option_code_parser"] = option_code_parser
        logger.info("OptionCodeParser 初始化 (3格式统一解析)")
    except Exception as e:
        logger.error("OptionCodeParser 初始化失败: %s", e)
        engines["option_code_parser"] = None

    # ─── ContractManager (V9.1: 完整移植V7 + xlsx代码表对齐) ────
    try:
        from market_state_system.core.contract_manager import ContractManager

        # V9.1: 从 global_settings 获取代码表路径, 默认为 notebooks/ 下的 xlsx
        try:
            from config.global_settings import TDX_CODE_TABLE_PATH
            code_table_path = TDX_CODE_TABLE_PATH
        except ImportError:
            code_table_path = config.get(
                "contract_manager.code_table_path",
                str(PROJECT_ROOT / "notebooks" / "tdx基金期货期权代码表.xlsx"),
            )

        contract_manager = ContractManager(
            code_table_path=code_table_path,
            option_code_parser=engines.get("option_code_parser"),
        )
        engines["contract_manager"] = contract_manager
        logger.info(
            "ContractManager V9.1 初始化 | 代码表: %s | 合约数: %d",
            code_table_path, len(contract_manager.contracts),
        )
    except Exception as e:
        logger.error("ContractManager V9.1 初始化失败: %s", e)
        engines["contract_manager"] = None

    # ─── OptionPCREngine ─────────────────────────────
    try:
        from market_state_system.core.option_pcr_engine import OptionPCREngine

        option_pcr_engine = OptionPCREngine(
            tdx_adapter=data_layer["tdx_adapter"],
            config=config,
            cache_service=cache,
            contract_manager=engines.get("contract_manager"),  # V9.1: 注入ContractManager
        )
        engines["option_pcr_engine"] = option_pcr_engine
        logger.info("OptionPCREngine 初始化 (9ETF + 3CFFEX + 20商品 + ContractManager)")
    except Exception as e:
        logger.error("OptionPCREngine 初始化失败: %s", e)
        engines["option_pcr_engine"] = None

    # ─── OverseasFuturesSignalEngine ─────────────────
    overseas_engine = None
    if not skip_overseas:
        try:
            from market_state_system.core.overseas_futures_signal_engine import (
                OverseasFuturesSignalEngine,
            )

            overseas_engine = OverseasFuturesSignalEngine(
                ak_adapter=data_layer["ak_adapter"],
                data_loader=data_layer["data_loader"],
                config=config,
                cache=cache,
            )
            logger.info("OverseasFuturesSignalEngine 初始化 (4维度信号: 价格+持仓+宏观+情绪)")
        except Exception as e:
            logger.error("OverseasFuturesSignalEngine 初始化失败: %s", e)

    engines["overseas_engine"] = overseas_engine

    # ─── DerivativesSignalEngine ─────────────────────
    try:
        from market_state_system.core.derivatives_signal_engine import DerivativesSignalEngine

        engines["derivatives_engine"] = DerivativesSignalEngine(
            data_service=data_layer["tdx_adapter"],
            contract_manager=engines.get("contract_manager"),
            overseas_signal_engine=overseas_engine,
            config=config,
            cache=cache,
        )
        logger.info("DerivativesSignalEngine 初始化 (含ContractManager + 海外整合)")
    except Exception as e:
        logger.error("DerivativesSignalEngine 初始化失败: %s", e)
        engines["derivatives_engine"] = None

    # ─── MacroSignalEngine ───────────────────────────
    try:
        from market_state_system.core.macro_signal_engine import MacroSignalEngine

        engines["macro_engine"] = MacroSignalEngine(
            tdx_adapter=data_layer["tdx_adapter"],
            ak_adapter=data_layer["ak_adapter"],
            config=config,
            cache=cache,
        )
        logger.info("MacroSignalEngine 初始化 (99指标5维度)")
    except Exception as e:
        logger.error("MacroSignalEngine 初始化失败: %s", e)
        engines["macro_engine"] = None

    # ─── MarketRegimeEngine ──────────────────────────
    try:
        from market_state_system.core.market_regime_engine import MarketRegimeEngine

        engines["regime_engine"] = MarketRegimeEngine(
            data_service=data_layer["tdx_adapter"],
            config=config,
            cache=cache,
        )
        logger.info("MarketRegimeEngine 初始化 (含海外Regime调整)")
    except Exception as e:
        logger.error("MarketRegimeEngine 初始化失败: %s", e)
        engines["regime_engine"] = None

    # ─── MarketStateClassifier (4D) ──────────────────
    try:
        from market_state_system.core.market_state_classifier import MarketStateClassifier

        engines["state_classifier"] = MarketStateClassifier(
            data_service=data_layer["tdx_adapter"],
            db_reader=data_layer["db_reader"],
            config=config,
            cache=cache,
        )
        logger.info("MarketStateClassifier 初始化 (4D模型: 估值+动量+Regime+海外)")
    except Exception as e:
        logger.error("MarketStateClassifier 初始化失败: %s", e)
        engines["state_classifier"] = None

    # ─── RiskAssessmentEngine ────────────────────────
    try:
        from market_state_system.core.risk_assessment_engine import RiskAssessmentEngine

        engines["risk_engine"] = RiskAssessmentEngine(
            data_service=data_layer["tdx_adapter"],
            db_reader=data_layer["db_reader"],
            config=config,
            cache=cache,
        )
        logger.info("RiskAssessmentEngine 初始化 (含海外+PCR风险因子)")
    except Exception as e:
        logger.error("RiskAssessmentEngine 初始化失败: %s", e)
        engines["risk_engine"] = None

    return engines


# ═══════════════════════════════════════════════════════════════════════════════
# 4. 执行分析管线
# ═══════════════════════════════════════════════════════════════════════════════

def execute_pipeline(
    services: Dict[str, Any],
    data_layer: Dict[str, Any],
    engines: Dict[str, Any],
    timer: PipelineTimer,
    skip_overseas: bool = False,
) -> Dict[str, Any]:
    """执行V9.1完整分析管线 (9步)

    Returns:
        全部结果的字典
    """
    logger = services["logger"]
    results: Dict[str, Any] = {}

    # ─── Step 1: 加载全部市场数据 ──────────────────
    logger.info("-" * 60)
    logger.info("Step 1/9: 加载市场数据")
    t0 = time.time()
    try:
        market_data = data_layer["data_loader"].load_all()
        results["market_data"] = market_data
        elapsed = (time.time() - t0) * 1000
        timer.record("Step1_数据加载", elapsed)
        logger.info("✅ Step 1 完成 | %.0fms | %d 数据段", elapsed, len(market_data))
    except Exception as e:
        elapsed = (time.time() - t0) * 1000
        timer.record("Step1_数据加载", elapsed, status="error")
        logger.error("❌ Step 1 失败: %s", e)
        results["market_data"] = {}

    # ─── Step 2: 更新合约映射 ─────────────────────
    logger.info("-" * 60)
    logger.info("Step 2/9: 更新合约映射 (ContractManager V9.1)")
    t0 = time.time()
    try:
        cm = engines.get("contract_manager")
        if cm:
            cm.update()
        elapsed = (time.time() - t0) * 1000
        timer.record("Step2_合约映射", elapsed)
        logger.info("✅ Step 2 完成 | %.0fms", elapsed)
    except Exception as e:
        elapsed = (time.time() - t0) * 1000
        timer.record("Step2_合约映射", elapsed, status="error")
        logger.error("❌ Step 2 失败: %s", e)

    # ─── Step 3: 外盘期货信号 (4D) ─────────────────
    logger.info("-" * 60)
    logger.info("Step 3/9: 计算外盘期货四维信号")
    overseas_signal: Optional[Dict[str, Any]] = None
    t0 = time.time()
    if not skip_overseas and engines.get("overseas_engine"):
        try:
            overseas_result = engines["overseas_engine"].generate_overseas_signal()
            # 将 OverseasCompositeSignal 转为字典
            if hasattr(overseas_result, "to_dict"):
                overseas_signal = overseas_result.to_dict()
            elif isinstance(overseas_result, dict):
                overseas_signal = overseas_result
            else:
                overseas_signal = {}
            results["overseas"] = overseas_signal
            elapsed = (time.time() - t0) * 1000
            timer.record("Step3_外盘信号", elapsed)
            logger.info(
                "✅ Step 3 完成 | %.0fms | 综合=%.1f 方向=%s",
                elapsed,
                overseas_signal.get("composite_score", 0) if overseas_signal else 0,
                overseas_signal.get("direction", "N/A") if overseas_signal else "N/A",
            )
        except Exception as e:
            elapsed = (time.time() - t0) * 1000
            timer.record("Step3_外盘信号", elapsed, status="error")
            logger.error("❌ Step 3 失败: %s", e)
    else:
        timer.record("Step3_外盘信号", 0, status="skipped")
        logger.info("⏭ Step 3 跳过 (skip_overseas=%s)", skip_overseas)

    # ─── Step 4: 期权PCR (9ETF + 3CFFEX + 20商品) ──
    logger.info("-" * 60)
    logger.info("Step 4/9: 计算期权PCR")
    t0 = time.time()
    pcr_result: Dict[str, Any] = {}
    try:
        pcr_engine = engines.get("option_pcr_engine")
        if pcr_engine:
            etf_pcr = pcr_engine.calculate_all_etf_pcr()
            cffex_pcr = pcr_engine.calculate_all_cffex_pcr()
            commodity_pcr = pcr_engine.calculate_top_commodity_pcr()
            composite_pcr = pcr_engine.calculate_composite_pcr()
            divergence_signal = pcr_engine.detect_pcr_divergence()

            # 转为可序列化的字典
            def _to_dict_safe(obj: Any) -> Any:
                if hasattr(obj, "to_dict"):
                    return obj.to_dict()
                if isinstance(obj, dict):
                    return {k: _to_dict_safe(v) for k, v in obj.items()}
                return obj

            pcr_result = {
                "etf_pcr": _to_dict_safe(etf_pcr),
                "cffex_pcr": _to_dict_safe(cffex_pcr),
                "commodity_pcr": _to_dict_safe(commodity_pcr),
                "composite_pcr": _to_dict_safe(composite_pcr),
                "divergence_signal": _to_dict_safe(divergence_signal),
            }
            results["pcr"] = pcr_result

        elapsed = (time.time() - t0) * 1000
        timer.record("Step4_PCR计算", elapsed)
        logger.info("✅ Step 4 完成 | %.0fms", elapsed)
    except Exception as e:
        elapsed = (time.time() - t0) * 1000
        timer.record("Step4_PCR计算", elapsed, status="error")
        logger.error("❌ Step 4 失败: %s", e)
        results["pcr"] = {}

    # ─── Step 5: 衍生品信号 (国内+海外) ────────────
    logger.info("-" * 60)
    logger.info("Step 5/9: 计算衍生品信号")
    t0 = time.time()
    derivatives_result: Dict[str, Any] = {}
    derivatives_result_obj = None  # 保留原始对象用于后续引擎
    try:
        deriv_engine = engines.get("derivatives_engine")
        if deriv_engine:
            derivatives_result_obj = deriv_engine.calculate_all()
            derivatives_result = (
                derivatives_result_obj.to_dict()
                if hasattr(derivatives_result_obj, "to_dict")
                else derivatives_result_obj
            )
        results["derivatives"] = derivatives_result

        elapsed = (time.time() - t0) * 1000
        timer.record("Step5_衍生品信号", elapsed)
        logger.info("✅ Step 5 完成 | %.0fms", elapsed)
    except Exception as e:
        elapsed = (time.time() - t0) * 1000
        timer.record("Step5_衍生品信号", elapsed, status="error")
        logger.error("❌ Step 5 失败: %s", e)
        results["derivatives"] = {}

    # ─── Step 6: 宏观信号 ─────────────────────────
    logger.info("-" * 60)
    logger.info("Step 6/9: 计算宏观信号")
    t0 = time.time()
    macro_result: Dict[str, Any] = {}
    try:
        macro_engine = engines.get("macro_engine")
        if macro_engine:
            macro_result_obj = macro_engine.calculate_macro_signals()
            macro_result = (
                macro_result_obj.to_dict()
                if hasattr(macro_result_obj, "to_dict")
                else macro_result_obj
            )
        results["macro"] = macro_result

        elapsed = (time.time() - t0) * 1000
        timer.record("Step6_宏观信号", elapsed)
        logger.info("✅ Step 6 完成 | %.0fms", elapsed)
    except Exception as e:
        elapsed = (time.time() - t0) * 1000
        timer.record("Step6_宏观信号", elapsed, status="error")
        logger.error("❌ Step 6 失败: %s", e)
        results["macro"] = {}

    # ─── Step 7: 市场Regime检测 (含海外调整) ─────
    logger.info("-" * 60)
    logger.info("Step 7/9: 检测市场Regime")
    t0 = time.time()
    regime_result: Dict[str, Any] = {}
    regime_result_obj = None  # 保留原始对象用于后续引擎
    try:
        regime_engine = engines.get("regime_engine")
        if regime_engine:
            # 从已加载数据提取沪深300作为基准数据
            index_data = results.get("market_data", {}).get("index_data", {})
            hs300_df = index_data.get("000300") if isinstance(index_data, dict) else None
            regime_result_obj = regime_engine.detect(
                market_data=hs300_df,
                derivatives_result=derivatives_result_obj,
                pcr_result=pcr_result,
                overseas_signal=overseas_signal,
            )
            regime_result = (
                regime_result_obj.to_dict()
                if hasattr(regime_result_obj, "to_dict")
                else regime_result_obj
            )
        results["regime"] = regime_result

        elapsed = (time.time() - t0) * 1000
        timer.record("Step7_Regime检测", elapsed)
        logger.info("✅ Step 7 完成 | %.0fms", elapsed)
    except Exception as e:
        elapsed = (time.time() - t0) * 1000
        timer.record("Step7_Regime检测", elapsed, status="error")
        logger.error("❌ Step 7 失败: %s", e)
        results["regime"] = {}

    # ─── Step 8: 市场状态分类 (4D模型) ────────────
    logger.info("-" * 60)
    logger.info("Step 8/9: 市场状态4D分类")
    t0 = time.time()
    classification_result: Dict[str, Any] = {}
    classification_result_obj = None  # 保留原始对象用于后续引擎
    try:
        classifier = engines.get("state_classifier")
        if classifier:
            # 从已加载数据提取沪深300作为基准数据
            index_data = results.get("market_data", {}).get("index_data", {})
            hs300_df = index_data.get("000300") if isinstance(index_data, dict) else None
            classification_result_obj = classifier.classify(
                market_data=hs300_df,
                regime_result=regime_result_obj,
                derivatives_result=derivatives_result_obj,
                pcr_result=pcr_result,
                overseas_signal=overseas_signal,
            )
            classification_result = (
                classification_result_obj.to_dict()
                if hasattr(classification_result_obj, "to_dict")
                else classification_result_obj
            )
        results["classification"] = classification_result

        elapsed = (time.time() - t0) * 1000
        timer.record("Step8_状态分类", elapsed)
        logger.info("✅ Step 8 完成 | %.0fms", elapsed)
    except Exception as e:
        elapsed = (time.time() - t0) * 1000
        timer.record("Step8_状态分类", elapsed, status="error")
        logger.error("❌ Step 8 失败: %s", e)
        results["classification"] = {}

    # ─── Step 9: 风险评估 (含海外+PCR风险因子) ───
    logger.info("-" * 60)
    logger.info("Step 9/9: 风险评估")
    t0 = time.time()
    risk_result: Dict[str, Any] = {}
    try:
        risk_engine = engines.get("risk_engine")
        if risk_engine:
            # 从已加载数据提取沪深300作为基准数据
            index_data = results.get("market_data", {}).get("index_data", {})
            hs300_df = index_data.get("000300") if isinstance(index_data, dict) else None
            risk_result_obj = risk_engine.assess(
                classification_result=classification_result_obj,
                regime_result=regime_result_obj,
                derivatives_result=derivatives_result_obj,
                pcr_result=pcr_result,
                overseas_signal=overseas_signal,
                market_data=hs300_df,
            )
            risk_result = (
                risk_result_obj.to_dict()
                if hasattr(risk_result_obj, "to_dict")
                else risk_result_obj
            )
        results["risk"] = risk_result

        elapsed = (time.time() - t0) * 1000
        timer.record("Step9_风险评估", elapsed)
        logger.info("✅ Step 9 完成 | %.0fms", elapsed)
    except Exception as e:
        elapsed = (time.time() - t0) * 1000
        timer.record("Step9_风险评估", elapsed, status="error")
        logger.error("❌ Step 9 失败: %s", e)
        results["risk"] = {}

    return results


# ═══════════════════════════════════════════════════════════════════════════════
# 辅助: 维度评分计算
# ═══════════════════════════════════════════════════════════════════════════════

def _compute_valuation_score(
    valuation_data: Any,
    logger: Any,
) -> float:
    """从估值数据计算估值维度评分"""
    if not valuation_data or not isinstance(valuation_data, dict):
        return 50.0

    scores = []
    for code, df in valuation_data.items():
        if df is None or not hasattr(df, "empty") or df.empty:
            continue
        try:
            if "pe_percentile" in df.columns:
                pe_pct = float(df["pe_percentile"].iloc[-1])
                # PE百分位越低越便宜 → 评分越高
                score = 100.0 - pe_pct
                scores.append(score)
            elif "close" in df.columns and len(df) >= 2:
                # 无百分位数据, 简单用价格变化估算
                ret = (float(df["close"].iloc[-1]) / float(df["close"].iloc[-2]) - 1.0)
                scores.append(50.0 + ret * 200.0)
        except Exception:
            continue

    if scores:
        return max(0.0, min(100.0, sum(scores) / len(scores)))
    return 50.0


def _compute_momentum_score(
    index_data: Any,
    logger: Any,
) -> float:
    """从指数数据计算动量维度评分"""
    if not index_data or not isinstance(index_data, dict):
        return 50.0

    scores = []
    for code, df in index_data.items():
        if df is None or not hasattr(df, "empty") or df.empty:
            continue
        try:
            if "close" in df.columns and len(df) >= 20:
                close = df["close"].values
                ret_20d = (float(close[-1]) / float(close[-20]) - 1.0) * 100.0
                # 动量映射: -5%→0分, 0%→50分, +5%→100分
                score = 50.0 + ret_20d * 10.0
                scores.append(score)
        except Exception:
            continue

    if scores:
        return max(0.0, min(100.0, sum(scores) / len(scores)))
    return 50.0


# ═══════════════════════════════════════════════════════════════════════════════
# 5. 报告生成
# ═══════════════════════════════════════════════════════════════════════════════

def generate_report(
    results: Dict[str, Any],
    timer: PipelineTimer,
    services: Dict[str, Any],
    skip_overseas: bool = False,
) -> str:
    """生成JSON报告

    Returns:
        报告文件路径
    """
    logger = services["logger"]

    # 构建报告
    report: Dict[str, Any] = {
        "version": "9.1.0",
        "timestamp": datetime.now().isoformat(),
        "mode": services["config"].get("system.mode", "production"),
        "skip_overseas": skip_overseas,
        "pipeline_timing": timer.to_list(),
        "total_elapsed_ms": round(timer.total_ms(), 1),
        "results": {},
    }

    # 逐模块写入 (排除原始市场数据, 仅保留分析结果)
    for key in ["classification", "regime", "derivatives", "pcr", "risk", "macro", "overseas"]:
        if key in results:
            report["results"][key] = results[key]

    # 摘要
    classification = results.get("classification", {})
    risk = results.get("risk", {})

    report["summary"] = {
        "composite_score": classification.get("composite_score", 50),
        "state_label": classification.get("state_label", "均衡持有"),
        "direction": classification.get("direction",
            "bullish" if classification.get("composite_score", 50) >= 60 else (
                "bearish" if classification.get("composite_score", 50) < 40 else "neutral"
            )
        ),
        "risk_level": risk.get("risk_level", "moderate"),
        "risk_score": risk.get("overall_risk_score", 50),
        "regime": results.get("regime", {}).get("regime_label",
            results.get("regime", {}).get("current_regime", "未知")),
        "overseas_signal": (
            results.get("overseas", {}).get("direction", "N/A")
            if not skip_overseas else "skipped"
        ),
    }

    # 保存
    output_dir = PROJECT_ROOT / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    report_path = output_dir / "latest_report.json"

    # 自定义序列化: 处理不可序列化的对象
    def _default_serializer(obj: Any) -> Any:
        if hasattr(obj, "to_dict"):
            return obj.to_dict()
        if hasattr(obj, "__dict__"):
            return str(obj)
        return str(obj)

    with open(str(report_path), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=_default_serializer)

    logger.info("报告已生成: %s", report_path)
    return str(report_path)


# ═══════════════════════════════════════════════════════════════════════════════
# 6. 可视化生成
# ═══════════════════════════════════════════════════════════════════════════════

def generate_visualizations(
    results: Dict[str, Any],
    services: Dict[str, Any],
    use_plotly: bool = True,
) -> list[str]:
    """生成所有可视化图表 (支持 matplotlib + Plotly 双引擎)

    Args:
        results:  管线结果字典
        services: 基础服务字典
        use_plotly: 是否使用 Plotly 交互可视化 (默认True)

    Returns:
        生成的图表文件路径列表
    """
    logger = services["logger"]
    paths: list[str] = []

    # ─── Plotly 交互可视化 (HTML) ──────────────────────
    if use_plotly:
        try:
            from market_state_system.visualization import PlotlyVisualizer

            pviz = PlotlyVisualizer(config=services["config"])
            figures = pviz.generate_all(results, save_html=True, save_json=False)
            paths.extend([
                f"[Plotly] {name}" for name in figures.keys()
            ])
            logger.info("✅ Plotly 交互图表生成完成: %d 个 HTML", len(figures))
        except ImportError as e:
            logger.warning("PlotlyVisualizer 导入失败, 回退到 matplotlib: %s", e)
            use_plotly = False
        except Exception as e:
            logger.warning("Plotly 交互图表生成异常: %s", e)
            use_plotly = False

    # ─── Matplotlib 静态可视化 (PNG, 保留兼容) ────────
    try:
        from market_state_system.visualization import StateVisualizer

        viz = StateVisualizer(config=services["config"])

        # 1. 4D雷达图
        try:
            p = viz.plot_market_state_4d(results.get("classification", {}))
            paths.append(p)
            logger.info("  ✅ 4D雷达图: %s", p)
        except Exception as e:
            logger.warning("4D雷达图生成失败: %s", e)

        # 2. Regime概率图
        try:
            p = viz.plot_regime_probability(results.get("regime", {}))
            paths.append(p)
            logger.info("  ✅ Regime概率图: %s", p)
        except Exception as e:
            logger.warning("Regime概率图生成失败: %s", e)

        # 3. 衍生品仪表板
        try:
            p = viz.plot_derivatives_dashboard(results.get("derivatives", {}))
            paths.append(p)
            logger.info("  ✅ 衍生品仪表板: %s", p)
        except Exception as e:
            logger.warning("衍生品仪表板生成失败: %s", e)

        # 4. 风险仪表板
        try:
            p = viz.plot_risk_dashboard(results.get("risk", {}))
            paths.append(p)
            logger.info("  ✅ 风险仪表板: %s", p)
        except Exception as e:
            logger.warning("风险仪表板生成失败: %s", e)

        # 5. PCR仪表板
        try:
            p = viz.plot_pcr_dashboard(results.get("pcr", {}))
            paths.append(p)
            logger.info("  ✅ PCR仪表板: %s", p)
        except Exception as e:
            logger.warning("PCR仪表板生成失败: %s", e)

        # 6. 外盘信号面板
        try:
            if "overseas" in results:
                p = viz.plot_overseas_signal_dashboard(results.get("overseas", {}))
                paths.append(p)
                logger.info("  ✅ 外盘信号面板: %s", p)
        except Exception as e:
            logger.warning("外盘信号面板生成失败: %s", e)

        # 7. 综合仪表板
        try:
            p = viz.plot_composite_dashboard(results)
            paths.append(p)
            logger.info("  ✅ 综合仪表板: %s", p)
        except Exception as e:
            logger.warning("综合仪表板生成失败: %s", e)

    except ImportError as e:
        logger.error("StateVisualizer 导入失败, 跳过可视化: %s", e)
    except Exception as e:
        logger.error("可视化生成异常: %s", e)

    return paths


# ═══════════════════════════════════════════════════════════════════════════════
# 7. 汇总摘要输出
# ═══════════════════════════════════════════════════════════════════════════════

def print_summary(
    results: Dict[str, Any],
    timer: PipelineTimer,
    report_path: str,
    viz_paths: list[str],
    skip_overseas: bool,
) -> None:
    """打印格式化的汇总摘要表"""

    classification = results.get("classification", {})
    risk = results.get("risk", {})
    regime = results.get("regime", {})
    overseas = results.get("overseas", {})
    pcr = results.get("pcr", {})
    derivatives = results.get("derivatives", {})
    macro = results.get("macro", {})

    comp_pcr = pcr.get("composite_pcr", {})
    if hasattr(comp_pcr, "to_dict"):
        comp_pcr = comp_pcr.to_dict()

    # ─── 兼容层: 从真实引擎结果提取关键字段 ────
    # 分类方向 (真实引擎无direction字段, 从composite_score推导)
    comp_score = classification.get("composite_score", 50)
    c_dir = classification.get("direction", "")
    if not c_dir:
        c_dir = "bullish" if comp_score >= 60 else ("bearish" if comp_score < 40 else "neutral")

    # Regime标签 (真实引擎用英文current_regime + 中文regime_label)
    r_dir = regime.get("regime_label", "") or regime.get("current_regime", "未知")

    o_dir = overseas.get("direction", "N/A") if not skip_overseas else "跳过"

    # 衍生品信号级别 (真实引擎用composite_direction)
    d_level = derivatives.get("signal_level", "") or derivatives.get("composite_direction", "normal")

    # 维度评分 (真实引擎scores嵌套结构)
    scores = classification.get("scores", {})
    val_score = classification.get("valuation_score", 0) or (
        scores.get("valuation", {}).get("score", 50) if isinstance(scores, dict) else 50
    )
    mom_score = classification.get("momentum_score", 0) or (
        scores.get("momentum", {}).get("score", 50) if isinstance(scores, dict) else 50
    )
    reg_score = classification.get("regime_score", 0) or (
        scores.get("regime", {}).get("score", 50) if isinstance(scores, dict) else 50
    )
    ovs_score = classification.get("overseas_score", 0) or (
        scores.get("overseas", {}).get("score", 50) if isinstance(scores, dict) else 50
    )

    # 宏观方向 (真实引擎用trend_direction)
    macro_dir = macro.get("direction", "") or macro.get("trend_direction", "N/A")

    # 风险颜色
    risk_level = risk.get("risk_level", "moderate")
    risk_icon = {"low": "🟢", "moderate": "🟡", "high": "🔴", "extreme": "⛔"}.get(
        risk_level, "⚪"
    )

    # 方向标记
    def _dir_icon(d: str) -> str:
        d = d.lower()
        if "bull" in d or d in ("up", "long", "improving"):
            return "▲"
        elif "bear" in d or d in ("down", "short", "deteriorating"):
            return "▼"
        return "◆"

    print("\n")
    print("╔" + "═" * 68 + "╗")
    print("║" + " AiStock V9.1 市场状态量化系统 — 运行摘要".center(66) + "║")
    print("╠" + "═" * 68 + "╣")

    # 核心结果
    print("║" + "".center(68) + "║")
    print(f"║  综合评分: {comp_score:>6.1f}  │  "
          f"状态: {classification.get('state_label', '均衡持有'):<8s}  │  "
          f"方向: {_dir_icon(c_dir)} {c_dir:<10s}  ║")

    print("║" + "─" * 68 + "║")

    # 维度评分
    print(f"║  估值: {val_score:>5.1f}  │  "
          f"动量: {mom_score:>5.1f}  │  "
          f"Regime: {reg_score:>5.1f}  │  "
          f"海外: {ovs_score:>5.1f}  ║")

    print("║" + "─" * 68 + "║")

    # 子模块
    print(f"║  Regime:   {r_dir:<8s}  │  "
          f"衍生品: {d_level:<8s}  │  "
          f"外盘: {_dir_icon(o_dir)} {o_dir:<8s}  ║")

    pcr_val = comp_pcr.get("composite_pcr", 0) if isinstance(comp_pcr, dict) else 0
    pcr_level = comp_pcr.get("signal_level", "N/A") if isinstance(comp_pcr, dict) else "N/A"
    print(f"║  PCR综合:  {pcr_val:>5.3f}  │  "
          f"PCR级别: {pcr_level:<8s}  │  "
          f"宏观: {macro_dir:<8s}  ║")

    print("║" + "─" * 68 + "║")

    # 风险
    print(f"║  风险评分: {risk.get('overall_risk_score', 50):>5.1f}  │  "
          f"级别: {risk_icon} {risk_level:<8s}  │  "
          f"警告: {len(risk.get('warnings', [])):<3d}条     ║")

    print("║" + "─" * 68 + "║")

    # 管线计时
    print(f"║  总耗时: {timer.total_ms():>8.0f}ms  │  "
          f"步骤: {len(timer.to_list())}步  │  "
          f"报告: {report_path:<20s}  ║")

    viz_count = len(viz_paths)
    print(f"║  可视化: {viz_count:>3d}张  │  "
          f"输出: output/visualization/  │  "
          f"海外: {'跳过' if skip_overseas else '启用':<6s}      ║")

    print("╚" + "═" * 68 + "╝")
    print()

    # 详细步骤计时
    print("步骤计时明细:")
    print("-" * 50)
    for rec in timer.to_list():
        status_icon = "✅" if rec["status"] == "ok" else (
            "❌" if rec["status"] == "error" else "⏭"
        )
        print(f"  {status_icon} {rec['step']:<20s}  {rec['elapsed_ms']:>8.0f}ms  [{rec['status']}]")
    print("-" * 50)
    print(f"  {'总计':<20s}  {timer.total_ms():>8.0f}ms")
    print()


# ═══════════════════════════════════════════════════════════════════════════════
# CLI 参数解析
# ═══════════════════════════════════════════════════════════════════════════════

def parse_args() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="AiStock V9.1 A股市场状态量化系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
运行模式:
  production   生产模式 (INFO日志, 完整数据加载)
  development  开发模式 (DEBUG日志, 可自定义配置)
  backtest     回测模式 (WARNING日志, 历史数据)

示例:
  python main.py
  python main.py --mode development
  python main.py --config ./my_config.yaml
  python main.py --skip-overseas --skip-visualization
        """,
    )

    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="自定义配置文件路径 (默认: config/system_config.yaml)",
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="production",
        choices=["production", "development", "backtest"],
        help="运行模式 (默认: production)",
    )
    parser.add_argument(
        "--skip-overseas",
        action="store_true",
        default=False,
        help="跳过外盘数据 (离线测试模式)",
    )
    parser.add_argument(
        "--skip-visualization",
        action="store_true",
        default=False,
        help="跳过可视化图表生成",
    )

    return parser.parse_args()


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> int:
    """AiStock V9.1 主入口"""
    total_start = time.time()

    # ─── 解析CLI参数 ─────────────────────────────────
    args = parse_args()

    # ─── 1. 初始化基础服务 ───────────────────────────
    try:
        services = init_base_services(
            config_path=args.config,
            mode=args.mode,
        )
    except Exception as e:
        print(f"❌ 基础服务初始化失败: {e}")
        return 1

    logger = services["logger"]
    timer = PipelineTimer()

    # ─── 2. 初始化数据层 ─────────────────────────────
    try:
        data_layer = init_data_layer(
            services,
            skip_overseas=args.skip_overseas,
        )
    except Exception as e:
        logger.error("数据层初始化失败: %s", e)
        return 1

    # ─── 3. 初始化核心引擎 ───────────────────────────
    try:
        engines = init_core_engines(
            services,
            data_layer,
            skip_overseas=args.skip_overseas,
        )
    except Exception as e:
        logger.error("核心引擎初始化失败: %s", e)
        return 1

    # ─── 4. 执行管线 ─────────────────────────────────
    try:
        results = execute_pipeline(
            services,
            data_layer,
            engines,
            timer,
            skip_overseas=args.skip_overseas,
        )
    except Exception as e:
        logger.error("管线执行异常: %s", e)
        results = {}

    # ─── 5. 生成报告 ─────────────────────────────────
    try:
        report_path = generate_report(
            results, timer, services,
            skip_overseas=args.skip_overseas,
        )
    except Exception as e:
        logger.error("报告生成失败: %s", e)
        report_path = "N/A"

    # ─── 6. 生成可视化 ───────────────────────────────
    viz_paths: list[str] = []
    if not args.skip_visualization:
        try:
            viz_paths = generate_visualizations(results, services)
        except Exception as e:
            logger.error("可视化生成失败: %s", e)

    # ─── 7. 输出摘要 ─────────────────────────────────
    total_elapsed = (time.time() - total_start) * 1000
    timer.record("总计", total_elapsed)

    print_summary(
        results, timer, report_path, viz_paths,
        skip_overseas=args.skip_overseas,
    )

    logger.info("AiStock V9.1 运行完成 | 总耗时 %.0fms", total_elapsed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
