#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ResultRepository：分析结果持久化服务
功能：
  - 保存/加载批量分析结果（JSON + SQLite）
  - 支持版本管理 + 按日期分区
  - 提供查询接口（按代码/板块/评分筛选）
"""

import json
import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
import pandas as pd

logger = logging.getLogger(__name__)


class ResultRepository:
    """分析结果仓库"""
    
    def __init__(self, base_dir: Union[str, Path], version: Optional[str] = None):
        """
        初始化结果仓库
        
        参数:
            base_dir: 结果存储根目录
            version: 版本标识（默认用当前日期）
        """
        self.base_dir = Path(base_dir)
        self.version = version or datetime.now().strftime('%Y%m%d')
        self.version_dir = self.base_dir / self.version
        self.version_dir.mkdir(parents=True, exist_ok=True)
        
        # 文件路径
        self.batch_results_path = self.version_dir / 'batch_results.json'
        self.recommended_path = self.version_dir / 'recommended_stocks.json'
        self.cache_db_path = self.version_dir / 'cache.db'
        
        # 初始化 SQLite 缓存
        self._init_cache_db()
        
        logger.info(f"✅ ResultRepository 初始化 | 版本: {self.version} | 目录: {self.version_dir}")
    
    def _init_cache_db(self):
        """初始化 SQLite 缓存数据库"""
        conn = sqlite3.connect(str(self.cache_db_path))
        cursor = conn.cursor()
        
        # 创建结果表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS analysis_results (
                code TEXT PRIMARY KEY,
                name TEXT,
                sector TEXT,
                entry_price REAL,
                stop_loss REAL,
                target_price REAL,
                pl_ratio REAL,
                fundamental_score REAL,
                confidence_factor REAL,
                recommendation TEXT,
                raw_data TEXT,  -- JSON 字符串存储完整结果
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 创建索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_sector ON analysis_results(sector)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_pl_ratio ON analysis_results(pl_ratio)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_confidence ON analysis_results(confidence_factor)')
        
        conn.commit()
        conn.close()
        logger.debug(f"✅ 缓存数据库初始化: {self.cache_db_path}")
    
    def save_batch_results(self, results: List[Dict[str, Any]], metadata: Optional[Dict] = None):
        """
        保存批量分析结果
        
        参数:
            results: 批量计算结果列表
            metadata: 元数据（计算时间/参数/版本等）
        """
        # 1. 保存 JSON 原始结果
        output = {
            'metadata': {
                'version': self.version,
                'timestamp': datetime.now().isoformat(),
                'count': len(results),
                **(metadata or {})
            },
            'results': results
        }
        
        with open(self.batch_results_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2, default=str)
        
        # 2. 写入 SQLite 缓存（便于查询）
        conn = sqlite3.connect(str(self.cache_db_path))
        cursor = conn.cursor()
        
        for r in results:
            cursor.execute('''
                INSERT OR REPLACE INTO analysis_results 
                (code, name, sector, entry_price, stop_loss, target_price, 
                 pl_ratio, fundamental_score, confidence_factor, recommendation, raw_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                r['code'], r['name'], r['sector'],
                r['prices']['entry'], r['prices']['stop_loss'], r['prices']['target'],
                r['scores']['pl_ratio'], r['scores']['fundamental'],
                r.get('technical_quality', {}).get('factor', 1.0),
                r['recommendation'],
                json.dumps(r, default=str)  # -- 存储完整原始数据
            ))
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ 保存批量结果: {len(results)} 只标的 | {self.batch_results_path}")
    
    def save_recommended_stocks(self, recommended: List[Dict], criteria: Dict):
        """
        保存推荐标的列表
        
        参数:
            recommended: 筛选后的推荐标的
            criteria: 筛选条件
        """
        output = {
            'metadata': {
                'version': self.version,
                'timestamp': datetime.now().isoformat(),
                'criteria': criteria,
                'count': len(recommended)
            },
            'recommended': recommended
        }
        
        with open(self.recommended_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2, default=str)
        
        logger.info(f"✅ 保存推荐标的: {len(recommended)} 只 | {self.recommended_path}")
    
    def load_batch_results(self, version: Optional[str] = None) -> List[Dict]:
        """加载批量分析结果"""
        version = version or self.version
        path = self.base_dir / version / 'batch_results.json'
        
        if not path.exists():
            logger.warning(f"⚠️ 结果文件不存在: {path}")
            return []
        
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        logger.info(f"✅ 加载批量结果: {len(data.get('results', []))} 只标的 | 版本: {version}")
        return data.get('results', [])
    
    def load_recommended_stocks(self, version: Optional[str] = None) -> List[Dict]:
        """加载推荐标的列表"""
        version = version or self.version
        path = self.base_dir / version / 'recommended_stocks.json'
        
        if not path.exists():
            logger.warning(f"⚠️ 推荐文件不存在: {path}")
            return []
        
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        logger.info(f"✅ 加载推荐标的: {len(data.get('recommended', []))} 只 | 版本: {version}")
        return data.get('recommended', [])
    
    def query_results(
        self,
        filters: Optional[Dict] = None,
        order_by: str = 'pl_ratio',
        limit: Optional[int] = None
    ) -> pd.DataFrame:
        """
        查询分析结果（支持筛选 + 排序 + 分页）
        
        参数:
            filters: 筛选条件 {field: {operator: value}}
            order_by: 排序字段
            limit: 返回条数限制
        
        返回:
            pd.DataFrame: 查询结果
        """
        conn = sqlite3.connect(str(self.cache_db_path))
        
        # 构建查询
        query = "SELECT * FROM analysis_results WHERE 1=1"
        params = []
        
        if filters:
            for field, conditions in filters.items():
                for op, value in conditions.items():
                    if op == '>=':
                        query += f" AND {field} >= ?"
                        params.append(value)
                    elif op == '<=':
                        query += f" AND {field} <= ?"
                        params.append(value)
                    elif op == '==':
                        query += f" AND {field} = ?"
                        params.append(value)
                    elif op == 'in':
                        placeholders = ','.join(['?'] * len(value))
                        query += f" AND {field} IN ({placeholders})"
                        params.extend(value)
        
        query += f" ORDER BY {order_by} DESC"
        if limit:
            query += f" LIMIT {limit}"
        
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        
        # 解析 raw_data 字段（可选）
        if 'raw_data' in df.columns:
            df['raw_data_parsed'] = df['raw_data'].apply(
                lambda x: json.loads(x) if isinstance(x, str) else x
            )
        
        logger.debug(f"🔍 查询结果: {len(df)} 条 | 条件: {filters}")
        return df
    
    def get_stock_detail(self, code: str, version: Optional[str] = None) -> Optional[Dict]:
        """
        获取单标的详细结果
        
        参数:
            code: 股票代码
            version: 结果版本
        
        返回:
            Dict: 完整分析结果，不存在返回 None
        """
        version = version or self.version
        path = self.base_dir / version / 'batch_results.json'
        
        if not path.exists():
            return None
        
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        for r in data.get('results', []):
            if r['code'] == code:
                return r
        
        return None
    
    def list_versions(self) -> List[str]:
        """列出所有可用版本"""
        if not self.base_dir.exists():
            return []
        return [d.name for d in self.base_dir.iterdir() if d.is_dir() and d.name != 'latest']
    
    def create_latest_symlink(self):
        """创建 latest 软链接指向当前版本"""
        latest_path = self.base_dir / 'latest'
        if latest_path.exists() or latest_path.is_symlink():
            latest_path.unlink()
        latest_path.symlink_to(self.version_dir, target_is_directory=True)
        logger.info(f"🔗 创建 latest 软链接 -> {self.version}")