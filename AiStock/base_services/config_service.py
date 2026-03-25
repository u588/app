#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ConfigService：统一配置加载服务（支持多系统配置隔离）
"""

import yaml
import os
import logging
from pathlib import Path
from typing import Any, Dict, Optional
from dotenv import load_dotenv

from config.global_settings import CONFIG_DIR

logger = logging.getLogger(__name__)


class ConfigService:
    """统一配置加载服务（支持多系统）"""
    
    def __init__(
        self,
        system_name: str,
        config_subdir: Optional[str] = None,
        env_file: Optional[str] = None
    ):
        """
        初始化配置服务
        
        参数:
            system_name: 系统名称（如 'dynamic_price'）
            config_subdir: 配置子目录（如 'dynamic_price'），默认与 system_name 相同
            env_file: .env 文件路径
        """
        # 加载环境变量
        if env_file:
            load_dotenv(env_file)
        else:
            load_dotenv()
        
        self.system_name = system_name
        self.config_subdir = config_subdir or system_name
        self.config_dir = CONFIG_DIR / self.config_subdir
        
        # 加载配置
        self.config = self._load_all_configs()
        
        # 注入全局数据库配置
        self._inject_global_db_config()
        
        logger.info(f"✅ ConfigService 初始化成功 | 系统={system_name} | 模式={self.config.get('system', {}).get('mode')}")
    
    def _load_all_configs(self) -> Dict[str, Any]:
        """加载所有配置文件"""
        config = {}
        
        # 1. 加载系统配置
        system_config_path = self.config_dir / "system_config.yaml"
        if system_config_path.exists():
            with open(system_config_path, 'r', encoding='utf-8') as f:
                config.update(yaml.safe_load(f))
            logger.info(f"✅ 加载系统配置：{system_config_path}")
        else:
            logger.warning(f"⚠️ 系统配置不存在：{system_config_path}")
        
        # 2. 加载标的配置
        stocks_config_path = self.config_dir / "stocks_config.yaml"
        if stocks_config_path.exists():
            with open(stocks_config_path, 'r', encoding='utf-8') as f:
                stocks_config = yaml.safe_load(f)
                config['stocks'] = stocks_config.get('stocks', [])
                config['macro_indicators'] = stocks_config.get('macro_indicators', {})
            logger.info(f"✅ 加载标的配置：{stocks_config_path}")
        
        # 3. 合并环境变量覆盖
        config = self._merge_env_overrides(config)
        
        return config
    
    def _merge_env_overrides(self, config: Dict) -> Dict:
        """合并环境变量覆盖的配置"""
        env_overrides = {
            f'CONFIG_{self.system_name.upper()}_MODE': ('system', 'mode'),
            f'CONFIG_{self.system_name.upper()}_LOG_LEVEL': ('system', 'log_level'),
            f'CONFIG_{self.system_name.upper()}_CACHE_ENABLE': ('cache', 'enable'),
        }
        
        for env_key, (section, key) in env_overrides.items():
            env_value = os.getenv(env_key)
            if env_value is not None:
                if section not in config:
                    config[section] = {}
                # 类型转换
                if env_value.lower() in ('true', 'false'):
                    config[section][key] = env_value.lower() == 'true'
                elif env_value.isdigit():
                    config[section][key] = int(env_value)
                else:
                    try:
                        config[section][key] = float(env_value)
                    except ValueError:
                        config[section][key] = env_value
                logger.info(f"🔄 配置覆盖：{section}.{key} = {config[section][key]} (来自 {env_key})")
        
        return config
    
    def _inject_global_db_config(self):
        """注入全局数据库配置"""
        from config.global_settings import DB_INDEX, DB_STOCK, DB_STOCK_BASE, DB_STOCK_FS, DB_INDEX_PE, DB_POOL_CONFIG
        
        if 'database' not in self.config:
            self.config['database'] = {}
        
        # 如果配置中指定使用全局配置
        if self.config['database'].get('use_global_config', True):
            self.config['database']['stock_db'] = DB_STOCK
            self.config['database']['pe_db'] = DB_INDEX_PE
            self.config['database'].update(DB_POOL_CONFIG)
            logger.debug(f"✅ 注入全局数据库配置")
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """获取配置项（支持嵌套路径）"""
        keys = key_path.split('.')
        value = self.config
        
        try:
            for key in keys:
                if isinstance(value, list):
                    key = int(key)
                value = value[key]
            return value
        except (KeyError, IndexError, TypeError, ValueError):
            return default
    
    def get_stock_config(self, code: str) -> Optional[Dict]:
        """获取指定标的的配置"""
        for stock in self.config.get('stocks', []):
            if stock.get('code') == code:
                return stock
        return None
    
    def get_macro_indicator(self, name: str) -> Optional[Dict]:
        """获取指定宏观指标的配置"""
        return self.config.get('macro_indicators', {}).get(name)
    
    def reload(self):
        """重新加载配置（热更新）"""
        self.config = self._load_all_configs()
        self._inject_global_db_config()
        logger.info("✅ 配置已重新加载")
    
    def __repr__(self) -> str:
        return f"ConfigService(system={self.system_name}, mode={self.config.get('system', {}).get('mode')})"