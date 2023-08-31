import tushare as ts
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import requests
from jqdatasdk import *
import librosa as rosa
import librosa.display
from IPython.display import Audio
from matplotlib.font_manager import FontProperties
import copy
from scipy import fft
import scipy
from scipy import signal


font_set = FontProperties(fname=r"/System/Library/Fonts/STHeiti Medium.ttc", size=10)

##### 优化傅里叶变换 v2
fs = 12
year_on_year_price_basis = list(year_on_year_price_basis_view)
fft_count = len(year_on_year_price_basis)
year_on_year_price_basis_sin = []
for i in range(fft_count):
    year_on_year_price_basis_sin.append(np.sin(2 * np.pi*year_on_year_price_basis[i]))
fft_count = len(year_on_year_price_basis_sin)
fft = np.fft.fft(year_on_year_price_basis_sin[0:fft_count])
normalization_fft = fft / fft_count  # 归一化
#f_x = np.arange(186) * fs / fft_count
f_x = np.fft.fftfreq(fft_count, 1 / fs)
print("fft_count %d"%(fft_count))

#计算最佳频率
max_amp = 0
max_index = 0
for i in range(len(normalization_fft)):
    if np.abs(normalization_fft[i]) > max_amp:
        max_amp = np.abs(normalization_fft[i])
        max_index = i
print("max_amp %.5f, freq %.5f, max_index %d "%(max_amp, f_x[max_index], max_index))         
second_max_amp = 0
second_max_index = 0
for i in range(len(normalization_fft)):
    if np.abs(normalization_fft[i]) > second_max_amp and int(np.abs(normalization_fft[i])) != int(max_amp) :
        second_max_amp = np.abs(normalization_fft[i])
        second_max_index = i        
print("second_max_amp %.5f, second_freq %.5f, second_max_index %d "%(second_max_amp, f_x[second_max_index], second_max_index)) 
#plt.stem(fft, use_line_collection=True)
max_freq = np.argmax(np.abs(fft))
print("max_freq %.5f"%(max_freq))      
tmp_freq = (fft[max_freq+1] - fft[max_freq-1]) / (2 * fft[max_freq] - fft[max_freq-1] - fft[max_freq+1])
best_freq = (max_freq - np.real(tmp_freq)) * fs / fft_count
print("best_freq = %.5f " % (best_freq))
print('bin = %.3f Hz' % (fs / fft_count))

#滤波
'''
这里假设采样频率为1000hz,信号本身最大的频率为500hz，要滤除100hz以下，400hz以上频率成分，即截至频率为100，400hz,则wn1=2*100/1000=0.2，Wn1=0.2； 
wn2=2*400/1000=0.8，Wn2=0.8。Wn=[0.02,0.8]
b, a = signal.butter(8, [0.2,0.8], 'bandpass')   #配置滤波器 8 表示滤波器的阶数

采样 12, 滤除0.1以下，0.3以上,
wn1 = 2 * 0.1 / 12 =0.0167
wn2 = 2 * 0.3 / 12 = 0.05
'''
#b, a = signal.butter(8, [0.0167,0.05], 'bandpass')   #配置滤波器 8 表示滤波器的阶数
b, a = signal.butter(8, 0.05, 'lowpass')   #配置滤波器 8 表示滤波器的阶数
filter_price_sin = signal.filtfilt(b, a, year_on_year_price_basis_sin)  
filter_price = signal.filtfilt(b, a, year_on_year_price_basis)  


#画图
plt.figure(figsize=(10, 10))
plt.subplots_adjust(left=None, bottom=None, right=None, top=None, \
    wspace=0.45, hspace=0.45)

plt.subplot(711)
plt.title('原始信号',fontproperties=font_set)
plt.plot(year_on_year_price_basis[0:fft_count]) 

plt.subplot(712)
plt.title('原始sin信号',fontproperties=font_set)
plt.plot(year_on_year_price_basis_sin[0:fft_count]) 

plt.subplot(713)
plt.title("未归一化的棉棒图",fontproperties=font_set)
plt.stem(f_x, np.abs(fft)[0:len(f_x)], use_line_collection=True)

plt.subplot(714)
plt.title("归一化的幅度谱",fontproperties=font_set)
plt.plot(f_x, np.abs(normalization_fft)[0:len(normalization_fft)])

plt.subplot(715)
plt.title("还原信号",fontproperties=font_set)
restore_fft = np.fft.ifft(fft)
plt.plot(restore_fft)

plt.subplot(716)
plt.title("滤波后的sin",fontproperties=font_set)
plt.plot(filter_price_sin)

plt.subplot(717)
plt.title("滤波后原始",fontproperties=font_set)
year_on_year_month_basis = list(year_on_year_basis.keys())
plt.plot(filter_price)
plt.show()

plt.plot(year_on_year_month_basis, filter_price)



