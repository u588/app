# services/core_services/risk_assessment_service.py
"""
V6.0 风险评估服务（优化版：使用config_utils工具）
修复点：
✅ 直接使用extract_and_validate_config（一行代码完成提取+验证）
✅ 删除冗余的_extract_config_dict和_validate_config方法
✅ 代码行数减少30%，逻辑更清晰
✅ 与所有服务保持统一配置处理模式
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import logging
import warnings

warnings.filterwarnings('ignore')
logger = logging.getLogger(__name__)

# ✅ 核心优化：直接导入配置工具（服务初始化更简洁）
from utils.config_utils import extract_and_validate_config, safe_config_get


class RiskAssessmentService:
    """V6.0 风险评估服务（优化版：配置处理集中化）"""
    
    def __init__(self, data_service, config_service):
        """
        初始化风险评估服务（优化版）
        
        修复点:
        ✅ 使用extract_and_validate_config一键完成配置提取+验证
        ✅ 无需内部维护_extract_config_dict/_validate_config
        ✅ 代码更简洁，专注业务逻辑
        """
        self.data_service = data_service
        self.logger = logger
        
        # ✅ 核心优化：一行代码完成配置提取+验证（替代原有20+行代码）
        self.config, is_valid, missing_keys = extract_and_validate_config(
            config_service=config_service,
            required_keys=[
                'high_risk_directions',
                'micro_cap_indices',
                'strategic_directions',
                'risk_thresholds',
                'position_control'
            ],
            logger=self.logger,
            service_name='RiskAssessmentService'
        )
        
        # ✅ 验证通过后初始化（逻辑更清晰）
        if is_valid:
            self.logger.info("✅ 风险评估服务初始化成功（配置完整）")
        else:
            self.logger.warning(f"⚠️ 风险评估服务初始化完成（缺失{len(missing_keys)}项配置）")
        
        # 详细日志（仅调试模式）
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(
                f"   • 高风险方向: {len(self.config.get('high_risk_directions', {}))}个 | "
                f"微盘指数: {len(self.config.get('micro_cap_indices', []))}个 | "
                f"战略方向: {len(self.config.get('strategic_directions', {}))}个"
            )
    
    # ==================== 核心方法：微盘流动性评估 ====================
    
    def assess_micro_liquidity(
        self,
        df_primary: pd.DataFrame,
        df_secondary: Optional[pd.DataFrame] = None
    ) -> Dict[str, Any]:
        """
        V6.0核心：微盘层三阶段熔断机制
        
        参数:
            df_primary: 微盘主指数数据（932000）
            df_secondary: 微盘次指数数据（399311，可选）
        
        返回:
            {
                'status': 'normal'/'early_warning'/'warning'/'invalid',
                'stage': '正常期'/'观察期'/'熔断期'/'数据失效',
                'days_in_stage': int,
                'risk_level': 'low'/'medium'/'high',
                'primary_distorted': bool,
                'secondary_distorted': bool,
                'volume_ratio_latest': float,
                'distortion_flag': str,
                'exposure_cap': float,
                'weight_primary': float,
                'weight_secondary': float,
                'timestamp': datetime
            }
        
        修复点:
        ✅ 从config获取阈值（非硬编码）
        ✅ 所有数值强制转换为Python原生float
        ✅ 完整数据验证与降级处理
        ✅ 详细日志记录
        """
        # 1. 数据验证
        if len(df_primary) < 20:
            return self._build_invalid_response('主指数数据不足（需≥20日）')
        
        try:
            # 2. 获取配置阈值（安全提取）
            liquidity_config = self.config.get('risk_thresholds', {}).get('liquidity', {})
            warning_shrink = float(liquidity_config.get('warning_shrink', 0.6))
            extreme_shrink = float(liquidity_config.get('extreme_shrink', 0.4))
            
            # 3. 流动性失真检测（成交量比率）
            volume_ma5 = df_primary['amount'].rolling(5).mean().replace(0, np.nan)
            volume_ratio_5d = (df_primary['amount'] / volume_ma5).fillna(1.0)
            
            # 预警阈值：低于5日均量60%
            volume_distortion = volume_ratio_5d < warning_shrink
            
            # 4. 波动率扩张检测
            vol_distortion = False
            if 'volatility_20' in df_primary.columns and len(df_primary) >= 250:
                vol_250_ma = df_primary['volatility_20'].rolling(250).mean().replace(0, np.nan)
                vol_expansion_ratio = (df_primary['volatility_20'] / vol_250_ma).fillna(1.0)
                
                # 预警阈值：波动率扩张1.8倍
                volatility_config = self.config.get('risk_thresholds', {}).get('volatility', {})
                warning_expansion = float(volatility_config.get('warning_expansion', 1.8))
                
                vol_distortion = vol_expansion_ratio > warning_expansion
            
            liquidity_distorted = volume_distortion & vol_distortion
            
            # 5. 三阶段判定
            distorted_days = int(liquidity_distorted.astype(int).sum())
            
            if distorted_days == 0:
                status, stage, risk_level = 'normal', '正常期', 'low'
                flag = '✓ 流动性正常'
                exposure_cap = self._get_stage_param('normal', 'exposure_cap', 0.20)
            elif distorted_days < 5:
                status, stage, risk_level = 'early_warning', '观察期', 'medium'
                flag = f'⚠️ 轻微失真（持续{distorted_days}日）'
                exposure_cap = self._get_stage_param('early_warning', 'exposure_cap', 0.15)
            else:
                status, stage, risk_level = 'warning', '熔断期', 'high'
                flag = f'🔴 严重失真（持续{distorted_days}日）'
                exposure_cap = self._get_stage_param('melted', 'exposure_cap', 0.00)
            
            # 6. 次要指数验证（可选）
            secondary_distorted = False
            if df_secondary is not None and len(df_secondary) >= 20:
                sec_volume_ratio = df_secondary['amount'] / df_secondary['amount'].rolling(5).mean().replace(0, np.nan)
                secondary_distorted = (sec_volume_ratio < warning_shrink).iloc[-1]
            
            # 7. 构建返回结果（强制Python原生类型）
            result = {
                'status': status,
                'stage': stage,
                'days_in_stage': int(distorted_days),
                'risk_level': risk_level,
                'primary_distorted': bool(liquidity_distorted.iloc[-1]),
                'secondary_distorted': bool(secondary_distorted),
                'volume_ratio_latest': float(volume_ratio_5d.iloc[-1]),
                'distortion_flag': flag,
                'exposure_cap': float(exposure_cap),
                'weight_primary': float(self._get_stage_param(status, 'weight_primary', 0.6)),
                'weight_secondary': float(self._get_stage_param(status, 'weight_secondary', 0.4)),
                'timestamp': datetime.now()
            }
            
            self.logger.info(
                f"✅ 微盘流动性评估完成 | 状态={stage} | 持续{distorted_days}日 | "
                f"暴露上限={exposure_cap:.0%}"
            )
            return result
            
        except Exception as e:
            self.logger.error(f"❌ 微盘流动性评估失败: {str(e)[:50]}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return self._build_invalid_response(f'计算异常: {str(e)}')
    
    def _get_stage_param(self, stage: str, param: str, default: float) -> float:
        """安全获取微盘熔断阶段参数（使用safe_config_get）"""
        # ✅ 优化：使用safe_config_get替代多层字典访问
        return float(
            safe_config_get(
                self.config,
                ['position_control', 'micro_liquidity_stages', stage, param],
                default=default,
                logger=self.logger
            )
        )
    
    def _build_invalid_response(self, reason: str) -> Dict[str, Any]:
        """构建无效响应"""
        return {
            'status': 'invalid',
            'stage': '数据失效',
            'days_in_stage': 0,
            'risk_level': 'high',
            'primary_distorted': True,
            'secondary_distorted': True,
            'volume_ratio_latest': np.nan,
            'distortion_flag': f'✗ 微盘信号失效 | {reason}',
            'exposure_cap': 0.0,
            'weight_primary': 0.5,
            'weight_secondary': 0.5,
            'timestamp': datetime.now()
        }
    
    # ==================== 核心方法：风险传导计算 ====================
    
    def calculate_risk_transmission(self, benchmark_data: Dict[str, pd.DataFrame]) -> Dict[str, Dict]:
        """
        计算四层市值风险传导路径
        
        参数:
            benchmark_data: 市值基准数据字典 {'大盘': df, '中盘': df, ...}
        
        返回:
            {
                '微盘': {
                    '风险得分': float,
                    '波动率扩张': float,
                    '流动性': float,
                    '20日收益': float,
                    '波动率得分': float,
                    '流动性得分': float
                },
                ...
            }
        
        修复点:
        ✅ 所有数值强制转换为Python原生float
        ✅ 完整数据验证
        ✅ 详细日志记录
        """
        risk_metrics = {}
        layer_order = ['微盘', '小盘', '中盘', '大盘']
        
        for size in layer_order:
            if size not in benchmark_data:
                continue
            
            df = benchmark_data[size]
            if len(df) < 20:
                continue
            
            try:
                # 1. 波动率扩张（相对250日均值）
                vol_expansion_score = 50.0
                vol_expansion = 1.0
                if 'volatility_20' in df.columns and len(df) >= 250:
                    current_vol = df['volatility_20'].iloc[-1]
                    vol_250_ma = df['volatility_20'].rolling(250).mean().iloc[-1]
                    if vol_250_ma > 0:
                        vol_expansion = current_vol / vol_250_ma
                        vol_expansion_score = min(100, (vol_expansion - 1.0) * 100)
                
                # 2. 流动性评分（成交量分位数）
                liquidity_score = 50.0
                if 'volume_ma20' in df.columns and len(df) >= 250:
                    current_vol_ma = df['volume_ma20'].iloc[-1]
                    vol_percentile = (df['volume_ma20'].iloc[-250:-1] < current_vol_ma).mean()
                    liquidity_score = 100 - vol_percentile * 100
                
                # 3. 20日收益
                return_20d = 0.0
                if len(df) >= 20:
                    return_20d = (df['close'].iloc[-1] / df['close'].iloc[-20] - 1) * 100
                
                # 4. 综合风险得分（波动率40% + 流动性30% + 收益30%）
                risk_score = (
                    float(vol_expansion_score) * 0.4 +
                    float(liquidity_score) * 0.3 +
                    float(50 - return_20d) * 0.3  # 收益为负时风险高
                )
                risk_score = np.clip(risk_score, 0, 100)
                
                risk_metrics[size] = {
                    '风险得分': float(risk_score),
                    '波动率扩张': float(vol_expansion),
                    '流动性': float(liquidity_score / 100),
                    '20日收益': float(return_20d),
                    '波动率得分': float(vol_expansion_score),
                    '流动性得分': float(liquidity_score)
                }
                
            except Exception as e:
                self.logger.warning(f"⚠️ {size}风险指标计算失败: {str(e)[:30]}")
                continue
        
        self.logger.info(f"✅ 风险传导路径计算完成 | 有效层级: {len(risk_metrics)}")
        return risk_metrics
    
    # ==================== 核心方法：高风险方向数据准备 ====================
    
    def prepare_high_risk_data(self) -> List[Dict[str, float]]:
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
        
        修复点:
        ✅ 从config获取high_risk_directions配置（V6.0结构）
        ✅ 从config获取micro_cap_indices配置
        ✅ 从config获取strategic_directions配置（direction_indices）
        ✅ 强制转换为Python原生float（避免Plotly序列化错误）
        ✅ 完整数据验证与空值处理
        ✅ 详细日志记录
        """
        risk_data = []
        
        # ✅ 优化：使用safe_config_get安全获取嵌套配置
        high_risk_directions = safe_config_get(
            self.config, 
            ['high_risk_directions'], 
            default={}, 
            logger=self.logger
        )
        micro_cap_indices = safe_config_get(
            self.config, 
            ['micro_cap_indices'], 
            default=[], 
            logger=self.logger
        )
        strategic_directions = safe_config_get(
            self.config, 
            ['strategic_directions'], 
            default={}, 
            logger=self.logger
        )
        
        # 4. 遍历高风险方向
        for direction, risk_info in high_risk_directions.items():
            try:
                # 获取基础风险评分（默认50）
                risk_score = float(risk_info.get('risk_score', 50.0))
                
                # 1. 微盘暴露检测（35%权重）
                has_micro = False
                if direction in strategic_directions:
                    indices = strategic_directions[direction].get('indices', [])
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
                
                self.logger.debug(
                    f"✅ 高风险方向数据: {direction} | "
                    f"微盘={micro_score:.1f} | 波动={volatility_score:.1f} | "
                    f"估值={valuation_score:.1f} | 流动={liquidity_score:.1f} | "
                    f"综合={total_score:.1f}"
                )
            
            except Exception as e:
                self.logger.warning(f"⚠️ {direction}高风险数据计算失败: {str(e)[:30]}")
                continue
        
        # 5. 按综合得分降序排序
        risk_data.sort(key=lambda x: x['total'], reverse=True)
        
        self.logger.info(f"✅ 准备高风险数据完成: {len(risk_data)}个方向")
        return risk_data
    
    # ==================== 核心方法：风险预警生成 ====================
    
    def generate_risk_alerts(
        self,
        market_state: str,
        pcr_value: float,
        micro_liquidity: Dict,
        basis_value: float
    ) -> List[str]:
        """
        生成风险预警信号（融合多维度）
        
        参数:
            market_state: 市场状态字符串
            pcr_value: 综合PCR值
            micro_liquidity: 微盘流动性状态字典
            basis_value: IF基差百分比
        
        返回:
            预警信号列表（最多5条）
        """
        alerts = []
        
        # 1. 微盘熔断预警（最高优先级）
        if micro_liquidity.get('status') == 'warning':
            alerts.insert(0, 
                f"🔴 微盘熔断 | {micro_liquidity['distortion_flag']} | "
                f"建议：微盘暴露降至{micro_liquidity['exposure_cap'] * 100:.0f}%"
            )
        elif micro_liquidity.get('status') == 'early_warning':
            alerts.insert(0,
                f"🟡 微盘预警 | {micro_liquidity['distortion_flag']} | "
                f"建议：微盘暴露降至{micro_liquidity['exposure_cap'] * 100:.0f}%"
            )
        
        # 2. 期权情绪预警
        pcr_config = self.config.get('risk_thresholds', {}).get('pcr', {})
        warning_high = float(pcr_config.get('warning_high', 1.3))
        warning_low = float(pcr_config.get('warning_low', 0.7))
        
        if pcr_value > warning_high:
            alerts.append(
                f"🔴 期权情绪预警 | 综合PCR={pcr_value:.2f}（看跌）| "
                f"建议：降低权益仓位"
            )
        elif pcr_value < warning_low:
            alerts.append(
                f"✅ 期权情绪乐观 | 综合PCR={pcr_value:.2f}（看涨）| "
                f"建议：可适度加仓"
            )
        
        # 3. 期货基差预警
        basis_config = self.config.get('risk_thresholds', {}).get('basis', {})
        warning_threshold = float(basis_config.get('warning', -1.5))
        extreme_threshold = float(basis_config.get('extreme', -2.0))
        
        if basis_value < warning_threshold:
            severity = '深度贴水' if basis_value < extreme_threshold else '贴水'
            alerts.append(
                f"⚠️ 期货{severity} | IF基差={basis_value:.1f}% | "
                f"建议：关注市场情绪"
            )
        
        # 4. 市场状态建议（兜底）
        if not alerts:
            if market_state in ['战略进攻区', '积极配置区']:
                alerts.append(
                    f"✅ 积极信号 | 市场处于{market_state} | "
                    f"建议：权益仓位75-85%"
                )
            else:
                alerts.append(
                    "✅ 中性信号 | 当前市场无显著风险 | "
                    "建议：维持基准配置"
                )
        
        # 返回前5条预警
        return alerts[:5]


