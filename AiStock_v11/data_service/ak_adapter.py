"""
AiStock V11 AKAdapter — AKShare 海外期货及辅助数据适配器 (配置驱动)

V11 关键修复 (2026-05):
  - ak_code 从中文代码更新为英文短代码 (akshare 1.18.x API变更)
    旧: ak_code="CL" → 新: ak_code="CL"
    旧: ak_code="GC" → 新: ak_code="GC"
    等29个品种全部更新
  - futures_foreign_hist() 新API返回英文列名 (date/open/high/low/close/volume)
    不再返回中文列名 (日期/开盘价/最高价/最低价/收盘价/成交量)

V10 关键变更:
  - 构造函数接受 ConfigService, 从 codes.yaml 读取海外期货配置
  - core/extended_symbols 可从配置加载, 也可从内置 FUTURES_SYMBOL_MAP 使用
  - 保留全部 V9 功能 (29品种, 3层级, 缓存, 限速, 重试, 辅助数据)

29 个验证过的海外期货品种 (3 层级: core / extended / auxiliary)
辅助数据: CFTC / LME 库存 / 国债收益率 / QVIX / EIA / ISM / 全球指数

V8 关键修复:
  - 所有 multiplier = 1.0 (akshare 已返回标准单位, 0.01 bug 已修复)
  - 移除 KC (coffee, akshare 不可用)
  - BZ → OIL (布伦特原油)
  - 新增 22 个品种, 共计 29 个
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import pandas as pd

# ─── ConfigService (V10) ─────────────────────────────────────────────────────
try:
    from base_service.config_service import ConfigService
except ImportError:
    ConfigService = None  # type: ignore[assignment,misc]

try:
    import akshare as ak
except ImportError:
    ak = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# 29 个海外期货品种定义
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class FuturesSymbol:
    """海外期货品种元数据"""
    symbol: str          # 标准代码 (如 CL, GC)
    ak_code: str         # akshare 接口参数 (如 "WTI原油")
    name: str            # 中文名称
    exchange: str        # 交易所
    tier: str            # core / extended / auxiliary
    priority: int        # 加载优先级 (越小越优先)
    a_share_sectors: List[str] = field(default_factory=list)  # 关联 A 股板块
    signal_type: str = "price"    # price / basis / volatility
    multiplier: float = 1.0       # V8: 全部为 1.0 (akshare 返回标准单位)


# ─── 品种符号映射表 (29 个) ───────────────────────────────────────────────────
FUTURES_SYMBOL_MAP: Dict[str, FuturesSymbol] = {
    # ═════════════════════════════════════════════════════════════════════
    # CORE 层 (8) — 流动性最高, 始终加载
    # ═════════════════════════════════════════════════════════════════════
    "CL": FuturesSymbol(
        symbol="CL", ak_code="CL", name="WTI原油",
        exchange="NYMEX", tier="core", priority=1,
        a_share_sectors=["石油开采", "油气服务"],
        signal_type="price", multiplier=1.0,
    ),
    "OIL": FuturesSymbol(
        symbol="OIL", ak_code="OIL", name="布伦特原油",
        exchange="ICE", tier="core", priority=2,
        a_share_sectors=["石油开采", "油气服务"],
        signal_type="price", multiplier=1.0,
    ),
    "GC": FuturesSymbol(
        symbol="GC", ak_code="GC", name="COMEX黄金",
        exchange="COMEX", tier="core", priority=3,
        a_share_sectors=["黄金", "贵金属"],
        signal_type="price", multiplier=1.0,
    ),
    "XAU": FuturesSymbol(
        symbol="XAU", ak_code="XAU", name="伦敦金现货",
        exchange="LBMA", tier="core", priority=4,
        a_share_sectors=["黄金", "贵金属"],
        signal_type="price", multiplier=1.0,
    ),
    "SI": FuturesSymbol(
        symbol="SI", ak_code="SI", name="COMEX白银",
        exchange="COMEX", tier="core", priority=5,
        a_share_sectors=["白银", "贵金属"],
        signal_type="price", multiplier=1.0,
    ),
    "XAG": FuturesSymbol(
        symbol="XAG", ak_code="XAG", name="伦敦银现货",
        exchange="LBMA", tier="core", priority=6,
        a_share_sectors=["白银", "贵金属"],
        signal_type="price", multiplier=1.0,
    ),
    "NG": FuturesSymbol(
        symbol="NG", ak_code="NG", name="天然气",
        exchange="NYMEX", tier="core", priority=7,
        a_share_sectors=["燃气", "天然气"],
        signal_type="price", multiplier=1.0,
    ),
    "HG": FuturesSymbol(
        symbol="HG", ak_code="HG", name="COMEX铜",
        exchange="COMEX", tier="core", priority=8,
        a_share_sectors=["铜", "有色金属"],
        signal_type="price", multiplier=1.0,
    ),

    # ═════════════════════════════════════════════════════════════════════
    # EXTENDED 层 (12) — 重要商品, 按需加载
    # ═════════════════════════════════════════════════════════════════════
    "C": FuturesSymbol(
        symbol="C", ak_code="C", name="CBOT玉米",
        exchange="CBOT", tier="extended", priority=9,
        a_share_sectors=["玉米", "农业种植"],
        signal_type="price", multiplier=1.0,
    ),
    "W": FuturesSymbol(
        symbol="W", ak_code="W", name="CBOT小麦",
        exchange="CBOT", tier="extended", priority=10,
        a_share_sectors=["小麦", "农业种植"],
        signal_type="price", multiplier=1.0,
    ),
    "S": FuturesSymbol(
        symbol="S", ak_code="S", name="CBOT大豆",
        exchange="CBOT", tier="extended", priority=11,
        a_share_sectors=["大豆", "农业种植"],
        signal_type="price", multiplier=1.0,
    ),
    "BO": FuturesSymbol(
        symbol="BO", ak_code="BO", name="CBOT豆油",
        exchange="CBOT", tier="extended", priority=12,
        a_share_sectors=["豆油", "食用油"],
        signal_type="price", multiplier=1.0,
    ),
    "SM": FuturesSymbol(
        symbol="SM", ak_code="SM", name="CBOT豆粕",
        exchange="CBOT", tier="extended", priority=13,
        a_share_sectors=["饲料", "农产品加工"],
        signal_type="price", multiplier=1.0,
    ),
    "CT": FuturesSymbol(
        symbol="CT", ak_code="CT", name="ICE棉花",
        exchange="ICE", tier="extended", priority=14,
        a_share_sectors=["棉花", "纺织"],
        signal_type="price", multiplier=1.0,
    ),
    "RS": FuturesSymbol(
        symbol="RS", ak_code="RS", name="ICE油菜籽",
        exchange="ICE", tier="extended", priority=15,
        a_share_sectors=["油菜籽", "食用油"],
        signal_type="price", multiplier=1.0,
    ),
    "CAD": FuturesSymbol(
        symbol="CAD", ak_code="CAD", name="CME加元",
        exchange="CME", tier="extended", priority=16,
        a_share_sectors=["外汇"],
        signal_type="price", multiplier=1.0,
    ),
    "LHC": FuturesSymbol(
        symbol="LHC", ak_code="LHC", name="LME铝",
        exchange="LME", tier="extended", priority=17,
        a_share_sectors=["铝", "有色金属"],
        signal_type="price", multiplier=1.0,
    ),
    "AHD": FuturesSymbol(
        symbol="AHD", ak_code="AHD", name="LME铝合金",
        exchange="LME", tier="extended", priority=18,
        a_share_sectors=["铝", "有色金属"],
        signal_type="price", multiplier=1.0,
    ),
    "EUA": FuturesSymbol(
        symbol="EUA", ak_code="EUA", name="ICE碳排放配额",
        exchange="ICE", tier="extended", priority=19,
        a_share_sectors=["碳中和", "环保"],
        signal_type="price", multiplier=1.0,
    ),
    "FEF": FuturesSymbol(
        symbol="FEF", ak_code="FEF", name="远期运费协议",
        exchange="ICE", tier="extended", priority=20,
        a_share_sectors=["航运", "物流"],
        signal_type="price", multiplier=1.0,
    ),

    # ═════════════════════════════════════════════════════════════════════
    # AUXILIARY 层 (9) — 低频辅助品种
    # ═════════════════════════════════════════════════════════════════════
    "NID": FuturesSymbol(
        symbol="NID", ak_code="NID", name="LME镍",
        exchange="LME", tier="auxiliary", priority=21,
        a_share_sectors=["镍", "有色金属"],
        signal_type="price", multiplier=1.0,
    ),
    "PBD": FuturesSymbol(
        symbol="PBD", ak_code="PBD", name="LME铅",
        exchange="LME", tier="auxiliary", priority=22,
        a_share_sectors=["铅", "有色金属"],
        signal_type="price", multiplier=1.0,
    ),
    "SND": FuturesSymbol(
        symbol="SND", ak_code="SND", name="LME锡",
        exchange="LME", tier="auxiliary", priority=23,
        a_share_sectors=["锡", "有色金属"],
        signal_type="price", multiplier=1.0,
    ),
    "XPT": FuturesSymbol(
        symbol="XPT", ak_code="XPT", name="NYMEX铂金",
        exchange="NYMEX", tier="auxiliary", priority=24,
        a_share_sectors=["铂金", "贵金属"],
        signal_type="price", multiplier=1.0,
    ),
    "XPD": FuturesSymbol(
        symbol="XPD", ak_code="XPD", name="NYMEX钯金",
        exchange="NYMEX", tier="auxiliary", priority=25,
        a_share_sectors=["钯金", "贵金属"],
        signal_type="price", multiplier=1.0,
    ),
    "FCPO": FuturesSymbol(
        symbol="FCPO", ak_code="FCPO", name="BMD棕榈油",
        exchange="BMD", tier="auxiliary", priority=26,
        a_share_sectors=["棕榈油", "食用油"],
        signal_type="price", multiplier=1.0,
    ),
    "RSS3": FuturesSymbol(
        symbol="RSS3", ak_code="RSS3", name="TSR20橡胶",
        exchange="SICOM", tier="auxiliary", priority=27,
        a_share_sectors=["橡胶", "化工"],
        signal_type="price", multiplier=1.0,
    ),
    "BTC": FuturesSymbol(
        symbol="BTC", ak_code="BTC", name="CME比特币",
        exchange="CME", tier="auxiliary", priority=28,
        a_share_sectors=["数字货币", "区块链"],
        signal_type="volatility", multiplier=1.0,
    ),
    "ZSD": FuturesSymbol(
        symbol="ZSD", ak_code="ZSD", name="LME锌",
        exchange="LME", tier="auxiliary", priority=29,
        a_share_sectors=["锌", "有色金属"],
        signal_type="price", multiplier=1.0,
    ),
}

# ─── 品种代码快速索引 ─────────────────────────────────────────────────────────
ALL_SYMBOLS: List[str] = list(FUTURES_SYMBOL_MAP.keys())
CORE_SYMBOLS: List[str] = [s for s, v in FUTURES_SYMBOL_MAP.items() if v.tier == "core"]
EXTENDED_SYMBOLS: List[str] = [s for s, v in FUTURES_SYMBOL_MAP.items() if v.tier == "extended"]
AUXILIARY_SYMBOLS: List[str] = [s for s, v in FUTURES_SYMBOL_MAP.items() if v.tier == "auxiliary"]

# ─── 单位转换表 (V8: 全部为 1.0) ─────────────────────────────────────────────
UNIT_CONVERT: Dict[str, float] = {
    sym: info.multiplier for sym, info in FUTURES_SYMBOL_MAP.items()
}

# ─── 辅助数据类型定义 ─────────────────────────────────────────────────────────
AUXILIARY_DATA_TYPES = {
    "cftc": "CFTC持仓报告",
    "lme_stock": "LME库存数据",
    "lme_holding": "LME持仓报告",
    "bond_zh_us": "中美利差",
    "bond_us_10y": "美国10年期国债",
    "qvix_50etf": "50ETF期权波动率指数",
    "qvix_300etf": "300ETF期权波动率指数",
    "eia_crude": "EIA原油库存",
    "ism_pmi": "ISM制造业PMI",
    "global_index": "全球主要指数",
}


# ═══════════════════════════════════════════════════════════════════════════════
# 内存缓存
# ═══════════════════════════════════════════════════════════════════════════════

class _MemoryCache:
    """带TTL的内存缓存"""

    def __init__(self, default_ttl: float = 300.0):
        self._store: Dict[str, tuple] = {}  # key -> (data, expire_time)
        self._default_ttl = default_ttl

    def get(self, key: str) -> Optional[Any]:
        if key in self._store:
            data, expire = self._store[key]
            if time.time() < expire:
                return data
            del self._store[key]
        return None

    def set(self, key: str, data: Any, ttl: Optional[float] = None):
        expire = time.time() + (ttl if ttl is not None else self._default_ttl)
        self._store[key] = (data, expire)

    def clear(self):
        self._store.clear()


# ═══════════════════════════════════════════════════════════════════════════════
# AKAdapter
# ═══════════════════════════════════════════════════════════════════════════════

class AKAdapter:
    """
    AKShare 海外期货及辅助数据适配器 (V10 配置驱动)

    V10 变更:
      - 构造函数接受 config_service: ConfigService
      - 海外品种 core/extended 列表可从 codes.yaml 配置加载
      - 辅助数据类型可从 codes.yaml 配置加载
      - 无 ConfigService 时完全向后兼容 V9 行为

    特性:
      - 29 个验证品种, 3 层级加载策略
      - 内存缓存 + 请求限速 (0.5s 间隔)
      - 重试逻辑 (2 次重试, 1s 间隔)
      - 辅助数据: CFTC / LME / 国债 / QVIX / EIA / ISM / 全球指数
    """

    def __init__(
        self,
        config_service: Optional[Any] = None,
        *,
        rate_limit_interval: float = 0.5,
        retry_count: int = 2,
        retry_delay: float = 1.0,
        cache_ttl: float = 300.0,
    ):
        self._rate_limit_interval = rate_limit_interval
        self._retry_count = retry_count
        self._retry_delay = retry_delay
        self._cache = _MemoryCache(default_ttl=cache_ttl)
        self._last_request_time: float = 0.0

        # ─── V10: 从 ConfigService 加载海外品种配置 ─────────────────────
        self._core_symbols_override: Optional[List[str]] = None
        self._extended_symbols_override: Optional[List[str]] = None
        self._auxiliary_types_override: Optional[List[str]] = None

        if config_service is not None and ConfigService is not None:
            logger.info("AKAdapter: 使用 ConfigService 加载海外期货配置")

            # core_symbols: 逗号分隔字符串 → list
            core_cfg = config_service.get("codes.overseas.core_symbols", None)
            if core_cfg and isinstance(core_cfg, str):
                self._core_symbols_override = [
                    s.strip() for s in core_cfg.split(",") if s.strip()
                ]
                logger.info(
                    "AKAdapter: 从配置加载 core_symbols: %s",
                    self._core_symbols_override,
                )

            # extended_symbols: 逗号分隔字符串 → list
            ext_cfg = config_service.get("codes.overseas.extended_symbols", None)
            if ext_cfg and isinstance(ext_cfg, str):
                self._extended_symbols_override = [
                    s.strip() for s in ext_cfg.split(",") if s.strip()
                ]
                logger.info(
                    "AKAdapter: 从配置加载 extended_symbols: %s",
                    self._extended_symbols_override,
                )

            # auxiliary_types: list
            aux_cfg = config_service.get("codes.overseas.auxiliary_types", None)
            if aux_cfg and isinstance(aux_cfg, list):
                self._auxiliary_types_override = aux_cfg
                logger.info(
                    "AKAdapter: 从配置加载 auxiliary_types: %s",
                    self._auxiliary_types_override,
                )

        if ak is None:
            logger.warning("AKAdapter: akshare 未安装, 所有数据请求将返回空")
        else:
            logger.info(
                "AKAdapter 初始化完成 — %d 品种, 限速 %.1fs, 缓存TTL %.0fs",
                len(FUTURES_SYMBOL_MAP), rate_limit_interval, cache_ttl,
            )

    # ─── 品种列表访问 (V10: 优先使用配置覆盖) ────────────────────────────

    @property
    def core_symbols(self) -> List[str]:
        """获取 core 层品种列表 (配置覆盖 > 内置默认)"""
        if self._core_symbols_override is not None:
            return self._core_symbols_override
        return CORE_SYMBOLS

    @property
    def extended_symbols(self) -> List[str]:
        """获取 extended 层品种列表 (配置覆盖 > 内置默认)"""
        if self._extended_symbols_override is not None:
            return self._extended_symbols_override
        return EXTENDED_SYMBOLS

    @property
    def auxiliary_types(self) -> List[str]:
        """获取辅助数据类型列表 (配置覆盖 > 内置默认)"""
        if self._auxiliary_types_override is not None:
            return self._auxiliary_types_override
        return list(AUXILIARY_DATA_TYPES.keys())

    # ─── 请求限速 ─────────────────────────────────────────────────────────

    def _rate_limit(self):
        """确保请求间隔 >= rate_limit_interval"""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._rate_limit_interval:
            time.sleep(self._rate_limit_interval - elapsed)
        self._last_request_time = time.time()

    # ─── 重试执行 ─────────────────────────────────────────────────────────

    def _execute_with_retry(self, func, *args, **kwargs):
        """带重试的函数执行"""
        if ak is None:
            logger.warning("akshare 未安装, 跳过请求")
            return None

        last_err = None
        for attempt in range(self._retry_count):
            try:
                self._rate_limit()
                return func(*args, **kwargs)
            except Exception as e:
                last_err = e
                logger.warning(
                    "AKAdapter 重试 (%d/%d): %s", attempt + 1, self._retry_count, e,
                )
                if attempt < self._retry_count - 1:
                    time.sleep(self._retry_delay)
        logger.error("AKAdapter 请求失败 (已重试 %d 次): %s", self._retry_count, last_err)
        return None

    # ═══════════════════════════════════════════════════════════════════════
    # 海外期货数据
    # ═══════════════════════════════════════════════════════════════════════

    def get_futures_realtime(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        获取单个海外期货品种实时数据

        Args:
            symbol: 品种代码 (如 'CL', 'GC')

        Returns:
            包含 price/change/pct_change 等字段的字典, 失败返回 None
        """
        info = FUTURES_SYMBOL_MAP.get(symbol)
        if info is None:
            logger.error("未知品种: %s", symbol)
            return None

        cache_key = f"futures_rt_{symbol}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        def _fetch():
            df = ak.futures_foreign_hist(symbol=info.ak_code)
            if df is None or df.empty:
                return None
            row = df.iloc[-1]
            multiplier = UNIT_CONVERT.get(symbol, 1.0)
            # V11: akshare 1.18.x 返回英文列名 (date/open/high/low/close/volume)
            # 兼容旧版中文列名作为 fallback
            result = {
                "symbol": symbol,
                "name": info.name,
                "exchange": info.exchange,
                "price": float(row.get("close", row.get("收盘价", 0))) * multiplier,
                "change": float(row.get("change", row.get("涨跌额", 0))) * multiplier,
                "pct_change": float(row.get("pct_change", row.get("涨跌幅", 0))),
                "open": float(row.get("open", row.get("开盘价", 0))) * multiplier,
                "high": float(row.get("high", row.get("最高价", 0))) * multiplier,
                "low": float(row.get("low", row.get("最低价", 0))) * multiplier,
                "volume": int(row.get("volume", row.get("成交量", 0))),
                "date": str(row.get("date", row.get("日期", ""))),
                "tier": info.tier,
                "timestamp": time.time(),
            }
            return result

        result = self._execute_with_retry(_fetch)
        if result is not None:
            self._cache.set(cache_key, result, ttl=60)  # 实时数据短TTL
        return result

    def get_futures_batch(
        self, symbols: Optional[List[str]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """
        批量获取海外期货实时数据

        Args:
            symbols: 品种代码列表, None = 全部 29 个

        Returns:
            {symbol: data_dict, ...}
        """
        if symbols is None:
            symbols = ALL_SYMBOLS

        results: Dict[str, Dict[str, Any]] = {}
        for sym in symbols:
            data = self.get_futures_realtime(sym)
            if data is not None:
                results[sym] = data
            else:
                logger.debug("get_futures_batch 跳过 %s (数据获取失败)", sym)

        logger.info("AKAdapter 批量获取完成: %d/%d 成功", len(results), len(symbols))
        return results

    def get_futures_hist(
        self, symbol: str, days: int = 120,
    ) -> Optional[pd.DataFrame]:
        """
        获取海外期货历史数据

        Args:
            symbol: 品种代码
            days: 回溯天数

        Returns:
            标准化后的 DataFrame (columns: date/open/high/low/close/volume)
        """
        info = FUTURES_SYMBOL_MAP.get(symbol)
        if info is None:
            logger.error("未知品种: %s", symbol)
            return None

        cache_key = f"futures_hist_{symbol}_{days}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        def _fetch():
            df = ak.futures_foreign_hist(symbol=info.ak_code)
            if df is None or df.empty:
                return None

            # V11: akshare 1.18.x 已返回英文列名, 兼容旧版中文列名
            # 英文列名: date/open/high/low/close/volume/position
            # 中文列名: 日期/开盘价/最高价/最低价/收盘价/成交量/涨跌额/涨跌幅
            col_map = {}
            cn_to_en = {
                "日期": "date", "开盘价": "open", "最高价": "high",
                "最低价": "low", "收盘价": "close", "成交量": "volume",
                "涨跌额": "change", "涨跌幅": "pct_change",
            }
            for cn, en in cn_to_en.items():
                if cn in df.columns and en not in df.columns:
                    col_map[cn] = en
            if col_map:
                df = df.rename(columns=col_map)

            # 截取最近 N 天
            if "date" in df.columns:
                df = df.tail(days).reset_index(drop=True)

            # 应用 multiplier
            multiplier = UNIT_CONVERT.get(symbol, 1.0)
            for col in ["open", "high", "low", "close", "change"]:
                if col in df.columns:
                    df[col] = df[col] * multiplier

            return df

        result = self._execute_with_retry(_fetch)
        if result is not None:
            self._cache.set(cache_key, result, ttl=600)  # 历史数据长TTL
        return result

    def get_futures_by_tier(self, tier: str) -> Dict[str, Dict[str, Any]]:
        """
        按层级批量获取海外期货实时数据

        Args:
            tier: "core" / "extended" / "auxiliary"

        Returns:
            {symbol: data_dict, ...}
        """
        # V10: 优先使用配置覆盖的品种列表
        tier_symbols = {
            "core": self.core_symbols,
            "extended": self.extended_symbols,
            "auxiliary": AUXILIARY_SYMBOLS,
        }.get(tier, [])

        if not tier_symbols:
            logger.warning("未知层级: %s", tier)
            return {}

        return self.get_futures_batch(tier_symbols)

    # ═══════════════════════════════════════════════════════════════════════
    # V11.5: 中证指数PE数据 (在线优先, PostgreSQL降级)
    # ═══════════════════════════════════════════════════════════════════════

    def get_index_pe_csindex(
        self,
        symbol: str,
        start_date: str = "20200101",
        end_date: Optional[str] = None,
    ) -> Optional[pd.DataFrame]:
        """
        获取中证指数历史PE数据 (含K线和滚动市盈率)

        V11.5 新增: 从 akshare stock_zh_index_hist_csindex 获取指数数据,
        该接口返回包含"滚动市盈率"列的完整指数数据。

        Args:
            symbol: 指数代码 (如 "000300", "000905", "932083")
            start_date: 开始日期 (格式: "20200101")
            end_date: 结束日期 (None=今天)

        Returns:
            DataFrame with columns:
              trade_date, open, high, low, close, volume, amount,
              pe_ttm, change_pct, sample_count
            或 None (失败时)
        """
        if end_date is None:
            from datetime import date
            end_date = date.today().strftime("%Y%m%d")

        cache_key = f"index_pe_{symbol}_{start_date}_{end_date}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        def _fetch():
            return self._fetch_index_pe_csindex(symbol, start_date, end_date)

        result = self._execute_with_retry(_fetch)
        if result is not None:
            # PE数据较长TTL (1小时)
            self._cache.set(cache_key, result, ttl=3600)
        return result

    def _fetch_index_pe_csindex(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
    ) -> Optional[pd.DataFrame]:
        """从 akshare stock_zh_index_hist_csindex 获取指数PE数据"""
        if ak is None:
            return None

        try:
            func = getattr(ak, "stock_zh_index_hist_csindex", None)
            if func is None:
                logger.warning("ak.stock_zh_index_hist_csindex 不可用")
                return None

            df = func(symbol=symbol, start_date=start_date, end_date=end_date)
            if df is None or df.empty:
                return None

            # 标准化列名 (中证指数接口返回中文列名)
            col_map = {
                "日期": "trade_date",
                "开盘": "open",
                "最高": "high",
                "最低": "low",
                "收盘": "close",
                "涨跌": "change",
                "涨跌幅": "change_pct",
                "成交量": "volume",
                "成交金额": "amount",
                "样本数量": "sample_count",
                "滚动市盈率": "pe_ttm",
                "指数代码": "index_code",
                "指数中文全称": "index_name_full",
                "指数中文简称": "index_name",
                "指数英文全称": "index_name_en",
                "指数英文简称": "index_name_short",
            }

            # 只映射存在的列
            rename_map = {}
            for cn, en in col_map.items():
                if cn in df.columns and en not in df.columns:
                    rename_map[cn] = en
            if rename_map:
                df = df.rename(columns=rename_map)

            # 确保关键列存在
            if "trade_date" not in df.columns or "pe_ttm" not in df.columns:
                logger.warning(
                    "stock_zh_index_hist_csindex(%s): 缺少关键列, "
                    "可用列: %s", symbol, list(df.columns)
                )
                return None

            # 数值类型转换
            numeric_cols = ["open", "high", "low", "close", "volume", "amount",
                           "pe_ttm", "change_pct", "sample_count"]
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            # 日期格式统一
            if "trade_date" in df.columns:
                df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce")

            # 按日期降序排列 (最新在前)
            if "trade_date" in df.columns:
                df = df.sort_values("trade_date", ascending=False).reset_index(drop=True)

            # 注入 index_code 列 (如果不存在)
            if "index_code" not in df.columns:
                df.insert(0, "index_code", symbol)

            return df

        except Exception as e:
            logger.error("stock_zh_index_hist_csindex(%s) 失败: %s", symbol, e)
            return None

    # ═══════════════════════════════════════════════════════════════════════
    # 实时商品数据
    # ═══════════════════════════════════════════════════════════════════════

    def get_realtime_commodity(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        使用 ak.futures_foreign_commodity_realtime() 获取实时商品数据

        Args:
            symbol: 品种代码

        Returns:
            实时商品数据字典
        """
        info = FUTURES_SYMBOL_MAP.get(symbol)
        if info is None:
            logger.error("未知品种: %s", symbol)
            return None

        cache_key = f"commodity_rt_{symbol}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        def _fetch():
            try:
                df = ak.futures_foreign_commodity_realtime(symbol=info.ak_code)
            except AttributeError:
                # akshare 版本可能不支持此接口
                logger.warning("ak.futures_foreign_commodity_realtime 不可用, 回退到 get_futures_realtime")
                return self.get_futures_realtime(symbol)

            if df is None or df.empty:
                return None

            row = df.iloc[0]
            multiplier = UNIT_CONVERT.get(symbol, 1.0)
            # V11: akshare 1.18.x 返回英文列名优先, 中文列名 fallback
            return {
                "symbol": symbol,
                "name": info.name,
                "exchange": info.exchange,
                "price": float(row.get("price", row.get("最新价", 0))) * multiplier,
                "change": float(row.get("change", row.get("涨跌", 0))) * multiplier,
                "pct_change": float(row.get("pct_change", row.get("涨跌幅", 0))),
                "bid": float(row.get("bid", row.get("买价", 0))) * multiplier,
                "ask": float(row.get("ask", row.get("卖价", 0))) * multiplier,
                "volume": int(row.get("volume", row.get("成交量", 0))),
                "open_interest": int(row.get("open_interest", row.get("持仓量", 0))),
                "timestamp": time.time(),
            }

        result = self._execute_with_retry(_fetch)
        if result is not None:
            self._cache.set(cache_key, result, ttl=30)  # 实时短TTL
        return result

    # ═══════════════════════════════════════════════════════════════════════
    # 辅助数据
    # ═══════════════════════════════════════════════════════════════════════

    def get_auxiliary_data(self, data_type: str) -> Optional[pd.DataFrame]:
        """
        获取辅助数据

        Args:
            data_type: 数据类型, 支持:
              'cftc'        - CFTC持仓报告
              'lme_stock'   - LME库存数据
              'lme_holding' - LME持仓报告
              'bond_zh_us'  - 中美利差
              'bond_us_10y' - 美国10年期国债
              'qvix_50etf'  - 50ETF期权波动率指数
              'qvix_300etf' - 300ETF期权波动率指数
              'eia_crude'   - EIA原油库存
              'ism_pmi'     - ISM制造业PMI
              'global_index'- 全球主要指数

        Returns:
            DataFrame 或 None
        """
        if data_type not in AUXILIARY_DATA_TYPES:
            logger.error("未知辅助数据类型: %s (支持: %s)", data_type, list(AUXILIARY_DATA_TYPES.keys()))
            return None

        cache_key = f"aux_{data_type}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        fetcher = {
            "cftc": self._fetch_cftc,
            "lme_stock": self._fetch_lme_stock,
            "lme_holding": self._fetch_lme_holding,
            "bond_zh_us": self._fetch_bond_zh_us,
            "bond_us_10y": self._fetch_bond_us_10y,
            "qvix_50etf": self._fetch_qvix_50etf,
            "qvix_300etf": self._fetch_qvix_300etf,
            "eia_crude": self._fetch_eia_crude,
            "ism_pmi": self._fetch_ism_pmi,
            "global_index": self._fetch_global_index,
        }.get(data_type)

        if fetcher is None:
            return None

        result = self._execute_with_retry(fetcher)
        if result is not None:
            # 辅助数据较长TTL (30分钟)
            self._cache.set(cache_key, result, ttl=1800)
        return result

    # ─── 辅助数据各接口实现 ───────────────────────────────────────────────

    def _fetch_cftc(self) -> Optional[pd.DataFrame]:
        """CFTC 持仓报告"""
        try:
            for func_name in ["futures_foreign_cftc", "futures_cftc"]:
                func = getattr(ak, func_name, None)
                if func is not None:
                    return func()
            logger.warning("CFTC 接口不可用")
            return None
        except Exception as e:
            logger.error("CFTC 数据获取失败: %s", e)
            return None

    def _fetch_lme_stock(self) -> Optional[pd.DataFrame]:
        """LME 库存数据"""
        try:
            func = getattr(ak, "futures_lme_stock", None)
            if func is not None:
                return func()
            logger.warning("LME 库存接口不可用")
            return None
        except Exception as e:
            logger.error("LME 库存数据获取失败: %s", e)
            return None

    def _fetch_lme_holding(self) -> Optional[pd.DataFrame]:
        """LME 持仓报告"""
        try:
            func = getattr(ak, "futures_lme_holding", None)
            if func is not None:
                return func()
            logger.warning("LME 持仓接口不可用")
            return None
        except Exception as e:
            logger.error("LME 持仓数据获取失败: %s", e)
            return None

    def _fetch_bond_zh_us(self) -> Optional[pd.DataFrame]:
        """中美利差"""
        try:
            func = getattr(ak, "bond_zh_us_rate", None)
            if func is not None:
                return func()
            func = getattr(ak, "bond_china_yield_start", None)
            if func is not None:
                return func()
            logger.warning("中美利差接口不可用")
            return None
        except Exception as e:
            logger.error("中美利差数据获取失败: %s", e)
            return None

    def _fetch_bond_us_10y(self) -> Optional[pd.DataFrame]:
        """美国10年期国债收益率"""
        try:
            func = getattr(ak, "bond_us_10y", None)
            if func is not None:
                return func()
            func = getattr(ak, "macro_bond_us_10y", None)
            if func is not None:
                return func()
            logger.warning("美债10Y接口不可用")
            return None
        except Exception as e:
            logger.error("美债10Y数据获取失败: %s", e)
            return None

    def _fetch_qvix_50etf(self) -> Optional[pd.DataFrame]:
        """50ETF 期权波动率指数 (QVIX)"""
        try:
            func = getattr(ak, "option_sina_sse_sina_vix", None)
            if func is not None:
                return func(symbol="50ETF")
            func = getattr(ak, "option_qvix_50etf", None)
            if func is not None:
                return func()
            logger.warning("QVIX 50ETF接口不可用")
            return None
        except Exception as e:
            logger.error("QVIX 50ETF数据获取失败: %s", e)
            return None

    def _fetch_qvix_300etf(self) -> Optional[pd.DataFrame]:
        """300ETF 期权波动率指数 (QVIX)"""
        try:
            func = getattr(ak, "option_sina_sse_sina_vix", None)
            if func is not None:
                return func(symbol="300ETF")
            func = getattr(ak, "option_qvix_300etf", None)
            if func is not None:
                return func()
            logger.warning("QVIX 300ETF接口不可用")
            return None
        except Exception as e:
            logger.error("QVIX 300ETF数据获取失败: %s", e)
            return None

    def _fetch_eia_crude(self) -> Optional[pd.DataFrame]:
        """EIA 原油库存"""
        try:
            func = getattr(ak, "macro_usa_eia_crude", None)
            if func is not None:
                return func()
            func = getattr(ak, "energy_eia_crude", None)
            if func is not None:
                return func()
            logger.warning("EIA原油库存接口不可用")
            return None
        except Exception as e:
            logger.error("EIA原油库存数据获取失败: %s", e)
            return None

    def _fetch_ism_pmi(self) -> Optional[pd.DataFrame]:
        """ISM 制造业 PMI"""
        try:
            func = getattr(ak, "macro_usa_ism_pmi", None)
            if func is not None:
                return func()
            func = getattr(ak, "macro_usa_ism", None)
            if func is not None:
                return func()
            logger.warning("ISM PMI接口不可用")
            return None
        except Exception as e:
            logger.error("ISM PMI数据获取失败: %s", e)
            return None

    def _fetch_global_index(self) -> Optional[pd.DataFrame]:
        """全球主要指数"""
        try:
            func = getattr(ak, "index_global_index", None)
            if func is not None:
                return func()
            func = getattr(ak, "stock_index_global", None)
            if func is not None:
                return func()
            logger.warning("全球指数接口不可用")
            return None
        except Exception as e:
            logger.error("全球指数数据获取失败: %s", e)
            return None

    # ═══════════════════════════════════════════════════════════════════════
    # 工具方法
    # ═══════════════════════════════════════════════════════════════════════

    def get_symbol_info(self, symbol: str) -> Optional[FuturesSymbol]:
        """获取品种元数据"""
        return FUTURES_SYMBOL_MAP.get(symbol)

    def get_symbols_by_sector(self, sector: str) -> List[str]:
        """按关联A股板块查找品种"""
        result = []
        for sym, info in FUTURES_SYMBOL_MAP.items():
            if sector in info.a_share_sectors:
                result.append(sym)
        return result

    def get_all_symbol_info(self) -> Dict[str, Dict[str, Any]]:
        """获取所有品种的元数据摘要"""
        return {
            sym: {
                "name": info.name,
                "exchange": info.exchange,
                "tier": info.tier,
                "priority": info.priority,
                "ak_code": info.ak_code,
                "multiplier": info.multiplier,
                "a_share_sectors": info.a_share_sectors,
                "signal_type": info.signal_type,
            }
            for sym, info in FUTURES_SYMBOL_MAP.items()
        }

    def health_check(self) -> Dict[str, Any]:
        """AKShare 健康检查"""
        if ak is None:
            return {"akshare": False, "reason": "akshare 未安装"}

        try:
            self._rate_limit()
            version = ak.__version__
            return {
                "akshare": True,
                "version": version,
                "symbols_loaded": len(FUTURES_SYMBOL_MAP),
            }
        except Exception as e:
            return {"akshare": False, "reason": str(e)}

    def clear_cache(self):
        """清空内存缓存"""
        self._cache.clear()
        logger.info("AKAdapter 缓存已清空")
