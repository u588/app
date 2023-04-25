import pandas as pd

stocks = pd.read_csv('f:/tdxraw/tdxhy.csv', dtype={'code':object,'sw_code':object})[['code', 'tdx_code', 'sw_code']]
indexs = pd.read_excel('f:/tdxraw/tdxzsto.xls', dtype={'index_code':object, 'code':object})[['index_name', 'index_code', 'code']]

consts = pd.DataFrame(columns=['index_code','index_name','code','code_index'])

codes = indexs.code.tolist()

for i, code in enumerate(codes):
    print('Code', i, '/', len(codes))
   # a = code[:5]+'5'
    const=stocks[(stocks['tdx_code']==code) | (stocks['tdx_code']==(code+'01')) | (stocks['tdx_code']==(code+'02')) | (stocks['tdx_code']==(code+'03')) | (stocks['tdx_code']==(code+'04')) | (stocks['tdx_code']==(code+'05')) | (stocks['tdx_code']==(code+'06')) | (stocks['tdx_code']==(code+'07')) | (stocks['tdx_code']==(code+'08'))]
    const.sort_index(inplace=True)
    const['index_name']=indexs.loc[i][0]
    const['index_code']=indexs.loc[i][1]
    const.index.rename('code_index', inplace=True)
    const.reset_index(inplace=True)
    const.drop(['tdx_code','sw_code'], axis= 1, inplace=True)
    consts= pd.concat([consts, const])
    print(code,'merged')

consts.to_excel('f:/TTconsts.xls', encoding='utf8')
print('All saved !')