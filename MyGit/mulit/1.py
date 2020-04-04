import concurrent.futures
import multiprocessing



def GetCorr(IndexOne,IndexCodess,IndexCodes):
    print('IndexOne:', IndexOne)
    print('IndexCodess:', IndexCodess)
    print('IndexCodes:', IndexCodes)



IndexO= [1,2,3,4,5,6]
IndexCodess = [3,34]
IndexCodes = [1,12,3]





def MultiCorr(workers, jobs, IndexCodess, IndexCodes):
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        for task in jobs:
            print('task', task)
            pool.submit(GetCorr, task, IndexCodess, IndexCodes)







if __name__ == '__main__':
    # for i in range(3):
    #     j = i*4
    MultiCorr(4,IndexO,IndexCodess, IndexCodes)