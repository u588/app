import pandas as pd
import os


path = "f:/ConsData/" #文件夹目录
files= os.listdir(path) #得到文件夹下的所有文件名称
for file in files: #遍历文件夹
	try:
		df = pd.read_excel(path + file, dtype={'指数代码Index Code':object, '成分券代码Constituent Code':object})[['日期Date', '指数代码Index Code',
		 '指数名称Index Name', '成分券代码Constituent Code', '成分券名称Constituent Name']]
		df.rename(columns={'日期Date':'date', '指数代码Index Code':'index_code', '指数名称Index Name':'index_name', '成分券代码Constituent Code':'st_code',
			'成分券名称Constituent Name':'st_name'}, inplace=True)
		if ((df.st_code.tolist()[1][:2]=='60') | (df.st_code.tolist()[1][:2]=='00') |(df.st_code.tolist()[1][:2]=='30')) :
			Index_name = df.index_name.tolist()[1]
			df.set_index('date', inplace=True)
			df.to_excel(path+'Cons/'+ file[:6] + '_'+Index_name +'.xls', encoding='utf-8')
			print(Index_name, 'Save !')
		else:
			pass

	except:
		pass

	# df.to_excel(path+'Cons'+)


     # if file[6]=='p': #判断是否是文件夹，不是文件夹才打开
     #      os.remove(path+'/'+file)
     #      print(file, 'removed!')
     # else:
     # 	pass