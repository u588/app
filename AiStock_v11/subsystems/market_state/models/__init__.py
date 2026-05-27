#!/usr/bin/env python3
"""
Market State 子系统 — 数据模型

V10: 数据类定义与核心模块重复导出, 方便外部按需导入。

完整数据类定义在 core/ 模块, 此处仅做重导出。
"""
from __future__ import annotations

from subsystems.market_state.core.contract_manager import (
    ContractInfo,
    FuturesContractPair,
    IndexFuturesContract,
    OptionContractGroup,
)
from subsystems.market_state.core.option_code_parser import OptionContractInfo
from subsystems.market_state.core.derivatives_signal_engine import (
    CommoditySignal,
    TermStructureSignal,
    IndexFuturesBasis,
    IndustrySentiment,
    OverseasDerivativesSignal,
    DerivativesResult,
)

__all__ = [
    "ContractInfo",
    "FuturesContractPair",
    "IndexFuturesContract",
    "OptionContractGroup",
    "OptionContractInfo",
    "CommoditySignal",
    "TermStructureSignal",
    "IndexFuturesBasis",
    "IndustrySentiment",
    "OverseasDerivativesSignal",
    "DerivativesResult",
]
