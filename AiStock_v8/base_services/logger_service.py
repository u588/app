"""AiStock V8 日志服务

提供专业级日志功能:
- 控制台彩色输出 + 文件轮转输出
- 按模块获取 logger: get_logger(name)
- 日志文件自动轮转 (50MB, 10 份备份)
- 性能计时上下文管理器: log_timer()
- 结构化日志格式

Usage:
    >>> from base_services import LoggerService
    >>> svc = LoggerService()
    >>> logger = svc.get_logger('market.data')
    >>> logger.info('行情数据接收完成', extra={'symbol': '000001', 'count': 1200})
    >>>
    >>> # 性能计时
    >>> with svc.log_timer('fetch_daily_bars', logger):
    ...     bars = fetch_bars()
"""

from __future__ import annotations

import logging
import os
import sys
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional


# ─── 彩色 ANSI 转义码 ────────────────────────────────────────────────

class _AnsiColor:
    """ANSI 颜色常量, 用于控制台日志着色"""

    RESET   = '\033[0m'
    BOLD    = '\033[1m'
    DIM     = '\033[2m'

    BLACK   = '\033[30m'
    RED     = '\033[31m'
    GREEN   = '\033[32m'
    YELLOW  = '\033[33m'
    BLUE    = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN    = '\033[36m'
    WHITE   = '\033[37m'

    # 高亮变体
    BRIGHT_RED    = '\033[91m'
    BRIGHT_GREEN  = '\033[92m'
    BRIGHT_YELLOW = '\033[93m'
    BRIGHT_CYAN   = '\033[96m'

    @classmethod
    def for_level(cls, level: int) -> str:
        """根据日志级别返回对应颜色"""
        _map = {
            logging.DEBUG:    cls.CYAN,
            logging.INFO:     cls.GREEN,
            logging.WARNING:  cls.YELLOW,
            logging.ERROR:    cls.RED,
            logging.CRITICAL: cls.BRIGHT_RED,
        }
        return _map.get(level, cls.WHITE)


# ─── 彩色控制台格式化器 ──────────────────────────────────────────────

class _ColorFormatter(logging.Formatter):
    """控制台彩色日志格式化器

    Format:
        2025-01-15 09:30:00.123 | INFO     | market.data | 行情数据接收完成
    """

    _FORMAT = (
        '%(asctime)s.%(msecs)03d | %(levelname)-8s | %(name)s | %(message)s'
    )
    _DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

    def __init__(self) -> None:
        super().__init__(fmt=self._FORMAT, datefmt=self._DATE_FORMAT)

    def format(self, record: logging.LogRecord) -> str:
        # 保存原始格式, 用于文件日志不受影响
        color = _AnsiColor.for_level(record.levelno)
        record.levelname = f'{color}{record.levelname:<8}{_AnsiColor.RESET}'
        record.name = f'{_AnsiColor.BRIGHT_CYAN}{record.name}{_AnsiColor.RESET}'
        result = super().format(record)
        return result

    def formatException(self, ei) -> str:  # type: ignore[override]
        text = super().formatException(ei)
        return f'{_AnsiColor.BRIGHT_RED}{text}{_AnsiColor.RESET}'


# ─── 文件日志格式化器 (无颜色) ───────────────────────────────────────

class _FileFormatter(logging.Formatter):
    """文件日志格式化器 (纯文本, 无 ANSI 转义)

    Format:
        2025-01-15 09:30:00.123 | INFO     | market.data | 行情数据接收完成
    """

    _FORMAT = (
        '%(asctime)s.%(msecs)03d | %(levelname)-8s | %(name)s | %(message)s'
    )
    _DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

    def __init__(self) -> None:
        super().__init__(fmt=self._FORMAT, datefmt=self._DATE_FORMAT)


# ─── 性能计时上下文管理器 ────────────────────────────────────────────

