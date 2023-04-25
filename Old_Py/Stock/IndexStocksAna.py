import pandas as pd
import matplotlib.pyplot as plt
import matplotlib as mpl
import seaborn as sns
import datetime
import sys

sys.path.append('F:/MyGit/Classes/')
import PointIndexSplit as pis
import PointIndexNorm as pin
import PointFindIndexValue as piv
import PointIndexPlot as pip
import PointIndexConst as pic
import PointMakeStockdbSplit as pmdb
import PointStockNorm as psn
import PointFindStockValue as psv
import PointStocksPlot as psp

# days =['2005-06-06', '2007-10-16', '2008-10-28', '2009-08-04', '2013-06-25', '2015-06-12', '2016-01-27', '2018-01-29', '2018-09-18']

Index = '399995'
Day = '2019-01-01'
Day = datetime.datetime.strptime(Day, '%Y-%m-%d')
Day2 = '2019-06-12'
Day2 = datetime.datetime.strptime(Day2, '%Y-%m-%d')
n = Day2-Day
Day = Day.strftime('%Y-%m-%d')


IndexLists = pd.read_csv('f:/indexlist.csv', dtype={'index_code':object})
IndexConst = pd.read_csv('f:/IndexConst.csv', dtype={'index_code':object, 'code':object})
StocksData = pd.read_csv('f:/stocksone.csv')
StockLists = pd.read_csv('f:/stocklists.csv', dtype={'code':object})
PlotIndexLists = pd.read_excel('f:/plotindexlists.xls',dtype={'index_code':object})
IndexOne = pd.read_csv('f:/indexone.csv')

file = IndexLists[IndexLists.index_code==Index]['index_name'].tolist()[0]+'('+Index+')'
Consts = IndexConst[IndexConst.index_code==Index][['index_code', 'code', 'name']]

Splits = pis.IndexSplit(Day, n, IndexOne)
IndNorm,IndDescri = pin.IndexNorm(Day, Splits)
Constdb = pmdb.MakeStockdb(Day, n, Index, Consts, StocksData, StockLists)
StockNorm,StockDescri = psn.StockNorm(Day, file, Constdb)
UpValue,DownValue = psv.Value(Day, file, StockDescri, IndexConst)
psp.StocksPlot(Day, file, IndNorm, StockNorm, UpValue, DownValue)






