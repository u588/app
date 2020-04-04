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

days =['2005-06-06', '2007-10-16', '2008-10-28', '2009-08-04', '2013-06-25', '2015-06-12', '2016-01-27', '2018-01-29', '2018-09-18']

Day = '2019-04-01'
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
file = 'Point'

Splits = pis.IndexSplit(Day, n, IndexOne)
IndNorm,IndDescri = pin.IndexNorm(Day, Splits)
UpIndex,DownIndex = piv.Value(Day, IndDescri, PlotIndexLists)
pip.IndexPlot(Day, file, IndNorm, UpIndex, DownIndex)
UpConst = pic.GetIndexConst(Day, 'Up', UpIndex, IndexConst)
DownConst = pic.GetIndexConst(Day, 'Down', DownIndex, IndexConst)
UpConstdb = pmdb.MakeStockdb(Day, n,'Up', UpConst, StocksData, StockLists)
DownConstdb = pmdb.MakeStockdb(Day, n, 'Down', DownConst, StocksData, StockLists)
UpStockNorm,UpStockDescri = psn.StockNorm(Day, 'Up', UpConstdb)
DownStockNorm,DownStockDescri = psn.StockNorm(Day, 'Down', DownConstdb)
UpUpValue,DownUpValue = psv.Value(Day, 'Up', UpStockDescri, IndexConst)
UpDownValue, DownDownValue = psv.Value(Day, 'Down', DownStockDescri, IndexConst)
psp.StocksPlot(Day,'Up', IndNorm, UpStockNorm, UpUpValue, DownUpValue)
psp.StocksPlot(Day, 'Down', IndNorm, DownStockNorm, UpDownValue, DownDownValue)





