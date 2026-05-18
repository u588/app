"""
配置加载器 - 从YAML文件加载所有配置
支持热重载和配置校验
"""

import os
import yaml
from typing import Any, Dict, Optional


class ConfigLoader:
    """YAML配置加载器，统一管理所有配置文件"""

    def __init__(self, config_dir: str = None):
        if config_dir is None:
            config_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config')
        self.config_dir = config_dir
        self._configs: Dict[str, Any] = {}

    def load(self, name: str) -> Dict[str, Any]:
        """加载指定配置文件"""
        if name in self._configs:
            return self._configs[name]

        filepath = os.path.join(self.config_dir, f'{name}.yaml')
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"配置文件不存在: {filepath}")

        with open(filepath, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        self._configs[name] = config
        return config

    def load_all(self) -> Dict[str, Any]:
        """加载所有配置文件"""
        configs = {}
        for fname in os.listdir(self.config_dir):
            if fname.endswith('.yaml') or fname.endswith('.yml'):
                name = fname.rsplit('.', 1)[0]
                configs[name] = self.load(name)
        return configs

    def get(self, name: str, key: str = None, default: Any = None) -> Any:
        """获取配置项，支持嵌套key路径 (如 'global.background')"""
        config = self.load(name)
        if key is None:
            return config

        parts = key.split('.')
        value = config
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return default
        return value

    def reload(self, name: str = None) -> None:
        """重新加载配置"""
        if name:
            self._configs.pop(name, None)
        else:
            self._configs.clear()

    def validate(self) -> Dict[str, Any]:
        """校验配置完整性"""
        results = {}
        required_files = ['industry_chain', 'relations', 'visual']

        for fname in required_files:
            path = os.path.join(self.config_dir, f'{fname}.yaml')
            results[fname] = os.path.exists(path)

        # 校验产业链配置
        if results.get('industry_chain'):
            chain_cfg = self.load('industry_chain')
            for direction, levels in chain_cfg.items():
                if not isinstance(levels, dict):
                    results[f'industry_chain.{direction}'] = False
                    continue
                for level in ['upstream', 'midstream', 'downstream']:
                    if level not in levels:
                        results[f'industry_chain.{direction}.{level}'] = 'missing'

        return results