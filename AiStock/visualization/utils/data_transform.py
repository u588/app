#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DataTransform：数据清洗与类型安全转换
"""
import numpy as np
import pandas as pd
from typing import Any, Union

def sanitize_for_json(obj: Any) -> Any:
    """递归转换 numpy/pandas 类型为原生 Python 类型"""
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_for_json(v) for v in obj]
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    elif pd.isna(obj):
        return None
    return obj