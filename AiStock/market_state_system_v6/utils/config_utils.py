def safe_config_get(config_dict: Dict, keys: List[str], default: Any = None) -> Any:
    """
    安全获取嵌套配置值（防御性编程）
    
    参数:
        config_dict: 配置字典
        keys: 键路径 ['adaptive_config', 'option_tolerance', 'base_tolerance']
        default: 默认值
    
    返回:
        配置值或默认值
    """
    value = config_dict
    for i, key in enumerate(keys):
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            logger.warning(f"⚠️ 配置路径缺失: {' → '.join(keys[:i+1])}，使用默认值 {default}")
            return default
    return value if value is not None else default

# utils/config_utils.py
def extract_config_dict(config: Any) -> Dict:
    """
    安全提取配置字典（兼容ConfigService实例和字典）
    
    参数:
        config: ConfigService实例 或 配置字典
    
    返回:
        配置字典
    
    示例:
        # 服务初始化时
        self.config = extract_config_dict(config)
    """
    if hasattr(config, 'config') and isinstance(config.config, dict):
        return config.config
    elif isinstance(config, dict):
        return config
    else:
        logger.warning(f"⚠️ 无效配置对象类型: {type(config)}, 使用空字典")
        return {}