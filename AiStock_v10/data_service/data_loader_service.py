"""
AiStock V10 DataLoaderService — 配置驱动的数据加载编排服务

V10 关键变更 (vs V9):
  - 移除 LoaderConfig 硬编码数据类, 所有配置来自 ConfigService (YAML)
  - 构造函数接受 config_service: ConfigService, 从 codes.yaml / tdx.yaml 读取
  - 配置热重载: codes.yaml 变更自动刷新品种列表
  - 缓存 TTL 从 codes.cache_ttl 配置, 不再硬编码

配置映射:
  codes.indices           → 指数K线品种列表
  codes.futures           → 期货主连品种列表
  codes.option_underlyings → 期权标的配置
  codes.overseas          → 海外期货配置
  codes.macro             → 宏观指标配置
  codes.valuation         → 估值数据配置
  codes.cache_ttl         → 各段缓存TTL
  tdx.bars_count          → K线条数配置

统一编排三大数据源:
  1. TDXAdapter  → 指数K线 / 期货K线 / 期权K线 / 宏观数据
  2. AKAdapter   → 海外期货 (29品种) / 辅助数据 (CFTC/LME/QVIX...)
  3. DatabaseReader → PE/PB 估值 / 期权合约映射

加载结果分为 7 个数据段:
  index_data       — A股指数K线 (TDX标准端口)
  futures_data     — 国内期货K线 (TDX扩展端口)
  option_data      — 期权K线 / PCR计算 (TDX扩展端口)
  overseas_futures — 海外期货价格 (AKAdapter)
  auxiliary_data   — CFTC/LME/QVIX等 (AKAdapter)
  valuation_data   — PE/PB百分位 (DatabaseReader)
  macro_data       — 宏观指标 (TDX扩展端口)

特性:
  - 按段加载 (load_section) / 全量加载 (load_all)
  - 数据质量校验
  - 缓存集成 (各段独立TTL, 从配置加载)
  - 进度日志
  - 配置热重载回调
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

import pandas as pd

# ─── ConfigService (V10) ─────────────────────────────────────────────────────
try:
    from base_service.config_service import ConfigService
except ImportError:
    ConfigService = None  # type: ignore[assignment,misc]

from .tdx_adapter import TDXAdapter, MarketType, BarCategory, MARKET_MAP
from .ak_adapter import AKAdapter, FUTURES_SYMBOL_MAP, CORE_SYMBOLS, ALL_SYMBOLS, AUXILIARY_DATA_TYPES
from .database_reader import DatabaseReader

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# 数据段定义
# ═══════════════════════════════════════════════════════════════════════════════

class DataSection(str, Enum):
    """数据段标识"""
    INDEX_DATA = "index_data"
    FUTURES_DATA = "futures_data"
    OPTION_DATA = "option_data"
    OVERSEAS_FUTURES = "overseas_futures"
    AUXILIARY_DATA = "auxiliary_data"
    VALUATION_DATA = "valuation_data"
    MACRO_DATA = "macro_data"


# ─── 默认缓存TTL (V10: 优先从 codes.cache_ttl 加载) ─────────────────────────
DEFAULT_SECTION_TTL: Dict[str, float] = {
    DataSection.INDEX_DATA: 300,         # 指数K线: 5分钟
    DataSection.FUTURES_DATA: 120,       # 期货K线: 2分钟
    DataSection.OPTION_DATA: 120,        # 期权K线: 2分钟
    DataSection.OVERSEAS_FUTURES: 60,    # 海外期货: 1分钟
    DataSection.AUXILIARY_DATA: 1800,    # 辅助数据: 30分钟
    DataSection.VALUATION_DATA: 3600,    # 估值数据: 1小时
    DataSection.MACRO_DATA: 3600,        # 宏观数据: 1小时
}


# ═══════════════════════════════════════════════════════════════════════════════
# 数据质量校验
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class QualityReport:
    """数据质量报告"""
    section: str
    total_items: int = 0
    valid_items: int = 0
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    load_time_ms: float = 0.0

    @property
    def success_rate(self) -> float:
        if self.total_items == 0:
            return 0.0
        return self.valid_items / self.total_items

    @property
    def is_healthy(self) -> bool:
        return len(self.errors) == 0 and self.success_rate >= 0.5

    def to_dict(self) -> Dict[str, Any]:
        return {
            "section": self.section,
            "total_items": self.total_items,
            "valid_items": self.valid_items,
            "success_rate": f"{self.success_rate:.1%}",
            "warnings": self.warnings,
            "errors": self.errors,
            "load_time_ms": f"{self.load_time_ms:.0f}",
            "is_healthy": self.is_healthy,
        }


def _validate_dataframe(
    df: pd.DataFrame,
    section: str,
    required_cols: Optional[Set[str]] = None,
    min_rows: int = 1,
) -> QualityReport:
    """校验DataFrame数据质量"""
    report = QualityReport(section=section)
    report.total_items = 1

    if df.empty:
        report.errors.append("数据为空")
        return report

    report.valid_items = 1

    if required_cols and not required_cols.issubset(df.columns):
        missing = required_cols - set(df.columns)
        report.warnings.append(f"缺少列: {missing}")

    if len(df) < min_rows:
        report.warnings.append(f"行数不足: {len(df)} < {min_rows}")

    # 检查空值
    null_counts = df.isnull().sum()
    high_null_cols = null_counts[null_counts > len(df) * 0.3]
    if not high_null_cols.empty:
        report.warnings.append(f"高空值列: {dict(high_null_cols)}")

    return report


def _validate_dict_data(
    data: Dict[str, Any],
    section: str,
    min_items: int = 1,
) -> QualityReport:
    """校验字典数据质量"""
    report = QualityReport(section=section)
    report.total_items = len(data)

    if not data:
        report.errors.append("数据为空字典")
        return report

    valid = sum(1 for v in data.values() if v is not None and v != {})
    report.valid_items = valid

    if valid < min_items:
        report.warnings.append(f"有效数据不足: {valid} < {min_items}")

    if valid < len(data):
        invalid_count = len(data) - valid
        report.warnings.append(f"无效条目: {invalid_count}")

    return report


# ═══════════════════════════════════════════════════════════════════════════════
# 内存缓存
# ═══════════════════════════════════════════════════════════════════════════════

class _SectionCache:
    """按数据段独立TTL的缓存"""

    def __init__(self):
        self._store: Dict[str, tuple] = {}  # section -> (data, expire_time, report)

    def get(self, section: str) -> Optional[tuple]:
        if section in self._store:
            data, expire, report = self._store[section]
            if time.time() < expire:
                return data, report
            del self._store[section]
        return None

    def set(self, section: str, data: Any, report: QualityReport, ttl: float):
        expire = time.time() + ttl
        self._store[section] = (data, expire, report)

    def invalidate(self, section: Optional[str] = None):
        if section:
            self._store.pop(section, None)
        else:
            self._store.clear()


# ═══════════════════════════════════════════════════════════════════════════════
# DataLoaderService
# ═══════════════════════════════════════════════════════════════════════════════

class DataLoaderService:
    """
    V10 数据加载编排服务 — 配置驱动

    V10 核心变更:
      - 移除 LoaderConfig 硬编码数据类
      - 所有配置从 ConfigService (YAML) 加载
      - 配置热重载: codes.yaml 变更 → 自动刷新品种列表 → 清除缓存

    统一管理三大数据源的加载流程, 提供:
      - load_all()         全量加载 7 个数据段
      - load_section()     按段加载
      - load_overseas_futures()  海外期货 (按层级)
      - load_option_data_for_pcr()  期权PCR数据
      - 数据质量校验
      - 缓存管理
      - 进度回调
      - 配置热重载回调
    """

    def __init__(
        self,
        tdx_adapter: TDXAdapter,
        ak_adapter: AKAdapter,
        db_reader: DatabaseReader,
        config_service: Optional[Any] = None,
        progress_callback: Optional[Callable[[str, float, str], None]] = None,
    ):
        """
        Args:
            tdx_adapter: 通达信双端口适配器
            ak_adapter: AKShare 适配器
            db_reader: PostgreSQL 数据库读取器
            config_service: V10 ConfigService 实例 (必需)
            progress_callback: 进度回调 (section, progress_0to1, message)
        """
        self._tdx = tdx_adapter
        self._ak = ak_adapter
        self._db = db_reader
        self._config_service = config_service
        self._progress_cb = progress_callback
        self._cache = _SectionCache()
        self._quality_reports: Dict[str, QualityReport] = {}

        # ─── 从 ConfigService 加载所有配置 ──────────────────────────────
        self._load_config()

        # ─── 注册配置热重载回调 ─────────────────────────────────────────
        if self._config_service is not None and ConfigService is not None:
            self._config_service.on_change("codes", self._on_config_change)
            logger.info("DataLoaderService: 已注册配置热重载回调")

        logger.info(
            "DataLoaderService 初始化完成 (配置驱动) — 索引:%d 期货:%d 期权标的:%d",
            len(self._index_codes),
            len(self._future_codes),
            len(self._option_underlyings_list),
        )

    # ═══════════════════════════════════════════════════════════════════════
    # 配置加载
    # ═══════════════════════════════════════════════════════════════════════

    def _load_config(self):
        """从 ConfigService 加载所有配置, 无 ConfigService 时使用硬编码默认值"""

        # ─── 指数K线配置 ─────────────────────────────────────────────────
        self._index_codes: List[Dict[str, str]] = self._get_config_list(
            "codes.indices",
            default=[
                {"code": "000001", "market_type": "index_sh", "name": "上证指数"},
                {"code": "399001", "market_type": "index_sz", "name": "深证成指"},
                {"code": "399006", "market_type": "index_sz", "name": "创业板指"},
                {"code": "000300", "market_type": "index_sh", "name": "沪深300"},
                {"code": "000905", "market_type": "index_sh", "name": "中证500"},
                {"code": "000852", "market_type": "index_sh", "name": "中证1000"},
            ],
        )
        self._index_bars_count: int = self._get_config_int(
            "tdx.bars_count.index", default=800,
        )

        # ─── 期货K线配置 ─────────────────────────────────────────────────
        self._future_codes: List[Dict[str, str]] = self._get_config_list(
            "codes.futures",
            default=[
                {"code": "IFL8", "market_type": "future_zj", "name": "沪深300主连"},
                {"code": "ICL8", "market_type": "future_zj", "name": "中证500主连"},
                {"code": "IML8", "market_type": "future_zj", "name": "中证1000主连"},
                {"code": "IHL8", "market_type": "future_zj", "name": "上证50主连"},
                {"code": "TFL8", "market_type": "future_zj", "name": "5年期国债主连"},
                {"code": "TLL8", "market_type": "future_zj", "name": "30年期国债主连"},
                {"code": "CUL8", "market_type": "future_sh", "name": "沪铜主连"},
                {"code": "ALL8", "market_type": "future_sh", "name": "沪铝主连"},
                {"code": "AUL8", "market_type": "future_sh", "name": "黄金主连"},
                {"code": "AGL8", "market_type": "future_sh", "name": "白银主连"},
            ],
        )
        self._future_bars_count: int = self._get_config_int(
            "tdx.bars_count.future", default=800,
        )

        # ─── 期权标的配置 ─────────────────────────────────────────────────
        raw_option_cfg = self._get_config_dict(
            "codes.option_underlyings",
            default={
                "510050": {"market_type": "option_sh", "name": "50ETF期权"},
                "510300": {"market_type": "option_sh", "name": "300ETF期权(沪)"},
                "159919": {"market_type": "option_sz", "name": "300ETF期权(深)"},
                "IO":     {"market_type": "option_zj", "name": "沪深300股指期权"},
            },
        )
        # 将 dict 形式转为 list, 保持 V9 兼容接口
        self._option_underlyings_raw: Dict[str, Dict[str, Any]] = raw_option_cfg
        self._option_underlyings_list: List[Dict[str, str]] = []
        for underlying, cfg in raw_option_cfg.items():
            self._option_underlyings_list.append({
                "underlying": underlying,
                "market_type": cfg.get("market_type", "option_sh"),
                "name": cfg.get("name", underlying),
            })
        self._option_bars_count: int = self._get_config_int(
            "tdx.bars_count.option", default=100,
        )

        # ─── 海外期货配置 ─────────────────────────────────────────────────
        self._overseas_config: Dict[str, Any] = self._get_config_dict(
            "codes.overseas",
            default={
                "core_symbols": "OIL,GC,CAD,NG,EUA",
                "extended_symbols": None,
                "auxiliary_types": [
                    "cftc", "lme_stock", "bond_zh_us",
                    "qvix_50etf", "qvix_300etf",
                ],
            },
        )

        # ─── 宏观数据配置 ─────────────────────────────────────────────────
        self._macro_config: Dict[str, Any] = self._get_config_dict(
            "codes.macro",
            default={
                "indicators": [
                    {"code": "CPI", "market": 50, "name": "CPI"},
                    {"code": "PPI", "market": 50, "name": "PPI"},
                    {"code": "PMI", "market": 50, "name": "PMI"},
                ],
            },
        )
        self._macro_count: int = self._get_config_int(
            "tdx.bars_count.macro", default=200,
        )

        # ─── 估值数据配置 ─────────────────────────────────────────────────
        self._valuation_config: Dict[str, Any] = self._get_config_dict(
            "codes.valuation",
            default={
                "codes": ["000300", "000905", "000852"],
                "days": 100,
            },
        )

        # ─── 缓存TTL配置 ─────────────────────────────────────────────────
        raw_ttl = self._get_config_dict(
            "codes.cache_ttl",
            default={},
        )
        self._section_ttl: Dict[str, float] = dict(DEFAULT_SECTION_TTL)
        if raw_ttl:
            for section_key, ttl_val in raw_ttl.items():
                section_name = f"{section_key}"
                if section_name in self._section_ttl:
                    self._section_ttl[section_name] = float(ttl_val)

        # ─── 通用配置 ─────────────────────────────────────────────────────
        self._enable_cache: bool = True
        self._log_progress: bool = True

    # ─── ConfigService 辅助方法 ───────────────────────────────────────────

    def _get_config_list(
        self, key: str, default: List[Any] = None,
    ) -> List[Any]:
        """从 ConfigService 获取列表配置"""
        if self._config_service is not None:
            val = self._config_service.get(key, None)
            if val is not None and isinstance(val, list):
                return val
        return default or []

    def _get_config_dict(
        self, key: str, default: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """从 ConfigService 获取字典配置"""
        if self._config_service is not None:
            val = self._config_service.get(key, None)
            if val is not None and isinstance(val, dict):
                return val
        return default or {}

    def _get_config_int(self, key: str, default: int = 0) -> int:
        """从 ConfigService 获取整数配置"""
        if self._config_service is not None:
            val = self._config_service.get(key, None)
            if val is not None:
                return int(val)
        return default

    # ═══════════════════════════════════════════════════════════════════════
    # 配置热重载
    # ═══════════════════════════════════════════════════════════════════════

    def _on_config_change(self, file_name: str) -> None:
        """
        配置变更回调 — 当 codes.yaml 变更时自动重载

        Args:
            file_name: 变更的配置文件名 (如 "codes")
        """
        logger.info("DataLoaderService: 检测到配置变更 (%s), 重新加载...", file_name)
        try:
            self._load_config()
            # 清除所有缓存, 下次加载时使用新配置
            self._cache.invalidate()
            logger.info(
                "DataLoaderService: 配置重载完成 — 索引:%d 期货:%d 期权标的:%d",
                len(self._index_codes),
                len(self._future_codes),
                len(self._option_underlyings_list),
            )
        except Exception as e:
            logger.error("DataLoaderService: 配置重载失败: %s", e)

    # ─── 进度通知 ─────────────────────────────────────────────────────────

    def _notify_progress(self, section: str, progress: float, message: str = ""):
        if self._log_progress:
            logger.info("[%s] %.0f%% — %s", section, progress * 100, message)
        if self._progress_cb:
            try:
                self._progress_cb(section, progress, message)
            except Exception as e:
                logger.debug("进度回调异常: %s", e)

    # ═══════════════════════════════════════════════════════════════════════
    # 全量加载
    # ═══════════════════════════════════════════════════════════════════════

    def load_all(self) -> Dict[str, Any]:
        """
        全量加载所有 7 个数据段

        Returns:
            {
                'index_data':       {code: DataFrame, ...},
                'futures_data':     {code: DataFrame, ...},
                'option_data':      {underlying: {...}, ...},
                'overseas_futures': {symbol: {...}, ...},
                'auxiliary_data':   {data_type: DataFrame, ...},
                'valuation_data':   {code: DataFrame, ...},
                'macro_data':       {code: DataFrame, ...},
                '_quality':         {section: QualityReport.to_dict(), ...},
                '_load_time_ms':    float,
            }
        """
        total_start = time.time()
        result: Dict[str, Any] = {}

        sections = [
            (DataSection.INDEX_DATA,       self._load_index_data),
            (DataSection.FUTURES_DATA,     self._load_futures_data),
            (DataSection.OPTION_DATA,      self._load_option_data),
            (DataSection.OVERSEAS_FUTURES, self._load_overseas_futures),
            (DataSection.AUXILIARY_DATA,   self._load_auxiliary_data),
            (DataSection.VALUATION_DATA,   self._load_valuation_data),
            (DataSection.MACRO_DATA,       self._load_macro_data),
        ]

        total = len(sections)
        for idx, (section, loader) in enumerate(sections):
            self._notify_progress(section, 0, "开始加载")
            try:
                section_data = loader()
                result[section] = section_data
            except Exception as e:
                logger.error("load_all [%s] 失败: %s", section, e)
                result[section] = {}
                self._quality_reports[section] = QualityReport(
                    section=section, errors=[str(e)],
                )

            progress = (idx + 1) / total
            self._notify_progress(section, progress, "加载完成")

        # 汇总
        total_ms = (time.time() - total_start) * 1000
        result["_quality"] = {
            s: r.to_dict() for s, r in self._quality_reports.items()
        }
        result["_load_time_ms"] = total_ms

        logger.info(
            "DataLoaderService.load_all 完成 — 耗时 %.0fms, %d 段",
            total_ms, total,
        )
        return result

    # ═══════════════════════════════════════════════════════════════════════
    # 按段加载
    # ═══════════════════════════════════════════════════════════════════════

    def load_section(self, section_name: str) -> Any:
        """
        加载指定数据段

        Args:
            section_name: DataSection 枚举值

        Returns:
            该段的数据 (格式因段而异)
        """
        # 检查缓存
        if self._enable_cache:
            cached = self._cache.get(section_name)
            if cached is not None:
                data, report = cached
                logger.info("load_section [%s] 命中缓存", section_name)
                return data

        section_loaders = {
            DataSection.INDEX_DATA:       self._load_index_data,
            DataSection.FUTURES_DATA:     self._load_futures_data,
            DataSection.OPTION_DATA:      self._load_option_data,
            DataSection.OVERSEAS_FUTURES: self._load_overseas_futures,
            DataSection.AUXILIARY_DATA:   self._load_auxiliary_data,
            DataSection.VALUATION_DATA:   self._load_valuation_data,
            DataSection.MACRO_DATA:       self._load_macro_data,
        }

        loader = section_loaders.get(section_name)
        if loader is None:
            logger.error("未知数据段: %s", section_name)
            return None

        data = loader()

        # 写入缓存
        if self._enable_cache:
            report = self._quality_reports.get(section_name, QualityReport(section=section_name))
            ttl = self._section_ttl.get(section_name, 300)
            self._cache.set(section_name, data, report, ttl)

        return data

    # ═══════════════════════════════════════════════════════════════════════
    # 海外期货 (按层级)
    # ═══════════════════════════════════════════════════════════════════════

    def load_overseas_futures(self, tier: str = "core") -> Dict[str, Dict[str, Any]]:
        """
        按层级加载海外期货数据

        Args:
            tier: "core" / "extended" / "auxiliary" / "all"

        Returns:
            {symbol: data_dict, ...}
        """
        self._notify_progress(DataSection.OVERSEAS_FUTURES, 0, f"加载层级: {tier}")

        if tier == "all":
            result = self._ak.get_futures_batch(ALL_SYMBOLS)
        else:
            result = self._ak.get_futures_by_tier(tier)

        # 质量校验
        report = _validate_dict_data(result, DataSection.OVERSEAS_FUTURES)
        self._quality_reports[DataSection.OVERSEAS_FUTURES] = report

        self._notify_progress(
            DataSection.OVERSEAS_FUTURES, 1.0,
            f"完成: {report.valid_items}/{report.total_items} 成功",
        )
        return result

    # ═══════════════════════════════════════════════════════════════════════
    # 期权PCR数据
    # ═══════════════════════════════════════════════════════════════════════

    def load_option_data_for_pcr(
        self, underlying: str,
    ) -> Dict[str, Any]:
        """
        加载指定标的的期权数据, 用于PCR (Put-Call Ratio) 计算

        Args:
            underlying: 标的代码 (如 '510050', 'IO')

        Returns:
            {
                'underlying': str,
                'calls': List[Dict],   # 看涨合约数据
                'puts': List[Dict],    # 看跌合约数据
                'call_volume': int,
                'put_volume': int,
                'pcr_volume': float,   # Put-Call Ratio (volume)
                'call_oi': int,
                'put_oi': int,
                'pcr_oi': float,       # Put-Call Ratio (open interest)
            }
        """
        # 查找对应的期权标的配置 (优先从配置查找)
        underlying_config = self._option_underlyings_raw.get(underlying)
        if underlying_config is not None:
            underlying_config = {
                "underlying": underlying,
                "market_type": underlying_config.get("market_type", "option_sh"),
                "name": underlying_config.get("name", underlying),
            }
        else:
            # 在 list 中查找 (V9 兼容)
            for cfg in self._option_underlyings_list:
                if cfg["underlying"] == underlying:
                    underlying_config = cfg
                    break

        if underlying_config is None:
            logger.warning("期权标的不在配置中: %s, 使用默认参数", underlying)
            underlying_config = {
                "underlying": underlying,
                "market_type": MarketType.OPTION_SH,
                "name": underlying,
            }

        market_type = underlying_config.get("market_type", MarketType.OPTION_SH)
        result: Dict[str, Any] = {
            "underlying": underlying,
            "calls": [],
            "puts": [],
            "call_volume": 0,
            "put_volume": 0,
            "pcr_volume": 0.0,
            "call_oi": 0,
            "put_oi": 0,
            "pcr_oi": 0.0,
        }

        try:
            # 从数据库获取合约映射
            mapping_df = self._db.get_contract_mapping(underlying_code=underlying)
            if mapping_df.empty:
                logger.warning("未找到合约映射: %s", underlying)
                return result

            calls = mapping_df[mapping_df["option_type"] == "C"] if "option_type" in mapping_df.columns else mapping_df
            puts = mapping_df[mapping_df["option_type"] == "P"] if "option_type" in mapping_df.columns else pd.DataFrame()

            # 获取合约K线数据 (最近1天)
            call_data = []
            put_data = []
            call_vol = 0
            put_vol = 0
            call_oi = 0
            put_oi = 0

            market_num = MARKET_MAP.get(market_type, 48)

            # 逐合约获取
            for _, row in calls.iterrows():
                code = row.get("contract_code", "")
                if not code:
                    continue
                try:
                    df = self._tdx.get_bars(
                        market_type, code,
                        category=BarCategory.DAILY,
                        count=1,
                    )
                    if not df.empty:
                        latest = df.iloc[-1]
                        entry = {
                            "code": code,
                            "name": row.get("contract_name", ""),
                            "strike": float(row.get("strike_price", 0)),
                            "expire": str(row.get("expire_date", "")),
                            "close": float(latest.get("close", 0)),
                            "volume": int(latest.get("volume", 0)),
                            "amount": float(latest.get("amount", 0)),
                        }
                        call_data.append(entry)
                        call_vol += entry["volume"]
                except Exception as e:
                    logger.debug("期权合约 %s 获取失败: %s", code, e)

            for _, row in puts.iterrows():
                code = row.get("contract_code", "")
                if not code:
                    continue
                try:
                    df = self._tdx.get_bars(
                        market_type, code,
                        category=BarCategory.DAILY,
                        count=1,
                    )
                    if not df.empty:
                        latest = df.iloc[-1]
                        entry = {
                            "code": code,
                            "name": row.get("contract_name", ""),
                            "strike": float(row.get("strike_price", 0)),
                            "expire": str(row.get("expire_date", "")),
                            "close": float(latest.get("close", 0)),
                            "volume": int(latest.get("volume", 0)),
                            "amount": float(latest.get("amount", 0)),
                        }
                        put_data.append(entry)
                        put_vol += entry["volume"]
                except Exception as e:
                    logger.debug("期权合约 %s 获取失败: %s", code, e)

            result["calls"] = call_data
            result["puts"] = put_data
            result["call_volume"] = call_vol
            result["put_volume"] = put_vol
            result["pcr_volume"] = put_vol / call_vol if call_vol > 0 else 0.0
            result["call_oi"] = call_oi
            result["put_oi"] = put_oi
            result["pcr_oi"] = put_oi / call_oi if call_oi > 0 else 0.0

        except Exception as e:
            logger.error("load_option_data_for_pcr(%s) 失败: %s", underlying, e)

        return result

    # ═══════════════════════════════════════════════════════════════════════
    # 各数据段加载实现
    # ═══════════════════════════════════════════════════════════════════════

    def _load_index_data(self) -> Dict[str, pd.DataFrame]:
        """加载A股指数K线 (TDX标准端口)"""
        start_time = time.time()
        result: Dict[str, pd.DataFrame] = {}

        total = len(self._index_codes)
        for idx, cfg in enumerate(self._index_codes):
            code = cfg["code"]
            name = cfg.get("name", code)
            market_type = cfg.get("market_type", MarketType.INDEX_SH)

            try:
                df = self._tdx.get_index_daily(
                    code=code,
                    market_type=market_type,
                    count=self._index_bars_count,
                )
                result[code] = df
                if df.empty:
                    logger.warning("指数 %s (%s) 数据为空", name, code)
            except Exception as e:
                logger.error("指数 %s (%s) 加载失败: %s", name, code, e)
                result[code] = pd.DataFrame()

            progress = (idx + 1) / total
            self._notify_progress(DataSection.INDEX_DATA, progress, f"{name} 完成")

        # 质量校验
        report = _validate_dict_data(result, DataSection.INDEX_DATA)
        report.load_time_ms = (time.time() - start_time) * 1000
        self._quality_reports[DataSection.INDEX_DATA] = report

        return result

    def _load_futures_data(self) -> Dict[str, pd.DataFrame]:
        """加载国内期货K线 (TDX扩展端口)"""
        start_time = time.time()
        result: Dict[str, pd.DataFrame] = {}

        total = len(self._future_codes)
        for idx, cfg in enumerate(self._future_codes):
            code = cfg["code"]
            name = cfg.get("name", code)
            market_type = cfg.get("market_type", MarketType.FUTURE_ZJ)

            try:
                df = self._tdx.get_future_daily(
                    code=code,
                    market_type=market_type,
                    count=self._future_bars_count,
                )
                result[code] = df
                if df.empty:
                    logger.warning("期货 %s (%s) 数据为空", name, code)
            except Exception as e:
                logger.error("期货 %s (%s) 加载失败: %s", name, code, e)
                result[code] = pd.DataFrame()

            progress = (idx + 1) / total
            self._notify_progress(DataSection.FUTURES_DATA, progress, f"{name} 完成")

        report = _validate_dict_data(result, DataSection.FUTURES_DATA)
        report.load_time_ms = (time.time() - start_time) * 1000
        self._quality_reports[DataSection.FUTURES_DATA] = report

        return result

    def _load_option_data(self) -> Dict[str, Dict[str, Any]]:
        """加载期权K线数据 (TDX扩展端口)"""
        start_time = time.time()
        result: Dict[str, Dict[str, Any]] = {}

        total = len(self._option_underlyings_list)
        for idx, cfg in enumerate(self._option_underlyings_list):
            underlying = cfg["underlying"]
            name = cfg.get("name", underlying)

            try:
                pcr_data = self.load_option_data_for_pcr(underlying)
                result[underlying] = pcr_data
            except Exception as e:
                logger.error("期权 %s (%s) 加载失败: %s", name, underlying, e)
                result[underlying] = {}

            progress = (idx + 1) / total
            self._notify_progress(DataSection.OPTION_DATA, progress, f"{name} 完成")

        report = _validate_dict_data(result, DataSection.OPTION_DATA)
        report.load_time_ms = (time.time() - start_time) * 1000
        self._quality_reports[DataSection.OPTION_DATA] = report

        return result

    def _load_overseas_futures(self) -> Dict[str, Dict[str, Any]]:
        """加载海外期货价格 (AKAdapter)"""
        start_time = time.time()

        # 确定加载范围: 优先使用配置中的品种
        symbols = None  # None = 让 AKAdapter 根据配置决定

        result = self._ak.get_futures_batch(symbols)

        report = _validate_dict_data(result, DataSection.OVERSEAS_FUTURES)
        report.load_time_ms = (time.time() - start_time) * 1000
        self._quality_reports[DataSection.OVERSEAS_FUTURES] = report

        return result

    def _load_auxiliary_data(self) -> Dict[str, pd.DataFrame]:
        """加载辅助数据 (AKAdapter)"""
        start_time = time.time()
        result: Dict[str, pd.DataFrame] = {}

        # V10: 辅助数据类型从 AKAdapter 配置获取 (优先) 或从 codes.overseas.auxiliary_types
        aux_types = self._ak.auxiliary_types
        if not aux_types:
            # 回退到海外配置中的 auxiliary_types
            aux_types = self._overseas_config.get("auxiliary_types", list(AUXILIARY_DATA_TYPES.keys()))

        total = len(aux_types)
        for idx, data_type in enumerate(aux_types):
            try:
                df = self._ak.get_auxiliary_data(data_type)
                if df is not None:
                    result[data_type] = df
                else:
                    result[data_type] = pd.DataFrame()
                    logger.warning("辅助数据 %s 返回 None", data_type)
            except Exception as e:
                logger.error("辅助数据 %s 加载失败: %s", data_type, e)
                result[data_type] = pd.DataFrame()

            progress = (idx + 1) / total
            self._notify_progress(DataSection.AUXILIARY_DATA, progress, f"{data_type} 完成")

        report = _validate_dict_data(result, DataSection.AUXILIARY_DATA)
        report.load_time_ms = (time.time() - start_time) * 1000
        self._quality_reports[DataSection.AUXILIARY_DATA] = report

        return result

    def _load_valuation_data(self) -> Dict[str, pd.DataFrame]:
        """加载PE/PB估值数据 (DatabaseReader)"""
        start_time = time.time()
        result: Dict[str, pd.DataFrame] = {}

        val_codes = self._valuation_config.get("codes", ["000300", "000905", "000852"])
        val_days = self._valuation_config.get("days", 100)

        try:
            batch_result = self._db.get_index_pe_batch(val_codes)
            result = batch_result
        except Exception as e:
            logger.error("批量估值数据加载失败, 回退逐条加载: %s", e)
            for code in val_codes:
                try:
                    df = self._db.get_index_pe(code, val_days)
                    result[code] = df
                except Exception as e2:
                    logger.error("估值数据 %s 加载失败: %s", code, e2)
                    result[code] = pd.DataFrame()

        report = _validate_dict_data(result, DataSection.VALUATION_DATA)
        report.load_time_ms = (time.time() - start_time) * 1000
        self._quality_reports[DataSection.VALUATION_DATA] = report

        return result

    def _load_macro_data(self) -> Dict[str, pd.DataFrame]:
        """加载宏观指标 (TDX扩展端口)"""
        start_time = time.time()
        result: Dict[str, pd.DataFrame] = {}

        macro_indicators = self._macro_config.get("indicators", [
            {"code": "CPI", "market": 50, "name": "CPI"},
            {"code": "PPI", "market": 50, "name": "PPI"},
            {"code": "PMI", "market": 50, "name": "PMI"},
        ])

        total = len(macro_indicators)
        for idx, cfg in enumerate(macro_indicators):
            code = cfg["code"]
            name = cfg.get("name", code)
            market = cfg.get("market", 50)

            try:
                df = self._tdx.get_macro_data(
                    code=code,
                    market=market,
                    count=self._macro_count,
                )
                result[code] = df
                if df.empty:
                    logger.warning("宏观指标 %s (%s) 数据为空", name, code)
            except Exception as e:
                logger.error("宏观指标 %s (%s) 加载失败: %s", name, code, e)
                result[code] = pd.DataFrame()

            progress = (idx + 1) / total
            self._notify_progress(DataSection.MACRO_DATA, progress, f"{name} 完成")

        report = _validate_dict_data(result, DataSection.MACRO_DATA)
        report.load_time_ms = (time.time() - start_time) * 1000
        self._quality_reports[DataSection.MACRO_DATA] = report

        return result

    # ═══════════════════════════════════════════════════════════════════════
    # 缓存管理
    # ═══════════════════════════════════════════════════════════════════════

    def invalidate_cache(self, section: Optional[str] = None):
        """使缓存失效"""
        self._cache.invalidate(section)
        if section:
            logger.info("缓存已失效: %s", section)
        else:
            logger.info("全部缓存已清空")

    def get_cached_sections(self) -> List[str]:
        """获取当前已缓存的段名"""
        return list(self._cache._store.keys())

    # ═══════════════════════════════════════════════════════════════════════
    # 质量报告
    # ═══════════════════════════════════════════════════════════════════════

    def get_quality_report(self, section: Optional[str] = None) -> Dict[str, Any]:
        """
        获取数据质量报告

        Args:
            section: 指定段名, None = 全部

        Returns:
            质量报告字典
        """
        if section:
            report = self._quality_reports.get(section)
            return report.to_dict() if report else {}
        return {s: r.to_dict() for s, r in self._quality_reports.items()}

    def get_health_summary(self) -> Dict[str, Any]:
        """获取整体健康摘要"""
        tdx_health = self._tdx.health_check()
        ak_health = self._ak.health_check()
        db_health = self._db.health_check()

        total_items = sum(r.total_items for r in self._quality_reports.values())
        valid_items = sum(r.valid_items for r in self._quality_reports.values())
        unhealthy = [s for s, r in self._quality_reports.items() if not r.is_healthy]

        return {
            "data_sources": {
                "tdx_standard": tdx_health.get("standard_port", False),
                "tdx_extension": tdx_health.get("extension_port", False),
                "akshare": ak_health.get("akshare", False),
                "database": db_health.get("connected", False),
            },
            "quality": {
                "total_items": total_items,
                "valid_items": valid_items,
                "success_rate": f"{valid_items / total_items:.1%}" if total_items > 0 else "N/A",
                "unhealthy_sections": unhealthy,
            },
            "cache": {
                "cached_sections": self.get_cached_sections(),
            },
            "config": {
                "config_driven": self._config_service is not None,
                "index_codes": len(self._index_codes),
                "future_codes": len(self._future_codes),
                "option_underlyings": len(self._option_underlyings_list),
            },
        }
