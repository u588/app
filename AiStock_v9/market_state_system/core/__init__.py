"""
AiStock V8 Market State System — Core Module

Core engine components for the market state quantification system.

Engines:
  OptionCodeParser              — 统一期权代码解析器 (3格式: SH/SZ ETF + CFFEX/Commodity)
  OptionPCREngine               — 期权PCR全量计算引擎 (ETF + CFFEX + Commodity + Composite)
  OverseasFuturesSignalEngine   — 外盘期货四维信号引擎 (Price+Position+Macro+Sentiment)
  DerivativesSignalEngine       — 衍生品信号引擎 (国内期货+期权+外盘融合)
  MarketRegimeEngine            — 市场体制检测引擎 (Bull/Bear/Volatile/Recovery + 海外调整)
  MarketStateClassifier         — 市场状态分类器 (V8四维模型: 估值+动量+体制+海外)
  RiskAssessmentEngine          — 风险评估引擎 (7维度含海外传导+期权情绪)
  MacroSignalEngine             — 宏观信号引擎 (99指标5分组: 通胀+增长+流动性+外部风险+市场情绪)
"""

from .option_code_parser import OptionCodeParser, OptionContractInfo
from .option_pcr_engine import (
    OptionPCREngine,
    PCRResult,
    CompositePCRResult,
    PCRDivergenceSignal,
)
from .overseas_futures_signal_engine import (
    OverseasFuturesSignalEngine,
    OverseasCompositeSignal,
    PriceSignalResult,
    PositionSignalResult,
    MacroSignalResult as OverseasMacroSignalResult,
    SentimentSignalResult,
    SpreadResult,
    SectorImpact,
)
from .derivatives_signal_engine import DerivativesSignalEngine
from .market_regime_engine import MarketRegimeEngine, RegimeResult
from .market_state_classifier import MarketStateClassifier, ClassificationResult
from .risk_assessment_engine import RiskAssessmentEngine, RiskResult
from .macro_signal_engine import MacroSignalEngine, MacroSignalResult

__all__ = [
    # Option Code Parser
    "OptionCodeParser",
    "OptionContractInfo",
    # Option PCR Engine
    "OptionPCREngine",
    "PCRResult",
    "CompositePCRResult",
    "PCRDivergenceSignal",
    # Overseas Futures Signal Engine
    "OverseasFuturesSignalEngine",
    "OverseasCompositeSignal",
    "PriceSignalResult",
    "PositionSignalResult",
    "OverseasMacroSignalResult",
    "SentimentSignalResult",
    "SpreadResult",
    "SectorImpact",
    # Derivatives Signal Engine
    "DerivativesSignalEngine",
    # Market Regime Engine
    "MarketRegimeEngine",
    "RegimeResult",
    # Market State Classifier
    "MarketStateClassifier",
    "ClassificationResult",
    # Risk Assessment Engine
    "RiskAssessmentEngine",
    "RiskResult",
    # Macro Signal Engine
    "MacroSignalEngine",
    "MacroSignalResult",
]
