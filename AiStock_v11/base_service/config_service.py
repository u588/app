#!/usr/bin/env python3
"""
AiStock V10 — 统一配置加载服务 (ConfigService)

核心特性:
  1. YAML配置文件为唯一数据源 — 代码与配置完全解耦
  2. 点路径访问: get("codes.futures.0.code") → "IFL8"
  3. 子系统隔离: get_subsystem_config("market_state") → 合并命名空间
  4. 热重载: 文件变更自动重载 + EventBus 通知
  5. 多层合并: system.yaml + 子系统.yaml → 最终配置
  6. 线程安全
"""
from __future__ import annotations

import os
import threading
import logging
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union
from copy import deepcopy

import yaml

logger = logging.getLogger(__name__)


class ConfigService:
    """V10 统一配置加载服务 — YAML 配置与代码完全解耦。

    设计原则:
    - **配置即数据**: YAML 是唯一数据源, 代码零硬编码
    - **改一处即全局生效**: 修改 codes.yaml 中 IFL8 → 所有消费方自动更新
    - **子系统隔离**: 各子系统只加载自己的命名空间
    - **热重载**: 文件变更 → 自动重载 → EventBus 通知消费方

    Usage:
        config = ConfigService(config_dir="config/yaml")
        config.load_all()
        
        # 点路径访问
        code = config.get("codes.futures.0.code")  # → "IFL8"
        
        # 子系统配置 (4层合并: system + shared + codes + subsystem)
        ms_config = config.get_subsystem_config("market_state")
        
        # 热重载回调
        config.on_change("codes.futures", lambda key: logger.info("futures config changed"))
    """

    def __init__(
        self,
        config_dir: str = "config/yaml",
        enable_hot_reload: bool = True,
        hot_reload_interval: float = 5.0,
        event_bus: Optional[Any] = None,
    ):
        self._config_dir = Path(config_dir)
        self._enable_hot_reload = enable_hot_reload
        self._hot_reload_interval = hot_reload_interval
        self._event_bus = event_bus
        
        self._configs: Dict[str, Dict] = {}  # file_name (no ext) → parsed dict
        self._merged: Dict[str, Any] = {}     # merged full config tree
        self._file_mtimes: Dict[str, float] = {}  # file_name → last mtime
        self._change_callbacks: Dict[str, List[Callable]] = {}
        self._lock = threading.RLock()
        self._hot_reload_thread: Optional[threading.Thread] = None
        self._running = False
        
    # ═══════════════════════════════════════════════════════════════
    # 加载
    # ═══════════════════════════════════════════════════════════════
    
    def load_all(self) -> None:
        """加载 config_dir 下所有 YAML 文件"""
        if not self._config_dir.exists():
            logger.warning("配置目录不存在: %s", self._config_dir)
            return
        
        yaml_files = sorted(self._config_dir.glob("*.yaml"))
        yaml_files += sorted(self._config_dir.glob("*.yml"))
        
        for yaml_file in yaml_files:
            self._load_file(yaml_file)
        
        self._rebuild_merged()
        logger.info("ConfigService 加载完成: %d 个配置文件", len(self._configs))
        
        if self._enable_hot_reload:
            self._start_hot_reload()
    
    def load_file(self, name: str) -> None:
        """加载指定配置文件 (不含扩展名)"""
        for ext in (".yaml", ".yml"):
            path = self._config_dir / f"{name}{ext}"
            if path.exists():
                self._load_file(path)
                self._rebuild_merged()
                return
        logger.warning("配置文件不存在: %s", name)
    
    def reload(self) -> None:
        """强制重新加载所有配置文件"""
        with self._lock:
            self._configs.clear()
            self._file_mtimes.clear()
        self.load_all()
        self._notify_change("*")
    
    def _load_file(self, path: Path) -> None:
        """加载单个 YAML 文件"""
        name = path.stem
        try:
            mtime = path.stat().st_mtime
            with self._lock:
                if name in self._file_mtimes and self._file_mtimes[name] == mtime:
                    return  # 未变更
                self._file_mtimes[name] = mtime
            
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            
            with self._lock:
                old_data = self._configs.get(name)
                self._configs[name] = data
            
            if old_data is not None:
                logger.info("配置文件已更新: %s", name)
                self._notify_change(name)
            else:
                logger.debug("配置文件已加载: %s", name)
                
        except Exception as e:
            logger.error("加载配置文件失败 %s: %s", path, e)
    
    # ═══════════════════════════════════════════════════════════════
    # 访问
    # ═══════════════════════════════════════════════════════════════
    
    def get(self, key: str, default: Any = None, value_type: Optional[type] = None) -> Any:
        """点路径访问配置值

        Args:
            key: 点路径, 如 "codes.futures.0.code"
            default: 默认值
            value_type: 期望的类型 (如 int, float, bool), 自动转换

        Returns:
            配置值, 或 default
        """
        with self._lock:
            parts = key.split(".")
            current = self._merged
            for part in parts:
                if isinstance(current, dict):
                    if part in current:
                        current = current[part]
                    else:
                        return default
                elif isinstance(current, list):
                    try:
                        idx = int(part)
                        current = current[idx]
                    except (ValueError, IndexError):
                        return default
                else:
                    return default
            value = deepcopy(current) if isinstance(current, (dict, list)) else current

        # 类型转换
        if value_type is not None and value is not default:
            try:
                if value_type == bool:
                    if isinstance(value, str):
                        return value.lower() in ('true', '1', 'yes')
                    return bool(value)
                return value_type(value)
            except (ValueError, TypeError):
                logger.warning("类型转换失败: key=%s, value=%s, target_type=%s", key, value, value_type)
                return default
        return value
    
    def get_section(self, section: str) -> Dict[str, Any]:
        """获取配置段 (如 "codes", "tdx")"""
        result = self.get(section, {})
        return result if isinstance(result, dict) else {}
    
    def get_subsystem_config(self, subsystem_name: str) -> Dict[str, Any]:
        """获取子系统配置 — 4层深度合并

        合并层级:
        1. system.yaml (系统级)
        2. tdx.yaml + database.yaml + cache.yaml + logging.yaml (服务级)
        3. codes.yaml (数据级)
        4. {subsystem_name}.yaml (子系统覆盖)

        Returns:
            合并后的子系统配置字典
        """
        with self._lock:
            merged = {}
            
            # Layer 1: system
            if "system" in self._configs:
                merged = self._deep_merge(merged, self._configs["system"])
            
            # Layer 2: shared services
            for svc_name in ("tdx", "database", "cache", "logging"):
                if svc_name in self._configs:
                    merged = self._deep_merge(merged, self._configs[svc_name])
            
            # Layer 3: codes
            if "codes" in self._configs:
                merged = self._deep_merge(merged, self._configs["codes"])
            
            # Layer 4: subsystem overlay
            if subsystem_name in self._configs:
                merged = self._deep_merge(merged, self._configs[subsystem_name])
            
            return deepcopy(merged)
    
    def require(self, key: str) -> Any:
        """获取必需配置项, 不存在则抛异常"""
        value = self.get(key)
        if value is None:
            raise KeyError(f"必需配置项不存在: {key}")
        return value
    
    # ═══════════════════════════════════════════════════════════════
    # 热重载
    # ═══════════════════════════════════════════════════════════════
    
    def on_change(self, key: str, callback: Callable[[str], None]) -> None:
        """注册配置变更回调

        Args:
            key: 监听的配置键 (如 "codes.futures"), "*" 表示全部
            callback: 变更回调函数
        """
        with self._lock:
            if key not in self._change_callbacks:
                self._change_callbacks[key] = []
            self._change_callbacks[key].append(callback)
    
    def _notify_change(self, file_name: str) -> None:
        """通知配置变更"""
        # 调用注册的回调
        for key, callbacks in self._change_callbacks.items():
            if key == "*" or key == file_name or key.startswith(file_name + "."):
                for cb in callbacks:
                    try:
                        cb(file_name)
                    except Exception as e:
                        logger.error("配置变更回调异常: %s", e)
        
        # 通过 EventBus 通知
        if self._event_bus is not None:
            try:
                from .event_bus import Topics
                self._event_bus.publish(Topics.CONFIG_CHANGED, {
                    "file": file_name,
                    "timestamp": time.time(),
                })
            except Exception as e:
                logger.debug("EventBus 通知失败: %s", e)
    
    def _start_hot_reload(self) -> None:
        """启动热重载线程"""
        if self._hot_reload_thread is not None:
            return
        self._running = True
        self._hot_reload_thread = threading.Thread(
            target=self._hot_reload_loop,
            daemon=True,
            name="ConfigService-HotReload",
        )
        self._hot_reload_thread.start()
        logger.info("配置热重载已启动 (间隔 %.1fs)", self._hot_reload_interval)
    
    def _hot_reload_loop(self) -> None:
        """热重载循环"""
        while self._running:
            try:
                time.sleep(self._hot_reload_interval)
                changed = False
                for yaml_file in self._config_dir.glob("*.yaml"):
                    name = yaml_file.stem
                    try:
                        mtime = yaml_file.stat().st_mtime
                        with self._lock:
                            old_mtime = self._file_mtimes.get(name, 0)
                        if mtime > old_mtime:
                            self._load_file(yaml_file)
                            changed = True
                    except Exception:
                        pass
                
                if changed:
                    self._rebuild_merged()
            except Exception as e:
                logger.error("热重载异常: %s", e)
    
    def stop(self) -> None:
        """停止热重载"""
        self._running = False
        if self._hot_reload_thread is not None:
            self._hot_reload_thread.join(timeout=2.0)
            self._hot_reload_thread = None
    
    # ═══════════════════════════════════════════════════════════════
    # 内部工具
    # ═══════════════════════════════════════════════════════════════
    
    def _rebuild_merged(self) -> None:
        """重建合并后的配置树"""
        with self._lock:
            merged = {}
            for name, data in self._configs.items():
                merged = self._deep_merge(merged, data)
            self._merged = merged
    
    @staticmethod
    def _deep_merge(base: Dict, overlay: Dict) -> Dict:
        """深度合并两个字典, overlay 覆盖 base"""
        result = deepcopy(base)
        for key, value in overlay.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = ConfigService._deep_merge(result[key], value)
            else:
                result[key] = deepcopy(value)
        return result
    
    # ═══════════════════════════════════════════════════════════════
    # 便捷方法 — 常用配置快速访问
    # ═══════════════════════════════════════════════════════════════
    
    def get_futures_codes(self) -> List[Dict]:
        """获取期货主连代码列表"""
        return self.get("codes.futures", [])
    
    def get_index_codes(self) -> List[Dict]:
        """获取指数代码列表"""
        return self.get("codes.indices", [])
    
    def get_option_underlyings(self) -> Dict:
        """获取期权标的配置"""
        return self.get("codes.option_underlyings", {})
    
    def get_variety_market(self) -> Dict:
        """获取品种→市场映射"""
        return self.get("codes.variety_market", {})
    
    def get_delivery_months(self) -> Dict:
        """获取品种交割月份规则"""
        return self.get("codes.commodity_delivery_months", {})
    
    def get_tdx_config(self) -> Dict:
        """获取TDX连接配置"""
        return self.get("tdx", {})
    
    def get_database_config(self) -> Dict:
        """获取数据库配置"""
        return self.get("database", {})
    
    def get_cache_ttl(self) -> Dict:
        """获取缓存TTL配置"""
        return self.get("codes.cache_ttl", {})
