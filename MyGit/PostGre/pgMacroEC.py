from sqlalchemy import create_engine
import tushare as ts

eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/MacroEC')

try:
	# 存款利率
	df = ts.get_deposit_rate()
	df.to_sql('DepoR',eng, if_exists='replace')
	print('存款利率 ok')

	# 贷款利率
	df = ts.get_loan_rate()
	df.to_sql('LoanR',eng, if_exists='replace')
	print('贷款利率 ok')
	
	# 存款准备金率
	df = ts.get_rrr()
	df.to_sql('RRR',eng, if_exists='replace')
	print('存款准备金率 ok')

	#货币供应量
	df = ts.get_money_supply()
	df.to_sql('MS',eng, if_exists='replace')
	print('货币供应量 ok')


	# 货币供应量(年底余额)
	df = ts.get_money_supply_bal()
	df.to_sql('MSB',eng, if_exists='replace')
	print('货币供应量(年底余额) ok')

	# 国内生产总值(年度)
	df = ts.get_gdp_year()
	df.to_sql('GDPy',eng, if_exists='replace')
	print('国内生产总值(年度) ok')

	# 国内生产总值(季度)
	df = ts.get_gdp_quarter()
	df.to_sql('GDPq',eng, if_exists='replace')
	print('国内生产总值(季度) ok')


	#三大需求对GDP贡献
	df = ts.get_gdp_for()
	df.to_sql('GDPf',eng, if_exists='replace')
	print('三大需求对GDP贡献 ok')

	# 三大产业对GDP拉动
	df = ts.get_gdp_pull()
	df.to_sql('GDPp',eng, if_exists='replace')
	print('三大产业对GDP拉动 ok')


	# 三大产业贡献率
	df = ts.get_gdp_contrib()
	df.to_sql('GDPc',eng, if_exists='replace')
	print('三大产业贡献率 ok')


	# 居民消费价格指数
	df = ts.get_cpi()
	df.to_sql('CPI',eng, if_exists='replace')
	print('居民消费价格指数 ok')


	# 工业品出厂价格指数
	df = ts.get_ppi()
	df.to_sql('PPI',eng, if_exists='replace')
	print('工业品出厂价格指数 ok')

except:
	pass
