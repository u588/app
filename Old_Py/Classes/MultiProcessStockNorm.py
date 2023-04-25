import pandas as pd
import concurrent.futures
import multiprocessing
import StockNormDescri as StNor


days =['2005-06-06', '2007-10-16', '2008-10-28',
     '2009-08-04', '2013-06-25', '2015-06-12', '2016-01-27', '2018-01-29']
     
files = ['Up', 'Down']


def MultiStockNorm(workers, jobs, files):
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        for file in files:
            for task in jobs:
                pool.submit(StNor.StockNorm, task, file)


if __name__ == '__main__':

    MultiStockNorm(4,days,files) 

print('Stocks NormDescri finshed !')