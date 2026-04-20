#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ExportService：文件导出与路径管理
"""
from pathlib import Path
from typing import Union, List
import logging
import shutil

logger = logging.getLogger(__name__)

class ExportService:
    def __init__(self, base_dir: Union[str, Path] = "output"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
    
    def ensure_dir(self, subdir: str) -> Path:
        path = self.base_dir / subdir
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    def move_to_archive(self, source: Union[str, Path], archive_dir: str = "archive") -> Path:
        archive_path = self.ensure_dir(archive_dir)
        dest = archive_path / Path(source).name
        shutil.move(str(source), str(dest))
        logger.info(f"📦 归档: {source} -> {dest}")
        return dest
    
    def list_exports(self, subdir: str = "visualization", pattern: str = "*.html") -> List[Path]:
        return list((self.base_dir / subdir).glob(pattern))