import yaml
from pathlib import Path
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class ConfigLoader:
    def __init__(self, config_path: str, settings_path: str = "config/app_settings.yaml"):
        self.config_path = Path(config_path)
        self.settings_path = Path(settings_path)
        
    def load(self) -> Dict[str, Any]:
        logger.info(f"加载配置: {self.config_path}")
        with open(self.config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        self._validate(cfg)
        
        settings = {}
        if self.settings_path.exists():
            with open(self.settings_path, "r", encoding="utf-8") as f:
                settings = yaml.safe_load(f)
                
        return {"data": cfg, "settings": settings}
        
    @staticmethod
    def _validate(cfg: Dict[str, Any]) -> None:
        required = ["metadata", "visual_style", "supply_chains", "global_indicators", "timeline"]
        missing = [k for k in required if k not in cfg]
        if missing:
            raise ValueError(f"YAML配置缺失必需字段: {', '.join(missing)}")