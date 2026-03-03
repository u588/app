# utils/path_utils.py
"""
V6.0 路径管理工具（生产级解决方案）
核心特性：
✅ 自动检测项目根目录（5种方法）
✅ 环境变量优先（部署友好）
✅ 多级回退策略（Jupyter/脚本/生产环境通用）
✅ LRU缓存（避免重复查找）
✅ 详细日志（问题快速定位）
"""
import os
import sys
from pathlib import Path
from functools import lru_cache
import logging

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_project_root() -> Path:
    """
    智能检测项目根目录（按优先级排序）
    
    检测顺序：
    1. 环境变量 PROJECT_ROOT（最高优先级，部署时指定）
    2. 当前文件 __file__ 所在目录（脚本运行）
    3. Notebook 路径（通过 ipynbname 检测）
    4. 当前工作目录向上查找（最多5级）
    5. sys.path 中查找包含 config 目录的路径
    
    返回:
        Path: 项目根目录绝对路径
    
    异常:
        FileNotFoundError: 无法找到项目根目录
    """
    # 方法1: 环境变量（部署时指定，最高优先级）
    env_root = os.environ.get('PROJECT_ROOT')
    if env_root:
        root = Path(env_root).resolve()
        if (root / 'config').exists():
            logger.info(f"✅ 使用环境变量 PROJECT_ROOT: {root}")
            return root
        logger.warning(f"⚠️ 环境变量 PROJECT_ROOT 无效（{root} 不存在 config 目录）")
    
    # 方法2: 从 __file__ 推断（适用于 .py 脚本）
    try:
        current_file = Path(__file__).resolve()
        for parent in [current_file] + list(current_file.parents)[:5]:
            if (parent / 'config').exists():
                logger.info(f"✅ 从 __file__ 检测到项目根目录: {parent}")
                return parent
    except NameError:
        pass  # __file__ 在 Notebook 中不可用
    
    # 方法3: Notebook 路径检测（需要 ipynbname）
    try:
        import ipynbname
        nb_path = ipynbname.path()
        if nb_path:
            for parent in [nb_path] + list(nb_path.parents)[:5]:
                if (parent / 'config').exists():
                    logger.info(f"✅ 从 Notebook 路径检测到项目根目录: {parent}")
                    return parent
    except (ImportError, FileNotFoundError, Exception):
        pass
    
    # 方法4: 从当前工作目录向上查找
    current = Path.cwd().resolve()
    for _ in range(6):  # 当前目录 + 5级父目录
        if (current / 'config').exists():
            logger.info(f"✅ 从工作目录检测到项目根目录: {current}")
            return current
        if current == current.parent:  # 到达根目录
            break
        current = current.parent
    
    # 方法5: 从 sys.path 查找
    for path_str in sys.path:
        path = Path(path_str).resolve()
        if path.is_dir() and (path / 'config').exists():
            logger.info(f"✅ 从 sys.path 检测到项目根目录: {path}")
            return path
    
    # 所有方法失败
    error_msg = (
        "❌ 无法自动检测项目根目录！\n"
        "请通过以下任一方式解决：\n"
        "1. 设置环境变量: export PROJECT_ROOT=/your/project/path\n"
        "2. 确保当前目录包含 config/ 目录\n"
        "3. 在代码开头调用: os.environ['PROJECT_ROOT'] = '/your/path'\n"
        f"当前工作目录: {Path.cwd().resolve()}\n"
        f"sys.path: {sys.path[:3]}..."
    )
    logger.error(error_msg)
    raise FileNotFoundError(error_msg)


def get_config_path(config_file: str = 'system_config_v6.yaml') -> Path:
    """
    获取配置文件绝对路径
    
    参数:
        config_file: 配置文件名（相对于 config/ 目录）
    
    返回:
        Path: 配置文件绝对路径
    """
    root = get_project_root()
    config_path = root / 'config' / config_file
    if not config_path.exists():
        logger.warning(f"⚠️ 配置文件不存在: {config_path}")
    return config_path


def get_data_path(relative_path: str) -> Path:
    """
    获取数据文件绝对路径（reports/cache/logs等）
    
    参数:
        relative_path: 相对于项目根目录的路径（如 'reports/output.html'）
    
    返回:
        Path: 数据文件绝对路径
    """
    root = get_project_root()
    data_path = root / relative_path
    # 确保目录存在
    data_path.parent.mkdir(parents=True, exist_ok=True)
    return data_path


# ==================== 兼容性封装（旧代码平滑迁移） ====================
class ProjectPath:
    """项目路径便捷访问器（兼容旧代码）"""
    
    def __init__(self):
        self.root = get_project_root()
    
    @property
    def config_dir(self) -> Path:
        """配置目录"""
        return self.root / 'config'
    
    @property
    def reports_dir(self) -> Path:
        """报告目录"""
        return self.root / 'reports'
    
    @property
    def cache_dir(self) -> Path:
        """缓存目录"""
        return self.root / 'cache'
    
    @property
    def logs_dir(self) -> Path:
        """日志目录"""
        return self.root / 'logs'
    
    def __repr__(self):
        return f"ProjectPath(root={self.root})"


# 全局单例（避免重复检测）
PROJECT_PATH = ProjectPath()