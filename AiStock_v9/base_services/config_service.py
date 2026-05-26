"""AiStock V8 配置服务

提供集中式配置管理:
- 从 YAML 文件加载配置
- 点号路径访问: config.get('tdx.standard.host', 'default')
- 环境变量覆盖: AISTOCK_TDX_STANDARD_HOST 优先于配置文件
- 配置节访问: config.get_section('tdx')
- 热重载: config.reload()
- 配置缓存

Usage:
    >>> from base_services import ConfigService
    >>> cfg = ConfigService()
    >>> host = cfg.get('tdx.standard.host', '119.147.212.81')
    >>> port = cfg.get('tdx.standard.port', 7709)
    >>> tdx_section = cfg.get_section('tdx')
"""

from __future__ import annotations

import os
import copy
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


# ─── 环境变量前缀 ────────────────────────────────────────────────────

_ENV_PREFIX = 'AISTOCK_'
_ENV_SEPARATOR = '__'


class ConfigService:
    """AiStock V8 配置服务

    以 YAML 配置文件为首要配置源, 并支持通过环境变量覆盖.
    环境变量命名规则: ``AISTOCK_<SECTION>__<KEY>``, 多级用双下划线分隔.

    例如:
        - 配置路径 ``tdx.standard.host`` 对应环境变量 ``AISTOCK_TDX__STANDARD__HOST``
        - 配置路径 ``cache.default_ttl`` 对应环境变量 ``AISTOCK_CACHE__DEFAULT_TTL``

    环境变量值会自动进行类型转换:
        - ``'true'`` / ``'false'`` → bool
        - 纯数字字符串 → int / float

    Args:
        config_path: 配置文件路径, 默认为项目根目录下 config/system_config.yaml
        auto_load: 是否在初始化时自动加载配置, 默认 True

    Example:
        >>> svc = ConfigService()
        >>> host = svc.get('tdx.standard.host', '119.147.212.81')
        >>> svc.reload()
    """

    _DEFAULT_CONFIG_FILENAME = 'config/system_config.yaml'

    def __init__(
        self,
        config_path: Optional[str | Path] = None,
        auto_load: bool = True,
    ) -> None:
        # 确定项目根目录 (base_services 的上级)
        self._project_root = Path(__file__).resolve().parent.parent

        # 确定配置文件路径
        if config_path is not None:
            self._config_path = Path(config_path)
        else:
            self._config_path = self._project_root / self._DEFAULT_CONFIG_FILENAME

        # 配置数据
        self._data: Dict[str, Any] = {}
        self._loaded: bool = False

        if auto_load:
            self.load()

    # ─── 属性 ─────────────────────────────────────────────

    @property
    def config_path(self) -> Path:
        """配置文件路径"""
        return self._config_path

    @property
    def is_loaded(self) -> bool:
        """配置是否已加载"""
        return self._loaded

    # ─── 加载与重载 ───────────────────────────────────────

    def load(self) -> None:
        """加载配置文件

        读取 YAML 配置文件并应用环境变量覆盖.
        若配置文件不存在, 使用空配置并记录警告.
        """
        if self._config_path.exists():
            with open(self._config_path, 'r', encoding='utf-8') as f:
                raw = yaml.safe_load(f)
                self._data = raw if isinstance(raw, dict) else {}
            self._loaded = True
        else:
            self._data = {}
            self._loaded = False

        # 应用环境变量覆盖
        self._apply_env_overrides()

    def reload(self) -> None:
        """重新加载配置文件

        清除当前缓存配置并重新从文件加载.
        环境变量覆盖会在重新加载后再次应用.

        Example:
            >>> cfg.reload()  # 修改了 YAML 文件后调用
        """
        self._data = {}
        self._loaded = False
        self.load()

    # ─── 读取方法 ─────────────────────────────────────────

    def get(
        self,
        key: str,
        default: Any = None,
        value_type: Optional[type] = None,
    ) -> Any:
        """通过点号路径获取配置值

        Args:
            key: 配置键, 使用点号分隔层级, 如 'tdx.standard.host'
            default: 键不存在时的默认值
            value_type: 期望的类型, 若指定则尝试转换
                (支持 int, float, bool, str, list)

        Returns:
            配置值, 若键不存在则返回 default

        Example:
            >>> host = cfg.get('tdx.standard.host', '119.147.212.81')
            >>> port = cfg.get('tdx.standard.port', 7709, value_type=int)
            >>> debug = cfg.get('debug', False, value_type=bool)
        """
        if not self._loaded:
            self.load()

        # 先检查环境变量
        env_key = self._key_to_env(key)
        env_value = os.environ.get(env_key)
        if env_value is not None:
            return self._cast_value(env_value, value_type)

        # 在配置字典中按路径查找
        value = self._resolve_path(key)
        if value is not None:
            return self._cast_value(value, value_type) if value_type else value

        return default

    def get_section(self, section: str) -> Dict[str, Any]:
        """获取整个配置节 (子字典)

        Args:
            section: 配置节路径, 如 'tdx', 'tdx.standard'

        Returns:
            该配置节的完整字典 (深拷贝), 若不存在返回空字典

        Example:
            >>> tdx_cfg = cfg.get_section('tdx')
            >>> # {'standard': {'host': '...', 'port': 7709}, ...}
        """
        if not self._loaded:
            self.load()

        value = self._resolve_path(section)
        if isinstance(value, dict):
            return copy.deepcopy(value)
        return {}

    def require(self, key: str) -> Any:
        """获取必需的配置值

        与 get() 类似, 但键不存在时抛出 KeyError.

        Args:
            key: 配置键

        Returns:
            配置值

        Raises:
            KeyError: 配置键不存在

        Example:
            >>> host = cfg.require('tdx.standard.host')  # 必须存在
        """
        value = self.get(key)
        if value is None:
            raise KeyError(f'必需的配置项不存在: {key}')
        return value

    def set(self, key: str, value: Any) -> None:
        """在运行时设置配置值

        仅在内存中修改, 不影响配置文件.
        设置的值会被环境变量覆盖.

        Args:
            key: 配置键
            value: 配置值

        Example:
            >>> cfg.set('debug', True)
        """
        if not self._loaded:
            self.load()

        parts = key.split('.')
        target = self._data
        for part in parts[:-1]:
            if part not in target or not isinstance(target[part], dict):
                target[part] = {}
            target = target[part]
        target[parts[-1]] = value

    # ─── 内部方法 ─────────────────────────────────────────

    def _resolve_path(self, key: str) -> Any:
        """在嵌套字典中按点号路径解析值

        Args:
            key: 点号分隔的键路径, 如 'tdx.standard.host'

        Returns:
            解析到的值, 若路径不存在返回 None
        """
        parts = key.split('.')
        current: Any = self._data
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current

    @staticmethod
    def _key_to_env(key: str) -> str:
        """将点号路径转换为环境变量名

        规则: 加 AISTOCK_ 前缀, 点号替换为双下划线, 全大写

        Example:
            >>> ConfigService._key_to_env('tdx.standard.host')
            'AISTOCK_TDX__STANDARD__HOST'
        """
        return _ENV_PREFIX + key.replace('.', _ENV_SEPARATOR).upper()

    def _apply_env_overrides(self) -> None:
        """扫描环境变量, 将 AISTOCK_ 前缀的变量覆盖到配置中

        仅覆盖已有路径或创建新路径, 不删除配置文件中的项.
        """
        for env_key, env_value in os.environ.items():
            if not env_key.startswith(_ENV_PREFIX):
                continue

            # 去掉前缀, 转换为小写, 双下划线还原为点号
            config_path = env_key[len(_ENV_PREFIX):]
            config_path = config_path.lower().replace(_ENV_SEPARATOR, '.')

            if config_path:
                self.set(config_path, self._auto_cast(env_value))

    @staticmethod
    def _auto_cast(value: str) -> Any:
        """自动类型推断, 将字符串转为合适的 Python 类型

        转换规则:
            - 'true' / 'false' (不区分大小写) → bool
            - 纯整数 → int
            - 纯浮点数 → float
            - 其他 → str
        """
        lower = value.lower()
        if lower in ('true', 'yes', '1'):
            return True
        if lower in ('false', 'no', '0'):
            return False
        try:
            return int(value)
        except ValueError:
            pass
        try:
            return float(value)
        except ValueError:
            pass
        return value

    @staticmethod
    def _cast_value(value: Any, target_type: Optional[type]) -> Any:
        """将值转换为指定类型

        Args:
            value: 原始值
            target_type: 目标类型

        Returns:
            转换后的值, 转换失败返回原值
        """
        if target_type is None:
            return value
        try:
            if target_type is bool:
                if isinstance(value, str):
                    return value.lower() in ('true', 'yes', '1')
                return bool(value)
            return target_type(value)  # type: ignore[call-arg]
        except (ValueError, TypeError):
            return value

    # ─── 魔术方法 ─────────────────────────────────────────

    def __repr__(self) -> str:
        return (
            f'ConfigService('
            f'path={self._config_path!r}, '
            f'loaded={self._loaded}, '
            f'keys={len(self._data)}'
            f')'
        )

    def __contains__(self, key: str) -> bool:
        """支持 ``'tdx.standard.host' in config`` 语法"""
        return self.get(key) is not None
