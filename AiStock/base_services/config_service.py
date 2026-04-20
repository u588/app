#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ConfigService：统一配置加载服务（支持多系统配置隔离 + 热重载）
"""

import yaml
import os
import time
import logging
import threading
from pathlib import Path
from typing import Any, Dict, Optional, List, Callable
from dotenv import load_dotenv

# watchdog 用于文件监听（生产环境推荐安装：pip install watchdog）
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    logging.warning("⚠️ watchdog 未安装，配置热重载功能禁用。请执行: pip install watchdog")

from config.global_settings import CONFIG_DIR

logger = logging.getLogger(__name__)


class _ConfigFileHandler(FileSystemEventHandler):
    """配置文件变更处理器（内部类）"""
    
    def __init__(self, config_service: 'ConfigService', file_patterns: List[str]):
        self.config_service = config_service
        self.file_patterns = file_patterns
        self._last_modified = {}
        self._debounce_seconds = 0.5  # 防抖：避免编辑器保存时触发多次
        
    def on_modified(self, event):
        if event.is_directory:
            return
            
        # 只处理目标配置文件
        file_name = os.path.basename(event.src_path)
        if file_name not in self.file_patterns:
            return
            
        # 防抖 + 去重
        now = time.time()
        last = self._last_modified.get(event.src_path, 0)
        if now - last < self._debounce_seconds:
            return
        self._last_modified[event.src_path] = now
        
        # 异步执行重载（避免阻塞 watchdog 线程）
        threading.Thread(
            target=self._safe_reload,
            args=(event.src_path,),
            daemon=True,
            name=f"ConfigReload-{file_name}"
        ).start()
    
    def _safe_reload(self, src_path: str):
        """线程安全地执行重载 + 通知回调"""
        try:
            logger.info(f"📝 检测到配置变更: {src_path}")
            time.sleep(0.2)  # 等待文件写入完成
            
            # 执行重载
            self.config_service.reload()
            
            # 通知所有注册的回调
            for callback in self.config_service._reload_callbacks:
                try:
                    callback(self.config_service.config)
                except Exception as e:
                    logger.error(f"❌ 配置变更回调执行失败: {e}")
                    
        except Exception as e:
            logger.error(f"❌ 配置热重载异常: {e}")


class ConfigService:
    """统一配置加载服务（支持多系统 + 热重载）"""
    
    def __init__(
        self,
        system_name: str,
        config_subdir: Optional[str] = None,
        env_file: Optional[str] = None,
        enable_hot_reload: bool = True,
        reload_callbacks: Optional[List[Callable[[Dict], None]]] = None
    ):
        """
        初始化配置服务
        
        参数:
            system_name: 系统名称（如 'dynamic_price'）
            config_subdir: 配置子目录（如 'dynamic_price'），默认与 system_name 相同
            env_file: .env 文件路径
            enable_hot_reload: 是否启用文件监听热重载
            reload_callbacks: 配置变更时的回调函数列表
        """
        # 加载环境变量
        if env_file:
            load_dotenv(env_file)
        else:
            load_dotenv()
        
        self.system_name = system_name
        self.config_subdir = config_subdir or system_name
        self.config_dir = CONFIG_DIR / self.config_subdir
        
        # 回调管理
        self._reload_callbacks: List[Callable[[Dict], None]] = reload_callbacks or []
        self._observer: Optional[Observer] = None
        self._watchdog_thread: Optional[threading.Thread] = None
        
        # 加载配置
        self.config = self._load_all_configs()
        self._inject_global_db_config()
        
        # 启动文件监听（可选）
        if enable_hot_reload and WATCHDOG_AVAILABLE:
            self._start_file_watcher()
        
        logger.info(f"✅ ConfigService 初始化成功 | 系统={system_name} | 模式={self.config.get('system', {}).get('mode')} | 热重载={'启用' if enable_hot_reload else '禁用'}")
    
    def _start_file_watcher(self):
        """启动配置文件监听"""
        if not WATCHDOG_AVAILABLE:
            return
            
        try:
            self._observer = Observer()
            handler = _ConfigFileHandler(
                self,
                file_patterns=['system_config.yaml', 'stocks_config.yaml', 'chart_config.yaml']
            )
            self._observer.schedule(
                handler,
                path=str(self.config_dir),
                recursive=False
            )
            self._observer.start()
            self._watchdog_thread = threading.Thread(
                target=self._observer.join,
                daemon=True,
                name="ConfigWatcher"
            )
            self._watchdog_thread.start()
            logger.info(f"👀 配置热重载监听已启动: {self.config_dir}")
        except Exception as e:
            logger.warning(f"⚠️ 启动配置监听失败: {e}")
    
    def _load_all_configs(self) -> Dict[str, Any]:
        """加载所有配置文件"""
        config = {}
        
        # 1. 加载系统配置
        system_config_path = self.config_dir / "system_config.yaml"
        if system_config_path.exists():
            with open(system_config_path, 'r', encoding='utf-8') as f:
                config.update(yaml.safe_load(f))
            logger.debug(f"✅ 加载系统配置：{system_config_path}")
        
        # 2. 加载标的配置
        stocks_config_path = self.config_dir / "stocks_config.yaml"
        if stocks_config_path.exists():
            with open(stocks_config_path, 'r', encoding='utf-8') as f:
                stocks_config = yaml.safe_load(f)
                config['stocks'] = stocks_config.get('stocks', [])
                config['macro_indicators'] = stocks_config.get('macro_indicators', {})
                config['sector_macro_link'] = stocks_config.get('sector_macro_link', {})
            logger.debug(f"✅ 加载标的配置：{stocks_config_path}")
        
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
        from config.global_settings import DATABASE_ENGINES, DB_POOL_CONFIG
        
        if 'database' not in self.config:
            self.config['database'] = {}
        
        if self.config['database'].get('use_global_config', True):
            self.config['database'] = {
                'DATABASE_ENGINES': DATABASE_ENGINES,
                'DB_POOL_CONFIG': DB_POOL_CONFIG
            }
            logger.debug("✅ 注入全局数据库配置")
    
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

    def get_macro_link(self, name: str) -> Optional[Dict]:
        """获取指定宏观指标的配置"""
        return self.config.get('sector_macro_link', {}).get(name)
    
    def reload(self):
        """重新加载配置（热更新）"""
        old_config = self.config.copy()
        self.config = self._load_all_configs()
        self._inject_global_db_config()
        
        # 记录变更摘要（便于调试）
        changed_keys = []
        for key in ['system.mode', 'cache.enable', 'risk_control.max_position_single']:
            old_val = old_config.get(key.split('.')[0], {}).get(key.split('.')[1]) if '.' in key else old_config.get(key)
            new_val = self.get(key)
            if old_val != new_val:
                changed_keys.append(f"{key}: {old_val} → {new_val}")
        
        if changed_keys:
            logger.info(f"🔄 配置热更新完成 | 变更: {', '.join(changed_keys)}")
        else:
            logger.debug("🔄 配置已重载（无实质变更）")
    
    def register_reload_callback(self, callback: Callable[[Dict], None]):
        """注册配置变更回调"""
        if callback not in self._reload_callbacks:
            self._reload_callbacks.append(callback)
            logger.debug(f"✅ 注册配置变更回调: {callback.__name__}")
    
    def unregister_reload_callback(self, callback: Callable[[Dict], None]):
        """注销配置变更回调"""
        if callback in self._reload_callbacks:
            self._reload_callbacks.remove(callback)
            logger.debug(f"✅ 注销配置变更回调: {callback.__name__}")
    
    def stop_watcher(self):
        """停止文件监听（用于优雅停机）"""
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=2)
            logger.info("🛑 配置监听已停止")
    
    def close(self):
        """资源清理"""
        self.stop_watcher()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
    
    def __repr__(self) -> str:
        return f"ConfigService(system={self.system_name}, mode={self.config.get('system', {}).get('mode')})"