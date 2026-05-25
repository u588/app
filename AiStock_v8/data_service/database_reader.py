"""
AiStock V8 DatabaseReader — PostgreSQL 估值数据读取器

功能:
  - 指数 PE/PB 百分位查询
  - 批量估值数据获取
  - 期权合约映射查询
  - 通用 SQL 查询接口

连接管理:
  - SQLAlchemy 连接池 (queuepool)
  - 主接口为同步, 可选异步执行
  - 自动重连与错误降级
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

try:
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import Engine
    from sqlalchemy.pool import QueuePool
except ImportError:
    create_engine = None  # type: ignore[assignment]
    text = None  # type: ignore[assignment]
    Engine = None  # type: ignore[assignment,misc]
    QueuePool = None  # type: ignore[assignment,misc]

# ─── 全局配置 (从 global_settings 获取或使用默认值) ────────────────────────────
try:
    from global_settings import DATABASE_ENGINES
except ImportError:
    DATABASE_ENGINES = {
        "valuation": {
            "url": "postgresql://aistock:aistock@localhost:5432/valuation",
            "pool_size": 5,
            "max_overflow": 10,
            "pool_timeout": 30,
            "pool_recycle": 3600,
        }
    }

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# 默认 SQL 模板
# ═══════════════════════════════════════════════════════════════════════════════

SQL_INDEX_PE = """
SELECT
    trade_date,
    index_code,
    pe_ttm,
    pb,
    pe_percentile,
    pb_percentile,
    dividend_yield
FROM index_valuation
WHERE index_code = :code
ORDER BY trade_date DESC
LIMIT :days
"""

SQL_INDEX_PE_BATCH = """
SELECT
    trade_date,
    index_code,
    pe_ttm,
    pb,
    pe_percentile,
    pb_percentile,
    dividend_yield
FROM index_valuation
WHERE index_code = ANY(:codes)
ORDER BY index_code, trade_date DESC
"""

SQL_CONTRACT_MAPPING = """
SELECT
    underlying_code,
    contract_code,
    contract_name,
    option_type,
    strike_price,
    expire_date,
    market
FROM option_contract_mapping
WHERE 1=1
"""

SQL_LATEST_PE = """
SELECT DISTINCT ON (index_code)
    trade_date,
    index_code,
    pe_ttm,
    pb,
    pe_percentile,
    pb_percentile,
    dividend_yield
FROM index_valuation
ORDER BY index_code, trade_date DESC
"""


# ═══════════════════════════════════════════════════════════════════════════════
# DatabaseReader
# ═══════════════════════════════════════════════════════════════════════════════

class DatabaseReader:
    """
    PostgreSQL 估值数据读取器

    支持:
      - 指数 PE/PB 百分位查询 (单条 / 批量)
      - 期权合约映射
      - 通用 SQL 查询
      - 连接池管理与自动重连
    """

    def __init__(
        self,
        db_config: Optional[Dict[str, Any]] = None,
        engine_name: str = "valuation",
        fallback_on_error: bool = True,
    ):
        """
        Args:
            db_config: 数据库配置, 若 None 则从 DATABASE_ENGINES 读取
            engine_name: DATABASE_ENGINES 中的引擎名称
            fallback_on_error: 查询失败时返回空而非抛异常
        """
        self._engine_name = engine_name
        self._fallback = fallback_on_error
        self._engine: Optional[Any] = None
        self._connected = False

        # 解析配置
        if db_config is not None:
            self._config = db_config
        elif engine_name in DATABASE_ENGINES:
            self._config = DATABASE_ENGINES[engine_name]
        else:
            self._config = {
                "url": "postgresql://aistock:aistock@localhost:5432/valuation",
                "pool_size": 5,
                "max_overflow": 10,
            }

        # 初始化引擎
        self._init_engine()

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
            logger.info("DatabaseReader 连接成功: %s (pool_size=%d)",
                        self._mask_url(db_url),
                        self._config.get("pool_size", 5))
        except Exception as e:
            self._connected = False
            logger.error("DatabaseReader 连接失败: %s", e)

    @staticmethod
    def _mask_url(url: str) -> str:
        """遮蔽密码"""
        import re
        return re.sub(r'://([^:]+):([^@]+)@', r'://\1:****@', url)

    # ─── 重新连接 ─────────────────────────────────────────────────────────

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

    # ═══════════════════════════════════════════════════════════════════════
    # 指数 PE/PB 查询
    # ═══════════════════════════════════════════════════════════════════════

    def get_index_pe(
        self,
        code: str,
        days: int = 100,
    ) -> pd.DataFrame:
        """
        获取指数 PE/PB 百分位数据

        Args:
            code: 指数代码 (如 '000300', '000905')
            days: 回溯天数

        Returns:
            DataFrame with columns:
              trade_date, index_code, pe_ttm, pb, pe_percentile, pb_percentile, dividend_yield
        """
        if not self._connected:
            logger.warning("DatabaseReader 未连接, 返回空数据")
            return pd.DataFrame()

        try:
            with self._engine.connect() as conn:
                df = pd.read_sql(
                    text(SQL_INDEX_PE),
                    conn,
                    params={"code": code, "days": days},
                )
            return df
        except Exception as e:
            logger.error("get_index_pe(%s) 失败: %s", code, e)
            if self._fallback:
                return pd.DataFrame()
            raise

    def get_index_pe_batch(
        self,
        codes: List[str],
    ) -> Dict[str, pd.DataFrame]:
        """
        批量获取指数 PE/PB 数据

        Args:
            codes: 指数代码列表

        Returns:
            {index_code: DataFrame, ...}
        """
        if not self._connected:
            logger.warning("DatabaseReader 未连接, 返回空数据")
            return {c: pd.DataFrame() for c in codes}

        try:
            with self._engine.connect() as conn:
                df = pd.read_sql(
                    text(SQL_INDEX_PE_BATCH),
                    conn,
                    params={"codes": codes},
                )

            # 按指数代码拆分
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
        获取所有指数的最新 PE/PB 数据 (每只指数取最新一条)

        Returns:
            DataFrame with columns: trade_date, index_code, pe_ttm, pb, pe_percentile, ...
        """
        if not self._connected:
            return pd.DataFrame()

        try:
            with self._engine.connect() as conn:
                df = pd.read_sql(text(SQL_LATEST_PE), conn)
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
        """
        获取期权合约映射

        Args:
            underlying_code: 标的代码筛选 (如 '510050')
            option_type: 期权类型筛选 ('C'=看涨, 'P'=看跌)

        Returns:
            DataFrame with columns:
              underlying_code, contract_code, contract_name,
              option_type, strike_price, expire_date, market
        """
        if not self._connected:
            return pd.DataFrame()

        query = SQL_CONTRACT_MAPPING
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
        """
        通用 SQL 查询

        Args:
            query: SQL 语句 (支持 :param 形式的参数绑定)
            params: 参数字典

        Returns:
            DataFrame
        """
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
        """
        执行标量查询 (返回单个值)

        Args:
            query: SQL 语句
            params: 参数字典

        Returns:
            单个值或 None
        """
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
        """数据库健康检查"""
        if self._engine is None:
            return {"connected": False, "reason": "引擎未初始化"}

        try:
            with self._engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                row = result.fetchone()
                return {
                    "connected": True,
                    "engine": self._engine_name,
                    "pool_status": {
                        "size": self._engine.pool.size(),
                        "checked_in": self._engine.pool.checkedin(),
                        "checked_out": self._engine.pool.checkedout(),
                    },
                }
        except Exception as e:
            return {"connected": False, "reason": str(e)}

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
