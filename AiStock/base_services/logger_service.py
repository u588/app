#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LoggerService：统一日志服务模块
职责：
1. 统一日志格式和输出
2. 支持控制台和文件双输出
3. 支持日志轮转（按大小和时间）
4. 支持不同模块的日志隔离
5. 支持日志级别动态调整
6. 与 ConfigService 集成

版本：V7.0.0
最后更新：2026-03-20
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from typing import Optional, Dict, Any
import json
import traceback


# ==================== 日志级别常量 ====================
LOG_LEVELS = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL,
}

# ==================== 日志格式模板 ====================
LOG_FORMATS = {
    'detailed': '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    'simple': '%(asctime)s - %(levelname)s - %(message)s',
    'minimal': '%(levelname)s - %(message)s',
    'json': '%(message)s',  # JSON 格式需特殊处理
}

DEFAULT_FORMAT = 'detailed'
DEFAULT_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'


class ColoredFormatter(logging.Formatter):
    """
    彩色日志格式化器（控制台输出）
    不同级别使用不同颜色，便于快速识别
    """
    
    # ANSI 颜色代码
    COLORS = {
        'DEBUG': '\033[36m',      # 青色
        'INFO': '\033[32m',       # 绿色
        'WARNING': '\033[33m',    # 黄色
        'ERROR': '\033[31m',      # 红色
        'CRITICAL': '\033[35m',   # 紫色
        'RESET': '\033[0m',       # 重置
    }
    
    def __init__(self, fmt: str, datefmt: str, use_color: bool = True):
        super().__init__(fmt, datefmt)
        self.use_color = use_color and self._supports_color()
    
    def _supports_color(self) -> bool:
        """检查终端是否支持颜色"""
        if not hasattr(sys.stdout, 'isatty'):
            return False
        if not sys.stdout.isatty():
            return False
        # 检查环境变量
        if os.environ.get('NO_COLOR'):
            return False
        return True
    
    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录"""
        log_message = super().format(record)
        
        if self.use_color and record.levelname in self.COLORS:
            color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
            reset = self.COLORS['RESET']
            log_message = f"{color}{log_message}{reset}"
        
        return log_message


class JSONFormatter(logging.Formatter):
    """
    JSON 格式日志格式化器
    适用于日志收集系统（如 ELK、Splunk）
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录为 JSON"""
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'file': record.pathname,
        }
        
        # 添加额外字段
        if hasattr(record, 'extra_data'):
            log_data['extra'] = record.extra_data
        
        # 添加异常信息
        if record.exc_info:
            log_data['exception'] = {
                'type': record.exc_info[0].__name__ if record.exc_info[0] else None,
                'message': str(record.exc_info[1]) if record.exc_info[1] else None,
                'traceback': traceback.format_exception(*record.exc_info),
            }
        
        return json.dumps(log_data, ensure_ascii=False, default=str)


class LoggerService:
    """
    统一日志服务类
    
    功能特性：
    - 支持多日志级别
    - 支持控制台和文件双输出
    - 支持日志轮转（按大小和时间）
    - 支持不同模块的日志隔离
    - 支持日志级别动态调整
    - 支持 JSON 格式输出
    - 支持日志上下文管理器
    """
    
    # 单例实例
    _instance: Optional['LoggerService'] = None
    _initialized: bool = False
    
    def __new__(cls, *args, **kwargs):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(
        self,
        log_dir: Optional[Path] = None,
        log_level: str = 'INFO',
        log_format: str = DEFAULT_FORMAT,
        enable_console: bool = True,
        enable_file: bool = True,
        enable_json: bool = False,
        max_bytes: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 10,
        rotation_when: str = 'midnight',
        use_color: bool = True,
    ):
        """
        初始化日志服务
        
        参数:
            log_dir: 日志目录路径
            log_level: 日志级别（DEBUG/INFO/WARNING/ERROR/CRITICAL）
            log_format: 日志格式（detailed/simple/minimal/json）
            enable_console: 是否启用控制台输出
            enable_file: 是否启用文件输出
            enable_json: 是否启用 JSON 格式（用于日志收集系统）
            max_bytes: 单个日志文件最大大小（字节）
            backup_count: 保留的备份文件数量
            rotation_when: 轮转时间（midnight/interval）
            use_color: 控制台是否使用彩色输出
        """
        # 避免重复初始化
        if LoggerService._initialized:
            return
        
        self.log_dir = log_dir or Path('./logs')
        self.log_level = LOG_LEVELS.get(log_level.upper(), logging.INFO)
        self.log_format = log_format
        self.enable_console = enable_console
        self.enable_file = enable_file
        self.enable_json = enable_json
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self.rotation_when = rotation_when
        self.use_color = use_color
        
        # 日志处理器存储
        self.handlers: Dict[str, logging.Handler] = {}
        self.loggers: Dict[str, logging.Logger] = {}
        
        # 确保日志目录存在
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化根日志器
        self._init_root_logger()
        
        LoggerService._initialized = True
    
    def _init_root_logger(self):
        """初始化根日志器"""
        root_logger = logging.getLogger()
        root_logger.setLevel(self.log_level)
        
        # 清除现有处理器
        root_logger.handlers.clear()
        
        # 添加控制台处理器
        if self.enable_console:
            console_handler = self._create_console_handler()
            root_logger.addHandler(console_handler)
            self.handlers['console'] = console_handler
        
        # 添加文件处理器
        if self.enable_file:
            file_handler = self._create_file_handler()
            root_logger.addHandler(file_handler)
            self.handlers['file'] = file_handler
        
        # 添加 JSON 处理器（可选）
        if self.enable_json:
            json_handler = self._create_json_handler()
            root_logger.addHandler(json_handler)
            self.handlers['json'] = json_handler
    
    def _create_console_handler(self) -> logging.StreamHandler:
        """创建控制台处理器"""
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(self.log_level)
        
        # 选择格式化器
        if self.enable_json:
            formatter = JSONFormatter()
        else:
            fmt = LOG_FORMATS.get(self.log_format, LOG_FORMATS['detailed'])
            formatter = ColoredFormatter(fmt, DEFAULT_DATE_FORMAT, use_color=self.use_color)
        
        handler.setFormatter(formatter)
        return handler
    
    def _create_file_handler(self) -> RotatingFileHandler:
        """创建文件处理器（按大小轮转）"""
        log_file = self.log_dir / 'system.log'
        handler = RotatingFileHandler(
            log_file,
            maxBytes=self.max_bytes,
            backupCount=self.backup_count,
            encoding='utf-8'
        )
        handler.setLevel(self.log_level)
        
        # 使用详细格式（文件日志不需要颜色）
        fmt = LOG_FORMATS.get('detailed', LOG_FORMATS['detailed'])
        formatter = logging.Formatter(fmt, DEFAULT_DATE_FORMAT)
        handler.setFormatter(formatter)
        
        return handler
    
    def _create_json_handler(self) -> RotatingFileHandler:
        """创建 JSON 格式文件处理器"""
        log_file = self.log_dir / 'system.json.log'
        handler = RotatingFileHandler(
            log_file,
            maxBytes=self.max_bytes,
            backupCount=self.backup_count,
            encoding='utf-8'
        )
        handler.setLevel(self.log_level)
        handler.setFormatter(JSONFormatter())
        return handler
    
    def get_logger(self, name: Optional[str] = None) -> logging.Logger:
        """
        获取日志器实例
        
        参数:
            name: 日志器名称（通常为模块名）
        
        返回:
            logging.Logger 实例
        """
        if name is None:
            return logging.getLogger()
        
        if name not in self.loggers:
            logger = logging.getLogger(name)
            logger.setLevel(self.log_level)
            self.loggers[name] = logger
        
        return self.loggers[name]
    
    def set_level(self, level: str, logger_name: Optional[str] = None):
        """
        动态设置日志级别
        
        参数:
            level: 日志级别（DEBUG/INFO/WARNING/ERROR/CRITICAL）
            logger_name: 日志器名称（None 表示根日志器）
        """
        log_level = LOG_LEVELS.get(level.upper(), logging.INFO)
        
        if logger_name is None:
            logging.getLogger().setLevel(log_level)
        else:
            logger = self.get_logger(logger_name)
            logger.setLevel(log_level)
        
        self.log_level = log_level
    
    def add_file_handler(
        self,
        filename: str,
        level: str = 'INFO',
        format_type: str = 'detailed',
        max_bytes: Optional[int] = None,
        backup_count: Optional[int] = None,
    ):
        """
        添加额外的文件处理器
        
        参数:
            filename: 日志文件名
            level: 日志级别
            format_type: 日志格式类型
            max_bytes: 最大文件大小
            backup_count: 备份文件数量
        """
        log_file = self.log_dir / filename
        handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes or self.max_bytes,
            backupCount=backup_count or self.backup_count,
            encoding='utf-8'
        )
        handler.setLevel(LOG_LEVELS.get(level.upper(), logging.INFO))
        
        fmt = LOG_FORMATS.get(format_type, LOG_FORMATS['detailed'])
        formatter = logging.Formatter(fmt, DEFAULT_DATE_FORMAT)
        handler.setFormatter(formatter)
        
        logging.getLogger().addHandler(handler)
        self.handlers[filename] = handler
    
    def add_timed_rotating_handler(
        self,
        filename: str,
        when: str = 'midnight',
        interval: int = 1,
        level: str = 'INFO',
    ):
        """
        添加按时间轮转的文件处理器
        
        参数:
            filename: 日志文件名
            when: 轮转时间（'S'-秒，'M'-分，'H'-时，'D'-天，'W'-周，'midnight'-每天午夜）
            interval: 轮转间隔
            level: 日志级别
        """
        log_file = self.log_dir / filename
        handler = TimedRotatingFileHandler(
            log_file,
            when=when,
            interval=interval,
            encoding='utf-8',
            backupCount=self.backup_count
        )
        handler.setLevel(LOG_LEVELS.get(level.upper(), logging.INFO))
        
        fmt = LOG_FORMATS.get('detailed', LOG_FORMATS['detailed'])
        formatter = logging.Formatter(fmt, DEFAULT_DATE_FORMAT)
        handler.setFormatter(formatter)
        
        logging.getLogger().addHandler(handler)
        self.handlers[f'timed_{filename}'] = handler
    
    def log_with_context(self, logger_name: str, level: str, message: str, **kwargs):
        """
        带上下文的日志记录
        
        参数:
            logger_name: 日志器名称
            level: 日志级别
            message: 日志消息
            **kwargs: 额外上下文数据
        """
        logger = self.get_logger(logger_name)
        log_level = LOG_LEVELS.get(level.upper(), logging.INFO)
        
        # 创建带额外数据的日志记录
        extra_data = {'extra_data': kwargs} if kwargs else {}
        logger.log(log_level, message, extra=extra_data)
    
    def log_exception(self, logger_name: str, message: str, exc_info: bool = True):
        """
        记录异常信息
        
        参数:
            logger_name: 日志器名称
            message: 日志消息
            exc_info: 是否包含异常堆栈信息
        """
        logger = self.get_logger(logger_name)
        logger.error(message, exc_info=exc_info)
    
    def get_handler_stats(self) -> Dict[str, Any]:
        """
        获取处理器统计信息
        
        返回:
            处理器统计信息字典
        """
        stats = {
            'log_dir': str(self.log_dir),
            'log_level': logging.getLevelName(self.log_level),
            'handlers': {},
        }
        
        for name, handler in self.handlers.items():
            handler_info = {
                'type': handler.__class__.__name__,
                'level': logging.getLevelName(handler.level),
            }
            
            # 文件处理器额外信息
            if isinstance(handler, RotatingFileHandler):
                handler_info['file'] = handler.baseFilename
                handler_info['max_bytes'] = handler.maxBytes
                handler_info['backup_count'] = handler.backupCount
                
                # 获取文件大小
                try:
                    handler_info['current_size'] = os.path.getsize(handler.baseFilename)
                except:
                    handler_info['current_size'] = 0
            
            stats['handlers'][name] = handler_info
        
        return stats
    
    def cleanup_old_logs(self, days: int = 30):
        """
        清理旧日志文件
        
        参数:
            days: 保留天数
        """
        import time
        
        current_time = time.time()
        cutoff_time = current_time - (days * 24 * 60 * 60)
        
        cleaned_count = 0
        for log_file in self.log_dir.glob('*.log*'):
            try:
                if log_file.stat().st_mtime < cutoff_time:
                    log_file.unlink()
                    cleaned_count += 1
            except Exception as e:
                self.get_logger('LoggerService').warning(f"清理日志文件失败：{log_file} - {e}")
        
        return cleaned_count
    
    def flush(self):
        """刷新所有处理器"""
        for handler in self.handlers.values():
            handler.flush()
    
    def close(self):
        """关闭所有处理器"""
        for handler in self.handlers.values():
            try:
                handler.close()
            except Exception as e:
                print(f"关闭日志处理器失败：{e}")
    
    @classmethod
    def reset(cls):
        """重置日志服务（用于测试）"""
        if cls._instance:
            cls._instance.close()
            cls._instance = None
            cls._initialized = False
        
        # 重置根日志器
        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        root_logger.setLevel(logging.WARNING)


# ==================== 便捷函数 ====================

def init_logger(
    log_dir: Optional[Path] = None,
    log_level: str = 'INFO',
    **kwargs
) -> LoggerService:
    """
    初始化日志服务（便捷函数）
    
    参数:
        log_dir: 日志目录
        log_level: 日志级别
        **kwargs: 其他参数传递给 LoggerService
    
    返回:
        LoggerService 实例
    """
    return LoggerService(log_dir=log_dir, log_level=log_level, **kwargs)


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    获取日志器（便捷函数）
    
    参数:
        name: 日志器名称
    
    返回:
        logging.Logger 实例
    """
    service = LoggerService()
    return service.get_logger(name)


