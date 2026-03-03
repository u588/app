# ==================== 2.2 配置管理 (YAML配置加载 + 热更新 + 版本管理) ConfigService ====================
# config_service_v6.py
"""
V6.0 配置服务（完全独立，无循环依赖）
职责：
1. 配置加载（YAML/JSON）
2. 配置验证
3. 配置热更新
4. 配置版本管理
5. 配置回滚
依赖：
- 仅依赖yaml库（无业务依赖）
- 不依赖任何业务服务
"""
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging

from utils.path_utils import get_config_path  # ✅ 关键修复：自动路径解析
from utils.file_loader import file_loader

import json
import os
from datetime import datetime

from copy import deepcopy

logger = logging.getLogger(__name__)


class ConfigService:
    """V6.0 配置服务（修复版：完全独立）
    

        初始化配置服务（无需指定完整路径！）
        
        参数:
            config_file: 配置文件名（自动在 config/ 目录查找）
                示例: 'system_config_v6.yaml'（无需 './config/' 前缀）
        """
    def __init__(self, config_file: str = 'system_config_v6.yaml'):
        # ✅ 核心修复：自动构建绝对路径
        self.config_path = get_config_path(config_file)
        
        # 加载配置
        self.config = self._load_config()
        self.version = self.config.get('version', {}).get('system_version', '6.0.0')
        
        logger.info(f"✅ 配置服务初始化成功 | 版本={self.version} | 路径={self.config_path}")

    def __getattr__(self, name):
        """安全代理：支持 config_service.xxx 直接访问配置项"""
        # 安全防护：避免覆盖ConfigService自身方法
        protected_attrs = {'config', 'config_path', 'logger', 'version', 
                        'save_config', 'reload', 'get_stats', '_load_config'}
        if name in protected_attrs:
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
        
        # 从config字典返回
        if name in self.config:
            return self.config[name]
        
        # 未找到，抛出标准错误
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

    def safe_get(self, keys: List[str], default: Any = None) -> Any:
        """
        安全获取嵌套配置值
        
        参数:
            keys: 键路径 ['adaptive_config', 'option_tolerance', 'base_tolerance']
            default: 默认值
        
        返回:
            配置值或默认值
        """
        value = self.config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                self.logger.warning(f"⚠️ 配置路径缺失: {'.'.join(keys[:keys.index(key)+1])}")
                return default
        return value if value is not None else default

    def _load_config(self) -> Dict:
        """加载配置（自动路径解析）"""
        try:
            # ✅ 使用统一文件加载器（自动处理路径）
            return file_loader.load_yaml(self.config_path.name, relative_to='config')
        except Exception as e:
            logger.error(f"❌ 配置加载失败: {str(e)}")
            # 回退到默认配置
            return self._get_default_config()
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值（支持嵌套键，用点号分隔）
        
        参数:
            key: 配置键（如'adaptive_config.pcr_thresholds.enabled'）
            default: 默认值
        
        返回:
            配置值或默认值
        """
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                self.logger.debug(f"⚠️ 配置键不存在: {key}，返回默认值")
                return default
        
        return value
    
    def set(self, key: str, value: Any, save: bool = True) -> bool:
        """
        设置配置值（支持嵌套键）
        
        参数:
            key: 配置键（如'adaptive_config.pcr_thresholds.enabled'）
            value: 配置值
            save: 是否保存到文件
        
        返回:
            bool: 是否设置成功
        """
        keys = key.split('.')
        config = self.config
        
        # 遍历到倒数第二个键
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            elif not isinstance(config[k], dict):
                self.logger.error(f"❌ 配置路径冲突: {key}（非字典类型）")
                return False
            config = config[k]
        
        # 设置最后一个键
        last_key = keys[-1]
        old_value = config.get(last_key)
        config[last_key] = value
        
        self.logger.info(f"✅ 配置更新: {key} = {value} (旧值={old_value})")
        
        # 保存配置
        if save:
            return self.save_config()
        
        return True
    
    def save_config(self, path: Optional[str] = None) -> bool:
        """
        保存配置到文件
        
        参数:
            path: 保存路径（None=使用初始化路径）
        
        返回:
            bool: 是否保存成功
        """
        try:
            save_path = path or self.config_path
            
            # 确保目录存在
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            
            # 保存前备份
            backup_path = f"{save_path}.bak"
            if os.path.exists(save_path):
                import shutil
                shutil.copy2(save_path, backup_path)
                self.logger.debug(f"✅ 配置备份: {backup_path}")
            
            # 保存YAML
            with open(save_path, 'w', encoding='utf-8') as f:
                yaml.dump(self.config, f, allow_unicode=True, default_flow_style=False)
            
            self.last_modified = datetime.now()
            self.logger.info(f"✅ 配置保存成功: {save_path}")
            
            # 保存版本
            self._save_version(f"manual_save_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            
            return True
        
        except Exception as e:
            self.logger.error(f"❌ 配置保存失败: {str(e)}")
            return False
    
    # ==================== 验证方法 ====================
    
    def validate_config(self) -> Tuple[bool, List[str]]:
        """
        验证配置完整性
        
        返回:
            (是否有效, 错误列表)
        """
        errors = []
        
        # 1. 检查必需字段
        required_fields = [
            'adaptive_config',
            'market_benchmarks',
            'micro_redundancy',
            'commodity_strategy_map',
            'risk_thresholds',
            'position_control',
            'option_markets'
        ]
        
        for field in required_fields:
            if field not in self.config:
                errors.append(f"缺少必需字段: {field}")
        
        # 2. 检查adaptive_config结构
        if 'adaptive_config' in self.config:
            adaptive = self.config['adaptive_config']
            if not isinstance(adaptive, dict):
                errors.append("adaptive_config 必须是字典类型")
            else:
                required_adaptive = ['enabled', 'pcr_thresholds', 'micro_liquidity_thresholds']
                for field in required_adaptive:
                    if field not in adaptive:
                        errors.append(f"adaptive_config 缺少字段: {field}")
        
        # 3. 检查market_benchmarks
        if 'market_benchmarks' in self.config:
            benchmarks = self.config['market_benchmarks']
            if not isinstance(benchmarks, dict):
                errors.append("market_benchmarks 必须是字典类型")
            else:
                required_sizes = ['大盘', '中盘', '小盘', '微盘']
                for size in required_sizes:
                    if size not in benchmarks:
                        errors.append(f"market_benchmarks 缺少 {size} 配置")
                    else:
                        size_config = benchmarks[size]
                        if 'code' not in size_config or 'weight' not in size_config:
                            errors.append(f"market_benchmarks.{size} 缺少 code 或 weight")
        
        # 4. 检查风险阈值
        if 'risk_thresholds' in self.config:
            thresholds = self.config['risk_thresholds']
            if 'liquidity' in thresholds:
                liquidity = thresholds['liquidity']
                if 'warning_shrink' not in liquidity or 'extreme_shrink' not in liquidity:
                    errors.append("risk_thresholds.liquidity 缺少 warning_shrink 或 extreme_shrink")
        
        return len(errors) == 0, errors
    
    # ==================== 版本管理 ====================
    
    def _save_version(self, reason: str):
        """保存配置版本"""
        version = {
            'timestamp': datetime.now().isoformat(),
            'reason': reason,
            'config': deepcopy(self.config)
        }
        self.config_history.append(version)
        
        # 保留最近10个版本
        if len(self.config_history) > 10:
            self.config_history.pop(0)
        
        self.logger.debug(f"✅ 配置版本保存: {reason} | 历史版本数={len(self.config_history)}")
    
    def rollback(self, version_index: int = -1) -> bool:
        """
        回滚到指定版本
        
        参数:
            version_index: 版本索引（-1=最新，-2=上一个，...）
        
        返回:
            bool: 是否回滚成功
        """
        if not self.config_history:
            self.logger.warning("⚠️ 无配置历史，无法回滚")
            return False
        
        try:
            version = self.config_history[version_index]
            self.config = deepcopy(version['config'])
            self.logger.info(f"✅ 配置回滚成功 | 原因={version['reason']} | 时间={version['timestamp']}")
            
            # 保存回滚操作
            self._save_version(f"rollback_{version['reason']}")
            
            # 保存到文件
            self.save_config()
            
            return True
        
        except IndexError:
            self.logger.error(f"❌ 版本索引无效: {version_index}")
            return False
    
    def get_version_history(self) -> List[Dict]:
        """获取配置版本历史"""
        return [
            {
                'index': i,
                'timestamp': v['timestamp'],
                'reason': v['reason']
            }
            for i, v in enumerate(self.config_history)
        ]
    
    # ==================== 辅助方法 ====================
    
    def _get_default_config(self) -> Dict:
        """获取默认配置"""
        return {
            'adaptive_config': {
                'enabled': True,
                'pcr_thresholds': {
                    'enabled': True,
                    'base_thresholds': {
                        'warning_high': 1.3,
                        'warning_low': 0.7,
                        'extreme_high': 1.5,
                        'extreme_low': 0.5
                    }
                }
            },
            'market_benchmarks': {
                '大盘': {'code': '000300', 'weight': 0.40},
                '中盘': {'code': '000905', 'weight': 0.30},
                '小盘': {'code': '000852', 'weight': 0.20},
                '微盘': {'code': '932000', 'weight': 0.10}
            },
            'micro_redundancy': {
                'primary': '932000',
                'secondary': '399311'
            },
            'risk_thresholds': {
                'liquidity': {
                    'warning_shrink': 0.6,
                    'extreme_shrink': 0.4
                }
            },
            'version': self.version,
            'last_updated': datetime.now().isoformat()
        }
    
    def export_to_json(self, path: str) -> bool:
        """导出配置为JSON"""
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            self.logger.info(f"✅ 配置导出为JSON: {path}")
            return True
        except Exception as e:
            self.logger.error(f"❌ 配置导出失败: {str(e)}")
            return False
    
    def reload(self) -> bool:
        """重新加载配置（从文件）"""
        self.logger.info("🔄 重新加载配置...")
        return self._load_config()
    
    def get_config(self) -> Dict:
        """获取完整配置（深拷贝）"""
        return deepcopy(self.config)


# ==================== 使用示例 ====================
def example_config_service():
    """配置服务使用示例"""
    
    print("=" * 80)
    print("🧪 ConfigService 使用示例")
    print("=" * 80)
    
    # 1. 初始化配置服务
    print("\n1️⃣ 初始化配置服务...")
    config_service = ConfigService('./config/system_config_v6.yaml')
    
    # 2. 获取配置
    print("\n2️⃣ 获取配置...")
    adaptive_enabled = config_service.get('adaptive_config.enabled', False)
    print(f"   ✅ adaptive_config.enabled = {adaptive_enabled}")
    
    warning_high = config_service.get('adaptive_config.pcr_thresholds.base_thresholds.warning_high', 1.3)
    print(f"   ✅ PCR警告高阈值 = {warning_high}")
    
    # 3. 修改配置
    print("\n3️⃣ 修改配置...")
    config_service.set('adaptive_config.pcr_thresholds.base_thresholds.warning_high', 1.4)
    new_value = config_service.get('adaptive_config.pcr_thresholds.base_thresholds.warning_high')
    print(f"   ✅ 新阈值 = {new_value}")
    
    # 4. 验证配置
    print("\n4️⃣ 验证配置...")
    is_valid, errors = config_service.validate_config()
    print(f"   配置有效: {is_valid}")
    if not is_valid:
        for error in errors[:3]:
            print(f"   ❌ {error}")
    
    # 5. 配置版本
    print("\n5️⃣ 配置版本历史...")
    history = config_service.get_version_history()
    print(f"   历史版本数: {len(history)}")
    if history:
        print(f"   最新版本: {history[-1]['reason']} ({history[-1]['timestamp']})")
    
    # 6. 回滚配置
    print("\n6️⃣ 回滚配置...")
    if len(history) > 1:
        config_service.rollback(-2)  # 回滚到上上个版本
        print(f"   ✅ 已回滚到版本: {history[-2]['reason']}")
    else:
        print("   ⚠️ 历史版本不足，无法回滚")
    
    print("\n" + "=" * 80)
    print("✅ ConfigService 示例运行完成")
    print("=" * 80)


if __name__ == "__main__":
    example_config_service()