class _LogTimer:
    """性能计时上下文管理器

    在 with 块开始时记录时间戳, 退出时计算耗时并写入日志.
    异常时以 WARNING 级别记录耗时 (标记失败).

    Usage:
        >>> with LoggerService().log_timer('query_stock_list', logger):
        ...     stocks = api.get_stock_list()
    """

    def __init__(
        self,
        operation: str,
        logger: logging.Logger,
        level: int = logging.INFO,
    ) -> None:
        self._operation = operation
        self._logger = logger
        self._level = level
        self._start: float = 0.0

    def __enter__(self) -> '_LogTimer':
        self._start = time.perf_counter()
        self._logger.log(
            self._level,
            '⏱ [%s] 开始执行',
            self._operation,
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore[override]
        elapsed_ms = (time.perf_counter() - self._start) * 1000.0
        if exc_type is None:
            self._logger.log(
                self._level,
                '✅ [%s] 执行完成 | 耗时 %.2f ms',
                self._operation,
                elapsed_ms,
            )
        else:
            self._logger.warning(
                '❌ [%s] 执行失败 | 耗时 %.2f ms | 错误: %s',
                self._operation,
                elapsed_ms,
                exc_val,
            )


# ─── 日志服务主体 ────────────────────────────────────────────────────

class LoggerService:
    """AiStock V8 日志服务

    单例式日志服务, 管理全局日志配置:
    - 控制台: 彩色输出, 级别可配
    - 文件: RotatingFileHandler, 自动轮转
    - 按模块获取子 logger
    - 性能计时上下文管理器

    Args:
        log_dir: 日志文件目录, 默认为项目根目录下 logs/
        console_level: 控制台日志级别, 默认 DEBUG
        file_level: 文件日志级别, 默认 DEBUG
        max_bytes: 单个日志文件最大字节数, 默认 50MB
        backup_count: 日志备份数, 默认 10
        project_root: 项目根目录, 用于默认路径推断

    Example:
        >>> svc = LoggerService()
        >>> logger = svc.get_logger('tdx.connector')
        >>> logger.info('连接建立', extra={'host': '180.153.18.170', 'port': 7709})
    """

    _DEFAULT_LOG_DIR_NAME = 'logs'
    _DEFAULT_MAX_BYTES = 50 * 1024 * 1024  # 50 MB
    _DEFAULT_BACKUP_COUNT = 10

    def __init__(
        self,
        log_dir: Optional[str | Path] = None,
        console_level: int = logging.DEBUG,
        file_level: int = logging.DEBUG,
        max_bytes: int = _DEFAULT_MAX_BYTES,
        backup_count: int = _DEFAULT_BACKUP_COUNT,
        project_root: Optional[str | Path] = None,
    ) -> None:
        self._console_level = console_level
        self._file_level = file_level
        self._max_bytes = max_bytes
        self._backup_count = backup_count

        # 确定项目根目录
        if project_root is not None:
            root = Path(project_root)
        else:
            # 向上查找, 找到包含 base_services 的目录作为项目根
            root = Path(__file__).resolve().parent.parent
        self._project_root = root

        # 确定日志目录
        if log_dir is not None:
            self._log_dir = Path(log_dir)
        else:
            self._log_dir = self._project_root / self._DEFAULT_LOG_DIR_NAME

        # 确保日志目录存在
        self._log_dir.mkdir(parents=True, exist_ok=True)

        # 已注册的 logger 名称集合, 防止重复添加 handler
        self._registered_loggers: set[str] = set()

        # 初始化根 logger
        self._root_logger = logging.getLogger('aistock')
        self._root_logger.setLevel(logging.DEBUG)
        # 防止日志向上传播到 root logger 导致重复输出
        self._root_logger.propagate = False

        self._setup_handlers()

    # ─── 属性 ─────────────────────────────────────────────

    @property
    def log_dir(self) -> Path:
        """日志文件目录路径"""
        return self._log_dir

    @property
    def project_root(self) -> Path:
        """项目根目录路径"""
        return self._project_root

    # ─── 公共方法 ─────────────────────────────────────────

    def get_logger(self, name: str) -> logging.Logger:
        """获取指定模块的 logger

        返回的 logger 名称为 ``aistock.<name>``, 继承根 logger 的
        handlers 与级别设置, 无需重复配置.

        Args:
            name: 模块名, 如 'market.data', 'tdx.connector'

        Returns:
            配置好的 Logger 实例

        Example:
            >>> logger = svc.get_logger('strategy.momentum')
            >>> logger.info('策略启动')
        """
        full_name = f'aistock.{name}'
        if full_name not in self._registered_loggers:
            logger = logging.getLogger(full_name)
            # 子 logger 继承父 logger 的 handlers, 不需要额外添加
            logger.propagate = True
            self._registered_loggers.add(full_name)
        return logging.getLogger(full_name)

    def log_timer(
        self,
        operation: str,
        logger: Optional[logging.Logger] = None,
        level: int = logging.INFO,
    ) -> _LogTimer:
        """创建性能计时上下文管理器

        Args:
            operation: 操作名称, 用于日志标识
            logger: 使用的 logger, 若为 None 则使用根 logger
            level: 日志级别, 默认 INFO

        Returns:
            _LogTimer 上下文管理器实例

        Example:
            >>> with svc.log_timer('fetch_kline', logger):
            ...     data = fetch_kline('000001')
        """
        target = logger or self._root_logger
        return _LogTimer(operation=operation, logger=target, level=level)

    # ─── 内部方法 ─────────────────────────────────────────

    def _setup_handlers(self) -> None:
        """配置根 logger 的 handlers (控制台 + 文件)"""
        # 清除既有 handlers, 防止重复
        self._root_logger.handlers.clear()

        # 1. 控制台 handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(self._console_level)
        console_handler.setFormatter(_ColorFormatter())
        self._root_logger.addHandler(console_handler)

        # 2. 主日志文件 handler (轮转)
        main_log_path = self._log_dir / 'aistock.log'
        main_handler = RotatingFileHandler(
            filename=str(main_log_path),
            maxBytes=self._max_bytes,
            backupCount=self._backup_count,
            encoding='utf-8',
        )
        main_handler.setLevel(self._file_level)
        main_handler.setFormatter(_FileFormatter())
        self._root_logger.addHandler(main_handler)

        # 3. 错误日志单独文件 (仅 ERROR 及以上)
        error_log_path = self._log_dir / 'aistock_error.log'
        error_handler = RotatingFileHandler(
            filename=str(error_log_path),
            maxBytes=self._max_bytes,
            backupCount=self._backup_count,
            encoding='utf-8',
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(_FileFormatter())
        self._root_logger.addHandler(error_handler)

        # 启动日志
        self._root_logger.info(
            '📋 LoggerService 初始化完成 | 日志目录: %s | '
            '控制台级别: %s | 文件级别: %s | 轮转: %sMB×%d',
            self._log_dir,
            logging.getLevelName(self._console_level),
            logging.getLevelName(self._file_level),
            self._max_bytes // (1024 * 1024),
            self._backup_count,
        )
