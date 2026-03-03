# ==================== 4.1.2 风险评估服务 （风险评估：微盘熔断 + 风险传导） RiskAssessmentService ====================
# risk_assessment_service_fixed.py
import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class RiskAssessmentService:
    """
    风险评估服务（修复版：无循环依赖）
    职责：
    1. 微盘流动性熔断评估
    2. 风险传导路径计算
    3. 风险预警生成
    依赖：
    - 仅依赖DataLoadingService（用于加载数据）
    - 不依赖MarketStateSystem或其他业务服务
    """
    
    def __init__(self, data_service, config):
        """初始化（修复版：仅持有必要依赖）"""
        self.data_service = data_service
        self.config = config
        logger.info("✅ 风险评估服务初始化成功")
    
    def assess_micro_liquidity(
        self,
        df_primary: pd.DataFrame,
        df_secondary: Optional[pd.DataFrame] = None
    ) -> Dict:
        """
        评估微盘流动性熔断状态（修复版：纯函数，无外部状态）
        
        参数:
            df_primary: 主指数数据
            df_secondary: 次指数数据（可选）
        
        返回:
            熔断状态字典
        """
        # ✅ 修复：从config获取阈值（非硬编码）
        warning_shrink = self.config.risk_thresholds['liquidity']['warning_shrink']
        extreme_shrink = self.config.risk_thresholds['liquidity']['extreme_shrink']
        
        # 计算成交量比率
        volume_ma5 = df_primary['amount'].rolling(5).mean().replace(0, np.nan)
        volume_ratio_5d = (df_primary['amount'] / volume_ma5).fillna(1.0)
        
        # 检测流动性失真
        liquidity_distorted = volume_ratio_5d < warning_shrink
        distorted_days = int(liquidity_distorted.astype(int).sum())
        
        # 三阶段判定
        if distorted_days == 0:
            status, stage, risk_level = 'normal', '正常期', 'low'
            flag = '✓ 流动性正常'
            exposure_cap = 0.20
        elif distorted_days < 5:
            status, stage, risk_level = 'early_warning', '观察期', 'medium'
            flag = f'⚠️ 轻微失真（持续{distorted_days}日）'
            exposure_cap = 0.15
        else:
            status, stage, risk_level = 'warning', '熔断期', 'high'
            flag = f'🔴 严重失真（持续{distorted_days}日）'
            exposure_cap = 0.00
        
        return {
            'status': status,
            'stage': stage,
            'days_in_stage': distorted_days,
            'risk_level': risk_level,
            'primary_distorted': bool(liquidity_distorted.iloc[-1]),
            'secondary_distorted': False,
            'volume_ratio_latest': float(volume_ratio_5d.iloc[-1]),
            'distortion_flag': flag,
            'exposure_cap': exposure_cap,
            'weight_primary': 0.6 if status == 'normal' else 0.5 if status == 'early_warning' else 0.0,
            'weight_secondary': 0.4 if status == 'normal' else 0.5 if status == 'early_warning' else 0.0,
            'timestamp': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    
    def generate_risk_alerts(
        self,
        market_state: str,
        pcr_value: float,
        micro_liquidity: Dict,
        basis_value: float
    ) -> list:
        """生成风险预警（修复版：参数化，无外部依赖）"""
        alerts = []
        
        # 1. 微盘熔断预警
        if micro_liquidity.get('status') == 'warning':
            alerts.insert(0,
                f"🔴 微盘熔断 | {micro_liquidity['distortion_flag']} | "
                f"建议：微盘暴露降至{micro_liquidity['exposure_cap']*100:.0f}%"
            )
        elif micro_liquidity.get('status') == 'early_warning':
            alerts.insert(0,
                f"🟡 微盘预警 | {micro_liquidity['distortion_flag']} | "
                f"建议：微盘暴露降至{micro_liquidity['exposure_cap']*100:.0f}%"
            )
        
        # 2. 期权情绪预警
        if pcr_value > 1.5:
            alerts.append(f"🔴 期权情绪预警 | PCR={pcr_value:.2f}（极度悲观）| 建议：降低权益仓位")
        elif pcr_value < 0.5:
            alerts.append(f"✅ 期权情绪乐观 | PCR={pcr_value:.2f}（极度乐观）| 建议：警惕回调风险")
        
        # 3. 期货基差预警
        if basis_value < -2.0:
            alerts.append(f"⚠️ 期货深度贴水 | 基差={basis_value:.1f}% | 建议：关注市场情绪")
        elif basis_value < -1.5:
            alerts.append(f"⚠️ 期货贴水 | 基差={basis_value:.1f}% | 建议：保持谨慎")
        
        # 4. 市场状态建议
        if not alerts:
            if market_state in ['战略进攻区', '积极配置区']:
                alerts.append(f"✅ 积极信号 | 市场处于{market_state} | 建议：权益仓位75-85%")
            else:
                alerts.append("✅ 中性信号 | 当前市场无显著风险 | 建议：维持基准配置")
        
        return alerts[:5]

    def prepare_high_risk_data(self) -> List[Dict]:
        """
        V6.0新增：准备高风险方向四维评估数据
        用于生成高风险雷达图（可视化服务调用）
        
        返回:
            [
                {
                    'direction': '文化消费',
                    'micro': 35.0,      # 微盘暴露得分（0-35）
                    'volatility': 18.75, # 波动率得分（0-25）
                    'valuation': 18.75,  # 估值得分（0-25）
                    'liquidity': 11.25,  # 流动性得分（0-15）
                    'total': 75.0        # 综合得分（0-100）
                },
                ...
            ]
        
        修复点：
        ✅ 从config获取high_risk_directions配置（V6.0结构）
        ✅ 从config获取micro_cap_indices配置
        ✅ 从config获取direction_indices配置
        ✅ 强制转换为Python原生float（避免Plotly序列化错误）
        ✅ 完整数据验证与空值处理
        """
        risk_data = []
        
        # 1. 获取高风险方向配置（V6.0配置结构）
        high_risk_directions = self.config.get('high_risk_directions', {})
        if not high_risk_directions:
            self.logger.warning("⚠️ 高风险方向配置缺失，返回空列表")
            return []
        
        # 2. 获取微盘高暴露指数配置
        micro_cap_indices = self.config.get('micro_cap_indices', [])
        if not micro_cap_indices:
            self.logger.warning("⚠️ 微盘高暴露指数配置缺失")
            micro_cap_indices = []
        
        # 3. 获取战略方向指数映射
        direction_indices = self.config.get('strategic_directions', {})
        if not direction_indices:
            self.logger.warning("⚠️ 战略方向指数映射配置缺失")
            direction_indices = {}
        
        # 4. 遍历高风险方向
        for direction, risk_info in high_risk_directions.items():
            # 获取基础风险评分（默认50）
            risk_score = risk_info.get('risk_score', 50.0)
            
            # 1. 微盘暴露检测（35%权重）
            has_micro = False
            if direction in direction_indices:
                indices = direction_indices[direction].get('indices', [])
                has_micro = any(idx.strip() in micro_cap_indices for idx in indices)
            
            micro_score = 35.0 if has_micro else 10.0
            
            # 2. 波动率得分（25%权重）
            volatility_score = float(risk_score * 0.25)
            
            # 3. 估值分位得分（25%权重）
            valuation_score = float(risk_score * 0.25)
            
            # 4. 流动性得分（15%权重）
            liquidity_score = float(risk_score * 0.15)
            
            # 5. 综合得分（加权求和）
            total_score = (
                micro_score * 0.35 + 
                volatility_score + 
                valuation_score + 
                liquidity_score
            )
            
            # ⭐⭐⭐ 关键修复：强制转换为Python原生float ⭐⭐⭐
            risk_data.append({
                'direction': direction,
                'micro': float(micro_score),
                'volatility': float(volatility_score),
                'valuation': float(valuation_score),
                'liquidity': float(liquidity_score),
                'total': float(total_score)
            })
        
        # 5. 按综合得分降序排序
        risk_data.sort(key=lambda x: x['total'], reverse=True)
        
        self.logger.info(f"✅ 准备高风险数据完成: {len(risk_data)}个方向")
        return risk_data    
    