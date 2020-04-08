from sqlalchemy import create_engine
import tushare as ts


eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/StockFund')


try:
	# 
	df = ts.get_area_classified()
	df.to_sql('Area',eng, if_exists='replace')
	print('地域分类 ok')

	# 行业分类
	df = ts.get_industry_classified()
	df.to_sql('Industry',eng, if_exists='replace')
	print('行业分类 ok')
	
	# 概念分类
	df = ts.get_concept_classified()
	df.to_sql('Concept',eng, if_exists='replace')
	print('概念分类 ok')

	#沪深300成份股及权重
	df = ts.get_hs300s()
	df.to_sql('Hs300s',eng, if_exists='replace')
	print('沪深300成份股及权重 ok')


	# 上证50成份股
	df = ts.get_sz50s()
	df.to_sql('Sz50s',eng, if_exists='replace')
	print('上证50成份股 ok')

	# 中小板分类
	df = ts.get_sme_classified()
	df.to_sql('SME',eng, if_exists='replace')
	print('中小板分类 ok')

	# 创业板分类
	df = ts.get_gem_classified()
	df.to_sql('GEM',eng, if_exists='replace')
	print('创业板分类 ok')


	#风险警示板分类
	df = ts.get_st_classified()
	df.to_sql('ST',eng, if_exists='replace')
	print('风险警示板分类 ok')

	# 中证500成份股
	df = ts.get_zz500s()
	df.to_sql('zz500s',eng, if_exists='replace')
	print('中证500成份股 ok')
	
except:
	pass
