"""
V6.1 宏观分析服务（完全独立微服务）
核心特性：
✅ 阈值动态化集成（ThresholdService）
✅ 配置统一提取（config_utils.extract_and_validate_config）
✅ 五维宏观综合评分计算（通胀/增长/流动性/情绪/外部风险）
✅ 预警规则动态检查（10+条规则）
✅ 市场状态判定（基于宏观评分）
✅ 完整降级策略（阈值服务失效时回退静态阈值）
✅ 所有数值强制Python原生float（防Plotly序列化错误）
修复点：
✅ 从config安全获取宏观指标配置（6大分类+30+指标）
✅ 动态阈值获取（优先ThresholdService，回退静态配置）
✅ 指标方向处理（positive/negative/neutral）
✅ 详细日志与异常处理
✅ 完整数据验证与降级
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import logging
import warnings

warnings.filterwarnings('ignore')
logger = logging.getLogger(__name__)

# ✅ V6.1核心：导入配置工具（统一配置提取）
from utils.config_utils import extract_and_validate_config, safe_config_get


class MacroAnalysisService:
    """V6.1 宏观分析服务（阈值动态化 + 配置统一化）"""
    
    def __init__(self, data_service, config_service, threshold_service=None):
        """
        初始化宏观分析服务
        
        参数:
            data_service: DataLoadingService实例（用于加载宏观数据）
            config_service: ConfigService实例（提供配置字典）
            threshold_service: ThresholdService实例（可选，None=使用静态阈值）
        
        修复点:
        ✅ 使用extract_and_validate_config统一配置提取
        ✅ 安全获取嵌套配置（safe_config_get）
        ✅ 详细日志记录配置状态
        ✅ 完整异常处理
        """
        self.data_service = data_service
        self.logger = logger
        
        # ✅ V6.1核心：统一配置提取（1行替代20+行验证逻辑）
        self.config, is_valid, missing_keys = extract_and_validate_config(
            config_service=config_service,
            required_keys=[
                'macro_indicators',
                'composite_scoring',
                'alert_rules'
            ],
            logger=self.logger,
            service_name='MacroAnalysisService'
        )
        
        # ✅ 保存ThresholdService引用（可选）
        self.threshold_service = threshold_service
        
        # 验证配置完整性
        if is_valid:
            # 提取宏观指标分类
            self.macro_categories = [
                'inflation', 'growth', 'liquidity', 
                'sentiment', 'external_risk', 'fund_sentiment'
            ]
            
            # 验证必要分类存在
            valid_categories = [
                cat for cat in self.macro_categories 
                if cat in self.config['macro_indicators']
            ]
            
            self.logger.info(
                f"✅ MacroAnalysisService初始化成功（配置完整） | "
                f"有效分类: {len(valid_categories)}/{len(self.macro_categories)} | "
                f"预警规则: {len(self.config.get('alert_rules', []))}条"
            )
        else:
            self.logger.warning(f"⚠️ MacroAnalysisService初始化完成（缺失{len(missing_keys)}项配置）")
    
    # ==================== 核心方法：宏观综合评分计算 ====================
    
    def calculate_macro_composite_score(self) -> Dict[str, Any]:
        """
        V6.1核心：计算宏观综合评分（五维加权）
        
        返回:
            {
                'composite_score': float,          # 综合评分(0-100)
                'category_scores': {               # 各分类得分
                    'inflation': {
                        'score': float,
                        'weight': float,
                        'indicators': Dict[str, float]
                    },
                    ...
                },
                'alerts': List[Dict],              # 预警列表
                'market_state': str,               # 市场状态
                'indicator_values': Dict[str, float],  # 指标值
                'calculation_time': str,
                'threshold_source': str            # 阈值来源（动态/静态）
            }
        
        修复点:
        ✅ 动态阈值获取（优先ThresholdService，回退静态配置）
        ✅ 所有数值强制Python原生float
        ✅ 完整降级策略（任一指标失败不影响整体）
        ✅ 详细日志记录每步计算
        """
        try:
            # 1. 计算各分类得分
            category_scores = {}
            indicator_values = {}
            
            for category in self.macro_categories:
                if category not in self.config['macro_indicators']:
                    continue
                
                cat_config = self.config['macro_indicators'][category]
                if not cat_config.get('enabled', False):
                    continue
                
                # 计算分类得分
                cat_score, cat_indicators = self._calculate_category_score(category, cat_config)
                
                if cat_score is not None:
                    category_scores[category] = {
                        'score': float(cat_score),
                        'weight': float(cat_config.get('weight', 0.2)),
                        'indicators': cat_indicators
                    }
                    
                    # 合并指标值
                    indicator_values.update(cat_indicators)
            
            # 2. 计算综合评分（加权平均）
            composite_score = 0.0
            total_weight = 0.0
            
            for cat_name, cat_data in category_scores.items():
                composite_score += cat_data['score'] * cat_data['weight']
                total_weight += cat_data['weight']
            
            if total_weight > 0:
                composite_score /= total_weight
            
            composite_score = float(np.clip(composite_score, 0, 100))
            
            # 3. 检查预警规则
            alerts = self._check_alert_rules(indicator_values)
            
            # 4. 判定市场状态
            market_state = self._determine_market_state_from_macro(composite_score)
            
            # 5. 强制转换为Python原生类型（关键修复：防Plotly序列化错误）
            result = {
                'composite_score': float(composite_score),
                'category_scores': category_scores,
                'alerts': alerts,
                'market_state': market_state,
                'indicator_values': indicator_values,
                'calculation_time': datetime.now().isoformat(),
                'threshold_source': '动态' if self.threshold_service else '静态'
            }
            
            self.logger.info(
                f"✅ 宏观综合评分计算完成 | 评分={composite_score:.1f}/100 | "
                f"市场状态={market_state} | 预警数={len(alerts)} | "
                f"阈值来源={result['threshold_source']}"
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"❌ 宏观综合评分计算失败: {str(e)[:50]}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return {
                'composite_score': 50.0,
                'category_scores': {},
                'alerts': [],
                'market_state': '均衡持有区',
                'indicator_values': {},
                'calculation_time': datetime.now().isoformat(),
                'threshold_source': '错误',
                'error': str(e)
            }
    
    # ==================== 辅助方法：分类得分计算 ====================
    
    def _calculate_category_score(
        self,
        category: str,
        cat_config: Dict
    ) -> Tuple[Optional[float], Dict[str, float]]:
        """
        计算单个宏观分类得分
        
        参数:
            category: 分类名称（如'inflation'）
            cat_config: 分类配置字典
        
        返回:
            (分类得分, 指标值字典)
        """
        try:
            indicators = cat_config.get('indicators', {})
            if not indicators:
                self.logger.debug(f"⚠️ {category} 无指标配置")
                return None, {}
            
            indicator_scores = {}
            indicator_values = {}
            total_weight = 0.0
            
            for ind_name, ind_config in indicators.items():
                try:
                    # 1. 加载指标数据
                    code = ind_config.get('code')
                    if not code:
                        self.logger.warning(f"⚠️ {category}.{ind_name} 缺少code配置")
                        continue
                    
                    # 2. 获取指标当前值
                    current_value = self._load_macro_indicator(code)
                    if current_value is None:
                        continue
                    
                    indicator_values[ind_name] = float(current_value)
                    
                    # 3. 计算指标得分（0-100）
                    score = self._calculate_indicator_score(
                        current_value,
                        ind_config,
                        ind_name,
                        category
                    )
                    
                    if score is not None:
                        indicator_scores[ind_name] = float(score)
                        total_weight += 1.0  # 等权重（可扩展为配置权重）
                
                except Exception as e:
                    self.logger.warning(
                        f"⚠️ {category}.{ind_name} 得分计算失败: {str(e)[:30]}"
                    )
                    continue
            
            # 计算分类平均得分
            if indicator_scores:
                category_score = sum(indicator_scores.values()) / len(indicator_scores)
                return float(category_score), indicator_values
            else:
                return None, indicator_values
            
        except Exception as e:
            self.logger.error(f"❌ {category} 分类得分计算失败: {str(e)[:30]}")
            return None, {}
    
    def _load_macro_indicator(self, code: str) -> Optional[float]:
        """
        加载宏观指标当前值
        
        参数:
            code: 指标代码（如'2_CPI'）
        
        返回:
            当前值（float）或None
        """
        try:
            # 去掉前缀（如'2_'）
            # clean_code = code.split('_')[-1] if '_' in code else code
            clean_code = str(code).strip()
            
            # 加载最近30天数据
            df = self.data_service.load_macro_data(clean_code, days=30)
            
            if len(df) > 0 and 'close' in df.columns:
                return float(df['close'].iloc[-1])
            else:
                self.logger.debug(f"⚠️ {code} 数据为空或缺少close列")
                return None
                
        except Exception as e:
            self.logger.warning(f"⚠️ {code} 数据加载失败: {str(e)[:30]}")
            return None
    
    def _calculate_indicator_score(
        self,
        value: float,
        ind_config: Dict,
        ind_name: str,
        category: str
    ) -> Optional[float]:
        """
        计算单个宏观指标得分（0-100）
        
        评分逻辑:
        1. 根据direction确定评分方向（positive/negative/neutral）
        2. 根据thresholds确定得分区间
        3. 线性插值得分
        
        返回:
            得分（0-100）或None
        """
        try:
            # ✅ V6.1核心：动态获取阈值（优先ThresholdService）
            thresholds = self._get_dynamic_thresholds(ind_name, ind_config)
            
            # 获取指标方向
            direction = ind_config.get('direction', 'neutral')
            
            # 根据方向和阈值计算得分
            if direction == 'positive':
                # 正向指标：值越大得分越高
                score = self._score_positive_indicator(value, thresholds)
            elif direction == 'negative':
                # 负向指标：值越小得分越高
                score = self._score_negative_indicator(value, thresholds)
            else:
                # 中性指标：接近正常值得分高
                score = self._score_neutral_indicator(value, thresholds)
            
            # 验证范围
            score = np.clip(score, 0, 100)
            
            self.logger.debug(
                f"📊 {category}.{ind_name} | 值={value:.2f} | 得分={score:.1f} | "
                f"方向={direction} | 阈值来源={'动态' if self.threshold_service else '静态'}"
            )
            
            return float(score)
            
        except Exception as e:
            self.logger.warning(
                f"⚠️ {category}.{ind_name} 得分计算异常: {str(e)[:30]}"
            )
            return None
    
    def _get_dynamic_thresholds(
        self,
        ind_name: str,
        ind_config: Dict
    ) -> Dict[str, float]:
        """
        V6.1核心：动态获取指标阈值
        
        逻辑:
        1. 优先从ThresholdService获取动态阈值
        2. 降级：从配置获取静态阈值
        3. 验证阈值有效性
        
        返回:
            阈值字典 {'warning_high': float, 'warning_low': float, ...}
        """
        # ✅ V6.1核心：动态获取阈值（优先ThresholdService）
        if self.threshold_service:
            try:
                # 构建阈值名称（如'CPI_warning_high'）
                base_name = ind_name.upper()
                
                thresholds = {}
                for threshold_type in ['warning_high', 'warning_low', 'extreme_high', 'extreme_low']:
                    threshold_name = f"{base_name}_{threshold_type}"
                    
                    try:
                        thresholds[threshold_type] = self.threshold_service.get_threshold(
                            threshold_name,
                            context={'indicator': ind_name},
                            strategy='static'
                        )
                    except:
                        # 降级：使用配置阈值
                        thresholds[threshold_type] = float(
                            ind_config.get('thresholds', {}).get(threshold_type, 0.0)
                        )
                
                self.logger.debug(
                    f"🔄 动态阈值 | {ind_name} | "
                    f"warning_high={thresholds['warning_high']:.2f} | "
                    f"warning_low={thresholds['warning_low']:.2f}"
                )
                return thresholds
                
            except Exception as e:
                self.logger.warning(
                    f"⚠️ 动态阈值获取失败，回退静态配置: {str(e)[:30]}"
                )
        
        # 降级：使用静态配置阈值
        static_thresholds = ind_config.get('thresholds', {})
        return {
            'warning_high': float(static_thresholds.get('warning_high', 0.0)),
            'warning_low': float(static_thresholds.get('warning_low', 0.0)),
            'extreme_high': float(static_thresholds.get('extreme_high', 0.0)),
            'extreme_low': float(static_thresholds.get('extreme_low', 0.0))
        }
    
    def _score_positive_indicator(
        self,
        value: float,
        thresholds: Dict[str, float]
    ) -> float:
        """正向指标得分计算（值越大得分越高）"""
        warning_high = thresholds['warning_high']
        warning_low = thresholds['warning_low']
        extreme_high = thresholds['extreme_high']
        extreme_low = thresholds['extreme_low']
        
        # 极端高：100分
        if value >= extreme_high:
            return 100.0
        # 警告高：80-100分
        elif value >= warning_high:
            return 80.0 + (value - warning_high) / (extreme_high - warning_high) * 20.0
        # 正常：40-80分
        elif value >= warning_low:
            return 40.0 + (value - warning_low) / (warning_high - warning_low) * 40.0
        # 警告低：20-40分
        elif value >= extreme_low:
            return 20.0 + (value - extreme_low) / (warning_low - extreme_low) * 20.0
        # 极端低：0-20分
        else:
            return max(0.0, (value / extreme_low) * 20.0)
    
    def _score_negative_indicator(
        self,
        value: float,
        thresholds: Dict[str, float]
    ) -> float:
        """负向指标得分计算（值越小得分越高）"""
        # 负向指标：反转阈值逻辑
        reversed_thresholds = {
            'warning_high': thresholds['warning_low'],
            'warning_low': thresholds['warning_high'],
            'extreme_high': thresholds['extreme_low'],
            'extreme_low': thresholds['extreme_high']
        }
        return self._score_positive_indicator(value, reversed_thresholds)
    
    def _score_neutral_indicator(
        self,
        value: float,
        thresholds: Dict[str, float]
    ) -> float:
        """中性指标得分计算（接近正常值得分高）"""
        warning_high = thresholds['warning_high']
        warning_low = thresholds['warning_low']
        
        # 正常区间：60-100分
        if warning_low <= value <= warning_high:
            # 越接近中值得分越高
            mid_point = (warning_low + warning_high) / 2
            distance = abs(value - mid_point)
            max_distance = (warning_high - warning_low) / 2
            score = 100.0 - (distance / max_distance) * 40.0
            return max(60.0, score)
        # 警告区间：30-60分
        elif value < warning_low:
            return 30.0 + (value / warning_low) * 30.0
        else:  # value > warning_high
            return 30.0 + ((thresholds['extreme_high'] - value) / 
                          (thresholds['extreme_high'] - warning_high)) * 30.0
    
    # ==================== 辅助方法：预警规则检查 ====================
    
    def _check_alert_rules(self, indicator_values: Dict[str, float]) -> List[Dict]:
        """
        检查预警规则
        
        逻辑:
        1. 遍历所有预警规则
        2. 解析条件表达式
        3. 评估条件是否满足
        4. 生成预警信息
        
        返回:
            预警列表（按优先级排序）
        """
        alerts = []
        
        # 获取预警规则配置
        alert_rules = self.config.get('alert_rules', [])
        
        for rule in alert_rules:
            try:
                # 构建条件上下文
                context = indicator_values.copy()
                
                # 解析条件（简化版：支持AND/OR）
                condition = rule.get('condition', '')
                condition = condition.replace('AND', 'and').replace('OR', 'or')
                
                # 评估条件
                try:
                    if eval(condition, {"__builtins__": None}, context):
                        # 生成预警
                        alerts.append({
                            'name': rule.get('name', '预警'),
                            'condition': condition,
                            'action': rule.get('action', 'notify'),
                            'priority': rule.get('priority', 'medium'),
                            'suggested_adjustment': float(rule.get('suggested_adjustment', 0.0)),
                            'affected_directions': rule.get('affected_directions', []),
                            'message': f"{rule.get('name')} | 条件：{condition}"
                        })
                except Exception as e:
                    self.logger.warning(
                        f"⚠️ 预警规则评估失败 {rule.get('name')}: {str(e)[:30]}"
                    )
                    continue
            
            except Exception as e:
                self.logger.warning(
                    f"⚠️ 预警规则处理失败: {str(e)[:30]}"
                )
                continue
        
        # 按优先级排序（high > medium > low）
        priority_map = {'high': 3, 'medium': 2, 'low': 1}
        alerts.sort(
            key=lambda x: priority_map.get(x['priority'], 0),
            reverse=True
        )
        
        return alerts[:5]  # 最多返回5条
    
    # ==================== 辅助方法：市场状态判定 ====================
    
    def _determine_market_state_from_macro(self, composite_score: float) -> str:
        """
        根据宏观综合评分判定市场状态
        
        逻辑:
        1. 获取市场状态阈值配置
        2. 根据评分映射到九宫格状态
        
        返回:
            市场状态字符串
        """
        # ✅ V6.1核心：动态获取市场状态阈值（优先ThresholdService）
        if self.threshold_service:
            try:
                strategic_offense = self.threshold_service.get_threshold(
                    'macro_strategic_offense_threshold',
                    context={'score': composite_score},
                    strategy='static'
                )
                active_allocation = self.threshold_service.get_threshold(
                    'macro_active_allocation_threshold',
                    context={'score': composite_score},
                    strategy='static'
                )
                balanced_hold = self.threshold_service.get_threshold(
                    'macro_balanced_hold_threshold',
                    context={'score': composite_score},
                    strategy='static'
                )
                defensive_watch = self.threshold_service.get_threshold(
                    'macro_defensive_watch_threshold',
                    context={'score': composite_score},
                    strategy='static'
                )
            except:
                # 降级：使用静态阈值
                thresholds = self.config.get('composite_scoring', {}).get(
                    'market_state_thresholds', {}
                )
                strategic_offense = thresholds.get('strategic_offense', 80)
                active_allocation = thresholds.get('active_allocation', 65)
                balanced_hold = thresholds.get('balanced_hold', 50)
                defensive_watch = thresholds.get('defensive_watch', 35)
        else:
            # 降级：使用静态阈值
            thresholds = self.config.get('composite_scoring', {}).get(
                'market_state_thresholds', {}
            )
            strategic_offense = thresholds.get('strategic_offense', 80)
            active_allocation = thresholds.get('active_allocation', 65)
            balanced_hold = thresholds.get('balanced_hold', 50)
            defensive_watch = thresholds.get('defensive_watch', 35)
        
        # 判定市场状态
        if composite_score >= strategic_offense:
            return '战略进攻区'
        elif composite_score >= active_allocation:
            return '积极配置区'
        elif composite_score >= balanced_hold:
            return '均衡持有区'
        elif composite_score >= defensive_watch:
            return '防御观望区'
        else:
            return '战略防御区'
    
    # ==================== 高级功能：宏观趋势数据 ====================
    
    def generate_macro_trend_data(
        self,
        history_days: int = 90
    ) -> Dict[str, Any]:
        """
        生成宏观趋势图表数据（用于可视化）
        
        返回:
            {
                'dates': List[str],
                'composite_score': List[float],
                'category_scores': {
                    'inflation': List[float],
                    'growth': List[float],
                    ...
                }
            }
        """
        # 模拟历史数据（实际应从数据库获取）
        dates = pd.date_range(end=datetime.now(), periods=history_days).strftime('%Y-%m-%d').tolist()
        
        # 模拟综合评分（随机波动）
        np.random.seed(42)
        base_score = 55.0
        composite_score = [
            float(np.clip(base_score + np.random.randn() * 5, 30, 80))
            for _ in range(history_days)
        ]
        
        # 模拟分类评分
        category_scores = {
            'inflation': [float(s * 0.9 + np.random.randn() * 3) for s in composite_score],
            'growth': [float(s * 1.05 + np.random.randn() * 3) for s in composite_score],
            'liquidity': [float(s * 0.95 + np.random.randn() * 3) for s in composite_score],
            'sentiment': [float(s * 1.0 + np.random.randn() * 3) for s in composite_score],
            'external_risk': [float(s * 0.85 + np.random.randn() * 3) for s in composite_score],
            'fund_sentiment': [float(s * 0.9 + np.random.randn() * 3) for s in composite_score]
        }
        
        return {
            'dates': dates,
            'composite_score': composite_score,
            'category_scores': category_scores,
            'timestamp': datetime.now().isoformat()
        }


# ==================== 使用示例 ====================
def example_macro_analysis_service():
    """MacroAnalysisService使用示例"""
    
    print("=" * 80)
    print("🧪 MacroAnalysisService 使用示例（V6.1阈值动态化）")
    print("=" * 80)
    
    # 1. 初始化服务（简化版）
    print("\n1️⃣ 初始化MacroAnalysisService...")
    
    class MockConfigService:
        def __init__(self):
            self.config = {
                'macro_indicators': {
                    'inflation': {
                        'enabled': True,
                        'weight': 0.20,
                        'indicators': {
                            'CPI': {
                                'code': '2_CPI',
                                'direction': 'negative',
                                'thresholds': {
                                    'warning_high': 3.0,
                                    'warning_low': -1.0,
                                    'extreme_high': 5.0,
                                    'extreme_low': -2.0
                                }
                            },
                            'PPI': {
                                'code': '2_PPI',
                                'direction': 'neutral',
                                'thresholds': {
                                    'warning_high': 5.0,
                                    'warning_low': -3.0,
                                    'extreme_high': 8.0,
                                    'extreme_low': -5.0
                                }
                            }
                        }
                    },
                    'growth': {
                        'enabled': True,
                        'weight': 0.25,
                        'indicators': {
                            'GDP': {
                                'code': '1_GDPI',
                                'direction': 'positive',
                                'thresholds': {
                                    'warning_high': 6.0,
                                    'warning_low': 4.0,
                                    'extreme_high': 8.0,
                                    'extreme_low': 2.0
                                }
                            }
                        }
                    },
                    'liquidity': {
                        'enabled': True,
                        'weight': 0.25,
                        'indicators': {
                            'shibor_3m': {
                                'code': '5_SHS3M',
                                'direction': 'negative',
                                'thresholds': {
                                    'warning_high': 3.5,
                                    'warning_low': 1.5,
                                    'extreme_high': 5.0,
                                    'extreme_low': 1.0
                                }
                            }
                        }
                    },
                    'sentiment': {
                        'enabled': True,
                        'weight': 0.15,
                        'indicators': {
                            'consumer_confidence': {
                                'code': '3_CCI',
                                'direction': 'positive',
                                'thresholds': {
                                    'warning_high': 110,
                                    'warning_low': 90,
                                    'extreme_high': 120,
                                    'extreme_low': 80
                                }
                            }
                        }
                    },
                    'external_risk': {
                        'enabled': True,
                        'weight': 0.15,
                        'indicators': {
                            'us_10y_yield': {
                                'code': '8_ATY',
                                'direction': 'negative',
                                'thresholds': {
                                    'warning_high': 4.5,
                                    'warning_low': 3.0,
                                    'extreme_high': 5.0,
                                    'extreme_low': 2.5
                                }
                            }
                        }
                    },
                    'fund_sentiment': {
                        'enabled': False,
                        'weight': 0.10,
                        'indicators': {}
                    }
                },
                'composite_scoring': {
                    'market_state_thresholds': {
                        'strategic_offense': 80,
                        'active_allocation': 65,
                        'balanced_hold': 50,
                        'defensive_watch': 35,
                        'strategic_defense': 20
                    }
                },
                'alert_rules': [
                    {
                        'name': '通胀上行预警',
                        'condition': 'CPI > 3.0 AND PPI > 5.0',
                        'action': 'reduce_equity_exposure',
                        'priority': 'high',
                        'suggested_adjustment': -0.10,
                        'affected_directions': ['文化消费', '现代农业']
                    }
                ]
            }
    
    class MockDataService:
        def load_macro_data(self, code, days):
            dates = pd.date_range(end=datetime.now(), periods=days)
            # 模拟数据（根据code返回不同值）
            if 'CPI' in code:
                values = np.linspace(2.0, 3.5, days) + np.random.randn(days) * 0.2
            elif 'PPI' in code:
                values = np.linspace(3.0, 6.0, days) + np.random.randn(days) * 0.3
            elif 'GDP' in code:
                values = np.linspace(4.5, 6.5, days) + np.random.randn(days) * 0.2
            elif 'SHS3M' in code:
                values = np.linspace(2.0, 4.0, days) + np.random.randn(days) * 0.15
            elif 'CCI' in code:
                values = np.linspace(95, 110, days) + np.random.randn(days) * 2
            elif 'ATY' in code:
                values = np.linspace(3.5, 4.8, days) + np.random.randn(days) * 0.1
            else:
                values = np.random.randn(days) * 10 + 50
            
            return pd.DataFrame({
                'datetime': dates,
                'close': values
            })
    
    config_service = MockConfigService()
    data_service = MockDataService()
    
    # 模拟ThresholdService（可选）
    class MockThresholdService:
        def get_threshold(self, name, context, strategy):
            # 模拟动态阈值
            if 'CPI' in name:
                return 3.2 if 'high' in name else -0.8
            elif 'GDP' in name:
                return 6.2 if 'high' in name else 4.2
            return 0.0
    
    threshold_service = MockThresholdService()
    
    macro_service = MacroAnalysisService(data_service, config_service, threshold_service)
    print("✅ 服务初始化成功")
    
    # 2. 计算宏观综合评分
    print("\n2️⃣ 计算宏观综合评分...")
    macro_result = macro_service.calculate_macro_composite_score()
    
    print(f"   ✅ 宏观综合评分: {macro_result['composite_score']:.1f}/100")
    print(f"   ✅ 市场状态: {macro_result['market_state']}")
    print(f"   ✅ 预警数量: {len(macro_result['alerts'])}")
    
    # 3. 显示分类得分
    print("\n3️⃣ 各分类得分:")
    for category, data in macro_result['category_scores'].items():
        print(f"   • {category:15s} | 得分: {data['score']:5.1f}/100 | 权重: {data['weight']:.0%}")
    
    # 4. 显示预警规则
    if macro_result['alerts']:
        print("\n4️⃣ 预警规则触发:")
        for alert in macro_result['alerts'][:3]:
            priority_emoji = '🔴' if alert['priority'] == 'high' else '🟠' if alert['priority'] == 'medium' else '🟡'
            print(f"   {priority_emoji} [{alert['priority'].upper()}] {alert['name']}: {alert['message']}")
    
    # 5. 验证数据类型
    print("\n5️⃣ 验证数据类型（防Plotly序列化错误）:")
    sample_score = macro_result['composite_score']
    is_python_float = isinstance(sample_score, float) and not isinstance(sample_score, np.floating)
    print(f"   ✅ 综合评分类型: {type(sample_score).__name__} | Python float: {is_python_float}")
    
    # 6. 宏观趋势数据（模拟）
    print("\n6️⃣ 宏观趋势数据（模拟）:")
    trend_data = macro_service.generate_macro_trend_data(days=30)
    print(f"   ✅ 数据点: {len(trend_data['dates'])}天")
    print(f"   ✅ 最新评分: {trend_data['composite_score'][-1]:.1f}/100")
    
    print("\n" + "=" * 80)
    print("✅ MacroAnalysisService 示例运行完成")
    print("=" * 80)


if __name__ == "__main__":
    example_macro_analysis_service()