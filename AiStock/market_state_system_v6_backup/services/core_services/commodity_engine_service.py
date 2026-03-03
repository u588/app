# ==================== 4.1.5 商品分析服务 （商品分析：信号计算 + 期限结构）CommodityEngineService ====================
# commodity_engine_service_v6.py
"""
V6.0 商品分析服务（完全独立，无循环依赖）
职责：
1. 商品期货信号计算（成本型/收益型）
2. 期货期限结构分析（Contango/Backwardation）
3. 产业景气度评估
依赖：
- 仅依赖DataLoadingService和ConfigService
- 所有计算独立完成，无外部业务服务依赖
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class CommodityEngineService:
    """V6.0 商品分析服务（修复版：完全独立）"""
    
    def __init__(self, data_service, config_service):
        """
        初始化商品分析服务
        
        参数:
            data_service: DataLoadingService实例
            config_service: ConfigService实例
        """
        self.data_service = data_service
        self.config_service = config_service
        self.logger = logger
        
        # 商品市场代码映射（内部维护）
        self._market_code_map = {
            'CU': 30, 'AL': 30, 'AU': 30, 'AG': 30, 'RB': 30, 'SC': 30,
            'NI': 30, 'SN': 30, 'ZN': 30, 'PB': 30, 'FU': 30, 'BU': 30,
            'RU': 30, 'NR': 30, 'SP': 30, 'LU': 30, 'BC': 30, 'SS': 30,
            'M': 29, 'Y': 29, 'C': 29, 'I': 29, 'J': 29, 'JM': 29, 'LH': 29,
            'CF': 32, 'SR': 32, 'TA': 32, 'MA': 32, 'FG': 32, 'SA': 32,
            'LC': 66, 'SI': 66, 'PS': 66
        }
        
        self.logger.info("✅ 商品分析服务初始化成功（V6.0独立版）")
    
    def calculate_commodity_signals(self) -> Dict[str, Dict]:
        """
        V6.0核心：商品期货信号计算
        
        返回:
            {
                'CUL8': {
                    'name': '沪铜',
                    'price_chg_20d': float,      # 20日价格变化(%)
                    'signal': str,                # 信号描述
                    'score': float,               # 调整分数（-0.15到+0.12）
                    'directions': List[str],      # 影响的战略方向
                    'weight': float,              # 商品权重
                    'impact_type': str,           # 影响类型（cost/benefit）
                    'threshold_up': float,        # 上阈值
                    'threshold_down': float       # 下阈值
                },
                ...
            }
        """
        commodity_signals = {}
        
        # 从配置获取商品映射
        commodity_config = self.config_service.config.get('commodity_strategy_map', {})
        
        for code, config in commodity_config.items():
            # 获取市场代码
            market_code = self._get_market_code(code)
            
            # 加载商品期货数据
            df = self.data_service.load_derivative_data(code, market_code, days=60)
            
            if len(df) < 20:
                self.logger.debug(f"⚠️ {code} 数据不足（需≥20日），跳过")
                continue
            
            # 计算20日价格变化
            price_chg_20d = (df['close'].iloc[-1] / df['close'].iloc[-20] - 1) * 100
            
            # 根据影响类型和阈值生成信号
            signal, score = self._generate_signal(
                price_chg=price_chg_20d,
                impact_type=config.get('impact_type', 'cost'),
                threshold_up=config.get('threshold_up', 10.0),
                threshold_down=config.get('threshold_down', -10.0)
            )
            
            commodity_signals[code] = {
                'name': self._get_commodity_name(code),
                'price_chg_20d': float(price_chg_20d),
                'signal': signal,
                'score': float(score),
                'directions': config.get('directions', []),
                'weight': config.get('weight', 0.05),
                'impact_type': config.get('impact_type', 'cost'),
                'threshold_up': config.get('threshold_up', 10.0),
                'threshold_down': config.get('threshold_down', -10.0),
                'market_code': market_code
            }
        
        self.logger.info(f"✅ 计算商品期货信号：{len(commodity_signals)}个商品")
        return commodity_signals
    
    def calculate_futures_term_structure(self) -> Dict[str, Dict]:
        """
        期货期限结构分析（Contango/Backwardation）
        
        返回:
            {
                'copper': {
                    'spread': float,              # 价差(%)
                    'structure': 'backwardation'/'contango',
                    'signal': str,                # 信号描述
                    'near_price': float,          # 近月价格
                    'far_price': float,           # 远月价格
                    'near_code': str,             # 近月合约代码
                    'far_code': str               # 远月合约代码
                },
                ...
            }
        """
        term_structure = {}
        
        # 定义监控的商品合约对（近月，远月，市场代码）
        commodity_contracts = {
            'copper': ('CU2603', 'CU2606', 30),    # 沪铜
            'aluminum': ('AL2603', 'AL2606', 30),  # 沪铝
            'lithium': ('LC2603', 'LC2606', 66),   # 碳酸锂
            'silicon': ('SI2603', 'SI2606', 66),   # 工业硅
            'crude': ('SC2603', 'SC2606', 30),     # 原油
            'rebar': ('RB2603', 'RB2606', 30),     # 螺纹钢
            'gold': ('AU2603', 'AU2606', 30),      # 黄金
            'soybean': ('M2603', 'M2605', 29)      # 豆粕
        }
        
        for key, (near_code, far_code, market_code) in commodity_contracts.items():
            # 1. 加载数据
            near_df = self.data_service.load_derivative_data(near_code, market_code, days=20)
            far_df = self.data_service.load_derivative_data(far_code, market_code, days=20)
            
            # 2. 计算价差
            if len(near_df) > 0 and len(far_df) > 0 and far_df['close'].iloc[-1] > 0:
                near_price = near_df['close'].iloc[-1]
                far_price = far_df['close'].iloc[-1]
                spread = ((near_price - far_price) / far_price) * 100
                
                # 3. 判断结构
                structure = 'backwardation' if spread > 0 else 'contango'
                signal = '供应紧张/景气' if spread > 0 else '供应充足/疲软'
                
                term_structure[key] = {
                    'spread': round(float(spread), 2),
                    'structure': structure,
                    'signal': signal,
                    'near_price': float(near_price),
                    'far_price': float(far_price),
                    'near_code': near_code,
                    'far_code': far_code
                }
        
        self.logger.info(f"✅ 计算期货期限结构：{len(term_structure)}个商品")
        return term_structure
    
    def calculate_industry_sentiment(self, term_structure: Dict) -> Dict[str, float]:
        """
        基于期限结构计算产业景气度评分
        
        参数:
            term_structure: 期限结构数据（来自calculate_futures_term_structure）
        
        返回:
            {'高端制造': 65.0, '新能源': 72.0, ...}  # 评分0-100
        """
        # 商品到战略方向的映射（简化版）
        commodity_to_direction = {
            'copper': ['高端制造', '供应链'],
            'aluminum': ['高端制造', '新能源'],
            'lithium': ['新能源', '信息技术'],
            'silicon': ['信息技术', '新能源'],
            'crude': ['公用事业', '供应链', '传统升级'],
            'rebar': ['传统升级', '供应链'],
            'gold': ['公用事业'],
            'soybean': ['现代农业', '生物健康']
        }
        
        # 初始化方向评分（默认50分）
        direction_sentiment = {direction: 50.0 for directions in commodity_to_direction.values() for direction in directions}
        
        # 根据期限结构更新评分
        for commodity, data in term_structure.items():
            if commodity not in commodity_to_direction:
                continue
            
            # Backwardation(近月>远月) = 供应紧张 = 景气度高
            # Contango(近月<远月) = 供应充足 = 景气度低
            if data['structure'] == 'backwardation':
                sentiment_score = min(100, 50 + abs(data['spread']) * 3)
            else:  # contango
                sentiment_score = max(0, 50 - abs(data['spread']) * 3)
            
            # 更新关联方向的评分（加权平均）
            for direction in commodity_to_direction[commodity]:
                if direction in direction_sentiment:
                    # 70%保留原评分 + 30%新评分
                    direction_sentiment[direction] = (
                        direction_sentiment[direction] * 0.7 + 
                        sentiment_score * 0.3
                    )
        
        # 强制转换为Python float
        return {k: float(v) for k, v in direction_sentiment.items()}
    
    # ==================== 辅助方法 ====================
    def _get_market_code(self, commodity_code: str) -> int:
        """获取商品期货的市场代码"""
        if commodity_code.endswith('L8'):
            base = commodity_code[:-2]
            return self._market_code_map.get(base, 30)  # 默认上海期货
        
        # 从配置中获取（兼容旧格式）
        if hasattr(self.config_service.config, 'commodity_strategy_map'):
            market_code = self.config_service.config.commodity_strategy_map.get(
                commodity_code, {}
            ).get('market_code')
            if market_code:
                return market_code
        
        return 30  # 默认上海期货
    
    def _get_commodity_name(self, code: str) -> str:
        """获取商品名称（优先从配置获取）"""
        # 从配置中获取
        if hasattr(self.config_service.config, 'commodity_strategy_map'):
            name = self.config_service.config.commodity_strategy_map.get(code, {}).get('name')
            if name:
                return name
        
        # 默认名称映射
        default_names = {
            'CUL8': '沪铜', 'ALL8': '沪铝', 'LCL8': '碳酸锂', 'SIL8': '工业硅',
            'SCL8': '原油', 'RBL8': '螺纹钢', 'ML8': '豆粕', 'CL8': '玉米',
            'AUL8': '黄金', 'AGL8': '白银', 'NIL8': '沪镍', 'ZNL8': '沪锌',
            'PBL8': '沪铅', 'SRL8': '白糖', 'CFL8': '棉花', 'TAL8': 'PTA',
            'MAL8': '甲醇', 'FGL8': '玻璃', 'SAL8': '纯碱'
        }
        return default_names.get(code, code)
    
    def _generate_signal(self, price_chg: float, impact_type: str, 
                        threshold_up: float, threshold_down: float) -> Tuple[str, float]:
        """生成商品信号和调整分数"""
        if impact_type == 'cost':
            # 成本型商品：价格上涨对相关方向不利
            if price_chg > threshold_up:
                return '成本大幅上升', -0.15
            elif price_chg > threshold_up / 2:
                return '成本上升', -0.08
            elif price_chg < threshold_down:
                return '成本大幅下降', 0.12
            elif price_chg < threshold_down / 2:
                return '成本下降', 0.06
            else:
                return '成本稳定', 0.0
        else:  # benefit
            # 收益型商品：价格上涨对相关方向有利
            if price_chg > 8:
                return '避险情绪高涨', 0.10
            else:
                return '正常', 0.0