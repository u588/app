import pandas as pd
import IndexNormDescri as Inno
import concurrent.futures
import multiprocessing

days =['2001-06-14','2005-06-06', '2007-10-16', '2008-10-28',
     '2009-08-04', '2013-06-25', '2015-06-12', '2016-01-27', '2018-01-29']



def MultiIndexNorm(workers, jobs):
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        for task in jobs:
            pool.submit(Inno.IndesNorm, task)


if __name__ == '__main__':

    MultiIndexNorm(4,days) 

print('Index NormDescri finshed !')
