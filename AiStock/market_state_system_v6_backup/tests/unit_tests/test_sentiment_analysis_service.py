"""
V6.0 SentimentAnalysisService单元测试
测试内容：
1. 情绪指标计算
2. 资金流向热力图
3. 情绪仪表盘生成
"""
import pytest
import pandas as pd
import numpy as np
from unittest.mock import Mock, patch
import sys
sys.path.insert(0, '..')

from services.core_services.sentiment_analysis_service import SentimentAnalysisService


class TestSentimentAnalysisService:
    """SentimentAnalysisService单元测试"""
    
    @pytest.fixture
    def mock_services(self):
        """模拟依赖服务"""
        data_service = Mock()
        config_service = Mock()
        
        # 模拟数据加载
        def mock_load_macro_data(code, days):
            dates = pd.date_range(end='2026-03-02', periods=days)
            if code == '7_RZ':  # 融资余额
                values = np.linspace(15000, 16000, days) + np.random.randn(days) * 100
            elif code == '7_TON':  # 北上资金
                values = np.linspace(18000, 19000, days) + np.random.randn(days) * 100
            elif code == '7_TETF':  # ETF规模
                values = np.linspace(20000, 21000, days) + np.random.randn(days) * 100
            elif code == '7_TOS':  # 南下资金
                values = np.linspace(12000, 13000, days) + np.random.randn(days) * 100
            else:
                values = np.random.randn(days) * 100 + 100
            
            return pd.DataFrame({
                'datetime': dates,
                'close': values
            })
        
        data_service.load_macro_data.side_effect = mock_load_macro_data
        
        return data_service, config_service
    
    def test_calculate_sentiment_scores(self, mock_services):
        """测试情绪指标计算"""
        data_service, config_service = mock_services
        service = SentimentAnalysisService(data_service, config_service)
        
        result = service.calculate_sentiment_scores()
        
        # 验证返回结构
        assert 'margin_score' in result
        assert 'fund_score' in result
        assert 'vol_score' in result
        assert 'vix_score' in result
        
        # 验证所有值为Python原生float
        assert isinstance(result['margin_score'], float)
        assert isinstance(result['fund_score'], float)
        assert isinstance(result['vol_score'], float)
        assert isinstance(result['vix_score'], float)
        
        # 验证范围在0-100
        assert 0 <= result['margin_score'] <= 100
        assert 0 <= result['fund_score'] <= 100
        assert 0 <= result['vol_score'] <= 100
        assert 0 <= result['vix_score'] <= 100
    
    def test_calculate_fund_flow_heatmap(self, mock_services):
        """测试资金流向热力图"""
        data_service, config_service = mock_services
        service = SentimentAnalysisService(data_service, config_service)
        
        result = service.calculate_fund_flow_heatmap()
        
        # 验证返回结构
        assert 'categories' in result
        assert 'data_values' in result
        assert len(result['categories']) == 4  # 4个资金类型
        assert len(result['data_values']) == 4
        
        # 验证所有值为Python原生float
        for row in result['data_values']:
            assert len(row) == 3  # 5d, 10d, 20d
            for value in row:
                assert isinstance(value, float)
    
    def test_calculate_fund_flow_heatmap_with_missing_data(self, mock_services):
        """测试资金流向热力图（数据缺失情况）"""
        data_service, config_service = mock_services
        
        # 模拟数据加载失败
        def mock_load_fail(code, days):
            raise Exception("数据加载失败")
        
        data_service.load_macro_data.side_effect = mock_load_fail
        
        service = SentimentAnalysisService(data_service, config_service)
        result = service.calculate_fund_flow_heatmap()
        
        # 验证降级策略生效（返回简化数据）
        assert len(result['data_values']) == 4
        for row in result['data_values']:
            assert len(row) == 3
            assert all(isinstance(v, float) for v in row)