import datetime
import time

clock = '2018-10-12 22:09:00.200000'

now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')

while now<clock:
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
    print(now)
    time.sleep(0.5)
