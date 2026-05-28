"""
AiStock V11.5 DatabaseReader — PostgreSQL 多表数据库读取器

V11.5 关键变更 (PE-only, online-first 架构):
  - 移除所有 PB (市净率) 相关逻辑: pb, pb_percentile 不再计算或填充
  - 新增 online-first PE 数据获取: get_index_pe_online_first()
    优先从在线数据源 (ak_adapter) 获取 PE, PostgreSQL 作为回退
  - 衍生列仅保留 pe_percentile (从 pe_ttm 计算) 和 dividend_yield (可选)
  - get_index_pe() / get_index_pe_with_derived() 仅返回 PE 相关列
  - get_valuation_percentiles() 移除 pb_percentile / has_pb 字段

V11.4 变更 (保留):
  - 实际数据库列名为中文: "日期", "滚动市盈率", "开盘", "收盘" 等
  - pe_percentile 从历史 pe_ttm 序列实时计算 (排名百分位法)
  - 新增 get_index_kline() 方法: 从 csiIndexPE 提取 K线数据 (OHLCV)
  - 新增 get_index_pe_with_derived() 方法: 返回含衍生列的完整估值数据
  - 数据库同时包含 K线 + PE, 实现 "一库两用"

V11.3 变更 (保留):
  - 数据库模型: csiIndexPE/tdxIndex 为多表数据库, 每张表以指数代码为表名
  - table_mode="per_code" 为默认模式
  - SQL 查询: FROM "{code}" 替代 FROM index_valuation WHERE index_code = :code
  - 列名映射: 通过 database.yaml columns 配置

V11.2 变更 (保留):
  - 表发现: discover_tables(), table_exists()
  - 增强 health_check()

功能:
  - 指数 PE 估值数据查询 (含衍生列 pe_percentile) — 在线优先, PG 回退
  - 指数日K线数据查询 (OHLCV + 成交额)
  - 批量估值数据获取
  - 期权合约映射查询
  - 通用 SQL 查询接口
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# ─── ConfigService (V10) ─────────────────────────────────────────────────────
try:
    from base_service.config_service import ConfigService
except ImportError:
    ConfigService = None  # type: ignore[assignment,misc]

try:
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import Engine
    from sqlalchemy.pool import QueuePool
except ImportError:
    create_engine = None  # type: ignore[assignment]
    text = None  # type: ignore[assignment]
    Engine = None  # type: ignore[assignment,misc]
    QueuePool = None  # type: ignore[assignment,misc]

# ─── 全局配置 (V9 回退) ────────────────────────────────────────────────────
try:
    from global_settings import DATABASE_ENGINES
except ImportError:
    DATABASE_ENGINES = {
        "valuation": {
            "url": "postgresql+psycopg://aistock:aistock@localhost:5432/valuation",
            "pool_size": 5,
            "max_overflow": 10,
            "pool_timeout": 30,
            "pool_recycle": 3600,
        }
    }

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# 常量
# ═══════════════════════════════════════════════════════════════════════════════

# 表名安全验证正则: 仅允许字母/数字/下划线 (防止 SQL 注入)
_SAFE_TABLE_NAME_RE = re.compile(r'^[A-Za-z0-9_]+$')

# V11.5: csiIndexPE PE-relevant 物理列名 (中文)
# 映射: 逻辑列名 → 物理列名 (中文)
_CSI_INDEX_PE_COLUMNS = {
    "trade_date": "日期",
    "index_code": "指数代码",
    "index_name_cn": "指数中文简称",
    "open": "开盘",
    "high": "最高",
    "low": "最低",
    "close": "收盘",
    "change": "涨跌",
    "change_pct": "涨跌幅",
    "volume": "成交量",
    "amount": "成交金额",
    "sample_count": "样本数量",
    "pe_ttm": "滚动市盈率",
}

# V11.5: 衍生列默认配置 (PE-only, 从 database.yaml 覆盖)
_DEFAULT_DERIVED_CONFIG = {
    "pe_percentile": {
        "source": "pe_ttm",
        "window": 2500,
        "method": "rank",
    },
    "dividend_yield": {"source": "external", "required": False},
}

# V11.5 旧版默认列名 (英文字母, tdxIndex 等可能使用) — PE-only, 无 PB
_DEFAULT_PE_COLUMNS = {
    "trade_date": "trade_date",
    "pe_ttm": "pe_ttm",
    "pe_percentile": "pe_percentile",
    "dividend_yield": "dividend_yield",
}

# 默认期权合约列名映射
_DEFAULT_OPTION_COLUMNS = {
    "underlying_code": "underlying_code",
    "contract_code": "contract_code",
    "contract_name": "contract_name",
    "option_type": "option_type",
    "strike_price": "strike_price",
    "expire_date": "expire_date",
    "market": "market",
}

# V11.5: K线相关逻辑列名集合
_KLINE_LOGICAL_COLUMNS = {"open", "high", "low", "close", "volume", "amount",
                           "change", "change_pct", "sample_count"}


# ═══════════════════════════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════════════════════════

def _validate_table_name(name: str) -> str:
    """
    验证表名安全性并返回引号包裹的 PostgreSQL 标识符

    Args:
        name: 表名 (如 "000300", "000905", "510050")

    Returns:
        带引号的标识符 (如 '"000300"')

    Raises:
        ValueError: 表名包含非法字符
    """
    if not name:
        raise ValueError("表名不能为空")
    if not _SAFE_TABLE_NAME_RE.match(name):
        raise ValueError(
            f"表名 '{name}' 包含非法字符, 仅允许字母/数字/下划线 "
            f"(防止SQL注入)"
        )
    return f'"{name}"'


def _build_select_clause(columns: Dict[str, str],
                         select_keys: Optional[List[str]] = None,
                         add_index_code: bool = True) -> str:
    """
    构建 SELECT 列子句, 支持列名映射

    V11.5: 支持通过 select_keys 筛选特定列, 仅 SELECT 需要的字段

    Args:
        columns: {逻辑列名: 物理列名} 映射
        select_keys: 需要查询的逻辑列名列表, None=查询全部
        add_index_code: 是否注入 index_code 列 (仅 per_code 模式)

    Returns:
        SQL SELECT 子句字符串

    示例:
        columns={"trade_date": "日期", "pe_ttm": "滚动市盈率"}, add_index_code=False
        → '"日期", "滚动市盈率"'

        columns={"trade_date": "日期", "pe_ttm": "滚动市盈率"}, add_index_code=True
        → ':index_code AS index_code, "日期", "滚动市盈率"'
    """
    parts = []

    # 确定要查询的键
    keys = select_keys if select_keys else list(columns.keys())

    for logical in keys:
        physical = columns.get(logical, logical)
        if physical == logical:
            parts.append(f'"{physical}"')
        else:
            parts.append(f'"{physical}" AS {logical}')

    if add_index_code:
        # index_code 取自表名, 放在第一列
        parts.insert(0, ":index_code AS index_code")

    return ", ".join(parts)


def _build_order_by(date_column: str = "trade_date", direction: str = "DESC") -> str:
    """构建 ORDER BY 子句"""
    return f'ORDER BY "{date_column}" {direction}'


def _calc_percentile_rank(series: pd.Series, window: int = 2500) -> pd.Series:
    """
    计算滚动百分位排名

    对于序列中的每个值, 计算其在过去 window 个值中的百分位排名。

    Args:
        series: 数值序列 (按时间降序排列)
        window: 滚动窗口大小 (默认2500, 约10年交易日)

    Returns:
        百分位序列 (0-100), 与输入同长度
    """
    if len(series) == 0:
        return pd.Series(dtype=float)

    # 转为升序 (时间从远到近) 以便滚动计算
    asc_series = series.iloc[::-1].reset_index(drop=True)

    result = []
    for i in range(len(asc_series)):
        # 窗口: 从 max(0, i-window+1) 到 i (含)
        start = max(0, i - window + 1)
        window_data = asc_series.iloc[start:i + 1]
        current_val = asc_series.iloc[i]

        if len(window_data) < 2:
            result.append(50.0)  # 数据不足, 默认50%
        else:
            # 百分位排名: 当前值在窗口中的位置
            pct = (window_data < current_val).sum() / (len(window_data) - 1) * 100.0
            result.append(round(pct, 2))

    # 转回降序
    result_series = pd.Series(result[::-1])
    return result_series


def _calc_percentile_fast(series: pd.Series, window: int = 2500) -> pd.Series:
    """
    快速百分位计算 (向量化, 适用于大数据量)

    使用 scipy.stats.percentileofrank 的等价计算。
    对于每条记录, 计算当前 PE 在过去 window 条记录中的百分位。

    Args:
        series: 数值序列 (按时间降序排列)
        window: 滚动窗口大小

    Returns:
        百分位序列 (0-100), 与输入同长度
    """
    if len(series) == 0:
        return pd.Series(dtype=float)

    try:
        from scipy.stats import percentileofscore
    except ImportError:
        # 回退到纯 Python 版本
        return _calc_percentile_rank(series, window)

    # 转为升序 (时间从远到近)
    values = series.values
    asc_values = values[::-1]

    result = np.full(len(asc_values), 50.0)

    for i in range(1, len(asc_values)):
        start = max(0, i - window + 1)
        window_data = asc_values[start:i + 1]
        if len(window_data) >= 2:
            result[i] = percentileofscore(window_data, asc_values[i], kind='rank')

    # 转回降序
    return pd.Series(result[::-1])


# ═══════════════════════════════════════════════════════════════════════════════
# DatabaseReader
# ═══════════════════════════════════════════════════════════════════════════════

class DatabaseReader:
    """
    PostgreSQL 多表数据库读取器 (V11.5 PE-only, online-first 架构)

    V11.5 关键变更:
      - 移除所有 PB 相关逻辑 (pb, pb_percentile 不再计算或填充)
      - 新增 online-first PE 获取: get_index_pe_online_first()
      - 衍生列仅保留 pe_percentile 和 dividend_yield (可选)

    数据库模型:
      csiIndexPE 实际结构:
        - 每张表以指数代码为表名 (如 "000300")
        - 列名为中文: 日期, 开盘, 最高, 最低, 收盘, 成交量, 成交金额, 滚动市盈率 等
        - 不含 pb / pb_percentile 列 (V11.5 已移除相关逻辑)
        - pe_percentile 由 DatabaseReader 从历史 pe_ttm 序列计算
        - 同时包含K线数据, 可用于提取 OHLCV

      tdxIndex (未验证, 保留旧版映射):
        - 列名可能为英文, 使用 _DEFAULT_PE_COLUMNS

    查询模式:
      per_code (默认): 每个指数代码对应一张表, 表名 = 指数代码

    配置 (database.yaml V11.5):
      csi_index_pe:
        columns:
          trade_date: "日期"
          pe_ttm: "滚动市盈率"
          open: "开盘"
          close: "收盘"
          ...
        derived_columns:
          pe_percentile:
            source: "pe_ttm"
            window: 2500
            method: "rank"
    """

    # V11.5: 估值核心查询所需的逻辑列名 (PE-only)
    _PE_CORE_KEYS = ["trade_date", "pe_ttm"]
    # V11.5: K线查询所需的逻辑列名
    _KLINE_KEYS = ["trade_date", "open", "high", "low", "close",
                    "change", "change_pct", "volume", "amount", "sample_count"]
    # V11.5: 完整查询 (PE + K线)
    _FULL_KEYS = ["trade_date", "index_code", "index_name_cn",
                   "open", "high", "low", "close",
                   "change", "change_pct", "volume", "amount",
                   "sample_count", "pe_ttm"]

    def __init__(
        self,
        config_service: Optional[Any] = None,
        *,
        db_config: Optional[Dict[str, Any]] = None,
        engine_name: str = "csi_index_pe",
        fallback_on_error: bool = True,
    ):
        """
        Args:
            config_service: ConfigService 实例
            db_config: 数据库配置 (V9 兼容)
            engine_name: 数据库引擎名称 (对应 database.yaml 中的 key)
            fallback_on_error: 查询失败时返回空而非抛异常
        """
        self._engine_name = engine_name
        self._fallback = fallback_on_error
        self._engine: Optional[Any] = None
        self._connected = False
        self._discovered_tables: List[str] = []
        self._table_match_status: Dict[str, bool] = {}

        # ─── V11.5: 列名映射 + 衍生列配置 (PE-only) ──────────────────
        self._table_mode = "per_code"  # 默认: 每指数代码一张表
        self._pe_columns = dict(_CSI_INDEX_PE_COLUMNS)  # 默认使用中文列名
        self._option_columns = dict(_DEFAULT_OPTION_COLUMNS)
        self._derived_config = dict(_DEFAULT_DERIVED_CONFIG)

        # V11.5: 检测列名语言 (中文 or 英文)
        self._column_lang = "zh"  # 默认中文

        # ─── V10: 从 ConfigService 加载配置 ──────────────────────────
        if config_service is not None and ConfigService is not None:
            db_section = config_service.get(f"database.{engine_name}", None)
            if db_section and isinstance(db_section, dict):
                # V11.3: 读取 table_mode
                self._table_mode = db_section.get("table_mode", "per_code")

                # V11.5: 读取列名映射
                columns_cfg = db_section.get("columns", None)
                if columns_cfg and isinstance(columns_cfg, dict):
                    self._pe_columns.update(columns_cfg)

                    # 检测列名语言: 如果物理列名含中文, 标记为 zh
                    for physical in columns_cfg.values():
                        if isinstance(physical, str) and any(
                            '\u4e00' <= c <= '\u9fff' for c in physical
                        ):
                            self._column_lang = "zh"
                            break
                    else:
                        # 纯英文列名 (如 tdxIndex)
                        self._column_lang = "en"

                # V11.5: 读取衍生列配置
                derived_cfg = db_section.get("derived_columns", None)
                if derived_cfg and isinstance(derived_cfg, dict):
                    self._derived_config.update(derived_cfg)

                option_columns_cfg = db_section.get("option_columns", None)
                if option_columns_cfg and isinstance(option_columns_cfg, dict):
                    self._option_columns.update(option_columns_cfg)

                # 构建连接配置
                self._config = self._build_config_from_yaml(db_section)
            else:
                if db_config is not None:
                    self._config = db_config
                elif engine_name in DATABASE_ENGINES:
                    self._config = DATABASE_ENGINES[engine_name]
                else:
                    self._config = self._default_config()
        elif db_config is not None:
            self._config = db_config
        elif engine_name in DATABASE_ENGINES:
            self._config = DATABASE_ENGINES[engine_name]
        else:
            self._config = self._default_config()

        logger.info(
            "DatabaseReader V11.5 初始化: engine=%s, table_mode=%s, "
            "column_lang=%s, pe_columns=%s, derived=%s",
            engine_name, self._table_mode, self._column_lang,
            self._pe_columns, self._derived_config,
        )

        # 初始化引擎
        self._init_engine()

    @staticmethod
    def _build_config_from_yaml(yaml_section: Dict[str, Any]) -> Dict[str, Any]:
        """将 database.yaml 配置节转换为 SQLAlchemy 配置"""
        host = yaml_section.get("host", "localhost")
        port = yaml_section.get("port", 5432)
        database = yaml_section.get("database", "")
        user = yaml_section.get("user", "postgres")
        password = yaml_section.get("password", "")

        if password:
            url = f"postgresql+psycopg://{user}:{password}@{host}:{port}/{database}"
        else:
            url = f"postgresql+psycopg://{user}@{host}:{port}/{database}"

        return {
            "url": url,
            "pool_size": yaml_section.get("pool_size", 5),
            "max_overflow": yaml_section.get("max_overflow", 10),
            "pool_timeout": yaml_section.get("pool_timeout", 30),
            "pool_recycle": yaml_section.get("pool_recycle", 3600),
        }

    @staticmethod
    def _default_config() -> Dict[str, Any]:
        """默认数据库配置"""
        return {
            "url": "postgresql+psycopg://aistock:aistock@localhost:5432/valuation",
            "pool_size": 5,
            "max_overflow": 10,
        }

    # ─── 引擎初始化 ───────────────────────────────────────────────────────

    def _init_engine(self):
        """创建 SQLAlchemy 引擎"""
        if create_engine is None:
            logger.warning("DatabaseReader: SQLAlchemy 未安装, 数据库功能不可用")
            return

        db_url = self._config.get("url", "")
        if not db_url:
            logger.error("DatabaseReader: 数据库 URL 为空")
            return

        try:
            self._engine = create_engine(
                db_url,
                poolclass=QueuePool,
                pool_size=self._config.get("pool_size", 5),
                max_overflow=self._config.get("max_overflow", 10),
                pool_timeout=self._config.get("pool_timeout", 30),
                pool_recycle=self._config.get("pool_recycle", 3600),
                echo=False,
            )
            # 测试连接
            with self._engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            self._connected = True
            logger.info("DatabaseReader 连接成功: %s (pool_size=%d, table_mode=%s, lang=%s)",
                        self._mask_url(db_url),
                        self._config.get("pool_size", 5),
                        self._table_mode, self._column_lang)

            # V11.2: 连接成功后自动发现表
            self._auto_discover_tables()

        except Exception as e:
            self._connected = False
            logger.error("DatabaseReader 连接失败: %s", e)

    @staticmethod
    def _mask_url(url: str) -> str:
        """遮蔽密码"""
        import re as _re
        return _re.sub(r'://([^:]+):([^@]+)@', r'://\1:****@', url)

    # ═══════════════════════════════════════════════════════════════════════
    # V11.2: 表自动发现
    # ═══════════════════════════════════════════════════════════════════════

    def _auto_discover_tables(self):
        """连接成功后自动发现数据库中的表"""
        if not self._connected or self._engine is None:
            return

        try:
            self._discovered_tables = self.discover_tables()
            logger.info("DatabaseReader: 发现 %d 个表: %s",
                        len(self._discovered_tables),
                        self._discovered_tables[:20])
            if len(self._discovered_tables) > 20:
                logger.info("  ... 共 %d 个表", len(self._discovered_tables))

            self._table_match_status = {}
            logger.info("DatabaseReader: per_code 模式, %d 个表可用",
                        len(self._discovered_tables))

        except Exception as e:
            logger.warning("DatabaseReader: 表自动发现失败: %s", e)

    def discover_tables(self, schema: str = "public") -> List[str]:
        """发现数据库中指定 schema 的所有表名"""
        if not self._connected or self._engine is None:
            return []

        try:
            with self._engine.connect() as conn:
                result = conn.execute(text(
                    "SELECT tablename FROM pg_tables WHERE schemaname = :schema ORDER BY tablename"
                ), {"schema": schema})
                return [row[0] for row in result]
        except Exception as e:
            logger.error("discover_tables 失败: %s", e)
            return []

    def table_exists(self, table_name: str) -> bool:
        """检查指定表是否存在于数据库中"""
        if not self._discovered_tables:
            self._discovered_tables = self.discover_tables()
        return table_name in self._discovered_tables

    # ═══════════════════════════════════════════════════════════════════════
    # V11.5: SQL 构建 (适配中文列名 + 可选列)
    # ═══════════════════════════════════════════════════════════════════════

    def _build_per_code_sql(self, code: str, days: int,
                             select_keys: Optional[List[str]] = None) -> str:
        """
        构建 per_code 模式的单表查询 SQL

        V11.5: 支持 select_keys 筛选列, 适配中文物理列名

        Args:
            code: 指数代码 (如 "000300"), 同时也是表名
            days: 回溯天数
            select_keys: 需要查询的逻辑列名列表

        Returns:
            SQL 字符串
        """
        table = _validate_table_name(code)
        select_clause = _build_select_clause(
            self._pe_columns, select_keys=select_keys, add_index_code=True
        )
        # 日期列: 使用物理列名
        date_physical = self._pe_columns.get("trade_date", "trade_date")
        order_by = f'ORDER BY "{date_physical}" DESC'

        return f"SELECT {select_clause} FROM {table} {order_by} LIMIT :days"

    def _build_option_per_code_sql(self, underlying: str) -> str:
        """构建 per_code 模式的期权合约查询 SQL"""
        table = _validate_table_name(underlying)
        select_clause = _build_select_clause(self._option_columns, add_index_code=False)
        return f"SELECT {select_clause} FROM {table} WHERE 1=1"

    # ═══════════════════════════════════════════════════════════════════════
    # V11.5: 核心查询 — 指数 PE 估值 (PE-only, no PB)
    # ═══════════════════════════════════════════════════════════════════════

    def get_index_pe(
        self,
        code: str,
        days: int = 100,
    ) -> pd.DataFrame:
        """
        获取指数 PE 估值数据 (V11.5 PE-only, 含衍生列)

        per_code 模式: 查询表 "{code}", 自动注入 index_code 列
        V11.5: 自动计算 pe_percentile 衍生列, 不再返回 pb/pb_percentile

        Args:
            code: 指数代码 (如 '000300', '000905'), 也是表名
            days: 回溯天数

        Returns:
            DataFrame with columns:
              index_code, trade_date, pe_ttm, pe_percentile
        """
        if not self._connected:
            logger.warning("DatabaseReader 未连接, 返回空数据")
            return pd.DataFrame()

        try:
            if self._table_mode == "per_code":
                return self._get_index_pe_per_code(code, days)
            else:
                return self._get_index_pe_single_table(code, days)
        except Exception as e:
            logger.error("get_index_pe(%s) 失败: %s", code, e)
            if self._fallback:
                return pd.DataFrame()
            raise

    def _get_index_pe_per_code(self, code: str, days: int) -> pd.DataFrame:
        """per_code 模式: 从表 "{code}" 查询 PE 数据, 含衍生列计算"""
        # 查询 PE 核心列
        sql = self._build_per_code_sql(code, days, select_keys=self._PE_CORE_KEYS)
        with self._engine.connect() as conn:
            df = pd.read_sql(
                text(sql),
                conn,
                params={"index_code": code, "days": days},
            )

        if df.empty:
            return df

        # V11.5: 计算 pe_percentile 衍生列
        df = self._add_derived_columns(df, code)

        # 确保 index_code 列存在
        if "index_code" not in df.columns:
            df.insert(0, "index_code", code)

        return df

    def _get_index_pe_single_table(self, code: str, days: int) -> pd.DataFrame:
        """single_table 模式 (兼容旧版): 从 index_valuation 表查询"""
        sql = """
        SELECT
            trade_date, index_code, pe_ttm,
            pe_percentile, dividend_yield
        FROM index_valuation
        WHERE index_code = :code
        ORDER BY trade_date DESC
        LIMIT :days
        """
        with self._engine.connect() as conn:
            df = pd.read_sql(text(sql), conn, params={"code": code, "days": days})
        return df

    # ═══════════════════════════════════════════════════════════════════════
    # V11.5: Online-first PE 数据获取
    # ═══════════════════════════════════════════════════════════════════════

    def get_index_pe_online_first(
        self,
        code: str,
        days: int = 100,
        ak_adapter: Optional[Any] = None,
    ) -> pd.DataFrame:
        """
        Online-first PE 数据获取 (V11.5 新增)

        优先从在线数据源 (ak_adapter.get_index_pe_csindex) 获取 PE 数据,
        如果在线获取失败, 则回退到 PostgreSQL 查询。
        在线数据同样会通过 _add_derived_columns() 计算 pe_percentile。

        Args:
            code: 指数代码 (如 '000300', '000905')
            days: 回溯天数
            ak_adapter: 在线数据适配器, 需实现 get_index_pe_csindex(code) 方法,
                        返回 DataFrame 含 trade_date, pe_ttm 列

        Returns:
            DataFrame with columns:
              index_code, trade_date, pe_ttm, pe_percentile
        """
        # ── 尝试在线获取 ──
        if ak_adapter is not None:
            try:
                online_df = ak_adapter.get_index_pe_csindex(code)
                if online_df is not None and not online_df.empty:
                    # 确保列名标准化
                    if "trade_date" not in online_df.columns and "日期" in online_df.columns:
                        online_df = online_df.rename(columns={"日期": "trade_date"})
                    if "pe_ttm" not in online_df.columns and "滚动市盈率" in online_df.columns:
                        online_df = online_df.rename(columns={"滚动市盈率": "pe_ttm"})

                    # 确保 pe_ttm 为数值
                    if "pe_ttm" in online_df.columns:
                        online_df["pe_ttm"] = pd.to_numeric(online_df["pe_ttm"], errors="coerce")

                    # 按日期降序排列
                    if "trade_date" in online_df.columns:
                        online_df = online_df.sort_values("trade_date", ascending=False).reset_index(drop=True)

                    # 截取 days 条
                    if len(online_df) > days:
                        online_df = online_df.iloc[:days].reset_index(drop=True)

                    # 添加 index_code 列
                    if "index_code" not in online_df.columns:
                        online_df.insert(0, "index_code", code)

                    # 计算 pe_percentile 衍生列
                    if "pe_ttm" in online_df.columns and "pe_percentile" not in online_df.columns:
                        online_df = self._add_derived_columns(online_df, code)

                    # 仅保留核心输出列
                    output_cols = ["index_code", "trade_date", "pe_ttm", "pe_percentile"]
                    available_cols = [c for c in output_cols if c in online_df.columns]
                    online_df = online_df[available_cols]

                    logger.info(
                        "get_index_pe_online_first(%s): 在线获取成功, %d 条记录",
                        code, len(online_df),
                    )
                    return online_df

            except Exception as e:
                logger.warning(
                    "get_index_pe_online_first(%s): 在线获取失败, 回退到 PG: %s",
                    code, e,
                )
        else:
            logger.debug(
                "get_index_pe_online_first(%s): 无 ak_adapter, 直接使用 PG",
                code,
            )

        # ── 回退到 PostgreSQL ──
        return self.get_index_pe(code, days)

    # ═══════════════════════════════════════════════════════════════════════
    # V11.5: 衍生列计算 (PE-only)
    # ═══════════════════════════════════════════════════════════════════════

    def _add_derived_columns(self, df: pd.DataFrame, code: str) -> pd.DataFrame:
        """
        为 DataFrame 添加衍生列 (pe_percentile)

        V11.5: 仅计算 pe_percentile; dividend_yield 为可选外部列 (NaN if unavailable)
        不再添加 pb / pb_percentile 列。

        Args:
            df: 原始查询 DataFrame (必须含 pe_ttm 和 trade_date 列)
            code: 指数代码 (用于日志)

        Returns:
            添加了衍生列的 DataFrame
        """
        if df.empty or "pe_ttm" not in df.columns:
            # 无法计算, 填充 NaN
            df["pe_percentile"] = np.nan
            df["dividend_yield"] = np.nan
            return df

        # ── pe_percentile: 从 pe_ttm 历史序列计算 ──
        pe_config = self._derived_config.get("pe_percentile", {})
        if pe_config.get("source") == "pe_ttm":
            window = pe_config.get("window", 2500)
            method = pe_config.get("method", "rank")

            pe_series = pd.to_numeric(df["pe_ttm"], errors="coerce")
            if len(pe_series.dropna()) >= 2:
                if method == "rank":
                    df["pe_percentile"] = _calc_percentile_rank(pe_series, window)
                else:
                    df["pe_percentile"] = _calc_percentile_rank(pe_series, window)

                logger.debug(
                    "DatabaseReader: %s pe_percentile 计算: "
                    "最新=%.1f%%, 数据量=%d, 窗口=%d",
                    code, df["pe_percentile"].iloc[0], len(pe_series), window
                )
            else:
                df["pe_percentile"] = np.nan
                logger.debug("DatabaseReader: %s pe_ttm 数据不足, 无法计算百分位", code)
        else:
            # 数据库可能有 pe_percentile 列
            if "pe_percentile" not in df.columns:
                df["pe_percentile"] = np.nan

        # ── dividend_yield: 可选外部列, 数据库无此数据 ──
        div_config = self._derived_config.get("dividend_yield", {})
        if "dividend_yield" not in df.columns:
            df["dividend_yield"] = np.nan

        return df

    def _get_pe_history_for_percentile(self, code: str, window: int = 2500) -> pd.DataFrame:
        """
        获取足够多的历史 PE 数据用于百分位计算

        MacroValuationEngine 需要 pe_percentile, 但百分位计算需要大量历史数据。
        此方法获取 window 条历史数据, 仅提取 pe_ttm + trade_date。

        Args:
            code: 指数代码
            window: 所需历史数据条数 (默认2500, 约10年)

        Returns:
            DataFrame with trade_date, pe_ttm
        """
        sql = self._build_per_code_sql(code, days=window, select_keys=self._PE_CORE_KEYS)
        with self._engine.connect() as conn:
            df = pd.read_sql(
                text(sql),
                conn,
                params={"index_code": code, "days": window},
            )
        return df

    # ═══════════════════════════════════════════════════════════════════════
    # V11.5: K线数据查询 (一库两用)
    # ═══════════════════════════════════════════════════════════════════════

    def get_index_kline(
        self,
        code: str,
        days: int = 100,
    ) -> pd.DataFrame:
        """
        获取指数日K线数据 (OHLCV + 成交额 + PE)

        V11.5: csiIndexPE 同时包含K线数据, 实现一库两用。
        返回标准化的K线 DataFrame。

        Args:
            code: 指数代码 (如 '000300'), 也是表名
            days: 回溯天数

        Returns:
            DataFrame with columns:
              index_code, trade_date, open, high, low, close,
              change, change_pct, volume, amount, sample_count, pe_ttm
        """
        if not self._connected:
            logger.warning("DatabaseReader 未连接, 返回空数据")
            return pd.DataFrame()

        try:
            sql = self._build_per_code_sql(code, days, select_keys=self._KLINE_KEYS)
            with self._engine.connect() as conn:
                df = pd.read_sql(
                    text(sql),
                    conn,
                    params={"index_code": code, "days": days},
                )

            # 确保 index_code 列存在
            if "index_code" not in df.columns and not df.empty:
                df.insert(0, "index_code", code)

            return df

        except Exception as e:
            logger.error("get_index_kline(%s) 失败: %s", code, e)
            if self._fallback:
                return pd.DataFrame()
            raise

    # ═══════════════════════════════════════════════════════════════════════
    # V11.5: 完整估值数据 (PE + K线 + 衍生列, no PB)
    # ═══════════════════════════════════════════════════════════════════════

    def get_index_pe_with_derived(
        self,
        code: str,
        days: int = 100,
        percentile_window: int = 2500,
    ) -> pd.DataFrame:
        """
        获取完整估值数据 (PE + K线 + 衍生列)

        V11.5: 一次性获取 PE百分位 + K线 + 估值数据。
        先获取 percentile_window 条数据计算百分位, 再截取 days 条返回。
        不再返回 pb / pb_percentile 列。

        Args:
            code: 指数代码
            days: 最终返回的数据条数
            percentile_window: 百分位计算所需历史数据条数

        Returns:
            DataFrame with columns:
              index_code, trade_date, open, high, low, close,
              change, change_pct, volume, amount, sample_count,
              pe_ttm, pe_percentile, dividend_yield(NaN)
        """
        if not self._connected:
            return pd.DataFrame()

        try:
            # 获取足够历史数据用于百分位计算
            actual_days = max(days, percentile_window)
            sql = self._build_per_code_sql(code, actual_days, select_keys=self._FULL_KEYS)

            with self._engine.connect() as conn:
                df = pd.read_sql(
                    text(sql),
                    conn,
                    params={"index_code": code, "days": actual_days},
                )

            if df.empty:
                return df

            # 添加衍生列 (使用完整历史数据计算百分位)
            df = self._add_derived_columns(df, code)

            # 确保 index_code 列存在
            if "index_code" not in df.columns:
                df.insert(0, "index_code", code)

            # 截取 days 条返回
            if len(df) > days:
                df = df.iloc[:days].reset_index(drop=True)

            return df

        except Exception as e:
            logger.error("get_index_pe_with_derived(%s) 失败: %s", code, e)
            if self._fallback:
                return pd.DataFrame()
            raise

    # ═══════════════════════════════════════════════════════════════════════
    # V11.5: MacroValuationEngine 专用接口 (PE-only)
    # ═══════════════════════════════════════════════════════════════════════

    def get_valuation_percentiles(
        self,
        code: str,
        days: int = 500,
        percentile_window: int = 2500,
    ) -> Dict[str, Any]:
        """
        获取最新估值百分位数据 (MacroValuationEngine 专用)

        V11.5: 返回 pe_percentile, 移除 pb_percentile 和 has_pb 字段。
        系统不再跟踪 PB 数据。

        Args:
            code: 指数代码
            days: 回溯天数 (用于趋势分析)
            percentile_window: 百分位计算所需历史数据

        Returns:
            Dict with keys:
              pe_percentile: float (0-100), 最新PE百分位
              pe_ttm: float, 最新滚动市盈率
              close: float, 最新收盘价
              data_available: bool, 是否有可用PE数据
              sample_count: float, 成分股数量
        """
        result = {
            "pe_percentile": np.nan,
            "pe_ttm": np.nan,
            "close": np.nan,
            "data_available": False,
            "sample_count": np.nan,
        }

        if not self._connected:
            return result

        try:
            # 获取足够的历史数据
            actual_days = max(days, percentile_window)
            sql = self._build_per_code_sql(code, actual_days,
                                            select_keys=["trade_date", "pe_ttm", "close", "sample_count"])
            with self._engine.connect() as conn:
                df = pd.read_sql(
                    text(sql),
                    conn,
                    params={"index_code": code, "days": actual_days},
                )

            if df.empty or "pe_ttm" not in df.columns:
                return result

            # 计算 pe_percentile
            pe_series = pd.to_numeric(df["pe_ttm"], errors="coerce")
            if len(pe_series.dropna()) >= 10:
                pct_series = _calc_percentile_rank(pe_series, percentile_window)
                result["pe_percentile"] = float(pct_series.iloc[0])
                result["data_available"] = True

            # 获取最新值
            latest = df.iloc[0]
            result["pe_ttm"] = float(pd.to_numeric(latest.get("pe_ttm", np.nan), errors="coerce"))

            if "close" in df.columns:
                result["close"] = float(pd.to_numeric(latest.get("close", np.nan), errors="coerce"))

            if "sample_count" in df.columns:
                result["sample_count"] = float(pd.to_numeric(latest.get("sample_count", np.nan), errors="coerce"))

            logger.debug(
                "get_valuation_percentiles(%s): pe_ttm=%.2f, pe_percentile=%.1f%%",
                code, result["pe_ttm"], result.get("pe_percentile", np.nan),
            )

            return result

        except Exception as e:
            logger.error("get_valuation_percentiles(%s) 失败: %s", code, e)
            return result

    # ═══════════════════════════════════════════════════════════════════════
    # 批量查询
    # ═══════════════════════════════════════════════════════════════════════

    def get_index_pe_batch(
        self,
        codes: List[str],
    ) -> Dict[str, pd.DataFrame]:
        """
        批量获取指数 PE 数据

        per_code 模式: 逐表查询并合并

        Args:
            codes: 指数代码列表 (如 ['000300', '000905'])

        Returns:
            {index_code: DataFrame, ...}
        """
        if not self._connected:
            logger.warning("DatabaseReader 未连接, 返回空数据")
            return {c: pd.DataFrame() for c in codes}

        if self._table_mode == "per_code":
            return self._get_index_pe_batch_per_code(codes)
        else:
            return self._get_index_pe_batch_single_table(codes)

    def _get_index_pe_batch_per_code(self, codes: List[str]) -> Dict[str, pd.DataFrame]:
        """per_code 模式: 逐表查询"""
        result: Dict[str, pd.DataFrame] = {}
        for code in codes:
            try:
                df = self.get_index_pe(code, days=100)
                result[code] = df
            except Exception as e:
                logger.error("批量估值 %s 失败: %s", code, e)
                result[code] = pd.DataFrame()
                if not self._fallback:
                    raise
        return result

    def _get_index_pe_batch_single_table(self, codes: List[str]) -> Dict[str, pd.DataFrame]:
        """single_table 模式 (兼容旧版)"""
        sql = """
        SELECT
            trade_date, index_code, pe_ttm,
            pe_percentile, dividend_yield
        FROM index_valuation
        WHERE index_code = ANY(:codes)
        ORDER BY index_code, trade_date DESC
        """
        try:
            with self._engine.connect() as conn:
                df = pd.read_sql(text(sql), conn, params={"codes": codes})

            result: Dict[str, pd.DataFrame] = {}
            if not df.empty and "index_code" in df.columns:
                for code, group in df.groupby("index_code"):
                    result[code] = group.reset_index(drop=True)
            else:
                result = {c: pd.DataFrame() for c in codes}

            return result
        except Exception as e:
            logger.error("get_index_pe_batch 失败: %s", e)
            if self._fallback:
                return {c: pd.DataFrame() for c in codes}
            raise

    def get_latest_pe(self) -> pd.DataFrame:
        """
        获取所有指数的最新 PE 数据 (每只指数取最新一条)

        per_code 模式: 发现所有表, 逐表取最新

        Returns:
            DataFrame with columns: index_code, trade_date, pe_ttm, pe_percentile, ...
        """
        if not self._connected:
            return pd.DataFrame()

        if self._table_mode == "per_code":
            return self._get_latest_pe_per_code()
        else:
            return self._get_latest_pe_single_table()

    def _get_latest_pe_per_code(self) -> pd.DataFrame:
        """per_code 模式: 发现所有表, 逐表取最新一条"""
        if not self._discovered_tables:
            self._discovered_tables = self.discover_tables()

        # 筛选看起来像指数代码的表 (6位数字)
        index_tables = [
            t for t in self._discovered_tables
            if re.match(r'^\d{6}$', t)
        ]

        if not index_tables:
            index_tables = self._discovered_tables

        frames = []
        for table_name in index_tables:
            try:
                df = self.get_index_pe(table_name, days=1)
                if not df.empty:
                    frames.append(df)
            except Exception as e:
                logger.debug("获取表 %s 最新数据失败: %s", table_name, e)

        if not frames:
            return pd.DataFrame()

        result = pd.concat(frames, ignore_index=True)
        return result

    def _get_latest_pe_single_table(self) -> pd.DataFrame:
        """single_table 模式 (兼容旧版)"""
        sql = """
        SELECT DISTINCT ON (index_code)
            trade_date, index_code, pe_ttm,
            pe_percentile, dividend_yield
        FROM index_valuation
        ORDER BY index_code, trade_date DESC
        """
        try:
            with self._engine.connect() as conn:
                df = pd.read_sql(text(sql), conn)
            return df
        except Exception as e:
            logger.error("get_latest_pe 失败: %s", e)
            if self._fallback:
                return pd.DataFrame()
            raise

    # ═══════════════════════════════════════════════════════════════════════
    # 期权合约映射
    # ═══════════════════════════════════════════════════════════════════════

    def get_contract_mapping(
        self,
        underlying_code: Optional[str] = None,
        option_type: Optional[str] = None,
    ) -> pd.DataFrame:
        """获取期权合约映射"""
        if not self._connected:
            return pd.DataFrame()

        if self._table_mode == "per_code":
            return self._get_contract_mapping_per_code(underlying_code, option_type)
        else:
            return self._get_contract_mapping_single_table(underlying_code, option_type)

    def _get_contract_mapping_per_code(
        self,
        underlying_code: Optional[str] = None,
        option_type: Optional[str] = None,
    ) -> pd.DataFrame:
        """per_code 模式: 从表 "{underlying_code}" 查询期权合约"""
        if not underlying_code:
            logger.warning("per_code 模式需要 underlying_code 参数来确定表名")
            return pd.DataFrame()

        try:
            sql = self._build_option_per_code_sql(underlying_code)
            params: Dict[str, Any] = {}

            if option_type:
                opt_col = self._option_columns.get("option_type", "option_type")
                sql += f' AND "{opt_col}" = :option_type'
                params["option_type"] = option_type

            exp_col = self._option_columns.get("expire_date", "expire_date")
            stk_col = self._option_columns.get("strike_price", "strike_price")
            sql += f' ORDER BY "{exp_col}", "{stk_col}"'

            with self._engine.connect() as conn:
                df = pd.read_sql(text(sql), conn, params=params)

            if "underlying_code" not in df.columns and not df.empty:
                df.insert(0, "underlying_code", underlying_code)

            return df

        except Exception as e:
            logger.error("get_contract_mapping(%s) 失败: %s", underlying_code, e)
            if self._fallback:
                return pd.DataFrame()
            raise

    def _get_contract_mapping_single_table(
        self,
        underlying_code: Optional[str] = None,
        option_type: Optional[str] = None,
    ) -> pd.DataFrame:
        """single_table 模式 (兼容旧版)"""
        query = """
        SELECT
            underlying_code, contract_code, contract_name,
            option_type, strike_price, expire_date, market
        FROM option_contract_mapping
        WHERE 1=1
        """
        params: Dict[str, Any] = {}

        if underlying_code:
            query += " AND underlying_code = :underlying_code"
            params["underlying_code"] = underlying_code

        if option_type:
            query += " AND option_type = :option_type"
            params["option_type"] = option_type

        query += " ORDER BY expire_date, strike_price"

        try:
            with self._engine.connect() as conn:
                df = pd.read_sql(text(query), conn, params=params)
            return df
        except Exception as e:
            logger.error("get_contract_mapping 失败: %s", e)
            if self._fallback:
                return pd.DataFrame()
            raise

    # ═══════════════════════════════════════════════════════════════════════
    # 通用查询
    # ═══════════════════════════════════════════════════════════════════════

    def execute_query(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> pd.DataFrame:
        """通用 SQL 查询"""
        if not self._connected:
            return pd.DataFrame()

        try:
            with self._engine.connect() as conn:
                df = pd.read_sql(text(query), conn, params=params or {})
            return df
        except Exception as e:
            logger.error("execute_query 失败: %s", e)
            if self._fallback:
                return pd.DataFrame()
            raise

    def execute_scalar(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """执行标量查询 (返回单个值)"""
        if not self._connected:
            return None

        try:
            with self._engine.connect() as conn:
                result = conn.execute(text(query), params or {})
                row = result.fetchone()
                return row[0] if row else None
        except Exception as e:
            logger.error("execute_scalar 失败: %s", e)
            if self._fallback:
                return None
            raise

    # ═══════════════════════════════════════════════════════════════════════
    # 健康检查 / 生命周期
    # ═══════════════════════════════════════════════════════════════════════

    def health_check(self) -> Dict[str, Any]:
        """数据库健康检查 (V11.5 PE-only, online-first 架构)"""
        if self._engine is None:
            return {"connected": False, "reason": "引擎未初始化"}

        try:
            with self._engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                row = result.fetchone()
                return {
                    "connected": True,
                    "engine": self._engine_name,
                    "database": self._config.get("url", "").split("/")[-1]
                                if self._config.get("url") else "unknown",
                    "table_mode": self._table_mode,
                    "column_lang": self._column_lang,
                    "pool_status": {
                        "size": self._engine.pool.size(),
                        "checked_in": self._engine.pool.checkedin(),
                        "checked_out": self._engine.pool.checkedout(),
                    },
                    "pe_columns": self._pe_columns,
                    "derived_config": self._derived_config,
                    "option_columns": self._option_columns,
                    "tables_discovered": len(self._discovered_tables),
                    "tables_sample": self._discovered_tables[:10],
                    "v11_5_notes": {
                        "architecture": "online-first, PG-fallback",
                        "pe_percentile": "计算列: 从历史 pe_ttm 排名百分位",
                        "dividend_yield": "可选外部列: 数据库无股息率数据, 值为 NaN",
                        "pb_removed": "V11.5 已移除所有 PB 相关逻辑 (pb, pb_percentile)",
                        "kline_available": "是: csiIndexPE 同时包含K线数据",
                    },
                }
        except Exception as e:
            return {"connected": False, "reason": str(e)}

    def reconnect(self) -> bool:
        """重新建立数据库连接"""
        self._connected = False
        if self._engine is not None:
            try:
                self._engine.dispose()
            except Exception:
                pass

        self._init_engine()
        return self._connected

    def close(self):
        """关闭数据库连接"""
        if self._engine is not None:
            try:
                self._engine.dispose()
                self._connected = False
                logger.info("DatabaseReader 连接已关闭")
            except Exception as e:
                logger.error("关闭数据库连接异常: %s", e)

    # ─── 上下文管理器 ─────────────────────────────────────────────────────

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    # ─── 属性 ─────────────────────────────────────────────────────────────

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def engine(self) -> Optional[Any]:
        return self._engine

    @property
    def table_mode(self) -> str:
        """当前表模式 ('per_code' 或 'single_table')"""
        return self._table_mode

    @property
    def pe_columns(self) -> Dict[str, str]:
        """PE 列名映射 (逻辑→物理)"""
        return dict(self._pe_columns)

    @property
    def column_lang(self) -> str:
        """V11.5: 列名语言 ('zh' 或 'en')"""
        return self._column_lang

    @property
    def derived_config(self) -> Dict[str, Any]:
        """V11.5: 衍生列配置"""
        return dict(self._derived_config)

    @property
    def option_columns(self) -> Dict[str, str]:
        """期权合约列名映射 (逻辑→物理)"""
        return dict(self._option_columns)

    @property
    def discovered_tables(self) -> List[str]:
        """已发现的表名列表"""
        return list(self._discovered_tables)