def log_debug(message: str, logger_name: Optional[str] = None, **kwargs):
    """记录 DEBUG 级别日志"""
    logger = get_logger(logger_name)
    logger.debug(message, extra={'extra_data': kwargs} if kwargs else {})


def log_info(message: str, logger_name: Optional[str] = None, **kwargs):
    """记录 INFO 级别日志"""
    logger = get_logger(logger_name)
    logger.info(message, extra={'extra_data': kwargs} if kwargs else {})


def log_warning(message: str, logger_name: Optional[str] = None, **kwargs):
    """记录 WARNING 级别日志"""
    logger = get_logger(logger_name)
    logger.warning(message, extra={'extra_data': kwargs} if kwargs else {})


def log_error(message: str, logger_name: Optional[str] = None, exc_info: bool = False, **kwargs):
    """记录 ERROR 级别日志"""
    logger = get_logger(logger_name)
    logger.error(message, exc_info=exc_info, extra={'extra_data': kwargs} if kwargs else {})


def log_critical(message: str, logger_name: Optional[str] = None, exc_info: bool = False, **kwargs):
    """记录 CRITICAL 级别日志"""
    logger = get_logger(logger_name)
    logger.critical(message, exc_info=exc_info, extra={'extra_data': kwargs} if kwargs else {})


