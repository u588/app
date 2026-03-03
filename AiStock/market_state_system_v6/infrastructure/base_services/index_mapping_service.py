# ==================== 2.3 指数映射 (指数/期货/期权代码映射) IndexMappingService ====================
# index_mapping_service_v6.py
"""
V6.0 指数映射服务（完全独立，无循环依赖）
职责：
1. 指数代码→名称映射
2. 期货代码→名称映射
3. 期权标的→名称映射
4. 宏观指标→名称映射
5. 市场代码查询
依赖：
- 仅依赖yaml库（无业务依赖）
- 不依赖任何业务服务
"""
import yaml
import os
from typing import Dict, Optional, List, Tuple
import logging

logger = logging.getLogger(__name__)


class IndexMappingService:
    """V6.0 指数映射服务（修复版：完全独立）"""
    
    def __init__(self, mapping_path: str = './config/index_name_mapping.yaml'):
        """
        初始化指数映射服务
        
        参数:
            mapping_path: 映射文件路径
        """
        self.mapping_path = mapping_path
        self.mappings: Dict = {}
        self.logger = logger
        
        # 加载映射
        self._load_mappings()
        
        self.logger.info(f"✅ 指数映射服务初始化成功 | 路径={mapping_path}")
        self.logger.info(f"   📊 指数数量: {len(self.mappings.get('csi_indices', {}))}")
        self.logger.info(f"   📈 期货数量: {len(self.mappings.get('futures_main', {}))}")
        self.logger.info(f"   📉 期权数量: {len(self.mappings.get('option_underlyings', {}))}")
    
    # ==================== 核心方法 ====================
    
    def _load_mappings(self) -> bool:
        """加载映射文件"""
        try:
            if not os.path.exists(self.mapping_path):
                self.logger.warning(f"⚠️ 映射文件不存在: {self.mapping_path}，使用空映射")
                self.mappings = {}
                return False
            
            with open(self.mapping_path, 'r', encoding='utf-8') as f:
                self.mappings = yaml.safe_load(f)
            
            self.logger.info(f"✅ 映射加载成功 | 路径={self.mapping_path}")
            return True
        
        except Exception as e:
            self.logger.error(f"❌ 映射加载失败: {str(e)}")
            self.mappings = {}
            return False
    
    def get_name(self, code: str, category: Optional[str] = None) -> str:
        """
        获取代码对应的名称
        
        参数:
            code: 代码（如'000300'、'CUL8'、'IO'）
            category: 类别（可选，如'csi_indices'、'futures_main'）
        
        返回:
            名称字符串（未找到返回代码本身）
        """
        code = code.strip().upper()
        
        # 1. 指定类别查询
        if category:
            if category in self.mappings and code in self.mappings[category]:
                name = self.mappings[category][code]
                self.logger.debug(f"✅ {category}.{code} = {name}")
                return name
        
        # 2. 全局查询（遍历所有类别）
        for cat, mapping in self.mappings.items():
            if isinstance(mapping, dict) and code in mapping:
                name = mapping[code]
                self.logger.debug(f"✅ {cat}.{code} = {name}")
                return name
        
        # 3. 未找到，返回代码本身
        self.logger.debug(f"⚠️ 未找到映射: {code}")
        return code
    
    def get_category(self, code: str) -> Optional[str]:
        """
        获取代码所属类别
        
        参数:
            code: 代码
        
        返回:
            类别名称（如'csi_indices'）或 None
        """
        code = code.strip().upper()
        
        for category, mapping in self.mappings.items():
            if isinstance(mapping, dict) and code in mapping:
                return category
        
        return None
    
    def get_market_code(self, code: str) -> int:
        """
        获取代码对应的市场代码
        
        参数:
            code: 代码
        
        返回:
            市场代码（整数）
        """
        # 期货代码映射
        futures_mapping = {
            'CU': 30, 'AL': 30, 'AU': 30, 'AG': 30, 'RB': 30, 'SC': 30,
            'NI': 30, 'SN': 30, 'ZN': 30, 'PB': 30, 'FU': 30, 'BU': 30,
            'RU': 30, 'NR': 30, 'SP': 30, 'LU': 30, 'BC': 30, 'SS': 30,
            'M': 29, 'Y': 29, 'C': 29, 'I': 29, 'J': 29, 'JM': 29, 'LH': 29,
            'CF': 32, 'SR': 32, 'TA': 32, 'MA': 32, 'FG': 32, 'SA': 32,
            'LC': 66, 'SI': 66, 'PS': 66,
            'IF': 47, 'IH': 47, 'IC': 47, 'IM': 47
        }
        
        # 期权标的映射
        option_mapping = {
            'IO': 7, 'HO': 7, 'MO': 7,  # 中金所
            '5': 8, '1': 9  # 上交所/深交所（以代码开头判断）
        }
        
        # 1. 期货代码（包含数字和字母）
        if any(c.isdigit() for c in code):
            # 提取前缀（如'CUL8'→'CU'）
            prefix = ''.join(c for c in code if c.isalpha())
            if prefix in futures_mapping:
                return futures_mapping[prefix]
        
        # 2. 期权标的
        if code in option_mapping:
            return option_mapping[code]
        elif code.startswith('5'):
            return 8  # 上交所期权
        elif code.startswith('1'):
            return 9  # 深交所期权
        
        # 3. 指数代码（默认中证指数）
        if code.isdigit():
            if code.startswith('000') or code.startswith('399'):
                return 62  # 中证/国证指数
            elif code.startswith('93'):
                return 62  # 中证指数
        
        # 4. 默认市场代码
        return 62  # 中证指数市场
    
    # ==================== 分类查询 ====================
    
    def get_csi_indices(self) -> Dict[str, str]:
        """获取所有中证指数映射"""
        return self.mappings.get('csi_indices', {})
    
    def get_futures(self) -> Dict[str, str]:
        """获取所有期货映射"""
        return self.mappings.get('futures_main', {})
    
    def get_options(self) -> Dict[str, str]:
        """获取所有期权标的映射"""
        return self.mappings.get('option_underlyings', {})
    
    def get_macro_indicators(self) -> Dict[str, str]:
        """获取所有宏观指标映射"""
        return self.mappings.get('macro_indicators', {})
    
    def search(self, keyword: str, max_results: int = 10) -> List[Tuple[str, str, str]]:
        """
        搜索映射（支持模糊匹配）
        
        参数:
            keyword: 关键词
            max_results: 最大结果数
        
        返回:
            [(代码, 名称, 类别), ...]
        """
        results = []
        keyword = keyword.lower()
        
        for category, mapping in self.mappings.items():
            if not isinstance(mapping, dict):
                continue
            
            for code, name in mapping.items():
                if keyword in code.lower() or keyword in name.lower():
                    results.append((code, name, category))
                    if len(results) >= max_results:
                        return results
        
        return results
    
    # ==================== 辅助方法 ====================
    
    def get_stats(self) -> Dict[str, int]:
        """获取映射统计信息"""
        return {
            'csi_indices': len(self.mappings.get('csi_indices', {})),
            'cni_indices': len(self.mappings.get('cni_indices', {})),
            'hk_indices': len(self.mappings.get('hk_indices', {})),
            'futures_main': len(self.mappings.get('futures_main', {})),
            'option_underlyings': len(self.mappings.get('option_underlyings', {})),
            'macro_indicators': len(self.mappings.get('macro_indicators', {})),
            'total': sum(len(v) for v in self.mappings.values() if isinstance(v, dict))
        }
    
    def reload(self) -> bool:
        """重新加载映射"""
        self.logger.info("🔄 重新加载映射...")
        return self._load_mappings()


