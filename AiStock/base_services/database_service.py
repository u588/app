#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DatabaseService：PostgreSQL 数据库服务（连接池 + 重试 + 降级）
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import OperationalError, DatabaseError
import logging
from contextlib import contextmanager
from typing import Optional, List, Dict, Any
import time

logger = logging.getLogger(__name__)


class DatabaseService:
    """PostgreSQL 数据库服务（支持多实例）"""
    
    def __init__(self, db_url: str, pool_config: Optional[Dict] = None):
        """
        初始化数据库连接池
        
        参数:
            db_url: PostgreSQL 连接字符串
            pool_config: 连接池配置字典
        """
        self.db_url = db_url
        self.pool_config = pool_config or {}
        
        self._engine = None
        self._session_factory = None
        self._init_engine()
    
    def _init_engine(self):
        """初始化 SQLAlchemy 引擎"""
        try:
            self._engine = create_engine(
                self.db_url,
                poolclass=QueuePool,
                pool_size=self.pool_config.get('pool_size', 10),
                max_overflow=self.pool_config.get('max_overflow', 20),
                pool_pre_ping=self.pool_config.get('pool_pre_ping', True),
                pool_recycle=self.pool_config.get('pool_recycle', 3600),
                connect_args={'connect_timeout': self.pool_config.get('connect_timeout', 30)},
                echo=False
            )
            self._session_factory = scoped_session(sessionmaker(bind=self._engine))
            logger.info(f"✅ 数据库连接池初始化成功 | {self.db_url[:50]}...")
        except Exception as e:
            logger.error(f"❌ 数据库连接池初始化失败：{e}")
            raise
    
    @contextmanager
    def get_session(self, retry_times: int = 3):
        """获取数据库会话（上下文管理器 + 重试）"""
        last_exception = None
        
        for attempt in range(retry_times):
            try:
                session = self._session_factory()
                yield session
                session.commit()
                return
            except (OperationalError, DatabaseError) as e:
                last_exception = e
                logger.warning(f"⚠️ 数据库操作失败 (尝试 {attempt+1}/{retry_times}): {e}")
                session.rollback()
                time.sleep(2 ** attempt)  # 指数退避
            except Exception as e:
                session.rollback()
                logger.error(f"❌ 数据库事务失败：{e}")
                raise
            finally:
                session.close()
        
        # 所有重试失败
        logger.error(f"❌ 数据库操作失败，已重试 {retry_times} 次：{last_exception}")
        raise last_exception
    
    def execute_query(self, query: str, params: Optional[Dict] = None) -> List[Dict]:
        """执行查询（返回结果列表）"""
        with self.get_session() as session:
            result = session.execute(text(query), params or {})
            return [dict(row._mapping) for row in result]
    
    def execute_update(self, query: str, params: Optional[Dict] = None) -> int:
        """执行更新（返回影响行数）"""
        with self.get_session() as session:
            result = session.execute(text(query), params or {})
            return result.rowcount
    
    def bulk_insert(self, table_name: str, records: List[Dict]):
        """批量插入数据"""
        if not records:
            return
        
        with self.get_session() as session:
            from sqlalchemy import table, column, insert
            cols = list(records[0].keys())
            t = table(table_name, *[column(c) for c in cols])
            session.execute(insert(t), records)
    
    def health_check(self) -> bool:
        """健康检查"""
        try:
            with self.get_session() as session:
                session.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error(f"❌ 数据库健康检查失败：{e}")
            return False
    
    def close(self):
        """关闭连接池"""
        if self._engine:
            self._engine.dispose()
            logger.info("✅ 数据库连接池已关闭")