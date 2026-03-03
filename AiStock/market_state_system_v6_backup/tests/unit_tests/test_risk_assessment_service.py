"""
V6.0 RiskAssessmentService单元测试
测试内容：
1. 微盘流动性评估
2. 高风险数据准备
3. 风险传导计算
4. 风险预警生成
"""
import pytest
import pandas as pd
import numpy as np
from unittest.mock import Mock, patch
import sys
sys.path.insert(0, '..')

from services.core_services.risk_assessment_service import RiskAssessmentService


class TestRiskAssessmentService:
    """RiskAssessmentService单元测试"""
    
    @pytest.fixture
    def mock_services(self):
        """模拟依赖服务"""
        data_service = Mock()
        config_service = Mock()
        
        # 模拟配置
        config_service.config = {
            'risk_thresholds': {
                'liquidity': {
                    'warning_shrink': 0.6,
                    'extreme_shrink': 0.4
                }
            },
            'high_risk_directions': {
                '文化消费': {'risk_score': 75, 'cap_weight': 0.15},
                '高端制造': {'risk_score': 58, 'cap_weight': 0.20}
            },
            'micro_cap_indices': ['930901', '931588'],
            'strategic_directions': {
                '文化消费': {'indices': ['930901', '931588']},
                '高端制造': {'indices': ['932042', '931865']}
            }
        }
        
        return data_service, config_service
    
    @pytest.fixture
    def sample_data(self):
        """生成样本数据"""
        dates = pd.date_range(end='2026-03-02', periods=500)
        df = pd.DataFrame({
            'datetime': dates,
            'close': np.random.randn(500).cumsum() + 100,
            'amount': np.random.rand(500) * 1000 + 500,
            'return_1d': np.random.randn(500) * 0.01,
            'volatility_20': np.random.rand(500) * 20 + 15
        })
        return df
    
    def test_assess_micro_liquidity_normal(self, mock_services, sample_data):
        """测试微盘流动性评估（正常状态）"""
        data_service, config_service = mock_services
        service = RiskAssessmentService(data_service, config_service)
        
        # 正常成交量（无收缩）
        df_normal = sample_data.copy()
        df_normal['amount'] = 1000  # 恒定成交量
        
        result = service.assess_micro_liquidity(df_normal)
        
        assert result['status'] == 'normal'
        assert result['stage'] == '正常期'
        assert result['risk_level'] == 'low'
        assert result['exposure_cap'] == 0.20
    
    def test_assess_micro_liquidity_warning(self, mock_services, sample_data):
        """测试微盘流动性评估（预警状态）"""
        data_service, config_service = mock_services
        service = RiskAssessmentService(data_service, config_service)
        
        # 流动性收缩（最近5天成交量下降）
        df_warning = sample_data.copy()
        df_warning.loc[df_warning.index[-5:], 'amount'] = 400  # 收缩到40%
        
        result = service.assess_micro_liquidity(df_warning)
        
        assert result['status'] == 'early_warning'
        assert result['stage'] == '观察期'
        assert result['risk_level'] == 'medium'
        assert result['exposure_cap'] == 0.15
    
    def test_assess_micro_liquidity_melted(self, mock_services, sample_data):
        """测试微盘流动性评估（熔断状态）"""
        data_service, config_service = mock_services
        service = RiskAssessmentService(data_service, config_service)
        
        # 严重流动性收缩（最近10天成交量下降）
        df_melted = sample_data.copy()
        df_melted.loc[df_melted.index[-10:], 'amount'] = 300  # 收缩到30%
        
        result = service.assess_micro_liquidity(df_melted)
        
        assert result['status'] == 'warning'
        assert result['stage'] == '熔断期'
        assert result['risk_level'] == 'high'
        assert result['exposure_cap'] == 0.00
    
    def test_prepare_high_risk_data(self, mock_services):
        """测试高风险数据准备"""
        data_service, config_service = mock_services
        service = RiskAssessmentService(data_service, config_service)
        
        result = service.prepare_high_risk_data()
        
        assert len(result) == 2  # 2个高风险方向
        assert result[0]['direction'] == '文化消费'
        assert result[0]['total'] > result[1]['total']  # 按综合得分降序
        
        # 验证所有字段为Python原生float
        for item in result:
            assert isinstance(item['micro'], float)
            assert isinstance(item['volatility'], float)
            assert isinstance(item['valuation'], float)
            assert isinstance(item['liquidity'], float)
            assert isinstance(item['total'], float)
    
    def test_calculate_risk_transmission(self, mock_services, sample_data):
        """测试风险传导计算"""
        data_service, config_service = mock_services
        service = RiskAssessmentService(data_service, config_service)
        
        benchmark_data = {
            '微盘': sample_data,
            '小盘': sample_data,
            '中盘': sample_data,
            '大盘': sample_data
        }
        
        result = service.calculate_risk_transmission(benchmark_data)
        
        assert '微盘' in result
        assert '小盘' in result
        assert '中盘' in result
        assert '大盘' in result
        
        # 验证风险得分在0-100范围内
        for size, metrics in result.items():
            assert 0 <= metrics['风险得分'] <= 100
            assert isinstance(metrics['风险得分'], float)
    
    def test_generate_risk_alerts(self, mock_services):
        """测试风险预警生成"""
        data_service, config_service = mock_services
        service = RiskAssessmentService(data_service, config_service)
        
        alerts = service.generate_risk_alerts(
            market_state='均衡持有区',
            pcr_value=1.2,
            micro_liquidity={'status': 'warning', 'distortion_flag': '严重失真'},
            basis_value=-1.8
        )
        
        assert len(alerts) > 0
        assert '微盘熔断' in alerts[0] or '微盘预警' in alerts[0]