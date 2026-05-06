#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析结果仓库
=============
提供分析结果的持久化存储和查询能力。
支持 JSON 格式的本地文件存储，按日期和维度组织结果文件，
便于历史对比和结果回溯。
"""

import os
import json
from typing import Dict, Optional, List
from datetime import datetime

from base_services.logger_service import LoggerService
# from base_services.logger_service import LoggerService, get_global_logger_service


class ResultRepository:
    """分析结果仓库

    将分析结果保存为 JSON 文件，按日期和维度组织。
    支持保存、查询、列表等操作。

    Usage:
        repo = ResultRepository(output_dir='/path/to/output')
        repo.save('macro_analysis', outlook, analysis)
        result = repo.load_latest('macro_analysis')
    """

    def __init__(self, output_dir: Optional[str] = None,
                 logger: Optional[LoggerService] = None):
        """初始化结果仓库

        Args:
            output_dir: 结果输出目录，默认为 AiStock/output/analysis_results/
            logger: 日志服务实例
        """
        if output_dir is None:
            # 定位到 AiStock 项目根目录
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            output_dir = os.path.join(base_dir, 'output', 'analysis_results')

        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        self._logger = logger.get_logger('result_repository')
        # self._logger = (logger or get_global_logger_service()).get_logger('result_repository')

    def save(self, name: str, outlook: Dict, analysis: Dict,
             snapshot: Optional[Dict] = None):
        """保存分析结果

        Args:
            name: 分析名称（如 'macro_analysis'）
            outlook: 综合展望字典
            analysis: 各维度分析结果字典
            snapshot: 最新指标快照（可选）
        """
        now = datetime.now()
        result = {
            'name': name,
            'timestamp': now.isoformat(),
            'date': now.strftime('%Y-%m-%d'),
            'outlook': self._serialize(outlook),
            'analysis': self._serialize(analysis),
        }
        if snapshot:
            result['snapshot'] = self._serialize(snapshot)

        # 按日期组织文件
        date_dir = os.path.join(self.output_dir, now.strftime('%Y%m%d'))
        os.makedirs(date_dir, exist_ok=True)

        filepath = os.path.join(date_dir, f'{name}_{now.strftime("%H%M%S")}.json')
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2, default=str)

        self._logger.info(f"分析结果已保存: {filepath}")

    def load(self, filepath: str) -> Optional[Dict]:
        """加载指定路径的分析结果

        Args:
            filepath: JSON 文件路径

        Returns:
            结果字典
        """
        if not os.path.exists(filepath):
            return None

        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)

    def load_latest(self, name: str) -> Optional[Dict]:
        """加载最新一次分析结果

        Args:
            name: 分析名称

        Returns:
            最新的结果字典
        """
        results = self.list_results(name)
        if not results:
            return None

        latest_path = results[-1]
        return self.load(latest_path)

    def list_results(self, name: Optional[str] = None) -> List[str]:
        """列出所有分析结果文件

        Args:
            name: 分析名称过滤（可选）

        Returns:
            结果文件路径列表（按时间排序）
        """
        all_files = []
        for root, _, files in os.walk(self.output_dir):
            for f in files:
                if f.endswith('.json'):
                    if name is None or f.startswith(name):
                        all_files.append(os.path.join(root, f))

        return sorted(all_files)

    def _serialize(self, obj):
        """递归序列化，处理不可 JSON 序列化的类型"""
        if isinstance(obj, dict):
            return {k: self._serialize(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self._serialize(v) for v in obj]
        elif isinstance(obj, float):
            return round(obj, 6)
        elif isinstance(obj, datetime):
            return obj.isoformat()
        elif hasattr(obj, 'isoformat'):
            return obj.isoformat()
        return obj

    def __repr__(self):
        count = len(self.list_results())
        return f"ResultRepository(dir={self.output_dir}, results={count})"