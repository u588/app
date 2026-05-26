# AiStock V10 Architecture Design Document

> **Version**: 10.0  
> **Date**: 2026-03-05  
> **Author**: Architecture Team  
> **Status**: Final Design  

---

## Table of Contents

1. [V9 Problems Summary](#1-v9-problems-summary)
2. [V10 Design Principles](#2-v10-design-principles)
3. [V10 Directory Structure](#3-v10-directory-structure)
4. [YAML Config File Schemas](#4-yaml-config-file-schemas)
5. [ConfigService API Design](#5-configservice-api-design)
6. [EventBus API Design](#6-eventbus-api-design)
7. [Service Injection Pattern](#7-service-injection-pattern)
8. [Main Entry Point Flow](#8-main-entry-point-flow)
9. [Key Class Dependency Diagram](#9-key-class-dependency-diagram)
10. [V9→V10 Migration Mapping](#10-v9v10-migration-mapping)

---

## 1. V9 Problems Summary

After thorough analysis of the V9 codebase, the following concrete problems were identified:

### 1.1 Hardcoded Config Scattered Across 8+ Files

| File | Hardcoded Config | Lines |
|------|-----------------|-------|
| `contract_manager.py` | `COMMODITY_DELIVERY_MONTHS` (80+ varieties), `VARIETY_MARKET_CODE`, `VARIETY_MARKET_TYPE`, `VARIETY_NAMES`, `OPTION_UNDERLYING_CONFIG` (50+ entries), `EXPIRY_WARNING_DAYS`, `ROLLOVER_DAY` | ~250 lines |
| `option_pcr_engine.py` | `SH_ETF_UNDERLYINGS`, `SZ_ETF_UNDERLYINGS`, `CFFEX_UNDERLYINGS`, `DEFAULT_COMMODITY_VARIETIES`, `DEFAULT_COMPOSITE_WEIGHTS`, `DEFAULT_PCR_THRESHOLDS`, `_MARKET_*` constants | ~80 lines |
| `option_code_parser.py` | `CFFEX_VARIETIES`, `COMMODITY_VARIETIES`, `_ETF_STRIKE_DIVISOR`, month maps | ~60 lines |
| `derivatives_signal_engine.py` | `DEFAULT_COMMODITY_VARIETIES`, `DEFAULT_INDEX_FUTURES`, `COMMODITY_SIGNAL_WEIGHTS`, `COMPOSITE_WEIGHTS`, `OVERSEAS_FUSION_WEIGHT` | ~50 lines |
| `data_loader_service.py` | `LoaderConfig` with `future_codes` (IFL8, CUL8...), `index_codes`, `option_underlyings` | ~70 lines |
| `tdx_adapter.py` | `STANDARD_HOST`, `STANDARD_PORT`, `EXTENSION_HOST`, `EXTENSION_PORT`, `MARKET_MAP` | ~30 lines |
| `global_settings.py` | `DATABASE_ENGINES`, `DB_POOL_CONFIG`, `TDX_CODE_TABLE_PATH` | ~50 lines |
| `system_config.yaml` | 1475+ line monolith, everything in one file | 1475 lines |

**Total: ~2065 lines of config that should be in YAML but is in Python code**

### 1.2 Config-Function Coupling Examples

- Changing `IFM0→IFL8`: Must edit `data_loader_service.py` (LoaderConfig), `contract_manager.py`, `derivatives_signal_engine.py` (DEFAULT_INDEX_FUTURES)
- Adding a new commodity variety (e.g., `BR`): Must edit `contract_manager.py` (3 dicts), `option_pcr_engine.py`, `option_code_parser.py`, `derivatives_signal_engine.py`, `data_loader_service.py`
- Changing market_code for CZCE options from 28→4: Must audit `contract_manager.py`, `option_code_parser.py`, `tdx_adapter.py`

### 1.3 No Inter-Subsystem Communication

- No EventBus: Subsystems can only communicate via direct method calls in main.py
- No hot reload: Config changes require full restart
- No shared data store: Results passed via Dict[str, Any] between functions

---

## 2. V10 Design Principles

| Principle | Description |
|-----------|-------------|
| **P1: Config-Function Decoupling** | Zero hardcoded config in Python. All config in YAML. Code reads config, never contains config. |
| **P2: YAML Independence** | Each config domain is an independent YAML file. Change codes.yaml without touching system.yaml. |
| **P3: Subsystem Isolation** | Each subsystem (market_state, price_quant, risk_engine) loads only its own config namespace. |
| **P4: Shared Service Layer** | ConfigService, CacheService, LoggerService, EventBus are shared singletons across ALL subsystems. |
| **P5: Event-Driven Communication** | Subsystems communicate via EventBus, never direct imports of each other's internals. |
| **P6: Hot Reload** | File watcher detects YAML changes → ConfigService reloads → EventBus notifies subscribers. |
| **P7: Validation First** | Every YAML is validated on load. Schema errors fail fast, not at runtime. |
| **P8: Single Source of Truth** | codes.yaml is the ONLY place for variety/market/contract definitions. No duplicates. |

---

## 3. V10 Directory Structure

```
AiStock_v10/
├── main.py                              # Single entry point
├── pyproject.toml                       # Project metadata & dependencies
├── README.md
│
├── config/                              # ★ ALL configuration lives here
│   ├── system.yaml                      # System-level: version, mode, paths, workers
│   ├── codes.yaml                       # ★ Single source of truth: varieties, markets, contracts
│   ├── market_state.yaml               # Market state subsystem config (overlays)
│   ├── logging.yaml                     # Logging levels, formats, rotation
│   ├── database.yaml                    # DB connection strings, pool config
│   ├── tdx.yaml                         # TDX server addresses, port routing, pool sizes
│   ├── cache.yaml                       # Cache sizes, TTLs per data type
│   ├── overseas.yaml                    # Overseas futures 29 symbols, tiers, weights
│   ├── thresholds.yaml                  # Signal thresholds, PCR limits, risk parameters
│   ├── macro.yaml                       # Macro indicators config (5 dimensions, 99 indicators)
│   ├── schemas/                         # JSON Schema files for validation
│   │   ├── system.schema.json
│   │   ├── codes.schema.json
│   │   ├── market_state.schema.json
│   │   ├── logging.schema.json
│   │   ├── database.schema.json
│   │   ├── tdx.schema.json
│   │   ├── cache.schema.json
│   │   ├── overseas.schema.json
│   │   ├── thresholds.schema.json
│   │   └── macro.schema.json
│   └── .env                             # Environment overrides (gitignored)
│
├── core/                                # ★ Shared infrastructure (NO business logic)
│   ├── __init__.py
│   ├── config_service.py                # Unified ConfigService (multi-file, hot-reload, validation)
│   ├── event_bus.py                     # Async EventBus (pub/sub, topic filtering)
│   ├── logger_service.py                # LoggerService (migrated from V9)
│   ├── cache_service.py                 # CacheService (migrated from V9)
│   ├── service_container.py             # DI container (ServiceContainer)
│   └── validator.py                     # YAML schema validation utility
│
├── data_service/                        # Data access layer (unchanged API, config-driven)
│   ├── __init__.py
│   ├── tdx_adapter.py                   # TDXAdapter (config from tdx.yaml + codes.yaml)
│   ├── ak_adapter.py                    # AKAdapter (config from overseas.yaml)
│   ├── database_reader.py              # DatabaseReader (config from database.yaml)
│   └── data_loader_service.py          # DataLoaderService (config from codes.yaml)
│
├── subsystems/                          # ★ Independent subsystems
│   ├── __init__.py
│   ├── market_state/                    # Market State Quantification Subsystem
│   │   ├── __init__.py
│   │   ├── subsystem.py                 # MarketStateSubsystem (entry, lifecycle)
│   │   ├── contract_manager.py          # ContractManager (reads codes.yaml)
│   │   ├── option_code_parser.py        # OptionCodeParser (reads codes.yaml)
│   │   ├── option_pcr_engine.py         # OptionPCREngine (reads market_state.yaml + codes.yaml)
│   │   ├── derivatives_signal_engine.py # DerivativesSignalEngine
│   │   ├── overseas_futures_engine.py   # OverseasFuturesSignalEngine
│   │   ├── macro_signal_engine.py       # MacroSignalEngine
│   │   ├── market_regime_engine.py      # MarketRegimeEngine
│   │   ├── market_state_classifier.py   # MarketStateClassifier
│   │   ├── risk_assessment_engine.py    # RiskAssessmentEngine
│   │   ├── visualization/              # Visualization module
│   │   │   ├── __init__.py
│   │   │   ├── state_visualizer.py
│   │   │   └── plotly_visualizer.py
│   │   └── utils/
│   │       ├── __init__.py
│   │       └── date_utils.py
│   │
│   ├── price_quant/                     # Future: Price Quantization Subsystem
│   │   ├── __init__.py
│   │   ├── subsystem.py
│   │   └── ... (future implementation)
│   │
│   └── risk_engine/                     # Future: Risk Engine Subsystem
│       ├── __init__.py
│       ├── subsystem.py
│       └── ... (future implementation)
│
├── notebooks/                           # Jupyter notebooks
│   └── tdxAPICode180.xlsx              # Code table (data file, NOT config)
│
├── data/                                # Runtime data directory
│   └── tdxAPICode180.xlsx              # Symlink or copy of code table
│
├── output/                              # Generated reports & visualizations
│   ├── reports/
│   └── visualizations/
│
└── logs/                                # Log files
    ├── aistock.log
    └── aistock_error.log
```

### Key Structural Changes from V9

| V9 | V10 | Rationale |
|----|-----|-----------|
| `base_services/` | `core/` | Clearer naming; "core" = shared infrastructure |
| `market_state_system/` | `subsystems/market_state/` | Namespace isolation; enables multi-subsystem |
| `config/system_config.yaml` (1475 lines) | 10 independent YAML files | Single responsibility; independent editing |
| `config/global_settings.py` | DELETED → `config/database.yaml` + `config/system.yaml` | No Python config files |
| Hardcoded `COMMODITY_DELIVERY_MONTHS` etc. | `config/codes.yaml` | Zero hardcoded config in Python |
| Direct dict passing in `main.py` | `ServiceContainer` + `EventBus` | DI + event-driven |
| No validation | `config/schemas/*.schema.json` | Fail-fast on misconfiguration |

---

## 4. YAML Config File Schemas

### 4.1 system.yaml — System-Level Configuration

```yaml
# system.yaml — System-level configuration
# Replaces: global_settings.py SYSTEM_VERSION, SYSTEM_NAME, etc.

system:
  version: "10.0.0"
  name: "AiStock V10 量化系统"
  mode: "production"           # production | development | backtest
  base_date: null              # Override reference date (null = today)
  max_workers: 8
  data_min_days: 500
  degradation_mode: "auto"     # auto | strict | lenient

paths:
  project_root: "."            # Relative to this file's parent
  data_dir: "./data"
  output_dir: "./output"
  log_dir: "./logs"
  code_table: "./data/tdxAPICode180.xlsx"

subsystems:
  active:
    - market_state
    # - price_quant            # Future
    # - risk_engine            # Future
  market_state:
    enabled: true
    config_file: "market_state.yaml"
  price_quant:
    enabled: false
    config_file: "price_quant.yaml"
  risk_engine:
    enabled: false
    config_file: "risk_engine.yaml"
```

### 4.2 codes.yaml — Single Source of Truth for All Codes

```yaml
# codes.yaml — Single source of truth for variety/market/contract definitions
# Replaces: COMMODITY_DELIVERY_MONTHS, VARIETY_MARKET_CODE, VARIETY_MARKET_TYPE,
#           VARIETY_NAMES, OPTION_UNDERLYING_CONFIG, SH_ETF_UNDERLYINGS,
#           SZ_ETF_UNDERLYINGS, CFFEX_UNDERLYINGS, DEFAULT_COMMODITY_VARIETIES,
#           LoaderConfig.future_codes, DEFAULT_INDEX_FUTURES, etc.
# ★ CHANGE A CODE HERE → IT PROPAGATES EVERYWHERE ★

# ─── TDX Market Codes (from tdxAPICode180.xlsx) ───────────────────
markets:
  futures:
    SHFE: { code: 30, name: "上海期货", market_type: "future_sh" }
    DCE:  { code: 29, name: "大连商品", market_type: "future_dl" }
    CZCE: { code: 28, name: "郑州商品", market_type: "future_zj" }  # Note: futures=28, options=4
    CFFEX:{ code: 47, name: "中金所",   market_type: "future_zj" }
    GFEX: { code: 66, name: "广州期货", market_type: "future_gz" }
  options:
    CZCE_OPT:  { code: 4,  name: "郑商所期权", market_type: "option_czce" }
    DCE_OPT:   { code: 5,  name: "大商所期权", market_type: "option_dce" }
    SHFE_OPT:  { code: 6,  name: "上期所期权", market_type: "option_shfe" }
    CFFEX_OPT: { code: 7,  name: "中金所期权", market_type: "option_zj" }
    SSE_ETF:   { code: 8,  name: "上交所ETF期权", market_type: "option_sh" }
    SZSE_ETF:  { code: 9,  name: "深交所ETF期权", market_type: "option_sz" }
    GFEX_OPT:  { code: 67, name: "广期所期权", market_type: "option_gz" }
  stocks:
    SSE: { code: 1, name: "上海证券交易所" }
    SZSE:{ code: 0, name: "深圳证券交易所" }
  special:
    MACRO:      { code: 50, name: "宏观指标" }
    GOLD_SH:    { code: 46, name: "上海黄金" }
    INDEX_CSI:  { code: 62, name: "中证指数" }
    INDEX_CNI:  { code: 102,name: "国证指数" }
    INDEX_INTL: { code: 12, name: "国际指数" }

# ─── Continuous Contract Suffixes (tdxAPICode180 standard) ─────────
continuous_contracts:
  L0: { name: "当月连续", description: "Current month continuous" }
  L1: { name: "下月连续", description: "Next month continuous" }
  L2: { name: "下季连续", description: "Next quarter continuous" }
  L3: { name: "隔季连续", description: "Following quarter continuous" }
  L8: { name: "主连",     description: "Main continuous contract" }
  L9: { name: "加权",     description: "Weighted continuous" }
  # Note: M0/M1 do NOT exist in tdxAPICode180 — legacy mistake

# ─── Commodity Futures Varieties ──────────────────────────────────
# Each variety: delivery months, market, display name
commodities:
  # ── SHFE (market_code=30) ────────────────
  CU:
    name: "沪铜"
    market: SHFE
    market_code: 30
    market_type: "future_sh"
    delivery_months: [1,2,3,4,5,6,7,8,9,10,11,12]
    industry: "有色金属"
    continuous: "CUL8"
    option:
      enabled: true
      market_code: 6
      market_type: "option_shfe"
      strike_divisor: 1
  AL:
    name: "沪铝"
    market: SHFE
    market_code: 30
    market_type: "future_sh"
    delivery_months: [1,2,3,4,5,6,7,8,9,10,11,12]
    industry: "有色金属"
    continuous: "ALL8"
    option:
      enabled: true
      market_code: 6
      market_type: "option_shfe"
      strike_divisor: 1
  # ... (all 80+ varieties follow same pattern)
  AU:
    name: "黄金"
    market: SHFE
    market_code: 30
    market_type: "future_sh"
    delivery_months: [2,4,6,8,10,12]
    industry: "贵金属"
    continuous: "AUL8"
    option:
      enabled: true
      market_code: 6
      market_type: "option_shfe"
      strike_divisor: 1
  AG:
    name: "白银"
    market: SHFE
    market_code: 30
    market_type: "future_sh"
    delivery_months: [1,2,3,4,5,6,7,8,9,10,11,12]
    industry: "贵金属"
    continuous: "AGL8"
    option:
      enabled: true
      market_code: 6
      market_type: "option_shfe"
      strike_divisor: 1
  RB:
    name: "螺纹钢"
    market: SHFE
    market_code: 30
    market_type: "future_sh"
    delivery_months: [1,2,3,4,5,6,7,8,9,10,11,12]
    industry: "钢铁"
    continuous: "RBL8"
    option:
      enabled: true
      market_code: 6
      market_type: "option_shfe"
      strike_divisor: 1
  SC:
    name: "原油"
    market: SHFE
    market_code: 30
    market_type: "future_sh"
    delivery_months: [1,2,3,4,5,6,7,8,9,10,11,12]
    industry: "能源"
    continuous: "SCL8"
    overseas_aligned: "CL"

  # ── DCE (market_code=29) ────────────────
  I:
    name: "铁矿石"
    market: DCE
    market_code: 29
    market_type: "future_dl"
    delivery_months: [1,2,3,4,5,6,7,8,9,10,11,12]
    industry: "钢铁"
    continuous: "IL8"
    overseas_aligned: "FEF"
    option:
      enabled: true
      market_code: 5
      market_type: "option_dce"
      strike_divisor: 1
  M:
    name: "豆粕"
    market: DCE
    market_code: 29
    market_type: "future_dl"
    delivery_months: [1,3,5,7,8,9,11,12]
    industry: "农业"
    continuous: "ML8"
    overseas_aligned: "SM"
    option:
      enabled: true
      market_code: 5
      market_type: "option_dce"
      strike_divisor: 1

  # ── CZCE (market_code=28) ──────────────
  CF:
    name: "棉花"
    market: CZCE
    market_code: 28
    market_type: "future_zj"
    delivery_months: [1,3,5,7,9,11]
    industry: "纺织"
    continuous: "CFL8"
    option:
      enabled: true
      market_code: 4
      market_type: "option_czce"
      strike_divisor: 1

  # ── GFEX (market_code=66) ──────────────
  LC:
    name: "碳酸锂"
    market: GFEX
    market_code: 66
    market_type: "future_gz"
    delivery_months: [1,2,3,4,5,6,7,8,9,10,11,12]
    industry: "新能源"
    continuous: "LCL8"
    option:
      enabled: true
      market_code: 67
      market_type: "option_gz"
      strike_divisor: 1
  SI:
    name: "工业硅"
    market: GFEX
    market_code: 66
    market_type: "future_gz"
    delivery_months: [1,2,3,4,5,6,7,8,9,10,11,12]
    industry: "新能源"
    continuous: "SIL8"
    option:
      enabled: true
      market_code: 67
      market_type: "option_gz"
      strike_divisor: 1

# ─── Index Futures (CFFEX) ────────────────────────────────────────
index_futures:
  IF:
    name: "沪深300"
    variety: "IF"
    spot_code: "000300"
    continuous: "IFL8"
    market_code: 47
    market_type: "future_zj"
    quarter_months: [3, 6, 9, 12]
  IH:
    name: "上证50"
    variety: "IH"
    spot_code: "000016"
    continuous: "IHL8"
    market_code: 47
    market_type: "future_zj"
    quarter_months: [3, 6, 9, 12]
  IC:
    name: "中证500"
    variety: "IC"
    spot_code: "000905"
    continuous: "ICL8"
    market_code: 47
    market_type: "future_zj"
    quarter_months: [3, 6, 9, 12]
  IM:
    name: "中证1000"
    variety: "IM"
    spot_code: "000852"
    continuous: "IML8"
    market_code: 47
    market_type: "future_zj"
    quarter_months: [3, 6, 9, 12]

# ─── ETF Option Underlyings ───────────────────────────────────────
etf_options:
  sh_etf:  # Market=8
    "510050":
      name: "上证50ETF"
      market_code: 8
      market_type: "option_sh"
      weight: 0.20
      default_price: 2.8
      strike_divisor: 1000
    "510300":
      name: "沪深300ETF"
      market_code: 8
      market_type: "option_sh"
      weight: 0.18
      default_price: 4.7
      strike_divisor: 1000
    "510500":
      name: "中证500ETF"
      market_code: 8
      market_type: "option_sh"
      weight: 0.07
      default_price: 8.1
      strike_divisor: 1000
    "588000":
      name: "科创50ETF"
      market_code: 8
      market_type: "option_sh"
      weight: 0.10
      default_price: 1.5
      strike_divisor: 1000
    "588080":
      name: "科创板50ETF"
      market_code: 8
      market_type: "option_sh"
      weight: 0.05
      default_price: 1.2
      strike_divisor: 1000
  sz_etf:  # Market=9
    "159915":
      name: "创业板ETF"
      market_code: 9
      market_type: "option_sz"
      weight: 0.15
      default_price: 3.3
      strike_divisor: 1000
    "159901":
      name: "深证100ETF"
      market_code: 9
      market_type: "option_sz"
      weight: 0.05
      default_price: 5.5
      strike_divisor: 1000
    "159919":
      name: "沪深300ETF(嘉实)"
      market_code: 9
      market_type: "option_sz"
      weight: 0.12
      default_price: 4.6
      strike_divisor: 1000
    "159922":
      name: "中证500ETF(嘉实)"
      market_code: 9
      market_type: "option_sz"
      weight: 0.08
      default_price: 8.0
      strike_divisor: 1000

# ─── CFFEX Index Options ──────────────────────────────────────────
cffex_options:
  IO:
    name: "沪深300股指期权"
    spot_code: "000300"
    market_code: 7
    market_type: "option_zj"
    weight: 0.55
    default_price: 4000.0
  HO:
    name: "上证50股指期权"
    spot_code: "000016"
    market_code: 7
    market_type: "option_zj"
    weight: 0.15
    default_price: 2800.0
  MO:
    name: "中证1000股指期权"
    spot_code: "000852"
    market_code: 7
    market_type: "option_zj"
    weight: 0.30
    default_price: 7000.0

# ─── Commodity Options ────────────────────────────────────────────
commodity_options:
  default_top_n: 20
  monitored: ["CU", "AG", "I", "AU", "AL", "ZN", "RB", "NI", "RU", "SN",
              "M", "Y", "P", "C", "CF", "SR", "TA", "MA", "AP", "PB",
              "LC", "SI"]

# ─── Index Codes for Data Loading ────────────────────────────────
index_codes:
  "000001": { name: "上证指数", market_type: "index_sh" }
  "399001": { name: "深证成指", market_type: "index_sz" }
  "399006": { name: "创业板指", market_type: "index_sz" }
  "000300": { name: "沪深300",  market_type: "index_sh" }
  "000905": { name: "中证500",  market_type: "index_sh" }
  "000852": { name: "中证1000", market_type: "index_sh" }

# ─── Strategic Directions ─────────────────────────────────────────
strategic_directions:
  高端制造:
    indices: ["932042", "931865", "930850", "931866", "930599"]
    base_weight: 0.28
    risk_level: "medium_high"
    risk_score: 58
    overseas_linkage: ["HG", "PA", "PL"]
  信息技术:
    indices: ["931087", "930851", "930902", "931495", "931585"]
    base_weight: 0.25
    risk_level: "medium_high"
    risk_score: 55
    overseas_linkage: ["NQ", "SI"]
  新能源:
    indices: ["931798", "931772", "931897", "931687", "931746"]
    base_weight: 0.15
    risk_level: "medium"
    risk_score: 45
    overseas_linkage: ["SI", "HG", "LME_CU"]
  生物健康:
    indices: ["931140", "931152", "931992", "931166", "399812"]
    base_weight: 0.10
    risk_level: "low"
    risk_score: 35
    overseas_linkage: []
  供应链:
    indices: ["931465", "931235", "930716", "930725"]
    base_weight: 0.06
    risk_level: "low"
    risk_score: 30
    overseas_linkage: ["FEF", "CL", "S"]
  现代农业:
    indices: ["930910", "930707", "930662", "000949"]
    base_weight: 0.01
    risk_level: "medium"
    risk_score: 48
    overseas_linkage: ["S", "C", "CT", "SM"]
  公用事业:
    indices: ["000917", "000937", "930955", "932047"]
    base_weight: 0.08
    risk_level: "low"
    risk_score: 25
    overseas_linkage: ["GC", "TN", "ZB"]
  传统升级:
    indices: ["932039", "931231", "930838", "931463"]
    base_weight: 0.04
    risk_level: "low"
    risk_score: 30
    overseas_linkage: ["FEF", "CL", "LBS"]
  文化消费:
    indices: ["931066", "931480", "930901", "930781", "931588"]
    base_weight: 0.03
    risk_level: "high"
    risk_score: 75
    overseas_linkage: ["KC", "CC", "SB"]

# ─── Market Benchmarks ────────────────────────────────────────────
benchmarks:
  大盘: { code: "000300", weight: 0.40, volatility_target: 20.0 }
  中盘: { code: "000905", weight: 0.30, volatility_target: 25.0 }
  小盘: { code: "000852", weight: 0.20, volatility_target: 30.0 }
  微盘: { code: "932000", weight: 0.10, volatility_target: 35.0 }

# ─── Contract Rollover Rules ──────────────────────────────────────
rollover:
  expiry_warning_days: 5
  rollover_day: 15
  index_futures_quarter_months: [3, 6, 9, 12]
  near_month_strategy: "auto"
  far_month_offset: 1
```

### 4.3 market_state.yaml — Market State Subsystem Overlay

```yaml
# market_state.yaml — Market state subsystem configuration overlay

market_state_classifier:
  dimensions: [valuation, momentum, regime, overseas]
  grid:
    strategic_offense: 80
    active_allocation: 65
    balanced_hold: 50
    defensive_watch: 35
    strategic_defense: 20
  weights:
    valuation: 0.30
    momentum: 0.25
    regime: 0.25
    overseas: 0.20
  valuation_sub_weights:
    pe_percentile: 0.40
    pb_percentile: 0.25
    equity_risk_premium: 0.20
    equity_bond_ratio: 0.15
  momentum_sub_weights:
    trend_strength: 0.35
    breadth_ratio: 0.30
    volume_price_divergence: 0.20
    sector_rotation: 0.15
  state_labels:
    90: "强进攻"
    80: "进攻"
    65: "积极配置"
    50: "均衡持有"
    35: "防御观望"
    20: "战略防御"
    10: "强防御"

market_regime:
  confirmation_days: 3
  volatility_window: 60
  momentum_window: 20
  volume_window: 20
  regimes:
    bull:
      volatility_threshold: 0.15
      momentum_threshold: 0.05
      volume_trend: "increasing"
    bear:
      volatility_threshold: 0.30
      momentum_threshold: -0.05
      volume_trend: "decreasing"
    volatile:
      volatility_threshold: 0.25
      momentum_range: [-0.02, 0.02]
      volume_trend: "neutral"
    recovery:
      volatility_decreasing: true
      momentum_positive: true
      volume_trend: "increasing"
  overseas_adjustment:
    enabled: true
    weight: 0.20
    bear_amplification: 1.3
    bull_suppression: 0.9

option_pcr:
  weights:
    etf: 0.45
    cffex: 0.30
    commodity: 0.25
  etf_top_n: 9
  commodity_top_n: 20

derivatives:
  signal_weights:
    momentum: 0.35
    basis: 0.25
    oi_change: 0.20
    volatility: 0.20
  composite_weights:
    commodity: 0.30
    term_structure: 0.15
    index_basis: 0.25
    industry: 0.15
    overseas: 0.15
  overseas_fusion_weight: 0.30
  term_structure_varieties: ["CU", "AL", "ZN", "AU", "AG", "RB", "I", "SC"]

data_loading:
  index_bars_count: 800
  future_bars_count: 800
  option_bars_count: 100
  valuation_codes: ["000300", "000905", "000852"]
  valuation_days: 100
  macro_codes:
    - { code: "CPI", market: 50, name: "CPI" }
    - { code: "PPI", market: 50, name: "PPI" }
    - { code: "PMI", market: 50, name: "PMI" }
  macro_count: 200
```

### 4.4 logging.yaml

```yaml
# logging.yaml
version: 1
console:
  level: "INFO"
  colored: true
  format: "%(asctime)s.%(msecs)03d | %(levelname)-8s | %(name)s | %(message)s"
  date_format: "%Y-%m-%d %H:%M:%S"
file:
  level: "DEBUG"
  format: "%(asctime)s.%(msecs)03d | %(levelname)-8s | %(name)s | %(message)s"
  main_log: "aistock.log"
  error_log: "aistock_error.log"
  max_bytes: 52428800         # 50MB
  backup_count: 10
```

### 4.5 database.yaml

```yaml
# database.yaml — Replaces global_settings.py DATABASE_ENGINES
engines:
  index_db:
    url: "postgresql://user:pass@10.3.18.56:5432/tdxIndex"
    env_key: "DB_INDEX"
  stock_db:
    url: "postgresql://user:pass@10.3.18.56:5432/stock"
    env_key: "DB_STOCK"
  stock_base_db:
    url: "postgresql://user:pass@10.3.18.56:5432/stock_base"
    env_key: "DB_STOCK_BASE"
  stock_fs_db:
    url: "postgresql://user:pass@10.3.18.56:5432/stock_fs"
    env_key: "DB_STOCK_FS"
  index_pe_db:
    url: "postgresql://user:pass@10.3.18.56:5432/csiIndexPE"
    env_key: "DB_INDEX_PE"
pool:
  pool_size: 10
  max_overflow: 20
  pool_pre_ping: true
  pool_recycle: 3600
  pool_timeout: 30
```

### 4.6 tdx.yaml

```yaml
# tdx.yaml — TDX server configuration
standard:
  host: "180.153.18.170"
  port: 7709
  description: "TDX标准行情端口"
  usage: "A股/指数/基础期货/基础期权"
  use_for: [index_daily, stock_daily, index_futures, etf_options, cffex_options]
extension:
  host: "180.153.18.176"
  port: 7721
  description: "TDX扩展行情端口"
  usage: "期货/期权全合约/外盘/宏观指标"
  use_for: [commodity_futures, commodity_options, overseas_futures, macro_indicators, full_option_chain]
connection:
  pool_size: 3
  connect_timeout: 10.0
  max_conn_age: 3600.0
  heartbeat_interval: 30.0
  retry_count: 3
  retry_delay: 1.0
  auto_fallback: true
  fallback_priority: [standard, extension, database]
routing:
  standard_port: [stock_sh, stock_sz, stock_xg, index_sh, index_sz, index_zz]
  extension_port: [future_zz, future_dl, future_sh, future_gz, future_zj,
                   option_zj, option_sh, option_sz, option_czce, option_dce,
                   option_shfe, option_gz, index_intl, gold_sh, index_csi, index_cni, macro]
```

### 4.7 cache.yaml

```yaml
# cache.yaml
max_size: 2000
default_ttl: 3600
cleanup_interval: 60
key_format: "{data_type}_{code}_{date}"
enable_compression: true
ttl:
  stock_daily: 7200
  index_daily: 7200
  index_futures: 1800
  commodity_futures: 900
  etf_options: 1800
  cffex_options: 1800
  commodity_options: 1800
  overseas_futures: 3600
  macro_indicators: 14400
  pe_data: 86400
  cftc_position: 86400
  lme_inventory: 86400
  bond_yield: 7200
  qvix: 1800
  pcr_full: 1800
  option_chain: 900
```

### 4.8 overseas.yaml, 4.9 thresholds.yaml, 4.10 macro.yaml
(See full content in sections above — same structure as V9 but extracted from the monolith)

---

## 5. ConfigService API Design

```python
"""
core/config_service.py — V10 Unified ConfigService

Key improvements over V9:
  - Multi-file loading (10 independent YAML files)
  - Subsystem namespace isolation
  - Hot reload with file watcher
  - Schema validation on load
  - Change notification via callbacks
"""

class ConfigService:
    """
    V10 Unified ConfigService
    
    Usage:
        >>> svc = ConfigService(config_dir="./config")
        >>> svc.load_all()
        >>> host = svc.get("tdx.standard.host")
        >>> cu_delivery = svc.get("codes.commodities.CU.delivery_months")
        >>> market_cfg = svc.get_subsystem_config("market_state")
    """
    
    # ─── File Registry ────────────────────────────────────────────
    FILE_REGISTRY = {
        "system":       ("system.yaml",       True),
        "codes":        ("codes.yaml",        True),
        "market_state": ("market_state.yaml",  False),
        "logging":      ("logging.yaml",      True),
        "database":     ("database.yaml",      True),
        "tdx":          ("tdx.yaml",           True),
        "cache":        ("cache.yaml",         True),
        "overseas":     ("overseas.yaml",      False),
        "thresholds":   ("thresholds.yaml",    True),
        "macro":        ("macro.yaml",         False),
    }
    
    def __init__(self, config_dir, auto_load=True, enable_hot_reload=True, enable_validation=True): ...
    
    # ─── Loading ─────────────────────────────────────────────────
    def load_all(self) -> None:
        """Load all registered YAML config files."""
    
    def load_file(self, name: str) -> None:
        """Reload a single config file by name (e.g., 'codes')."""
    
    # ─── Reading ─────────────────────────────────────────────────
    def get(self, key: str, default=None, value_type=None) -> Any:
        """Get config value by dot-path.
        Examples:
            svc.get("tdx.standard.host", "180.153.18.170")
            svc.get("codes.commodities.CU.delivery_months")
            svc.get("cache.max_size", 2000, value_type=int)
        """
    
    def get_section(self, section: str) -> Dict[str, Any]:
        """Get entire config section as deep copy.
        Example: svc.get_section("codes.commodities.CU")
        """
    
    def require(self, key: str) -> Any:
        """Get required config value. Raises KeyError if missing."""
    
    def get_subsystem_config(self, subsystem: str) -> Dict[str, Any]:
        """Get merged config for a subsystem (base + overlay).
        Merge order:
          1. system.yaml (base)
          2. tdx.yaml, database.yaml, cache.yaml (shared services)
          3. codes.yaml, thresholds.yaml, overseas.yaml, macro.yaml (ref data)
          4. <subsystem>.yaml (overlay)
        """
    
    def get_loaded_files(self) -> Dict[str, Dict]:
        """Get metadata about loaded config files (path, hash, keys)."""
    
    # ─── Change Notification ─────────────────────────────────────
    def on_change(self, key_prefix: str, callback: Callable) -> None:
        """Register callback for config changes matching key_prefix.
        Example: svc.on_change("codes.commodities.CU", on_cu_config_changed)
        """
    
    def off_change(self, key_prefix: str, callback: Callable) -> None:
        """Unregister a change callback."""
    
    # ─── Hot Reload ─────────────────────────────────────────────
    def _start_watcher(self) -> None:
        """Start filesystem watcher for config directory (watchdog)."""
    
    def stop_watcher(self) -> None:
        """Stop the file watcher."""
    
    # ─── Validation ─────────────────────────────────────────────
    def _validate(self, config_file) -> None:
        """Validate config file against JSON Schema in config/schemas/."""
```

---

## 6. EventBus API Design

```python
"""
core/event_bus.py — V10 Event Bus for inter-subsystem communication
"""

@dataclass
class Event:
    """Base event data class."""
    topic: str           # e.g., "config.changed", "market_state.updated"
    data: Any = None     # Event payload
    source: str = ""     # Publisher subsystem name
    timestamp: float = 0.0
    event_id: str = ""

class Topics:
    """Standard event topics."""
    CONFIG_CHANGED = "config.changed"
    CONFIG_RELOADED = "config.reloaded"
    DATA_LOADED = "data.loaded"
    DATA_REFRESHED = "data.refreshed"
    DATA_ERROR = "data.error"
    MARKET_STATE_UPDATED = "market_state.updated"
    REGIME_CHANGED = "market_state.regime_changed"
    PCR_SIGNAL = "market_state.pcr_signal"
    RISK_ALERT = "market_state.risk_alert"
    CONTRACT_ROLLOVER = "contract.rollover"
    CONTRACT_EXPIRY_WARNING = "contract.expiry_warning"
    SUBSYSTEM_STARTED = "subsystem.started"
    SUBSYSTEM_STOPPED = "subsystem.stopped"
    SUBSYSTEM_ERROR = "subsystem.error"

class EventBus:
    """
    V10 Event Bus for inter-subsystem communication.
    
    Features:
      - Topic-based pub/sub with wildcard support
      - Priority-based handler ordering
      - Event history replay for late subscribers
      - Thread-safe
    
    Usage:
        >>> bus = EventBus()
        >>> bus.subscribe("config.changed", on_config_changed)
        >>> bus.subscribe("market_state.*", on_any_market_state_event)
        >>> bus.publish(Event(topic="config.changed", data={"file": "codes"}, source="config_service"))
    """
    
    def __init__(self, history_size=100, replay_on_subscribe=False): ...
    
    def subscribe(self, topic: str, handler: Callable[[Event], None], priority: int = 20) -> None:
        """Subscribe to a topic. Supports wildcard suffix '*'.
        priority: lower = called first (EventPriority.CRITICAL=0, HIGH=10, NORMAL=20, LOW=30)
        """
    
    def unsubscribe(self, topic: str, handler: Callable) -> None:
        """Unsubscribe a handler from a topic."""
    
    def publish(self, event: Event) -> int:
        """Publish an event. Returns number of handlers invoked."""
    
    def publish_data(self, topic: str, data: Any, source: str = "") -> int:
        """Convenience: publish with just topic and data."""
    
    def get_history(self, topic_prefix=None, limit=20) -> List[Event]:
        """Get recent events, optionally filtered by topic prefix."""
    
    # Wildcard matching:
    #   "config.changed" == "config.changed"       (exact)
    #   "config.*"       matches "config.changed"   (one level)
    #   "market_state.**" matches any depth          (multi-level)
```

---

## 7. Service Injection Pattern

```python
"""
core/service_container.py — V10 Dependency Injection Container
"""

class ServiceContainer:
    """
    Lightweight DI container that manages shared service singletons.
    
    Usage:
        >>> container = ServiceContainer()
        >>> container.register_singleton(ConfigService, lambda: ConfigService(config_dir="./config"))
        >>> container.register_singleton(CacheService, lambda: CacheService())
        >>> container.register_singleton(EventBus, lambda: EventBus())
        >>>
        >>> config = container.get(ConfigService)
        >>> cache = container.get(CacheService)
    """
    
    def register_singleton(self, service_type: Type[T], factory: Callable[[], T]) -> None: ...
    def get(self, service_type: Type[T]) -> T: ...
    def has(self, service_type: Type) -> bool: ...
    def list_services(self) -> Dict[str, str]: ...
    def shutdown(self) -> None: ...


class SubsystemBase:
    """
    Base class for all subsystems.
    
    Every subsystem receives the ServiceContainer and gets:
      - Its own merged config (via get_subsystem_config)
      - Access to all shared services (cache, logger, event_bus, data services)
      - Lifecycle management (start/stop)
      - Event subscription capability
    """
    
    def __init__(self, container: ServiceContainer) -> None:
        self._container = container
        self._config = container.get(ConfigService).get_subsystem_config(self.name)
        self._logger = container.get(LoggerService).get_logger(f"subsystem.{self.name}")
        self._event_bus = container.get(EventBus)
        self._cache = container.get(CacheService)
        self._running = False
    
    @property
    def name(self) -> str:
        """Subsystem name (must match config/<name>.yaml)."""
        raise NotImplementedError
    
    @property
    def is_running(self) -> bool: ...
    
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def on_event(self, event: Event) -> None: ...
    def run_pipeline(self, **kwargs) -> Dict[str, Any]: ...
    
    # Convenience
    @property
    def config(self) -> Dict[str, Any]:
        """Get this subsystem's merged config dict."""
    
    def get_config(self, key: str, default=None, value_type=None) -> Any:
        """Get a config value from this subsystem's config namespace."""
```

---

## 8. Main Entry Point Flow

```
Startup Sequence:
  1. parse_args()                    → CLI: --config-dir, --mode, --skip-overseas, etc.
  2. bootstrap_shared_services()     → Create ServiceContainer
     2a. register ConfigService      → Loads all 10 YAML files
     2b. register LoggerService      → Uses logging.yaml
     2c. register CacheService       → Uses cache.yaml
     2d. register EventBus           → Topic pub/sub
  3. bootstrap_data_services()       → Register data layer
     3a. register TDXAdapter         → Uses tdx.yaml
     3b. register AKAdapter          → Uses overseas.yaml
     3c. register DatabaseReader     → Uses database.yaml
     3d. register DataLoaderService  → Uses codes.yaml
  4. bootstrap_subsystems()          → Discover & start active subsystems
     4a. Read system.subsystems.active from ConfigService
     4b. For each active subsystem:
         - Create SubsystemXxx(container)
         - subsystem.start()
         - subscribe to events
  5. Setup signal handlers           → SIGINT/SIGTERM → graceful shutdown
  6. run_pipeline()                  → Execute each subsystem's pipeline
     6a. For each subsystem: subsystem.run_pipeline()
     6b. Publish completion events
  7. Generate outputs                → Reports, visualizations
  8. shutdown()                      → Stop subsystems → stop watcher → close connections
```

```python
# main.py (simplified)
def main():
    args = parse_args()
    
    # Step 2-4: Bootstrap
    container = bootstrap_shared_services(args)
    bootstrap_data_services(container)
    subsystems = bootstrap_subsystems(container)
    
    # Step 5: Signal handlers
    signal.signal(signal.SIGINT, lambda s,f: shutdown(container, subsystems))
    
    # Step 6-7: Pipeline
    try:
        results = run_pipeline(container, subsystems, args)
        generate_outputs(container, subsystems, results, args)
    finally:
        shutdown(container, subsystems)
```

---

## 9. Key Class Dependency Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          main.py                                       │
│  (Entry point: parse args → bootstrap → pipeline → shutdown)           │
└────────────┬─────────────────────────────────────────────┬──────────────┘
             │                                             │
             ▼                                             ▼
┌────────────────────────┐                    ┌──────────────────────────┐
│   ServiceContainer     │◄──── registers ────│   Shared Services       │
│   (DI Container)       │                    │                          │
├────────────────────────┤                    │  ┌──────────────────┐   │
│ get(ConfigService)     │──────────────────► │  │  ConfigService    │   │
│ get(LoggerService)     │──────────────────► │  │  (10 YAML files)  │   │
│ get(CacheService)      │──────────────────► │  │  + hot reload     │   │
│ get(EventBus)          │──────────────────► │  │  + validation     │   │
│ get(TDXAdapter)        │──────────────────► │  └──────────────────┘   │
│ get(AKAdapter)         │──────────────────► │  ┌──────────────────┐   │
│ get(DatabaseReader)    │──────────────────► │  │  LoggerService    │   │
│ get(DataLoaderService) │──────────────────► │  └──────────────────┘   │
└────────────────────────┘                    │  ┌──────────────────┐   │
                                              │  │  CacheService     │   │
                                              │  └──────────────────┘   │
                                              │  ┌──────────────────┐   │
                                              │  │  EventBus         │   │
                                              │  │  (pub/sub/async)  │   │
                                              │  └──────────────────┘   │
                                              └──────────────────────────┘
                                                        ▲
                                                        │ subscribes
                              ┌──────────────────────────┼──────────────────┐
                              │                          │                  │
                    ┌─────────┴─────────┐  ┌────────────┴───────┐  ┌──────┴────────┐
                    │  market_state     │  │  price_quant       │  │  risk_engine   │
                    │  Subsystem        │  │  Subsystem         │  │  Subsystem     │
                    │                   │  │  (future)          │  │  (future)      │
                    ├───────────────────┤  └────────────────────┘  └───────────────┘
                    │ SubsystemBase     │
                    │   ├ config ───────┼──── get_subsystem_config("market_state")
                    │   ├ event_bus     │
                    │   ├ cache         │
                    │   └ logger        │
                    ├───────────────────┤
                    │ ContractManager   │◄──── reads codes.yaml
                    │ OptionCodeParser  │◄──── reads codes.yaml
                    │ OptionPCREngine   │◄──── reads market_state.yaml + codes.yaml
                    │ DerivativesSignal │◄──── reads market_state.yaml + codes.yaml
                    │ OverseasEngine    │◄──── reads overseas.yaml
                    │ MacroSignalEngine │◄──── reads macro.yaml
                    │ MarketRegimeEngine│◄──── reads market_state.yaml
                    │ StateClassifier   │◄──── reads market_state.yaml
                    │ RiskAssessment    │◄──── reads thresholds.yaml
                    └───────────────────┘
                              │
                              │ publishes events via EventBus
                              ▼
                    ┌───────────────────┐
                    │  EventBus Topics   │
                    ├───────────────────┤
                    │ config.changed    │ ← ConfigService hot reload
                    │ data.loaded       │ ← DataLoaderService
                    │ market_state.*    │ ← MarketStateSubsystem
                    │ contract.rollover │ ← ContractManager
                    │ subsystem.*       │ ← Lifecycle events
                    └───────────────────┘
```

### Detailed Class Dependencies (market_state subsystem)

```
MarketStateSubsystem(SubsystemBase)
  │
  ├── config: Dict = ConfigService.get_subsystem_config("market_state")
  │     │
  │     ├── system.*           (from system.yaml)
  │     ├── tdx.*              (from tdx.yaml)
  │     ├── database.*         (from database.yaml)
  │     ├── cache.*            (from cache.yaml)
  │     ├── codes.*            (from codes.yaml)     ← Single source of truth
  │     ├── thresholds.*       (from thresholds.yaml)
  │     ├── overseas.*         (from overseas.yaml)
  │     ├── macro.*            (from macro.yaml)
  │     └── market_state_classifier.*  (overlay from market_state.yaml)
  │
  ├── _container.get(TDXAdapter)          ← Shared data service
  ├── _container.get(AKAdapter)           ← Shared data service
  ├── _container.get(DatabaseReader)      ← Shared data service
  ├── _container.get(DataLoaderService)   ← Shared data service
  ├── _container.get(CacheService)        ← Shared cache
  ├── _container.get(EventBus)            ← Shared event bus
  │
  ├── ContractManager
  │     └── Reads: codes.commodities.*, codes.index_futures.*, codes.rollover.*
  │     └── Event: contract.rollover, contract.expiry_warning
  │
  ├── OptionCodeParser
  │     └── Reads: codes.etf_options.*, codes.cffex_options.*, codes.commodities.*.option
  │
  ├── OptionPCREngine
  │     └── Reads: codes.etf_options.*, codes.cffex_options.*, codes.commodity_options.*
  │     └── Reads: market_state.option_pcr.*
  │     └── Depends: TDXAdapter, ContractManager, OptionCodeParser
  │     └── Event: market_state.pcr_signal
  │
  ├── DerivativesSignalEngine
  │     └── Reads: codes.commodities.*, codes.index_futures.*, codes.continuous_contracts.*
  │     └── Reads: market_state.derivatives.*
  │     └── Depends: TDXAdapter, ContractManager, OverseasFuturesSignalEngine
  │     └── Event: market_state.derivatives_signal
  │
  ├── OverseasFuturesSignalEngine
  │     └── Reads: overseas.core.*, overseas.extended.*, overseas.auxiliary.*
  │     └── Depends: AKAdapter, DataLoaderService
  │
  ├── MacroSignalEngine
  │     └── Reads: macro.dimensions.*
  │     └── Depends: TDXAdapter, AKAdapter
  │
  ├── MarketRegimeEngine
  │     └── Reads: market_state.market_regime.*
  │     └── Depends: TDXAdapter
  │
  ├── MarketStateClassifier
  │     └── Reads: market_state.market_state_classifier.*
  │     └── Depends: TDXAdapter, DatabaseReader
  │
  └── RiskAssessmentEngine
        └── Reads: thresholds.pcr.*, thresholds.basis.*, thresholds.volatility.*
        └── Depends: TDXAdapter, DatabaseReader
```

---

## 10. V9→V10 Migration Mapping

| V9 Artifact | V10 Location | What Changes |
|-------------|-------------|-------------|
| `config/system_config.yaml` (1475 lines) | `config/` (10 YAML files) | Split into domain-specific files |
| `config/global_settings.py` | DELETED | → `config/database.yaml` + `config/system.yaml` |
| `base_services/` | `core/` | Rename; add `event_bus.py`, `service_container.py`, `validator.py` |
| `market_state_system/` | `subsystems/market_state/` | Wrap in SubsystemBase; add `subsystem.py` |
| `contract_manager.py` COMMODITY_DELIVERY_MONTHS | `config/codes.yaml` → `codes.commodities.*.delivery_months` | Code reads config |
| `contract_manager.py` VARIETY_MARKET_CODE | `config/codes.yaml` → `codes.commodities.*.market_code` | Single source |
| `contract_manager.py` VARIETY_MARKET_TYPE | `config/codes.yaml` → `codes.commodities.*.market_type` | Single source |
| `contract_manager.py` VARIETY_NAMES | `config/codes.yaml` → `codes.commodities.*.name` | Single source |
| `contract_manager.py` OPTION_UNDERLYING_CONFIG | `config/codes.yaml` → `codes.etf_options.*`, `codes.cffex_options.*`, `codes.commodities.*.option` | Unified |
| `option_pcr_engine.py` SH_ETF_UNDERLYINGS | `config/codes.yaml` → `codes.etf_options.sh_etf` | Single source |
| `option_pcr_engine.py` SZ_ETF_UNDERLYINGS | `config/codes.yaml` → `codes.etf_options.sz_etf` | Single source |
| `option_pcr_engine.py` CFFEX_UNDERLYINGS | `config/codes.yaml` → `codes.cffex_options` | Single source |
| `option_pcr_engine.py` DEFAULT_COMMODITY_VARIETIES | `config/codes.yaml` → `codes.commodity_options.monitored` | Single source |
| `option_pcr_engine.py` DEFAULT_COMPOSITE_WEIGHTS | `config/market_state.yaml` → `market_state.option_pcr.weights` | Subsystem overlay |
| `option_pcr_engine.py` DEFAULT_PCR_THRESHOLDS | `config/thresholds.yaml` → `thresholds.pcr.*` | Shared thresholds |
| `option_code_parser.py` CFFEX_VARIETIES | `config/codes.yaml` → `codes.cffex_options` | Single source |
| `option_code_parser.py` COMMODITY_VARIETIES | `config/codes.yaml` → `codes.commodities.*.option` | Single source |
| `option_code_parser.py` _ETF_STRIKE_DIVISOR | `config/codes.yaml` → `codes.etf_options.*.strike_divisor` | Single source |
| `derivatives_signal_engine.py` DEFAULT_COMMODITY_VARIETIES | `config/codes.yaml` → `codes.commodities` | Read from codes |
| `derivatives_signal_engine.py` DEFAULT_INDEX_FUTURES | `config/codes.yaml` → `codes.index_futures` | Read from codes |
| `derivatives_signal_engine.py` COMPOSITE_WEIGHTS | `config/market_state.yaml` → `market_state.derivatives.composite_weights` | Subsystem overlay |
| `data_loader_service.py` LoaderConfig.future_codes | `config/codes.yaml` → derived from codes.commodities + codes.index_futures | Dynamic |
| `data_loader_service.py` LoaderConfig.index_codes | `config/codes.yaml` → `codes.index_codes` | Single source |
| `tdx_adapter.py` STANDARD_HOST/PORT | `config/tdx.yaml` → `tdx.standard.host/port` | YAML-driven |
| `tdx_adapter.py` MARKET_MAP | `config/codes.yaml` → `codes.markets.*` | YAML-driven |
| `global_settings.py` DATABASE_ENGINES | `config/database.yaml` → `database.engines.*` | YAML + env override |
| `global_settings.py` TDX_CODE_TABLE_PATH | `config/system.yaml` → `system.paths.code_table` | YAML-driven |
| main.py dict-passing | `ServiceContainer` + `EventBus` | DI + event-driven |

### Config Change Example: IFM0→IFL8

**V9 (before):** Must edit 4+ files
1. `data_loader_service.py` → `LoaderConfig.future_codes` change "IFM0" to "IFL8"
2. `contract_manager.py` → check if M0 suffix is handled
3. `derivatives_signal_engine.py` → `DEFAULT_INDEX_FUTURES` change "M0" to "L8"
4. Search notebooks for any M0 references

**V10 (after):** Edit ONE line in ONE file
1. `config/codes.yaml` → `codes.index_futures.IF.continuous: "IFL8"` (already correct)

The continuous contract code is defined ONCE in `codes.yaml`. All engines read it from there. No Python file needs changing.

---

## Appendix A: Event Flow Diagram

```
 ┌──────────────┐     config.changed     ┌──────────────────────┐
 │ ConfigService├────────────────────────►│  All Subsystems      │
 │ (hot reload) │                         │  (reload callbacks)  │
 └──────────────┘                         └──────────────────────┘
 
 ┌──────────────────┐   data.loaded    ┌──────────────────────┐
 │ DataLoaderService├─────────────────►│  MarketStateSubsystem│
 │                  │                  │  (trigger analysis)  │
 └──────────────────┘                  └──────────┬───────────┘
                                                  │
                                    market_state.updated
                                                  │
                                                  ▼
                                       ┌──────────────────────┐
                                       │  price_quant         │
                                       │  (future subsystem)  │
                                       └──────────────────────┘
 
 ┌──────────────────┐  contract.rollover ┌──────────────────────┐
 │ ContractManager  ├───────────────────►│  DerivativesSignal   │
 │                  │                    │  (re-resolve codes)  │
 └──────────────────┘                    └──────────────────────┘
```

## Appendix B: Config Merge Order for Subsystem

```
Subsystem "market_state" sees merged config from:

  Layer 1 (base):    system.yaml
  Layer 2 (shared):  tdx.yaml + database.yaml + cache.yaml + logging.yaml
  Layer 3 (ref):     codes.yaml + thresholds.yaml + overseas.yaml + macro.yaml
  Layer 4 (overlay): market_state.yaml

  Example resolution:
    market_state_classifier.weights.valuation
      → NOT in system.yaml
      → NOT in tdx.yaml
      → FOUND in market_state.yaml → 0.30 ✓
    
    codes.commodities.CU.delivery_months
      → NOT in system/tdx/database/cache/logging/market_state
      → FOUND in codes.yaml → [1,2,...,12] ✓
    
    tdx.standard.host
      → NOT in system.yaml
      → FOUND in tdx.yaml → "180.153.18.170" ✓
```

---

*End of V10 Architecture Design Document*
