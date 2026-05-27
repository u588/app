#!/usr/bin/env python3
"""AiStock V10 — 统一日志服务 (LoggerService)

从 logging.yaml 加载配置, 或使用默认配置。
"""
from __future__ import annotations

import logging
import logging.config
from pathlib import Path
from typing import Optional

import yaml


class LoggerService:
    """V10 统一日志服务"""
    
    def __init__(self, config_dir: str = "config/yaml"):
        self._config_dir = Path(config_dir)
        self._initialized = False
    
    def initialize(self) -> None:
        """初始化日志系统"""
        if self._initialized:
            return
        
        log_config_path = self._config_dir / "logging.yaml"
        if log_config_path.exists():
            try:
                with open(log_config_path, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f)
                
                # 确保 logs 目录存在
                for handler_cfg in config.get("handlers", {}).values():
                    if "filename" in handler_cfg:
                        log_path = Path(handler_cfg["filename"])
                        log_path.parent.mkdir(parents=True, exist_ok=True)
                
                logging.config.dictConfig(config)
                self._initialized = True
                return
            except Exception as e:
                print(f"日志配置加载失败, 使用默认: {e}")
        
        # 默认配置
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        self._initialized = True
    
    def get_logger(self, name: str) -> logging.Logger:
        """获取命名 logger"""
        if not self._initialized:
            self.initialize()
        return logging.getLogger(name)
