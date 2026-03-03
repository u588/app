# utils/config_utils.py
"""
V6.0 配置工具模块（增强版）
核心功能：
✅ extract_config_dict: 安全提取配置字典
✅ validate_config_keys: 通用配置验证（新增）
✅ safe_config_get: 安全获取嵌套配置值（新增）
✅ extract_and_validate_config: 一键提取+验证（新增）
修复点：
✅ 所有函数支持ConfigService实例和字典
✅ 详细日志记录缺失配置
✅ 降级策略：缺失时返回默认值
✅ 服务初始化更简洁清晰
"""
import logging
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger(__name__)


def extract_config_dict(config_service) -> Dict:
    """安全提取配置字典（兼容ConfigService实例和字典）"""
    if hasattr(config_service, 'config') and isinstance(config_service.config, dict):
        return config_service.config
    elif isinstance(config_service, dict):
        return config_service
    else:
        logger.warning("⚠️ 无效配置对象，使用空字典")
        return {}


def validate_config_keys(
    config_dict: Dict,
    required_keys: List[str],
    logger: Optional[logging.Logger] = None,
    service_name: str = "Service"
) -> Tuple[bool, List[str]]:
    """
    通用配置验证函数（核心新增）
    
    参数:
        config_dict: 配置字典
        required_keys: 必需键列表
        logger: 日志记录器（可选）
        service_name: 服务名称（用于日志）
    
    返回:
        (是否完整, 缺失键列表)
    
    优势:
    ✅ 多服务复用，避免重复验证逻辑
    ✅ 统一日志格式，便于问题追踪
    ✅ 支持服务名称标识，快速定位问题
    """
    if not isinstance(config_dict, dict):
        if logger:
            logger.error(f"❌ {service_name} 配置验证失败: config_dict 非字典类型")
        return False, required_keys
    
    missing_keys = [key for key in required_keys if key not in config_dict]
    
    if missing_keys and logger:
        logger.warning(
            f"⚠️ {service_name} 配置缺失 {len(missing_keys)}/{len(required_keys)} 项: "
            f"{', '.join(missing_keys)} | 将使用默认值"
        )
    
    return len(missing_keys) == 0, missing_keys


def safe_config_get(
    config_dict: Dict,
    keys: List[str],
    default: Any = None,
    logger: Optional[logging.Logger] = None
) -> Any:
    """
    安全获取嵌套配置值（新增）
    
    参数:
        config_dict: 配置字典
        keys: 键路径 ['adaptive_config', 'option_tolerance', 'base_tolerance']
        default: 默认值
        logger: 日志记录器
    
    返回:
        配置值或默认值
    
    示例:
        # 旧方式（易出错）:
        tolerance = config['adaptive_config']['option_tolerance']['base_tolerance']
        
        # 新方式（安全）:
        tolerance = safe_config_get(
            config, 
            ['adaptive_config', 'option_tolerance', 'base_tolerance'],
            default=0.05
        )
    """
    value = config_dict
    for i, key in enumerate(keys):
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            if logger:
                logger.warning(
                    f"⚠️ 配置路径缺失: {' → '.join(keys[:i+1])} | 使用默认值 {default}"
                )
            return default
    return value if value is not None else default


def extract_and_validate_config(
    config_service,
    required_keys: List[str],
    logger: Optional[logging.Logger] = None,
    service_name: str = "Service"
) -> Tuple[Dict, bool, List[str]]:
    """
    一键提取+验证配置（新增：服务初始化最佳实践）
    
    参数:
        config_service: ConfigService实例或配置字典
        required_keys: 必需键列表
        logger: 日志记录器
        service_name: 服务名称
    
    返回:
        (配置字典, 是否完整, 缺失键列表)
    
    使用示例:
        self.config, is_valid, missing = extract_and_validate_config(
            config_service,
            required_keys=['high_risk_directions', 'micro_cap_indices'],
            logger=self.logger,
            service_name='RiskAssessmentService'
        )
    """
    config_dict = extract_config_dict(config_service)
    is_valid, missing_keys = validate_config_keys(
        config_dict, 
        required_keys, 
        logger, 
        service_name
    )
    return config_dict, is_valid, missing_keys