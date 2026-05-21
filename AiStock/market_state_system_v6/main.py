from main_system.market_state_system_v6 import MarketStateSystem

system = MarketStateSystem('./system_config_v6.yaml')
result = system.run()
# system.show_in_jupyter()  # 生成18大图表