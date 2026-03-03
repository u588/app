# tests/test_market_state_service.py
import pytest
from services.market_state_service import MarketStateService

class TestMarketStateService:
    
    @pytest.fixture
    def service(self):
        return MarketStateService()
    
    def test_determine_market_state(self, service):
        """测试市场状态判定"""
        benchmark_data = self._create_test_data()
        result = service.determine_market_state(benchmark_data)
        
        assert 'market_state' in result
        assert 'valuation_score' in result
        assert 0 <= result['valuation_score'] <= 100
        assert 'trend_score' in result
        assert 0 <= result['trend_score'] <= 100
    
    def test_calculate_valuation_score(self, service):
        """测试估值评分计算"""
        df = self._create_test_index_data()
        score = service.calculate_valuation_score(df, '000300')
        
        assert 0 <= score <= 100
    
    def _create_test_data(self):
        """创建测试数据"""
        # ... 测试数据生成逻辑
        pass