# ==================== 使用示例 ====================
def example_index_mapping_service():
    """指数映射服务使用示例"""
    
    print("=" * 80)
    print("🧪 IndexMappingService 使用示例")
    print("=" * 80)
    
    # 1. 初始化映射服务
    print("\n1️⃣ 初始化映射服务...")
    mapping_service = IndexMappingService('./config/index_name_mapping.yaml')
    
    # 2. 查询指数名称
    print("\n2️⃣ 查询指数名称...")
    name = mapping_service.get_name('000300')
    print(f"   ✅ 000300 = {name}")
    
    name = mapping_service.get_name('932000')
    print(f"   ✅ 932000 = {name}")
    
    # 3. 查询期货名称
    print("\n3️⃣ 查询期货名称...")
    name = mapping_service.get_name('CUL8')
    print(f"   ✅ CUL8 = {name}")
    
    name = mapping_service.get_name('LCL8')
    print(f"   ✅ LCL8 = {name}")
    
    # 4. 查询期权标的
    print("\n4️⃣ 查询期权标的...")
    name = mapping_service.get_name('IO')
    print(f"   ✅ IO = {name}")
    
    name = mapping_service.get_name('510300')
    print(f"   ✅ 510300 = {name}")
    
    # 5. 获取市场代码
    print("\n5️⃣ 获取市场代码...")
    market_code = mapping_service.get_market_code('CUL8')
    print(f"   ✅ CUL8 市场代码 = {market_code} (上海期货)")
    
    market_code = mapping_service.get_market_code('IO')
    print(f"   ✅ IO 市场代码 = {market_code} (中金所)")
    
    market_code = mapping_service.get_market_code('510300')
    print(f"   ✅ 510300 市场代码 = {market_code} (上交所)")
    
    # 6. 搜索映射
    print("\n6️⃣ 搜索映射...")
    results = mapping_service.search('新能源')
    print(f"   搜索'新能源'，找到{len(results)}个结果:")
    for code, name, category in results[:3]:
        print(f"   • {code} = {name} ({category})")
    
    # 7. 映射统计
    print("\n7️⃣ 映射统计...")
    stats = mapping_service.get_stats()
    print(f"   📊 中证指数: {stats['csi_indices']}")
    print(f"   📈 期货合约: {stats['futures_main']}")
    print(f"   📉 期权标的: {stats['option_underlyings']}")
    print(f"   🌍 宏观指标: {stats['macro_indicators']}")
    print(f"   📦 总计: {stats['total']}")
    
    print("\n" + "=" * 80)
    print("✅ IndexMappingService 示例运行完成")
    print("=" * 80)


if __name__ == "__main__":
    example_index_mapping_service()