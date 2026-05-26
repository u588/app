"""AiStock V8 基础服务层

本模块提供量化交易系统的基础服务组件:
- LoggerService: 结构化日志服务, 支持控制台彩色输出与文件轮转
- ConfigService: YAML 配置管理, 支持点号路径访问与环境变量覆盖
- CacheService: 线程安全 LRU 缓存, 支持单键 TTL、命名空间与批量操作
- TDXConnectionPool: 通达信双端口连接池, 标准端口(7709) + 扩展端口(7721)
"""

from .logger_service import LoggerService
from .config_service import ConfigService
from .cache_service import CacheService
from .connection_pool import TDXConnectionPool

__all__ = [
    'LoggerService',
    'ConfigService',
    'CacheService',
    'TDXConnectionPool',
]

__version__ = '8.0.0'