# ==================== 使用示例 ====================

if __name__ == '__main__':
    # 示例 1：基本使用
    print("=" * 60)
    print("示例 1：基本使用")
    print("=" * 60)
    
    # 初始化日志服务
    logger_service = LoggerService(
        log_dir=Path('./logs'),
        log_level='DEBUG',
        enable_console=True,
        enable_file=True,
        use_color=True,
    )
    
    # 获取日志器
    logger = logger_service.get_logger('test_module')
    
    # 记录不同级别的日志
    logger.debug("这是一条 DEBUG 日志")
    logger.info("这是一条 INFO 日志")
    logger.warning("这是一条 WARNING 日志")
    logger.error("这是一条 ERROR 日志")
    logger.critical("这是一条 CRITICAL 日志")
    
    # 示例 2：带上下文的日志
    print("\n" + "=" * 60)
    print("示例 2：带上下文的日志")
    print("=" * 60)
    
    logger_service.log_with_context(
        'test_module',
        'INFO',
        '用户操作日志',
        user_id='12345',
        action='login',
        ip='192.168.1.100'
    )
    
    # 示例 3：异常日志
    print("\n" + "=" * 60)
    print("示例 3：异常日志")
    print("=" * 60)
    
    try:
        result = 10 / 0
    except Exception as e:
        logger_service.log_exception('test_module', f'发生异常：{e}')
    
    # 示例 4：动态调整日志级别
    print("\n" + "=" * 60)
    print("示例 4：动态调整日志级别")
    print("=" * 60)
    
    logger_service.set_level('WARNING')
    logger.debug("这条 DEBUG 日志不会显示（级别已调整为 WARNING）")
    logger.warning("这条 WARNING 日志会显示")
    
    # 示例 5：获取处理器统计
    print("\n" + "=" * 60)
    print("示例 5：获取处理器统计")
    print("=" * 60)
    
    stats = logger_service.get_handler_stats()
    print(f"日志目录：{stats['log_dir']}")
    print(f"日志级别：{stats['log_level']}")
    print(f"处理器数量：{len(stats['handlers'])}")
    
    for name, info in stats['handlers'].items():
        print(f"  • {name}: {info['type']} ({info['level']})")
    
    # 示例 6：添加额外文件处理器
    print("\n" + "=" * 60)
    print("示例 6：添加额外文件处理器")
    print("=" * 60)
    
    logger_service.add_file_handler(
        'error.log',
        level='ERROR',
        format_type='detailed'
    )
    logger.error("这条 ERROR 日志会同时写入 system.log 和 error.log")
    
    # 示例 7：使用便捷函数
    print("\n" + "=" * 60)
    print("示例 7：使用便捷函数")
    print("=" * 60)
    
    log_info("使用便捷函数记录 INFO 日志", logger_name='convenience')
    log_error("使用便捷函数记录 ERROR 日志", logger_name='convenience')
    
    # 清理
    print("\n" + "=" * 60)
    print("清理资源")
    print("=" * 60)
    
    logger_service.flush()
    logger_service.close()
    
    print("✅ 日志服务示例运行完成")