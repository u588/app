# ==================== 4.1.6 宏观分析服务 （宏观分析：五维评分 + 预警规则）MacroAnalysisService ====================
# macro_analysis_service_v6.py
"""
V6.0 宏观分析服务（完全独立，无循环依赖）
职责：
1. 宏观综合评分计算（五维加权）
2. 预警规则检查
3. 市场状态判定
依赖：
- 仅依赖DataLoadingService和ConfigService
- 所有指标独立计算，无外部业务服务依赖
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class MacroAnalysisService:
    """V6.0 宏观分析服务（修复版：完全独立）"""
    
    def __init__(self, data_service, config_service):
        """
        初始化宏观分析服务
        
        参数:
            data_service: DataLoadingService实例
            config_service: ConfigService实例
        """
        self.data_service = data_service
        self.config_service = config_service
        self.logger = logger
        self.logger.info("✅ 宏观分析服务初始化成功（V6.0独立版）")
    
    def calculate_macro_composite_score(self) -> Dict:
        """
        计算宏观综合评分（五维加权）
        
        返回:
            {
                'composite_score': float,          # 综合评分(0-100)
                'category_scores': {               # 各分类得分
                    'inflation': {'score': float, 'weight': float, ...},
                    'growth': {...},
                    ...
                },
                'alerts': List[Dict],              # 预警列表
                'market_state': str,               # 市场状态
                'indicator_values': Dict,          # 指标值
                'timestamp': str
            }
        """
        # 1. 加载各指标最新数据
        indicator_values = {}
        category_scores = {}
        
        # 获取宏观指标配置
        macro_config = self.config_service.config.get('macro_indicators', {})
        
        for category, cat_config in macro_config.items():
            if not cat_config.get('enabled', False):
                continue
            
            category_weight = cat_config.get('weight', 0.2)
            indicators = cat_config.get('indicators', {})
            
            # 计算该分类得分
            cat_score_sum = 0
            cat_weight_sum = 0
            
            for ind_name, ind_config in indicators.items():
                code = ind_config.get('code')
                weight = ind_config.get('weight', 1.0)
                direction = ind_config.get('direction', 'positive')
                
                # 加载数据
                df = self.data_service.load_macro_data(code, days=30)
                if len(df) > 0:
                    value = df['close'].iloc[-1]
                    indicator_values[ind_name] = float(value)
                    
                    # 根据阈值计算得分（0-100）
                    score = self._calculate_indicator_score(value, ind_config, direction)
                    cat_score_sum += score * weight
                    cat_weight_sum += weight
            
            # 分类综合得分
            if cat_weight_sum > 0:
                category_scores[category] = {
                    'score': float(cat_score_sum / cat_weight_sum),
                    'weight': category_weight,
                    'indicators': {k: v for k, v in indicator_values.items() if k in indicators}
                }
        
        # 2. 计算综合评分（加权平均）
        composite_score = 0
        total_weight = 0
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
        
        return {
            'composite_score': composite_score,
            'category_scores': category_scores,
            'alerts': alerts,
            'market_state': market_state,
            'indicator_values': indicator_values,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    
    def _calculate_indicator_score(self, value: float, config: Dict, direction: str) -> float:
        """根据指标值和阈值计算得分（0-100）"""
        thresholds = config.get('thresholds', {})
        
        if direction == 'positive':
            # 正向指标：值越大越好
            if 'extreme_high' in thresholds and value >= thresholds['extreme_high']:
                return 90.0
            elif 'warning_high' in thresholds and value >= thresholds['warning_high']:
                return 75.0
            elif 'warning_low' in thresholds and value >= thresholds['warning_low']:
                return 50.0
            elif 'extreme_low' in thresholds and value >= thresholds['extreme_low']:
                return 30.0
            else:
                return 10.0
        else:
            # 负向指标：值越小越好
            if 'extreme_low' in thresholds and value <= thresholds['extreme_low']:
                return 90.0
            elif 'warning_low' in thresholds and value <= thresholds['warning_low']:
                return 75.0
            elif 'warning_high' in thresholds and value <= thresholds['warning_high']:
                return 50.0
            elif 'extreme_high' in thresholds and value <= thresholds['extreme_high']:
                return 30.0
            else:
                return 10.0
    
    def _check_alert_rules(self, indicator_values: Dict) -> List[Dict]:
        """检查预警规则"""
        alerts = []
        
        # 获取预警规则配置
        alert_rules = self.config_service.config.get('alert_rules', [])
        
        for rule in alert_rules:
            condition = rule.get('condition', '')
            
            # 简化条件解析（实际应使用表达式解析器）
            try:
                # 替换指标名为实际值
                eval_condition = condition
                for ind_name, value in indicator_values.items():
                    eval_condition = eval_condition.replace(ind_name, str(value))
                
                # 评估条件
                if eval(eval_condition):
                    alerts.append({
                        'name': rule.get('name', '预警'),
                        'condition': condition,
                        'action': rule.get('action', 'notify'),
                        'priority': rule.get('priority', 'medium'),
                        'suggested_adjustment': rule.get('suggested_adjustment', 0.0),
                        'affected_directions': rule.get('affected_directions', []),
                        'message': f"{rule.get('name')} | 条件：{condition}"
                    })
            except Exception as e:
                self.logger.warning(f"⚠️ 预警规则评估失败：{str(e)[:50]}")
        
        # 按优先级排序
        priority_map = {'high': 3, 'medium': 2, 'low': 1}
        alerts.sort(key=lambda x: priority_map.get(x['priority'], 0), reverse=True)
        
        return alerts[:5]  # 最多返回5条
    
    def _determine_market_state_from_macro(self, composite_score: float) -> str:
        """根据宏观综合评分判定市场状态"""
        # 获取市场状态阈值配置
        thresholds = self.config_service.config.get('composite_scoring', {}).get(
            'market_state_thresholds', {}
        )
        
        if composite_score >= thresholds.get('strategic_offense', 80):
            return '战略进攻区'
        elif composite_score >= thresholds.get('active_allocation', 65):
            return '积极配置区'
        elif composite_score >= thresholds.get('balanced_hold', 50):
            return '均衡持有区'
        elif composite_score >= thresholds.get('defensive_watch', 35):
            return '防御观望区'
        else:
            return '战略防御区'
    
    def generate_macro_trend_data(self, history_days: int = 90) -> Dict:
        """
        生成宏观趋势图表数据（用于可视化）
        
        参数:
            history_days: 历史数据天数
        
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
        # 简化实现：返回模拟数据（实际应计算历史评分）
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
            'external_risk': [float(s * 0.85 + np.random.randn() * 3) for s in composite_score]
        }
        
        return {
            'dates': dates,
            'composite_score': composite_score,
            'category_scores': category_scores,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }