import pandas as  pd


d = ['Corr20090805.csv', 'Corr20130626.csv', 'Corr20150615.csv', 'Corr20160128.csv', 'Corr20180130.csv']
for f in d:
    try:
        df = pd.read_csv('f:/s/s5/' + f, index_col=0)
        df.dropna(how='all', axis=1, inplace=True)
        df.dropna(thresh=4, inplace=True)
        df.set_index('ts_code', inplace=True)
        f = f[4:11]
        df.to_excel('f:/s/s5/'+f+'.xlsx')
        print('File:', f ,'got.' )
    except:
        pass
