"""
V6.0 类型转换工具模块（核心修复）
职责：
1. 强制转换为Python原生类型（防Plotly序列化错误）
2. NumPy类型安全转换
3. Pandas类型安全转换
修复点：
✅ 所有数值强制转换为Python原生float/int
✅ 完整异常处理
✅ 详细日志
✅ 降级策略（转换失败时提供默认值）
"""
import numpy as np
import pandas as pd
from typing import Any, Optional, List, Dict
import logging

logger = logging.getLogger(__name__)


def ensure_python_float(value: Any, default: float = 0.0) -> float:
    """
    确保数值为Python原生float（防Plotly序列化错误）
    
    参数:
        value: 任意数值类型
        default: 转换失败时的默认值
    
    返回:
        Python原生float
    """
    try:
        # 处理None和NaN
        if value is None or pd.isna(value) or np.isnan(value):
            return default
        
        # 转换为Python float
        result = float(value)
        
        # 检查无穷大
        if np.isinf(result):
            logger.warning(f"⚠️ 检测到无穷大值: {value}，替换为默认值 {default}")
            return default
        
        return result
    except (ValueError, TypeError) as e:
        logger.error(f"❌ 转换为float失败: {value} ({type(value).__name__}) | 错误: {str(e)}")
        return default


def ensure_python_int(value: Any, default: int = 0) -> int:
    """
    确保数值为Python原生int
    
    参数:
        value: 任意数值类型
        default: 转换失败时的默认值
    
    返回:
        Python原生int
    """
    try:
        if value is None or pd.isna(value):
            return default
        
        # 先转float再转int（处理字符串"3.5"等情况）
        result = int(float(value))
        return result
    except (ValueError, TypeError) as e:
        logger.error(f"❌ 转换为int失败: {value} ({type(value).__name__}) | 错误: {str(e)}")
        return default


def ensure_python_str(value: Any, default: str = "") -> str:
    """
    确保值为Python原生str
    
    参数:
        value: 任意类型
        default: 转换失败时的默认值
    
    返回:
        Python原生str
    """
    try:
        if value is None:
            return default
        
        # 直接转字符串
        result = str(value)
        return result
    except Exception as e:
        logger.error(f"❌ 转换为str失败: {value} ({type(value).__name__}) | 错误: {str(e)}")
        return default


def convert_dict_values_to_python_types(data: Dict) -> Dict:
    """
    递归转换字典中所有数值为Python原生类型
    
    参数:
        data: 字典
    
    返回:
        转换后的字典
    """
    converted = {}
    
    for key, value in data.items():
        if isinstance(value, dict):
            # 递归处理嵌套字典
            converted[key] = convert_dict_values_to_python_types(value)
        elif isinstance(value, list):
            # 处理列表
            converted[key] = [ensure_python_float(v) if isinstance(v, (int, float, np.number)) else v for v in value]
        elif isinstance(value, (int, float, np.number)):
            # 转换数值
            converted[key] = ensure_python_float(value)
        elif isinstance(value, str):
            # 保留字符串
            converted[key] = value
        else:
            # 其他类型直接保留
            converted[key] = value
    
    return converted


def convert_dataframe_to_python_types(df: pd.DataFrame) -> pd.DataFrame:
    """
    转换DataFrame中所有数值列为Python原生类型
    
    参数:
        df: DataFrame
    
    返回:
        转换后的DataFrame
    """
    if df is None or len(df) == 0:
        return df
    
    # 复制避免修改原数据
    df_converted = df.copy()
    
    # 转换数值列
    for col in df_converted.select_dtypes(include=[np.number]).columns:
        try:
            df_converted[col] = df_converted[col].apply(ensure_python_float)
        except Exception as e:
            logger.error(f"❌ 转换列 {col} 失败: {str(e)}")
    
    return df_converted


def safe_json_serialize(obj: Any) -> Any:
    """
    安全JSON序列化（处理NumPy/Pandas类型）
    
    参数:
        obj: 任意对象
    
    返回:
        JSON可序列化对象
    """
    if isinstance(obj, dict):
        return {k: safe_json_serialize(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [safe_json_serialize(v) for v in obj]
    elif isinstance(obj, (np.integer, np.floating)):
        return float(obj) if isinstance(obj, np.floating) else int(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif pd.isna(obj):
        return None
    elif isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    else:
        return obj