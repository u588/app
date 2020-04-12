import pandas as pd
import StockNormDescri as StNor

days =['2005-06-06', '2007-10-16', '2008-10-28',
     '2009-08-04', '2013-06-25', '2015-06-12', '2016-01-27', '2018-01-29']

# for i, day in enumerate(days):
#      print ('Day', i, '/', len(days))
#      Inno.IndesNorm(day)
#      print(day, 'Index NormDescri finshed !')

# file = 'Down'
# file = 'Up'
files = ['Up', 'Down']

for i, file in enumerate(files):
    for i, day in enumerate(days):
    #  day = day[:4]+day[5:7]+day[8:]
        try:
            StNor.StockNorm(day, file)
        except:
            pass
print('Consts NormDescri finshed !')