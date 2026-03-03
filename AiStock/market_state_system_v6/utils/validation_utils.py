"""
V6.0 验证工具模块
职责：
1. DataFrame数据验证
2. 数值范围验证
3. 必需字段验证
4. 空值处理
修复点：
✅ 完整异常处理
✅ 详细错误信息
✅ 降级策略（验证失败时提供默认值）
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


def validate_dataframe(
    df: pd.DataFrame,
    required_columns: List[str],
    min_rows: int = 10,
    name: str = "DataFrame"
) -> bool:
    """
    验证DataFrame完整性
    
    参数:
        df: 待验证的DataFrame
        required_columns: 必需列名列表
        min_rows: 最小行数
        name: DataFrame名称（用于日志）
    
    返回:
        bool: 是否验证通过
    """
    if df is None or not isinstance(df, pd.DataFrame):
        logger.error(f"❌ {name} 验证失败: 不是有效的DataFrame")
        return False
    
    if len(df) < min_rows:
        logger.warning(f"⚠️ {name} 行数不足: {len(df)} < {min_rows}")
        return False
    
    missing_cols = [col for col in required_columns if col not in df.columns]
    if missing_cols:
        logger.error(f"❌ {name} 缺少必需列: {missing_cols}")
        return False
    
    # 检查空值
    null_counts = df[required_columns].isnull().sum()
    high_null_cols = null_counts[null_counts > len(df) * 0.1]  # 空值率>10%
    if len(high_null_cols) > 0:
        logger.warning(f"⚠️ {name} 高空值率列: {high_null_cols.to_dict()}")
    
    logger.debug(f"✅ {name} 验证通过: {len(df)}行, {len(df.columns)}列")
    return True


def validate_numeric_range(
    value: Any,
    min_val: float = -np.inf,
    max_val: float = np.inf,
    name: str = "数值"
) -> bool:
    """
    验证数值范围
    
    参数:
        value: 待验证数值
        min_val: 最小值
        max_val: 最大值
        name: 数值名称
    
    返回:
        bool: 是否在范围内
    """
    try:
        num = float(value)
        if np.isnan(num) or np.isinf(num):
            logger.error(f"❌ {name} 验证失败: 非法数值 {value}")
            return False
        
        if num < min_val or num > max_val:
            logger.warning(f"⚠️ {name} 超出范围 [{min_val}, {max_val}]: {num}")
            return False
        
        return True
    except (ValueError, TypeError):
        logger.error(f"❌ {name} 验证失败: 无法转换为数值 {value}")
        return False


def validate_required_fields(
    data: Dict,
    required_fields: List[str],
    name: str = "数据字典"
) -> bool:
    """
    验证字典必需字段
    
    参数:
        data: 待验证字典
        required_fields: 必需字段列表
        name: 字典名称
    
    返回:
        bool: 是否验证通过
    """
    if not isinstance(data, dict):
        logger.error(f"❌ {name} 验证失败: 不是有效的字典")
        return False
    
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        logger.error(f"❌ {name} 缺少必需字段: {missing_fields}")
        return False
    
    # 检查空值
    empty_fields = [field for field in required_fields if data.get(field) is None]
    if empty_fields:
        logger.warning(f"⚠️ {name} 空值字段: {empty_fields}")
    
    logger.debug(f"✅ {name} 验证通过: {len(data)}个字段")
    return True


def validate_market_state(
    market_state: str,
    valid_states: List[str] = None
) -> bool:
    """
    验证市场状态
    
    参数:
        market_state: 市场状态字符串
        valid_states: 有效状态列表
    
    返回:
        bool: 是否有效
    """
    if valid_states is None:
        valid_states = [
            '战略进攻区', '积极配置区', '防御进攻区', '左侧布局区',
            '均衡持有区', '防御观望区', '左侧防御区', '谨慎持有区', '战略防御区'
        ]
    
    if market_state not in valid_states:
        logger.error(f"❌ 无效市场状态: {market_state} (有效值: {valid_states})")
        return False
    
    logger.debug(f"✅ 市场状态验证通过: {market_state}")
    return True


def validate_service_response(
    response: Dict,
    required_keys: List[str],
    service_name: str = "服务"
) -> bool:
    """
    验证服务响应完整性
    
    参数:
        response: 服务响应字典
        required_keys: 必需键列表
        service_name: 服务名称
    
    返回:
        bool: 是否验证通过
    """
    if not isinstance(response, dict):
        logger.error(f"❌ {service_name} 响应验证失败: 不是有效的字典")
        return False
    
    missing_keys = [key for key in required_keys if key not in response]
    if missing_keys:
        logger.error(f"❌ {service_name} 响应缺少必需键: {missing_keys}")
        return False
    
    # 检查错误字段
    if 'error' in response:
        logger.error(f"❌ {service_name} 响应包含错误: {response['error']}")
        return False
    
    logger.debug(f"✅ {service_name} 响应验证通过")
    return True


def safe_get_value(
    data: Dict,
    key: str,
    default: Any = None,
    validator: callable = None
) -> Any:
    """
    安全获取字典值（带验证和默认值）
    
    参数:
        data: 数据字典
        key: 键名
        default: 默认值
        validator: 验证函数
    
    返回:
        值或默认值
    """
    try:
        value = data.get(key, default)
        
        if validator and not validator(value):
            logger.warning(f"⚠️ {key} 验证失败，使用默认值: {default}")
            return default
        
        return value
    except Exception as e:
        logger.error(f"❌ 安全获取 {key} 失败: {str(e)}")
        return default