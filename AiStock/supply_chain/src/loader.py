# supply_chain/src/loader.py
import yaml
from pathlib import Path
from typing import Any, Dict

class ChainConfigLoader:
    """配置加载器：读取 YAML 并执行基础结构校验"""
    
    def __init__(self, config_path: str | Path):
        self.config_path = Path(config_path)
        
    def load(self) -> Dict[str, Any]:
        if not self.config_path.exists():
            raise FileNotFoundError(f"配置缺失: {self.config_path}")
            
        with open(self.config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            
        required_keys = {"nodes", "links"}
        if not required_keys.issubset(data.keys()):
            raise ValueError(f"YAML 缺少必需字段: {required_keys - data.keys()}")
            
        return data