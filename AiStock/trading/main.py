# trading/main.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from base_services.config_service import ConfigService
from trading.adapters.qmt_adapter import QMTAdapter
from trading.core.execution_engine import ExecutionEngine
from dynamic_price_system.core.dynamic_price_engine import DynamicPriceEngine

def run_live_trading():
    # 1. 初始化配置
    config = ConfigService(system_name='dynamic_price')
    
    # 2. 初始化券商适配器
    broker_cfg = config.get('trading.broker.qmt', {})
    broker = QMTAdapter(path=broker_cfg['path'], session_id=broker_cfg['session_id'])
    
    # 3. 初始化交易引擎
    trading_cfg_path = Path(__file__).parent / 'config' / 'trading_config.yaml'
    engine = ExecutionEngine(broker=broker, config_path=str(trading_cfg_path))
    
    # 4. 开盘初始化
    engine.start_trading_day()
    
    # 5. 获取策略目标权重（对接您的 DynamicPriceEngine）
    # target_weights = strategy_engine.calculate_target_weights(...)
    target_weights = {'600938': 0.12, '601899': 0.10, '300750': 0.08}  # 示例
    current_positions = broker.get_positions()
    market_prices = {'600938': 42.24, '601899': 32.40, '300750': 400.50}
    
    # 6. 执行调仓
    executed = engine.execute_rebalance(target_weights, current_positions, market_prices)
    print(f"✅ 成功提交 {len(executed)} 笔委托")
    
    # 7. 盘中循环（可接入定时任务或事件驱动）
    # while market_open:
    #     engine.order_mgr.check_timeout_orders()
    #     time.sleep(5)
    
    # 8. 收盘同步与清理
    engine.sync_positions()
    engine.close_trading_day()

if __name__ == '__main__':
    run_live_trading()