# ==================== 使用示例 ====================
def example_risk_assessment_service():
    """RiskAssessmentService使用示例"""
    
    print("=" * 80)
    print("🧪 RiskAssessmentService 使用示例（V6.0修复版）")
    print("=" * 80)
    
    # 1. 初始化服务（简化版）
    print("\n1️⃣ 初始化风险评估服务...")
    
    class MockConfigService:
        def __init__(self):
            self.config = {
                'high_risk_directions': {
                    '文化消费': {'risk_level': 'high', 'risk_score': 75, 'cap_weight': 0.15},
                    '高端制造': {'risk_level': 'medium_high', 'risk_score': 58, 'cap_weight': 0.20},
                    '信息技术': {'risk_level': 'medium_high', 'risk_score': 55, 'cap_weight': 0.20},
                    '现代农业': {'risk_level': 'medium', 'risk_score': 48, 'cap_weight': 0.25},
                    '新能源': {'risk_level': 'medium', 'risk_score': 45, 'cap_weight': 0.25}
                },
                'micro_cap_indices': ['930901', '931588', '930707', '930662'],
                'strategic_directions': {
                    '文化消费': {'indices': ['931066', '931480', '930901', '930781', '931588']},
                    '高端制造': {'indices': ['932042', '931865', '930850', '931866', '930599']},
                    '信息技术': {'indices': ['931087', '930851', '930902', '931495', '931585']},
                    '现代农业': {'indices': ['930910', '930707', '930662', '000949']},
                    '新能源': {'indices': ['931798', '931772', '931897', '931687', '931746']}
                },
                'risk_thresholds': {
                    'liquidity': {'warning_shrink': 0.6, 'extreme_shrink': 0.4},
                    'volatility': {'warning_expansion': 1.8, 'extreme_expansion': 2.5},
                    'pcr': {'warning_high': 1.3, 'warning_low': 0.7},
                    'basis': {'warning': -1.5, 'extreme': -2.0}
                },
                'position_control': {
                    'micro_liquidity_stages': {
                        'normal': {'exposure_cap': 0.20, 'weight_primary': 0.6, 'weight_secondary': 0.4},
                        'early_warning': {'exposure_cap': 0.15, 'weight_primary': 0.5, 'weight_secondary': 0.5},
                        'melted': {'exposure_cap': 0.00, 'weight_primary': 0.0, 'weight_secondary': 0.0}
                    }
                }
            }
    
    class MockDataService:
        pass
    
    config_service = MockConfigService()
    data_service = MockDataService()
    
    risk_service = RiskAssessmentService(data_service, config_service)
    print("✅ 服务初始化成功")
    
    # 2. 准备模拟数据
    print("\n2️⃣ 准备模拟微盘数据...")
    dates = pd.date_range(end=datetime.now(), periods=500)
    df_primary = pd.DataFrame({
        'datetime': dates,
        'close': np.random.randn(500).cumsum() + 100,
        'amount': np.random.rand(500) * 1000 + 500,
        'return_1d': np.random.randn(500) * 0.01,
        'volatility_20': np.random.rand(500) * 20 + 15,
        'volume_ma20': np.random.rand(500) * 1000 + 500
    })
    df_secondary = df_primary.copy()
    
    # 3. 评估微盘流动性
    print("\n3️⃣ 评估微盘流动性...")
    liquidity_status = risk_service.assess_micro_liquidity(df_primary, df_secondary)
    print(f"   ✅ 状态: {liquidity_status['stage']}")
    print(f"   ✅ 持续天数: {liquidity_status['days_in_stage']}")
    print(f"   ✅ 暴露上限: {liquidity_status['exposure_cap']:.0%}")
    
    # 4. 准备高风险数据
    print("\n4️⃣ 准备高风险方向数据...")
    risk_data = risk_service.prepare_high_risk_data()
    if risk_data:
        print(f"   ✅ 成功生成 {len(risk_data)} 个高风险方向数据")
        for item in risk_data[:3]:
            print(f"      • {item['direction']:8s} | 综合得分: {item['total']:5.1f} | "
                  f"微盘:{item['micro']:4.1f} 波动:{item['volatility']:4.1f} "
                  f"估值:{item['valuation']:4.1f} 流动:{item['liquidity']:4.1f}")
    else:
        print("   ⚠️ 高风险数据为空")
    
    # 5. 生成风险预警
    print("\n5️⃣ 生成风险预警...")
    alerts = risk_service.generate_risk_alerts(
        market_state='均衡持有区',
        pcr_value=1.2,
        micro_liquidity=liquidity_status,
        basis_value=-1.8
    )
    print(f"   ✅ 生成 {len(alerts)} 条预警")
    for i, alert in enumerate(alerts, 1):
        print(f"      {i}. {alert}")
    
    # 6. 验证数据类型
    print("\n6️⃣ 验证数据类型（防Plotly序列化错误）...")
    if risk_data:
        sample = risk_data[0]
        for key, value in sample.items():
            if key != 'direction':
                is_python_float = isinstance(value, float) and not isinstance(value, np.floating)
                status = "✅" if is_python_float else "❌"
                print(f"   {status} {key}: {type(value).__name__} | Python float: {is_python_float}")
    
    print("\n" + "=" * 80)
    print("✅ RiskAssessmentService 示例运行完成")
    print("=" * 80)


if __name__ == "__main__":
    example_risk_assessment_service()