"""AiStock V8 数据服务层

整合三大数据源:
- TDXAdapter: 通达信双端口数据 (标准端口7709 + 扩展端口7721)
- AKAdapter: AKShare海外期货及辅助数据 (29个验证品种)
- DatabaseReader: PostgreSQL估值数据 (PE/PB百分位)

DataLoaderService统一编排所有数据源的加载流程。
"""

from .tdx_adapter import TDXAdapter
from .ak_adapter import AKAdapter
from .database_reader import DatabaseReader
from .data_loader_service import DataLoaderService

__all__ = ['TDXAdapter', 'AKAdapter', 'DatabaseReader', 'DataLoaderService']
__version__ = '8.0.0'
