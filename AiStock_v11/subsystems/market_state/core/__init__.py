#!/usr/bin/env python3
"""Market State 子系统 — 核心模块 (V11.5 7分量模型)"""
from __future__ import annotations

from subsystems.market_state.core.market_state_engine import MarketStateEngine
from subsystems.market_state.core.contract_manager import (
    ContractManager,
    ContractInfo,
    FuturesContractPair,
    IndexFuturesContract,
    OptionContractGroup,
)
from subsystems.market_state.core.option_code_parser import (
    OptionCodeParser,
    OptionContractInfo,
)
from subsystems.market_state.core.derivatives_signal_engine import (
    DerivativesSignalEngine,
    CommoditySignal,
    TermStructureSignal,
    IndexFuturesBasis,
    IndustrySentiment,
    OverseasDerivativesSignal,
    DerivativesResult,
)
# ─── V11 NEW 引擎导出 ──────────────────────────────────────────────────
from subsystems.market_state.core.fund_flow_engine import (
    FundFlowEngine,
    FundFlowSignal,
)
from subsystems.market_state.core.option_pcr_engine import (
    OptionPCREngine,
    OptionPCRSignal,
)
from subsystems.market_state.core.macro_valuation_engine import (
    MacroValuationEngine,
    MacroValuationSignal,
)
from subsystems.market_state.core.style_rotation_engine import (
    StyleRotationEngine,
    StyleRotationSignal,
)

__all__ = [
    "MarketStateEngine",
    "ContractManager",
    "ContractInfo",
    "FuturesContractPair",
    "IndexFuturesContract",
    "OptionContractGroup",
    "OptionCodeParser",
    "OptionContractInfo",
    "DerivativesSignalEngine",
    "CommoditySignal",
    "TermStructureSignal",
    "IndexFuturesBasis",
    "IndustrySentiment",
    "OverseasDerivativesSignal",
    "DerivativesResult",
    # V11 NEW
    "FundFlowEngine",
    "FundFlowSignal",
    "OptionPCREngine",
    "OptionPCRSignal",
    "MacroValuationEngine",
    "MacroValuationSignal",
    # V11.5 Style Rotation
    "StyleRotationEngine",
    "StyleRotationSignal",
]
