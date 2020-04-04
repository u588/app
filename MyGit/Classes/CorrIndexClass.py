from sqlalchemy import create_engine
import pandas as pd

eng = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.55:5432/csIndex')

a = 0

def GetCorr(IndexOne,IndexCodess,IndexCodes):
    for i, IndexCode in enumerate(IndexCodes):
        print ('=========IndexCode========', i, '/', len(IndexCodes))
        global a
        a = i
        try:
            IndexCodess[IndexCode] = 0
            while a < len(IndexCodes):
                
                try:
    #              print(IndexOne[IndexCode[2:]])
                    IndexCodess.loc[a,[IndexCode]] = IndexOne[IndexCode[2:]].corr(IndexOne.iloc[:,(a+1)])#, method='spearman')
                    if a % 50 == 0 :
                        print ('ICode', a, '/', len(IndexCodes))
                        print(IndexCodess.loc[a,[IndexCode]])
                    else:
                        pass
                    a = a + 1
                except:
                    pass
                # if i>10:
                #     break
        except:
            pass
        # if i>2:
        #    break


IndexOne = pd.read_csv('f:/indexone.csv')
s0 = IndexOne[(IndexOne['date']>'2018-01-01') & (IndexOne['date']<='2018-02-01')]
# s1 = IndexOne[IndexOne['date']<='2001-06-14']
# s2 = IndexOne[(IndexOne['date']>'2001-06-14') & (IndexOne['date']<='2005-06-06')]
# s3 = IndexOne[(IndexOne['date']>'2005-06-06') & (IndexOne['date']<='2007-10-16')]
# s4 = IndexOne[(IndexOne['date']>'2007-10-16') & (IndexOne['date']<='2008-10-28')]
# s5 = IndexOne[(IndexOne['date']>'2008-10-28') & (IndexOne['date']<='2009-08-04')]
# s6 = IndexOne[(IndexOne['date']>'2009-08-04') & (IndexOne['date']<='2013-06-25')]
# s7 = IndexOne[(IndexOne['date']>'2013-06-25') & (IndexOne['date']<='2015-06-12')]
# s8 = IndexOne[(IndexOne['date']>'2015-06-12') & (IndexOne['date']<='2016-01-27')]
# s9 = IndexOne[(IndexOne['date']>'2016-01-27') & (IndexOne['date']<='2018-01-29')]
# s10 = IndexOne[(IndexOne['date']>'2018-01-29')]

# IndexO = [s2, s3, s4, s5, s6, s7, s8 ,s9 ,s10]


IndexCodess = pd.read_csv('f:/IndexList.csv', dtype={'index_code':object})[['index_code', 'code', 'name', 'const', 'hot', 'cate']]
#IndexCodess = pd.read_excel('f:/indexlist.xls', dtype={'index_code':object})[['index_code', 'code', 'name', 'const', 'hot', 'cate']]
IndexCodes = IndexCodess.code.tolist()

GetCorr(s0,IndexCodess,IndexCodes)
IndexCodess.to_csv('f:/股票指数分布/' + IndexOne.head(1).date.tolist()[0] + 'per.csv')
