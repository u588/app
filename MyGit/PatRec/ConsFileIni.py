import pandas as pd
import os


path = "f:/ConsData/" #文件夹目录
files= os.listdir(path) #得到文件夹下的所有文件名称
for file in files: #遍历文件夹

    if file[6]=='p': #判断是否是文件夹，不是文件夹才打开
        os.remove(path+'/'+file)
        print(file, 'removed!')
    else:
        pass