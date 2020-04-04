import concurrent.futures
import multiprocessing
from rqalpha import run


tasks = []

# for short_period in range(3, 10, 2):
#     for long_period in range(30, 90, 5):

for short_period in [2, 3, 5, 8, 13]:
    for long_period in [13,21,34,55,89]:
        config = {
            "extra": {
                "context_vars": {
                    "SHORTPERIOD": short_period,
                    "LONGPERIOD": long_period,
                },
                "log_level": "error",
            },
            "base": {
                "matching_type": "current_bar",
                'data_bundle_path': 'e:\\RqalphaData\\bundle',
                "start_date": "2017-01-01",
                "end_date": "2018-08-01",
                "benchmark": "000300.XSHG",
                "frequency": "1d",
                "strategy_file": "./examples/golden_cross.py",
                "accounts": {
                    "stock": 100000
                    }
            },
            "mod": {
                "sys_progress": {
                    "enabled": True,
                    "show": True,
                },
                "sys_analyser": {
                    "enabled": True,
                    "output_file": "./results/out-{short_period}-{long_period}.pkl".format(
                        short_period=short_period,
                        long_period=long_period,
                    )
                },
            },
        }

        tasks.append(config)


def run_bt(config):
    run(config)

def main(workers, jobs):
# executor = concurrent.futures.ProcessPoolExecutor(max_workers=None)
# if __name__ == '__main__':

#  #   for task in tasks:
#         future = executor.submit(run_bt(task))
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as executor:
         for task in jobs:
        #     future = executor.submit(run_bt, task)

            executor.submit(run_bt, task)

        # for future in futures:
        #     print('执行中:%s, 已完成:%s' % (future.running(), future.done()))
        #     print('#### 分界线 ####')
        
        # for future in as_completed(futures, timeout=2):
        #     print('执行中:%s, 已完成:%s' % (future.running(), future.done()))



if __name__ == '__main__':
    for i in range(6):
        j = i*10
        main(4, tasks[j-9:j])
  

