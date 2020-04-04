import pandas as pd
import IndexNormDescri as Inno

days =['2001-06-14','2005-06-06', '2007-10-16', '2008-10-28',
     '2009-08-04', '2013-06-25', '2015-06-12', '2016-01-27', '2018-01-29']


# days =['2005-06-06']

for i, day in enumerate(days):
     print ('Day', i, '/', len(days))
     Inno.IndesNorm(day)
     print(day, 'Index NormDescri finshed !')
