# utils/file_loader.py
"""
V6.0 统一文件加载器
核心特性：
✅ 自动路径解析（无需手动拼接）
✅ YAML/JSON/CSV/Pickle 多格式支持
✅ 智能降级（主路径失败时尝试备用路径）
✅ 详细错误提示（快速定位问题）
"""
import yaml
import json
import pandas as pd
from pathlib import Path
from typing import Any, Optional, Dict, List
import logging

from .path_utils import get_project_root, get_config_path

logger = logging.getLogger(__name__)


class FileLoader:
    """统一文件加载器（生产级）"""
    
    @staticmethod
    def load_yaml(
        file_path: str,
        relative_to: str = 'config',
        fallback_paths: Optional[List[str]] = None
    ) -> Dict:
        """
        加载 YAML 文件
        
        参数:
            file_path: 文件名（如 'system_config_v6.yaml'）
            relative_to: 相对于哪个目录（'config'/'reports'/'cache'）
            fallback_paths: 备用路径列表（降级策略）
        
        返回:
            Dict: YAML 解析后的字典
        
        示例:
            # 自动从 config/ 目录加载
            config = FileLoader.load_yaml('system_config_v6.yaml')
            
            # 从 reports/ 目录加载
            report = FileLoader.load_yaml('output.json', relative_to='reports')
        """
        # 构建主路径
        root = get_project_root()
        main_path = root / relative_to / file_path
        
        # 尝试加载
        paths_to_try = [main_path]
        if fallback_paths:
            paths_to_try.extend([root / p for p in fallback_paths])
        
        for path in paths_to_try:
            if path.exists():
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        data = yaml.safe_load(f)
                    logger.info(f"✅ 加载 YAML: {path.relative_to(root)}")
                    return data
                except Exception as e:
                    logger.warning(f"⚠️ YAML 加载失败 {path}: {str(e)[:50]}")
        
        # 所有路径失败
        error_msg = (
            f"❌ 无法加载 YAML 文件: {file_path}\n"
            f"尝试路径:\n" + "\n".join([f"  - {p}" for p in paths_to_try])
        )
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)
    
    @staticmethod
    def load_json(file_path: str, relative_to: str = 'config') -> Dict:
        """加载 JSON 文件（类似 load_yaml）"""
        root = get_project_root()
        path = root / relative_to / file_path
        
        if not path.exists():
            raise FileNotFoundError(f"JSON 文件不存在: {path}")
        
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        logger.info(f"✅ 加载 JSON: {path.relative_to(root)}")
        return data
    
    @staticmethod
    def load_csv(file_path: str, relative_to: str = 'reports', **kwargs) -> pd.DataFrame:
        """加载 CSV 文件"""
        root = get_project_root()
        path = root / relative_to / file_path
        
        if not path.exists():
            raise FileNotFoundError(f"CSV 文件不存在: {path}")
        
        df = pd.read_csv(path, **kwargs)
        logger.info(f"✅ 加载 CSV ({len(df)}行): {path.relative_to(root)}")
        return df
    
    @staticmethod
    def save_yaml(data: Dict, file_path: str, relative_to: str = 'config'):
        """保存 YAML 文件"""
        root = get_project_root()
        path = root / relative_to / file_path
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
        logger.info(f"✅ 保存 YAML: {path.relative_to(root)}")
    
    @staticmethod
    def save_json(data: Dict, file_path: str, relative_to: str = 'reports'):
        """保存 JSON 文件"""
        root = get_project_root()
        path = root / relative_to / file_path
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"✅ 保存 JSON: {path.relative_to(root)}")


# 全局单例
file_loader = FileLoader()