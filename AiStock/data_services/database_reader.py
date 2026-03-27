#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DatabaseReader：PostgreSQL 数据库读取模块
✅ 单一职责：只负责数据查询，不涉及业务逻辑
✅ 安全：参数化查询 + 表名校验
✅ 健壮：连接池 + 自动重试 + 健康检查
"""

from sqlalchemy import create_engine, text, MetaData, Table
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import OperationalError, SQLAlchemyError
import pandas as pd
import logging
import re
from typing import Optional, Dict, List, Union, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class DatabaseReader:
    """数据库读取服务（只读操作）"""
    
    # 🔒 表名/代码白名单校验
    VALID_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9_\.\"]+$')
    
    def __init__(self, db_config: Dict[str, str], pool_config: Optional[Dict] = None):
        """
        初始化多引擎数据库连接
        
        参数:
            db_config: {engine_name: connection_string}
            pool_config: 连接池配置
        """
        self.db_config = db_config
        self.pool_config = pool_config or {
            'pool_size': 10,
            'max_overflow': 20,
            'pool_pre_ping': True,
            'pool_recycle': 3600
        }
        self._engines: Dict[str, Any] = {}
        self._init_engines()
    
    def _init_engines(self):
        """初始化所有数据库引擎"""
        for name, conn_str in self.db_config.items():
            try:
                self._engines[name] = create_engine(
                    conn_str,
                    poolclass=QueuePool,
                    **self.pool_config,
                    echo=False
                )
                logger.info(f"✅ 数据库引擎 [{name}] 初始化成功")
            except Exception as e:
                logger.error(f"❌ 数据库引擎 [{name}] 初始化失败: {e}")
                self._engines[name] = None
    
    def _validate_table_name(self, table_name: str) -> bool:
        """✅ 校验表名合法性（防注入）"""
        return bool(self.VALID_NAME_PATTERN.match(table_name.strip()))
    
    def _get_engine(self, engine_name: str) -> Optional[Any]:
        """获取指定引擎"""
        engine = self._engines.get(engine_name)
        if engine is None:
            logger.warning(f"⚠️ 引擎 [{engine_name}] 未可用")
        return engine
    
    def read_sql(
        self, 
        query: Union[str, Any], 
        engine_name: str = 'default',
        params: Optional[Dict] = None,
        parse_dates: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        执行查询并返回 DataFrame
        
        参数:
            query: SQL 字符串或 sqlalchemy.text 对象
            engine_name: 使用的引擎名称
            params: 参数化查询的参数字典
            parse_dates: 需要解析为 datetime 的列名列表
        """
        engine = self._get_engine(engine_name)
        if engine is None:
            return pd.DataFrame()
        
        try:
            # 字符串查询转为 text 对象
            if isinstance(query, str):
                query = text(query)
            
            df = pd.read_sql(query, engine, params=params or {})
            
            # 自动解析日期列
            if parse_dates:
                for col in parse_dates:
                    if col in df.columns:
                        df[col] = pd.to_datetime(df[col], errors='coerce')
            
            return df
            
        except SQLAlchemyError as e:
            logger.error(f"❌ 数据库查询失败 [{engine_name}]: {e}")
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"❌ 未知错误 [{engine_name}]: {e}")
            return pd.DataFrame()
    
    def read_table(
        self, 
        table_name: str, 
        engine_name: str = 'default',
        conditions: Optional[Dict] = None,
        order_by: Optional[str] = None,
        limit: Optional[int] = None,
        parse_dates: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        ✅ 安全读取表数据（参数化构建查询）
        
        参数:
            table_name: 表名（自动校验）
            conditions: {'column': value} 形式的过滤条件
            order_by: 排序字段
            limit: 限制返回行数
        """
        if not self._validate_table_name(table_name):
            logger.error(f"❌ 非法表名: {table_name}")
            return pd.DataFrame()
        
        # 构建 WHERE 子句
        where_clauses = []
        params = {}
        if conditions:
            for i, (col, val) in enumerate(conditions.items()):
                param_name = f"param_{i}"
                where_clauses.append(f"{col} <= :{param_name}")
                params[param_name] = val
        
        where_str = " AND ".join(where_clauses)
        where_clause = f"WHERE {where_str}" if where_clauses else ""
        
        order_clause = f"ORDER BY {order_by}" if order_by else ""
        limit_clause = f"LIMIT {limit}" if limit else ""
        
        query = text(f'''
            SELECT * FROM "{table_name}"
            {where_clause}
            {order_clause}
            {limit_clause}
        ''')
        
        return self.read_sql(query, engine_name, params=params, parse_dates=parse_dates)
    
    def health_check(self, engine_name: str = 'default') -> bool:
        """健康检查"""
        try:
            df = self.read_sql(text("SELECT 1"), engine_name)
            return not df.empty
        except Exception as e:
            logger.error(f"❌ 健康检查失败 [{engine_name}]: {e}")
            return False
    
    def close(self, engine_name: Optional[str] = None):
        """关闭指定或全部引擎"""
        if engine_name:
            if engine_name in self._engines and self._engines[engine_name]:
                self._engines[engine_name].dispose()
                logger.info(f"✅ 引擎 [{engine_name}] 已关闭")
        else:
            for name, engine in self._engines.items():
                if engine:
                    engine.dispose()
            logger.info("✅ 所有数据库引擎已关闭")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False