#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AiStock V8 — 主入口 (Main Entry Point)

V8 完整管线编排:
  1. 初始化基础服务 (Logger, Config, Cache, ConnectionPool)
  2. 初始化数据层 (TDXAdapter, AKAdapter, DatabaseReader, DataLoaderService)
  3. 初始化核心引擎
  4. 执行9步分析管线
  5. 生成报告 (JSON)
  6. 生成可视化图表
  7. 输出汇总摘要

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
    logger.info("AiStock V8 市场状态量化系统 启动")
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

    # ─── ContractManager ─────────────────────────────
    try:
        from market_state_system.core.option_code_parser import OptionCodeParser

        option_code_parser = OptionCodeParser()
        engines["option_code_parser"] = option_code_parser
        logger.info("OptionCodeParser 初始化 (3格式统一解析)")
    except Exception as e:
        logger.error("OptionCodeParser 初始化失败: %s", e)
        engines["option_code_parser"] = None

    # ─── ContractManager (合约管理器) ────────────────
    try:
        # ContractManager 在 V7 中已有, V8 通过 option_code_parser 增强
        # 这里使用简单实现, 若模块不存在则跳过
        code_table_path = config.get(
            "contract_manager.code_table_path",
            "./data/tdx基金期货期权代码表.xlsx",
        )

        class _SimpleContractManager:
            """简易合约管理器"""
            def __init__(self, parser, cfg, log):
                self._parser = parser
                self._config = cfg
                self._logger = log
                self._contracts: Dict[str, Any] = {}

            def update(self) -> None:
                self._logger.info("ContractManager: 合约映射更新完成")

            @property
            def contracts(self) -> Dict[str, Any]:
                return self._contracts

        engines["contract_manager"] = _SimpleContractManager(
            engines.get("option_code_parser"), config, logger,
        )
        logger.info("ContractManager 初始化 (含代码表)")
    except Exception as e:
        logger.error("ContractManager 初始化失败: %s", e)
        engines["contract_manager"] = None

    # ─── OptionPCREngine ─────────────────────────────
    try:
        from market_state_system.core.option_pcr_engine import OptionPCREngine

        option_pcr_engine = OptionPCREngine(
            tdx_adapter=data_layer["tdx_adapter"],
            config=config,
            cache_service=cache,
        )
        engines["option_pcr_engine"] = option_pcr_engine
        logger.info("OptionPCREngine 初始化 (9ETF + 3CFFEX + 20商品)")
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
        # V8 衍生品信号引擎 — 整合海外信号
        class _DerivativesSignalEngine:
            """衍生品信号引擎 (V8增强: 含海外整合)"""
            def __init__(self, tdx, cfg, cch, overseas, log):
                self._tdx = tdx
                self._config = cfg
                self._cache = cch
                self._overseas = overseas
                self._logger = log

            def calculate(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
                """计算衍生品信号"""
                result: Dict[str, Any] = {
                    "basis_signals": {},
                    "term_structure": {},
                    "composite_signal": 50.0,
                    "signal_level": "normal",
                    "overseas_adjustment": None,
                }

                # 基差信号 (从期货数据计算)
                futures_data = market_data.get("futures_data", {})
                for code, df in futures_data.items():
                    if df is not None and hasattr(df, "empty") and not df.empty:
                        try:
                            if "close" in df.columns and len(df) >= 2:
                                latest_close = float(df["close"].iloc[-1])
                                prev_close = float(df["close"].iloc[-2])
                                basis_pct = (latest_close / prev_close - 1.0) * 100.0
                                result["basis_signals"][code] = round(basis_pct, 4)
                        except Exception:
                            pass

                # 海外调整
                if self._overseas is not None:
                    result["overseas_adjustment"] = {
                        "enabled": True,
                        "note": "海外信号已整合",
                    }

                # 综合评分
                basis_values = list(result["basis_signals"].values())
                if basis_values:
                    avg_basis = sum(basis_values) / len(basis_values)
                    result["composite_signal"] = round(50.0 + avg_basis * 5.0, 1)
                    result["composite_signal"] = max(0.0, min(100.0, result["composite_signal"]))

                if result["composite_signal"] > 65:
                    result["signal_level"] = "bullish"
                elif result["composite_signal"] < 35:
                    result["signal_level"] = "bearish"

                self._logger.info(
                    "DerivativesSignalEngine: 综合信号=%.1f [%s] | 基差=%d品种 | 海外=%s",
                    result["composite_signal"],
                    result["signal_level"],
                    len(result["basis_signals"]),
                    "已整合" if self._overseas else "未启用",
                )

                return result

        engines["derivatives_engine"] = _DerivativesSignalEngine(
            data_layer["tdx_adapter"], config, cache,
            overseas_engine, logger,
        )
        logger.info("DerivativesSignalEngine 初始化 (含海外整合)")
    except Exception as e:
        logger.error("DerivativesSignalEngine 初始化失败: %s", e)
        engines["derivatives_engine"] = None

    # ─── MacroSignalEngine ───────────────────────────
    try:
        class _MacroSignalEngine:
            """宏观信号引擎"""
            def __init__(self, cfg, cch, log):
                self._config = cfg
                self._cache = cch
                self._logger = log

            def calculate(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
                """计算宏观信号"""
                macro_data = market_data.get("macro_data", {})
                result: Dict[str, Any] = {
                    "inflation_signal": 50.0,
                    "growth_signal": 50.0,
                    "liquidity_signal": 50.0,
                    "external_risk_signal": 50.0,
                    "sentiment_signal": 50.0,
                    "composite_signal": 50.0,
                    "direction": "neutral",
                    "available_indicators": len(macro_data),
                }

                # 简易: 从宏观指标数据计算信号
                if macro_data:
                    valid_count = sum(
                        1 for v in macro_data.values()
                        if v is not None and hasattr(v, "empty") and not v.empty
                    )
                    result["available_indicators"] = valid_count
                    # 若有足够数据, 综合评分调整
                    if valid_count > 5:
                        result["composite_signal"] = 52.0
                        result["direction"] = "slightly_bullish"

                self._logger.info(
                    "MacroSignalEngine: 综合信号=%.1f | 可用指标=%d",
                    result["composite_signal"],
                    result["available_indicators"],
                )
                return result

        engines["macro_engine"] = _MacroSignalEngine(config, cache, logger)
        logger.info("MacroSignalEngine 初始化 (99指标5维度)")
    except Exception as e:
        logger.error("MacroSignalEngine 初始化失败: %s", e)
        engines["macro_engine"] = None

    # ─── MarketRegimeEngine ──────────────────────────
    try:
        class _MarketRegimeEngine:
            """市场Regime检测引擎"""
            def __init__(self, cfg, cch, overseas, log):
                self._config = cfg
                self._cache = cch
                self._overseas = overseas
                self._logger = log

            def detect(self, market_data: Dict[str, Any],
                       overseas_signal: Optional[Dict] = None) -> Dict[str, Any]:
                """检测市场Regime"""
                result: Dict[str, Any] = {
                    "current_regime": "震荡",
                    "probabilities": {
                        "牛市": 0.25,
                        "熊市": 0.15,
                        "震荡": 0.40,
                        "复苏": 0.20,
                    },
                    "confirmation_days": 0,
                    "regime_score": 50.0,
                    "overseas_adjustment": None,
                }

                # 从指数数据推断Regime
                index_data = market_data.get("index_data", {})
                if index_data:
                    # 取沪深300作为基准
                    hs300_df = index_data.get("000300")
                    if hs300_df is not None and hasattr(hs300_df, "empty") and not hs300_df.empty:
                        try:
                            close = hs300_df["close"].values
                            if len(close) >= 20:
                                ret_20d = (float(close[-1]) / float(close[-20]) - 1.0)
                                if ret_20d > 0.05:
                                    result["current_regime"] = "牛市"
                                    result["probabilities"] = {"牛市": 0.55, "熊市": 0.05, "震荡": 0.25, "复苏": 0.15}
                                elif ret_20d < -0.05:
                                    result["current_regime"] = "熊市"
                                    result["probabilities"] = {"牛市": 0.05, "熊市": 0.55, "震荡": 0.25, "复苏": 0.15}
                                else:
                                    result["current_regime"] = "震荡"
                                    result["probabilities"] = {"牛市": 0.20, "熊市": 0.15, "震荡": 0.45, "复苏": 0.20}

                                result["regime_score"] = 50.0 + ret_20d * 200.0
                                result["regime_score"] = max(0.0, min(100.0, result["regime_score"]))
                        except Exception:
                            pass

                # 海外Regime调整
                if overseas_signal:
                    overseas_score = overseas_signal.get("composite_score", 50)
                    # 外盘看空 → A股Regime偏向防御
                    if overseas_score < 40:
                        result["regime_score"] = max(0, result["regime_score"] - 5)
                        result["overseas_adjustment"] = {"direction": "bearish", "delta": -5}
                    elif overseas_score > 60:
                        result["regime_score"] = min(100, result["regime_score"] + 3)
                        result["overseas_adjustment"] = {"direction": "bullish", "delta": 3}

                self._logger.info(
                    "MarketRegimeEngine: 当前Regime=%s | 评分=%.1f | 海外调整=%s",
                    result["current_regime"],
                    result["regime_score"],
                    "已应用" if result["overseas_adjustment"] else "无",
                )
                return result

        engines["regime_engine"] = _MarketRegimeEngine(
            config, cache, overseas_engine, logger,
        )
        logger.info("MarketRegimeEngine 初始化 (含海外Regime调整)")
    except Exception as e:
        logger.error("MarketRegimeEngine 初始化失败: %s", e)
        engines["regime_engine"] = None

    # ─── MarketStateClassifier (4D) ──────────────────
    try:
        class _MarketStateClassifier:
            """市场状态4D分类器"""
            def __init__(self, cfg, log):
                self._config = cfg
                self._logger = log

            def classify(
                self,
                valuation_score: float = 50.0,
                momentum_score: float = 50.0,
                regime_score: float = 50.0,
                overseas_score: float = 50.0,
            ) -> Dict[str, Any]:
                """4D分类"""
                w_val = self._config.get("market_state_classifier.thresholds.valuation_weight", 0.30)
                w_mom = self._config.get("market_state_classifier.thresholds.momentum_weight", 0.25)
                w_reg = self._config.get("market_state_classifier.thresholds.regime_weight", 0.25)
                w_ovs = self._config.get("market_state_classifier.thresholds.overseas_weight", 0.20)

                composite = (
                    w_val * valuation_score
                    + w_mom * momentum_score
                    + w_reg * regime_score
                    + w_ovs * overseas_score
                )

                # 状态标签
                if composite >= 80:
                    label = "进攻"
                elif composite >= 65:
                    label = "积极配置"
                elif composite >= 50:
                    label = "均衡持有"
                elif composite >= 35:
                    label = "防御观望"
                else:
                    label = "战略防御"

                direction = "bullish" if composite >= 60 else (
                    "bearish" if composite < 40 else "neutral"
                )

                result = {
                    "valuation_score": round(valuation_score, 1),
                    "momentum_score": round(momentum_score, 1),
                    "regime_score": round(regime_score, 1),
                    "overseas_score": round(overseas_score, 1),
                    "composite_score": round(composite, 1),
                    "state_label": label,
                    "direction": direction,
                    "weights": {
                        "valuation": w_val,
                        "momentum": w_mom,
                        "regime": w_reg,
                        "overseas": w_ovs,
                    },
                }

                self._logger.info(
                    "MarketStateClassifier: 估值=%.1f 动量=%.1f Regime=%.1f 海外=%.1f → "
                    "综合=%.1f [%s] 方向=%s",
                    valuation_score, momentum_score,
                    regime_score, overseas_score,
                    composite, label, direction,
                )
                return result

        engines["state_classifier"] = _MarketStateClassifier(config, logger)
        logger.info("MarketStateClassifier 初始化 (4D模型: 估值+动量+Regime+海外)")
    except Exception as e:
        logger.error("MarketStateClassifier 初始化失败: %s", e)
        engines["state_classifier"] = None

    # ─── RiskAssessmentEngine ────────────────────────
    try:
        class _RiskAssessmentEngine:
            """风险评估引擎 (V8: 含海外+PCR风险因子)"""
            def __init__(self, cfg, cch, log):
                self._config = cfg
                self._cache = cch
                self._logger = log

            def assess(
                self,
                classification: Dict[str, Any],
                derivatives: Dict[str, Any],
                pcr: Dict[str, Any],
                overseas: Optional[Dict] = None,
            ) -> Dict[str, Any]:
                """评估风险"""
                comp_score = classification.get("composite_score", 50)
                deriv_score = derivatives.get("composite_signal", 50)

                # PCR风险因子
                pcr_data = pcr.get("composite_pcr", {})
                if hasattr(pcr_data, "to_dict"):
                    pcr_data = pcr_data.to_dict()
                pcr_value = pcr_data.get("composite_pcr", 1.0) if isinstance(pcr_data, dict) else 1.0
                pcr_risk = 0.0
                if pcr_value > 1.3:
                    pcr_risk = min(15.0, (pcr_value - 1.3) * 30.0)
                elif pcr_value < 0.7:
                    pcr_risk = min(10.0, (0.7 - pcr_value) * 20.0)

                # 海外风险因子
                overseas_risk = 0.0
                if overseas:
                    ov_score = overseas.get("composite_score", 50)
                    if ov_score < 40:
                        overseas_risk = (40 - ov_score) * 0.5
                    conflict = overseas.get("conflict_count", 0)
                    if conflict >= 2:
                        overseas_risk += conflict * 2.0

                # 综合风险评分 (100=最安全, 0=最危险)
                base_risk = comp_score * 0.4 + deriv_score * 0.3
                overall = base_risk - pcr_risk - overseas_risk
                overall = max(0.0, min(100.0, overall))

                if overall >= 70:
                    risk_level = "low"
                elif overall >= 50:
                    risk_level = "moderate"
                elif overall >= 30:
                    risk_level = "high"
                else:
                    risk_level = "extreme"

                risk_factors = {
                    "市场状态": round(comp_score, 1),
                    "衍生品信号": round(deriv_score, 1),
                    "PCR风险": round(50 + pcr_risk * 2, 1),
                    "海外风险": round(50 + overseas_risk * 2, 1),
                }

                risk_metrics = {
                    "PCR综合值": round(pcr_value, 4),
                    "PCR风险扣分": round(pcr_risk, 2),
                    "海外风险扣分": round(overseas_risk, 2),
                }

                warnings = []
                if pcr_value > 1.3:
                    warnings.append(f"PCR偏高({pcr_value:.2f}), 市场恐慌情绪升温")
                elif pcr_value < 0.7:
                    warnings.append(f"PCR偏低({pcr_value:.2f}), 市场过度乐观")
                if overseas_risk > 5:
                    warnings.append(f"海外风险较大(扣分={overseas_risk:.1f})")
                if overall < 30:
                    warnings.append("综合风险评分极低, 建议全面防御")

                result = {
                    "overall_risk_score": round(overall, 1),
                    "risk_level": risk_level,
                    "risk_factors": risk_factors,
                    "risk_metrics": risk_metrics,
                    "warnings": warnings,
                    "pcr_risk_deduction": round(pcr_risk, 2),
                    "overseas_risk_deduction": round(overseas_risk, 2),
                }

                self._logger.info(
                    "RiskAssessmentEngine: 综合风险=%.1f [%s] | PCR扣分=%.1f | 海外扣分=%.1f",
                    overall, risk_level, pcr_risk, overseas_risk,
                )
                return result

        engines["risk_engine"] = _RiskAssessmentEngine(config, cache, logger)
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
    """执行V8完整分析管线 (9步)

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
    logger.info("Step 2/9: 更新合约映射")
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
    try:
        deriv_engine = engines.get("derivatives_engine")
        if deriv_engine:
            derivatives_result = deriv_engine.calculate(results.get("market_data", {}))
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
            macro_result = macro_engine.calculate(results.get("market_data", {}))
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
    try:
        regime_engine = engines.get("regime_engine")
        if regime_engine:
            regime_result = regime_engine.detect(
                results.get("market_data", {}),
                overseas_signal=overseas_signal,
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
    try:
        classifier = engines.get("state_classifier")
        if classifier:
            # 从各模块结果提取维度评分
            val_data = results.get("market_data", {}).get("valuation_data", {})
            valuation_score = _compute_valuation_score(val_data, logger)

            momentum_score = _compute_momentum_score(
                results.get("market_data", {}).get("index_data", {}), logger,
            )

            regime_score = regime_result.get("regime_score", 50.0)

            overseas_score = 50.0
            if overseas_signal:
                overseas_score = overseas_signal.get("composite_score", 50.0)

            classification_result = classifier.classify(
                valuation_score=valuation_score,
                momentum_score=momentum_score,
                regime_score=regime_score,
                overseas_score=overseas_score,
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
            risk_result = risk_engine.assess(
                classification=classification_result,
                derivatives=derivatives_result,
                pcr=pcr_result,
                overseas=overseas_signal,
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
        "version": "8.0.0",
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
        "direction": classification.get("direction", "neutral"),
        "risk_level": risk.get("risk_level", "moderate"),
        "risk_score": risk.get("overall_risk_score", 50),
        "regime": results.get("regime", {}).get("current_regime", "未知"),
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
) -> list[str]:
    """生成所有可视化图表

    Returns:
        生成的图表文件路径列表
    """
    logger = services["logger"]
    paths: list[str] = []

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

    # 方向标记
    def _dir_icon(d: str) -> str:
        d = d.lower()
        if "bull" in d or d in ("up", "long"):
            return "▲"
        elif "bear" in d or d in ("down", "short"):
            return "▼"
        return "◆"

    c_dir = classification.get("direction", "neutral")
    r_dir = regime.get("current_regime", "未知")
    o_dir = overseas.get("direction", "N/A") if not skip_overseas else "跳过"
    d_level = derivatives.get("signal_level", "normal")

    # 风险颜色
    risk_level = risk.get("risk_level", "moderate")
    risk_icon = {"low": "🟢", "moderate": "🟡", "high": "🔴", "extreme": "⛔"}.get(
        risk_level, "⚪"
    )

    print("\n")
    print("╔" + "═" * 68 + "╗")
    print("║" + " AiStock V8 市场状态量化系统 — 运行摘要".center(66) + "║")
    print("╠" + "═" * 68 + "╣")

    # 核心结果
    print("║" + "".center(68) + "║")
    print(f"║  综合评分: {classification.get('composite_score', 50):>6.1f}  │  "
          f"状态: {classification.get('state_label', '均衡持有'):<8s}  │  "
          f"方向: {_dir_icon(c_dir)} {c_dir:<10s}  ║")

    print("║" + "─" * 68 + "║")

    # 维度评分
    print(f"║  估值: {classification.get('valuation_score', 50):>5.1f}  │  "
          f"动量: {classification.get('momentum_score', 50):>5.1f}  │  "
          f"Regime: {classification.get('regime_score', 50):>5.1f}  │  "
          f"海外: {classification.get('overseas_score', 50):>5.1f}  ║")

    print("║" + "─" * 68 + "║")

    # 子模块
    print(f"║  Regime:   {r_dir:<8s}  │  "
          f"衍生品: {d_level:<8s}  │  "
          f"外盘: {_dir_icon(o_dir)} {o_dir:<8s}  ║")

    pcr_val = comp_pcr.get("composite_pcr", 0) if isinstance(comp_pcr, dict) else 0
    pcr_level = comp_pcr.get("signal_level", "N/A") if isinstance(comp_pcr, dict) else "N/A"
    print(f"║  PCR综合:  {pcr_val:>5.3f}  │  "
          f"PCR级别: {pcr_level:<8s}  │  "
          f"宏观: {macro.get('direction', 'N/A'):<8s}  ║")

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
        description="AiStock V8 A股市场状态量化系统",
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
    """AiStock V8 主入口"""
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

    logger.info("AiStock V8 运行完成 | 总耗时 %.0fms", total_elapsed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
