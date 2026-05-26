"""
AiStock V10 TDXAdapter — 通达信双端口数据适配器 (配置驱动)

V10 关键变更:
  - 构造函数接受 ConfigService, 从 tdx.yaml 读取 hosts/ports/market_codes
  - 保留向后兼容: 无 ConfigService 时仍使用内置默认值
  - 保留全部 V9 功能 (双端口, 重试, 连接池, etc.)
  - MarketType / BarCategory 保留为代码级概念 (非配置)

双端口架构:
  标准端口 (7709): 股票/指数K线、实时行情
  扩展端口 (7721): 期货K线、期权K线、宏观指标、合约列表

路由规则:
  stock_sh/sz/xg, index_sh/sz/zz → 标准端口
  future_zz/dl/sh/gz/zj, option_zj/sh/sz, option_czce/dce/shfe/gz,
  index_intl/csi/cni, gold_sh, macro → 扩展端口
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

# ─── ConfigService (V10) ─────────────────────────────────────────────────────
try:
    from base_service.config_service import ConfigService
except ImportError:
    ConfigService = None  # type: ignore[assignment,misc]

# ─── pytdx imports ───────────────────────────────────────────────────────────
try:
    from pytdx.hq import TdxHq_API
    from pytdx.exhq import TdxExHq_API
except ImportError:
    TdxHq_API = None  # type: ignore[assignment,misc]
    TdxExHq_API = None  # type: ignore[assignment,misc]

# ─── Connection pool from base_service ─────────────────────────────────────
try:
    from base_service.connection_pool import TDXConnectionPool
except ImportError:
    TDXConnectionPool = None  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# 默认常量 (无 ConfigService 时的回退值)
# ═══════════════════════════════════════════════════════════════════════════════

# 标准/扩展服务器地址
STANDARD_HOST = "180.153.18.170"
STANDARD_PORT = 7709

EXTENSION_HOST = "180.153.18.176"
EXTENSION_PORT = 7721


class BarCategory(IntEnum):
    """K线周期类别"""
    MIN_5 = 0
    MIN_15 = 4
    MIN_30 = 5
    MIN_60 = 6
    DAILY = 7
    WEEKLY = 8
    MONTHLY = 9
    QUARTERLY = 10
    YEARLY = 11


class MarketType:
    """市场类型标识 (用于路由到正确端口)"""
    # ─── 标准端口市场 ─────────────────────────────────────────────────────
    STOCK_SZ = "stock_sz"       # 深圳股票
    STOCK_SH = "stock_sh"       # 上海股票
    STOCK_XG = "stock_xg"      # 科创板
    INDEX_SZ = "index_sz"       # 深圳指数
    INDEX_SH = "index_sh"       # 上海指数
    INDEX_ZZ = "index_zz"       # 中证指数

    # ─── 扩展端口市场 ─────────────────────────────────────────────────────
    FUTURE_ZZ = "future_zz"     # 郑州期货
    FUTURE_DL = "future_dl"     # 大连期货
    FUTURE_SH = "future_sh"     # 上海期货
    FUTURE_GZ = "future_gz"     # 广州期货
    FUTURE_ZJ = "future_zj"     # 中金期货
    OPTION_ZJ = "option_zj"     # 中金期权
    OPTION_SH = "option_sh"     # 上海期权
    OPTION_SZ = "option_sz"     # 深圳期权
    COPTION_SH = "coption_sh"   # 上海商品期权
    COPTION_DL = "coption_dl"   # 大连商品期权
    COPTION_ZZ = "coption_zz"   # 郑州商品期权
    COPTION_GZ = "coption_gz"   # 广州商品期权

    # ─── 扩展端口市场 — 郑商所/大商所/上期所/广期所期权专用市场码 ────
    OPTION_CZCE = "option_czce"  # 郑州商品期权 (郑商所期权专用市场码)
    OPTION_DCE = "option_dce"    # 大连商品期权 (大商所期权专用市场码)
    OPTION_SHFE = "option_shfe"  # 上海商品期权 (上期所期权专用市场码)
    OPTION_GZ = "option_gz"      # 广州期权 (广期所期权专用市场码)

    # ─── 扩展端口市场 — 指数/黄金 ───────────────────────────────────────
    INDEX_INTL = "index_intl"    # 国际指数
    GOLD_SH = "gold_sh"          # 上海黄金
    INDEX_CSI = "index_csi"      # 中证指数
    INDEX_CNI = "index_cni"      # 国证指数

    MACRO = "macro"             # 宏观指标

    @classmethod
    def is_standard_port(cls, market_type: str) -> bool:
        """判断是否路由到标准端口"""
        return market_type in {
            cls.STOCK_SZ, cls.STOCK_SH, cls.STOCK_XG,
            cls.INDEX_SZ, cls.INDEX_SH, cls.INDEX_ZZ,
        }

    @classmethod
    def is_extension_port(cls, market_type: str) -> bool:
        """判断是否路由到扩展端口"""
        return not cls.is_standard_port(market_type)


# ─── 默认市场编号映射 (无 ConfigService 时的回退值) ──────────────────────────
DEFAULT_MARKET_MAP: Dict[str, int] = {
    # 标准端口市场
    MarketType.STOCK_SZ: 0,     # 深圳
    MarketType.STOCK_SH: 1,     # 上海
    MarketType.STOCK_XG: 1,     # 科创板 (上海市场, 688xxx)
    MarketType.INDEX_SZ: 0,     # 深圳指数
    MarketType.INDEX_SH: 1,     # 上海指数
    MarketType.INDEX_ZZ: 1,     # 中证指数 (上海市场发布)
    # 扩展端口市场 — 期货
    MarketType.FUTURE_ZZ: 29,   # 郑州商品
    MarketType.FUTURE_DL: 28,   # 大连商品
    MarketType.FUTURE_SH: 30,   # 上海期货
    MarketType.FUTURE_GZ: 67,   # 广州期货
    MarketType.FUTURE_ZJ: 47,   # 中金期货
    # 扩展端口市场 — 期权
    MarketType.OPTION_ZJ: 48,   # 中金期权
    MarketType.OPTION_SH: 27,   # 上海期权
    MarketType.OPTION_SZ: 8,    # 深圳期权
    # 扩展端口市场 — 商品期权
    MarketType.COPTION_SH: 6,   # 上海商品期权
    MarketType.COPTION_DL: 5,   # 大连商品期权
    MarketType.COPTION_ZZ: 4,   # 郑州商品期权
    MarketType.COPTION_GZ: 67,  # 广州商品期权
    # 扩展端口市场 — 期权专用市场码
    MarketType.OPTION_CZCE: 4,   # 郑州商品期权 (郑商所期权专用市场码)
    MarketType.OPTION_DCE: 5,    # 大连商品期权 (大商所期权专用市场码)
    MarketType.OPTION_SHFE: 6,   # 上海商品期权 (上期所期权专用市场码)
    MarketType.OPTION_GZ: 67,    # 广州期权 (广期所期权专用市场码)
    # 扩展端口市场 — 指数/黄金
    MarketType.INDEX_INTL: 12,   # 国际指数
    MarketType.GOLD_SH: 46,      # 上海黄金
    MarketType.INDEX_CSI: 62,    # 中证指数
    MarketType.INDEX_CNI: 102,   # 国证指数
}

# ─── 全局市场编号映射 (运行时填充, 优先从 ConfigService 加载) ────────────────
MARKET_MAP: Dict[str, int] = dict(DEFAULT_MARKET_MAP)

# ─── 标准列名映射 ─────────────────────────────────────────────────────────────
STANDARD_COLUMNS: Dict[str, str] = {
    "open": "open",
    "close": "close",
    "high": "high",
    "low": "low",
    "vol": "volume",
    "amount": "amount",
    "year": "year",
    "month": "month",
    "day": "day",
    "hour": "hour",
    "minute": "minute",
}

# pytdx 返回列 → 标准列名
_PDX_COL_RENAME: Dict[str, str] = {
    "vol": "volume",
}


# ═══════════════════════════════════════════════════════════════════════════════
# 连接池 (fallback 实现)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class _SimplePool:
    """简单连接池 — 当 base_service.TDXConnectionPool 不可用时使用"""

    host: str
    port: int
    api_type: str = "standard"   # "standard" | "extension"
    max_conn: int = 3
    _conns: list = field(default_factory=list, repr=False)
    _created: int = field(default=0, repr=False)

    # ─── 获取连接 ─────────────────────────────────────────────────────────
    def acquire(self):
        if self._conns:
            return self._conns.pop()
        return self._create()

    # ─── 归还连接 ─────────────────────────────────────────────────────────
    def release(self, api):
        if api and self._created < self.max_conn:
            self._conns.append(api)
        elif api:
            try:
                api.disconnect()
            except Exception:
                pass

    # ─── 创建新连接 ───────────────────────────────────────────────────────
    def _create(self):
        if self.api_type == "standard":
            if TdxHq_API is None:
                raise ImportError("pytdx not installed: pip install pytdx")
            api = TdxHq_API()
            api.connect(self.host, self.port)
        else:
            if TdxExHq_API is None:
                raise ImportError("pytdx not installed: pip install pytdx")
            api = TdxExHq_API()
            api.connect(self.host, self.port)
        self._created += 1
        return api

    # ─── 健康检查 ─────────────────────────────────────────────────────────
    def health_check(self) -> bool:
        api = None
        try:
            api = self.acquire()
            if self.api_type == "standard":
                return api.get_security_count(0) > 0
            else:
                return api.get_instrument_count() > 0
        except Exception:
            return False
        finally:
            if api:
                self.release(api)

    # ─── 关闭所有连接 ─────────────────────────────────────────────────────
    def close_all(self):
        for api in self._conns:
            try:
                api.disconnect()
            except Exception:
                pass
        self._conns.clear()
        self._created = 0


# ═══════════════════════════════════════════════════════════════════════════════
# TDXAdapter
# ═══════════════════════════════════════════════════════════════════════════════

class TDXAdapter:
    """
    通达信双端口数据适配器 (V10 配置驱动)

    V10 变更:
      - 构造函数接受 config_service: ConfigService
      - 从 tdx.yaml 读取标准/扩展端口的 host/port/pool_size/retry
      - 从 tdx.yaml 读取 market_codes 替代硬编码 MARKET_MAP
      - 无 ConfigService 时完全向后兼容 V9 行为

    标准端口 (7709): 股票/指数 K线 + 实时行情
    扩展端口 (7721): 期货/期权 K线 + 宏观指标 + 合约列表
    """

    def __init__(
        self,
        config_service: Optional[Any] = None,
        *,
        # ─── 向后兼容: 直接传参 (无 ConfigService 时使用) ─────────────
        std_host: str = STANDARD_HOST,
        std_port: int = STANDARD_PORT,
        ext_host: str = EXTENSION_HOST,
        ext_port: int = EXTENSION_PORT,
        pool_size: int = 3,
        retry_count: int = 2,
        retry_delay: float = 1.0,
    ):
        # ─── 从 ConfigService 加载配置 ───────────────────────────────────
        if config_service is not None and ConfigService is not None:
            logger.info("TDXAdapter: 使用 ConfigService 加载配置")
            self._std_host = config_service.get(
                "tdx.standard.host", std_host,
            )
            self._std_port = int(config_service.get(
                "tdx.standard.port", std_port,
            ))
            self._ext_host = config_service.get(
                "tdx.extension.host", ext_host,
            )
            self._ext_port = int(config_service.get(
                "tdx.extension.port", ext_port,
            ))
            self._retry_count = int(config_service.get(
                "tdx.standard.retry_count", retry_count,
            ))
            self._retry_delay = float(config_service.get(
                "tdx.standard.retry_delay", retry_delay,
            ))
            _pool_size = int(config_service.get(
                "tdx.standard.pool_size", pool_size,
            ))

            # 从 ConfigService 加载 market_codes
            cfg_market_codes = config_service.get("tdx.market_codes", None)
            if cfg_market_codes and isinstance(cfg_market_codes, dict):
                # YAML 中的 market_codes 是 str→int 映射
                global MARKET_MAP
                MARKET_MAP.clear()
                for k, v in cfg_market_codes.items():
                    MARKET_MAP[k] = int(v)
                # 补充 V9 中有但 YAML 中没有的条目 (stock_xg, coption_* 等)
                for k, v in DEFAULT_MARKET_MAP.items():
                    if k not in MARKET_MAP:
                        MARKET_MAP[k] = v
                logger.info(
                    "TDXAdapter: 从 ConfigService 加载 market_codes (%d 条)",
                    len(MARKET_MAP),
                )
        else:
            # ─── 回退: 使用直接传参或默认值 ─────────────────────────────
            self._std_host = std_host
            self._std_port = std_port
            self._ext_host = ext_host
            self._ext_port = ext_port
            self._retry_count = retry_count
            self._retry_delay = retry_delay
            _pool_size = pool_size

        # 初始化连接池 — 始终使用内置 _SimplePool
        # (TDXConnectionPool 使用 context-manager 接口, 与 acquire/release 不兼容)
        self._std_pool = _SimplePool(
            host=self._std_host, port=self._std_port,
            api_type="standard", max_conn=_pool_size,
        )
        self._ext_pool = _SimplePool(
            host=self._ext_host, port=self._ext_port,
            api_type="extension", max_conn=_pool_size,
        )

        logger.info(
            "TDXAdapter 初始化完成 — 标准端口 %s:%d, 扩展端口 %s:%d",
            self._std_host, self._std_port, self._ext_host, self._ext_port,
        )

    # ─── 连接池访问 ───────────────────────────────────────────────────────

    def _get_pool(self, market_type: str):
        """根据市场类型路由到正确的连接池"""
        if MarketType.is_standard_port(market_type):
            return self._std_pool
        return self._ext_pool

    # ─── 重试装饰器 ───────────────────────────────────────────────────────

    def _with_retry(self, func, *args, **kwargs):
        """带重试的函数执行"""
        last_err = None
        for attempt in range(self._retry_count):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_err = e
                logger.warning(
                    "TDXAdapter 重试 (%d/%d): %s", attempt + 1, self._retry_count, e,
                )
                if attempt < self._retry_count - 1:
                    time.sleep(self._retry_delay)
        raise last_err  # type: ignore[misc]

    # ═══════════════════════════════════════════════════════════════════════
    # 通用 K线获取
    # ═══════════════════════════════════════════════════════════════════════

    @staticmethod
    def _normalize_bars(df) -> pd.DataFrame:
        """标准化K线数据列名 — 兼容 pytdx 返回 list 或 DataFrame"""
        # pytdx 某些版本/方法返回 list 而非 DataFrame, 先统一转换
        if isinstance(df, list):
            if not df:
                return pd.DataFrame()
            df = pd.DataFrame(df)
        if df is None or (isinstance(df, pd.DataFrame) and df.empty):
            return pd.DataFrame()
        df = df.rename(columns=_PDX_COL_RENAME)
        # 构造日期列
        if "year" in df.columns:
            df["date"] = (
                df["year"].astype(str) + "-" +
                df["month"].astype(str).str.zfill(2) + "-" +
                df["day"].astype(str).str.zfill(2)
            )
        return df

    def get_bars(
        self,
        market_type: str,
        code: str,
        category: int = BarCategory.DAILY,
        start: int = 0,
        count: int = 800,
    ) -> pd.DataFrame:
        """
        通用K线获取 — 自动路由到正确端口

        Args:
            market_type: MarketType 中的市场类型
            code: 证券代码 (如 '600000', 'IF2401')
            category: K线周期 (BarCategory)
            start: 起始位置 (0 = 最新)
            count: 数据条数

        Returns:
            标准化后的 DataFrame
        """
        market = MARKET_MAP.get(market_type)
        if market is None:
            logger.error("未知市场类型: %s", market_type)
            return pd.DataFrame()

        pool = self._get_pool(market_type)

        def _fetch():
            api = pool.acquire()
            try:
                if MarketType.is_standard_port(market_type):
                    # 标准端口: 股票/指数
                    if market_type.startswith("index"):
                        df = api.get_index_bars(category, market, code, start, count)
                    else:
                        df = api.get_security_bars(category, market, code, start, count)
                else:
                    # 扩展端口: 期货/期权
                    df = api.get_instrument_bars(category, market, code, start, count)
                return self._normalize_bars(df) if df is not None and df != [] else pd.DataFrame()
            except Exception as e:
                # 自动重连
                logger.warning("get_bars 连接异常,尝试重连: %s", e)
                try:
                    api.disconnect()
                    if MarketType.is_standard_port(market_type):
                        api.connect(self._std_host, self._std_port)
                    else:
                        api.connect(self._ext_host, self._ext_port)
                except Exception:
                    pass
                raise
            finally:
                pool.release(api)

        return self._with_retry(_fetch)

    # ═══════════════════════════════════════════════════════════════════════
    # 股票 K线
    # ═══════════════════════════════════════════════════════════════════════

    def get_stock_daily(
        self,
        code: str,
        market_type: str = MarketType.STOCK_SH,
        start: int = 0,
        count: int = 800,
    ) -> pd.DataFrame:
        """获取股票日线数据 (标准端口)"""
        return self.get_bars(market_type, code, BarCategory.DAILY, start, count)

    def get_stock_minute(
        self,
        code: str,
        category: int = BarCategory.MIN_5,
        market_type: str = MarketType.STOCK_SH,
        start: int = 0,
        count: int = 800,
    ) -> pd.DataFrame:
        """获取股票分钟K线 (标准端口)"""
        return self.get_bars(market_type, code, category, start, count)

    # ═══════════════════════════════════════════════════════════════════════
    # 指数 K线
    # ═══════════════════════════════════════════════════════════════════════

    def get_index_daily(
        self,
        code: str,
        market_type: str = MarketType.INDEX_SH,
        start: int = 0,
        count: int = 800,
    ) -> pd.DataFrame:
        """获取指数日线数据 (标准端口)"""
        return self.get_bars(market_type, code, BarCategory.DAILY, start, count)

    def get_index_minute(
        self,
        code: str,
        category: int = BarCategory.MIN_5,
        market_type: str = MarketType.INDEX_SH,
        start: int = 0,
        count: int = 800,
    ) -> pd.DataFrame:
        """获取指数分钟K线 (标准端口)"""
        return self.get_bars(market_type, code, category, start, count)

    # ═══════════════════════════════════════════════════════════════════════
    # 期货 K线
    # ═══════════════════════════════════════════════════════════════════════

    def get_future_daily(
        self,
        code: str,
        market_type: str = MarketType.FUTURE_ZJ,
        start: int = 0,
        count: int = 800,
    ) -> pd.DataFrame:
        """获取期货日线数据 (扩展端口)"""
        return self.get_bars(market_type, code, BarCategory.DAILY, start, count)

    def get_future_minute(
        self,
        code: str,
        category: int = BarCategory.MIN_5,
        market_type: str = MarketType.FUTURE_ZJ,
        start: int = 0,
        count: int = 800,
    ) -> pd.DataFrame:
        """获取期货分钟K线 (扩展端口)"""
        return self.get_bars(market_type, code, category, start, count)

    # ═══════════════════════════════════════════════════════════════════════
    # 期权 K线
    # ═══════════════════════════════════════════════════════════════════════

    def get_option_daily(
        self,
        code: str,
        market_type: str = MarketType.OPTION_ZJ,
        start: int = 0,
        count: int = 800,
    ) -> pd.DataFrame:
        """获取期权日线数据 (扩展端口)"""
        return self.get_bars(market_type, code, BarCategory.DAILY, start, count)

    # ═══════════════════════════════════════════════════════════════════════
    # 实时行情
    # ═══════════════════════════════════════════════════════════════════════

    def get_realtime_quotes(
        self,
        code: str,
        market_type: str = MarketType.STOCK_SH,
    ) -> Dict[str, Any]:
        """
        获取单个证券实时行情 (标准端口)

        Returns:
            包含 price/open/high/low/volume/amount 等字段的字典
        """
        market = MARKET_MAP.get(market_type, 1)
        pool = self._std_pool

        def _fetch():
            api = pool.acquire()
            try:
                quotes = api.get_security_quotes([(market, code)])
                if quotes:
                    q = quotes[0]
                    return {
                        "code": q.get("code", code),
                        "name": q.get("name", ""),
                        "price": q.get("price", 0.0),
                        "open": q.get("open", 0.0),
                        "high": q.get("high", 0.0),
                        "low": q.get("low", 0.0),
                        "pre_close": q.get("last_close", 0.0),
                        "volume": q.get("vol", 0),
                        "amount": q.get("amount", 0.0),
                        "bid1": q.get("bid1", 0.0),
                        "ask1": q.get("ask1", 0.0),
                        "bid1_vol": q.get("bid1_vol", 0),
                        "ask1_vol": q.get("ask1_vol", 0),
                        "timestamp": time.time(),
                    }
                return {}
            finally:
                pool.release(api)

        return self._with_retry(_fetch)

    def batch_realtime_quotes(
        self,
        code_market_pairs: List[Tuple[str, str]],
    ) -> List[Dict[str, Any]]:
        """
        批量获取实时行情 (标准端口)

        Args:
            code_market_pairs: [(code, market_type), ...] 列表
                               最多80个 (pytdx单次限制)

        Returns:
            行情字典列表
        """
        if not code_market_pairs:
            return []

        # 转换为 (market_num, code) 元组
        pytdx_pairs = []
        for code, mt in code_market_pairs:
            m = MARKET_MAP.get(mt, 1)
            pytdx_pairs.append((m, code))

        pool = self._std_pool

        def _fetch():
            api = pool.acquire()
            try:
                # pytdx 单次最多80条
                all_quotes: List[Dict[str, Any]] = []
                for i in range(0, len(pytdx_pairs), 80):
                    batch = pytdx_pairs[i : i + 80]
                    quotes = api.get_security_quotes(batch)
                    if quotes:
                        for q in quotes:
                            all_quotes.append({
                                "code": q.get("code", ""),
                                "name": q.get("name", ""),
                                "price": q.get("price", 0.0),
                                "open": q.get("open", 0.0),
                                "high": q.get("high", 0.0),
                                "low": q.get("low", 0.0),
                                "pre_close": q.get("last_close", 0.0),
                                "volume": q.get("vol", 0),
                                "amount": q.get("amount", 0.0),
                            })
                return all_quotes
            finally:
                pool.release(api)

        return self._with_retry(_fetch)

    # ═══════════════════════════════════════════════════════════════════════
    # 期权批量行情 (扩展端口)
    # ═══════════════════════════════════════════════════════════════════════

    def get_option_quotes(
        self,
        codes: List[str],
        market_code: int = 48,
    ) -> List[Dict[str, Any]]:
        """
        批量获取期权实时行情 (扩展端口)

        Args:
            codes: 期权合约代码列表 (如 ['10003720', ...])
            market_code: 市场编号 (默认48=中金期权)

        Returns:
            行情字典列表
        """
        pool = self._ext_pool

        def _fetch():
            api = pool.acquire()
            try:
                results: List[Dict[str, Any]] = []
                for code in codes:
                    try:
                        df = api.get_instrument_bars(
                            BarCategory.DAILY, market_code, code, 0, 1,
                        )
                        # pytdx 某些版本返回 list
                        if isinstance(df, list):
                            if not df:
                                continue
                            df = pd.DataFrame(df)
                        if df is not None and not df.empty:
                            row = df.iloc[-1]
                            results.append({
                                "code": code,
                                "close": float(row.get("close", 0)),
                                "open": float(row.get("open", 0)),
                                "high": float(row.get("high", 0)),
                                "low": float(row.get("low", 0)),
                                "volume": int(row.get("vol", 0)),
                                "amount": float(row.get("amount", 0)),
                            })
                    except Exception as e:
                        logger.debug("get_option_quotes 跳过 %s: %s", code, e)
                        continue
                return results
            finally:
                pool.release(api)

        return self._with_retry(_fetch)

    # ═══════════════════════════════════════════════════════════════════════
    # 合约列表 / 合约信息
    # ═══════════════════════════════════════════════════════════════════════

    def get_instrument_list(
        self,
        market_type: str = MarketType.FUTURE_ZJ,
        start: int = 0,
        count: int = 2000,
    ) -> pd.DataFrame:
        """
        获取合约列表 (扩展端口)

        Returns:
            DataFrame with columns: market, code, name, ...
        """
        market = MARKET_MAP.get(market_type)
        if market is None:
            logger.error("未知市场类型: %s", market_type)
            return pd.DataFrame()

        pool = self._ext_pool

        def _fetch():
            api = pool.acquire()
            try:
                # pytdx 扩展端口: 获取所有合约后筛选
                df = api.get_instrument_info(start=start, count=count)
                # pytdx 某些版本返回 list
                if isinstance(df, list):
                    if not df:
                        return pd.DataFrame()
                    df = pd.DataFrame(df)
                if df is not None and not df.empty and market is not None:
                    # 按市场编号筛选
                    if "market" in df.columns:
                        df = df[df["market"] == market]
                return df if df is not None else pd.DataFrame()
            finally:
                pool.release(api)

        return self._with_retry(_fetch)

    def get_instrument_info(self, market: int) -> pd.DataFrame:
        """
        获取指定市场的合约信息 — 用于动态合约发现

        使用扩展端口 api.get_instrument_info() 获取全量合约列表,
        然后按 market 编号筛选.

        Args:
            market: 市场编号 (如 48=中金期权, 47=中金期货, 29=郑州, ...)

        Returns:
            筛选后的 DataFrame
        """
        pool = self._ext_pool

        def _fetch():
            api = pool.acquire()
            try:
                total = api.get_instrument_count()
                all_dfs = []
                batch_size = 2000
                for start in range(0, total + batch_size, batch_size):
                    df = api.get_instrument_info(start=start, count=batch_size)
                    # pytdx 某些版本返回 list, 需先转换
                    if isinstance(df, list):
                        if not df:
                            continue
                        df = pd.DataFrame(df)
                    if df is not None and not df.empty:
                        all_dfs.append(df)
                if all_dfs:
                    combined = pd.concat(all_dfs, ignore_index=True)
                    if "market" in combined.columns:
                        combined = combined[combined["market"] == market]
                    return combined
                return pd.DataFrame()
            finally:
                pool.release(api)

        return self._with_retry(_fetch)

    # ═══════════════════════════════════════════════════════════════════════
    # 宏观指标 (扩展端口)
    # ═══════════════════════════════════════════════════════════════════════

    def get_macro_data(
        self,
        code: str,
        market: int = 50,
        start: int = 0,
        count: int = 800,
    ) -> pd.DataFrame:
        """
        获取宏观经济指标数据 (扩展端口)

        Args:
            code: 指标代码
            market: 宏观市场编号 (通常50)
            start: 起始位置
            count: 数据条数
        """
        pool = self._ext_pool

        def _fetch():
            api = pool.acquire()
            try:
                df = api.get_instrument_bars(
                    BarCategory.DAILY, market, code, start, count,
                )
                return self._normalize_bars(df) if df is not None and df != [] else pd.DataFrame()
            finally:
                pool.release(api)

        return self._with_retry(_fetch)

    # ═══════════════════════════════════════════════════════════════════════
    # 健康检查 / 连接管理
    # ═══════════════════════════════════════════════════════════════════════

    def health_check(self) -> Dict[str, bool]:
        """双端口健康检查"""
        std_ok = False
        ext_ok = False
        try:
            std_ok = self._std_pool.health_check()
        except Exception as e:
            logger.error("标准端口健康检查失败: %s", e)
        try:
            ext_ok = self._ext_pool.health_check()
        except Exception as e:
            logger.error("扩展端口健康检查失败: %s", e)

        status = {"standard_port": std_ok, "extension_port": ext_ok}
        logger.info("TDXAdapter 健康检查: %s", status)
        return status

    def reconnect(self, port: str = "both") -> Dict[str, bool]:
        """
        重新建立连接

        Args:
            port: "standard" | "extension" | "both"
        """
        results: Dict[str, bool] = {}
        if port in ("standard", "both"):
            try:
                if isinstance(self._std_pool, _SimplePool):
                    self._std_pool.close_all()
                results["standard_port"] = self._std_pool.health_check()
            except Exception as e:
                logger.error("标准端口重连失败: %s", e)
                results["standard_port"] = False

        if port in ("extension", "both"):
            try:
                if isinstance(self._ext_pool, _SimplePool):
                    self._ext_pool.close_all()
                results["extension_port"] = self._ext_pool.health_check()
            except Exception as e:
                logger.error("扩展端口重连失败: %s", e)
                results["extension_port"] = False

        return results

    def close(self):
        """关闭所有连接"""
        try:
            if isinstance(self._std_pool, _SimplePool):
                self._std_pool.close_all()
            if isinstance(self._ext_pool, _SimplePool):
                self._ext_pool.close_all()
        except Exception as e:
            logger.error("关闭连接异常: %s", e)

    # ─── 上下文管理器 ─────────────────────────────────────────────────────

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
