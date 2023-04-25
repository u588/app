# !/usr/bin/env python
# -*- coding: utf-8 -*-

# import os
from selenium import webdriver
import datetime
import time
# from os import path
 

driver = webdriver.Firefox()

 

# 打开淘宝登录页，并进行扫码登录
driver.get("https://login.taobao.com/")
time.sleep(20)

driver.get("https://cart.taobao.com/cart.htm")
time.sleep(3)
cart2 = 'window.open("https://cart.taobao.com/cart.htm")'
driver.execute_script(cart2)
handles = driver.window_handles
time.sleep(3)   
   
now = datetime.datetime.now()
print('login success:', now.strftime('%Y-%m-%d %H:%M:%S'))
 
def buy(buytime, handles):
    while True:
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
        # 对比时间，时间到的话就点击结算
        if now > buytime:
            try:
                # 点击结算按钮
                if driver.find_element_by_id("J_Go"):
                    driver.find_element_by_id("J_Go").click()
                    driver.implicitly_wait(1)
                    driver.find_element_by_link_text('提交订单').click()
                    driver.switch_to_window(handles[1])
                    driver.find_element_by_id("J_Go").click()
                    driver.implicitly_wait(1)
                    driver.find_element_by_link_text('提交订单').click()
                    
            except:
                time.sleep(0.1)
        print(now)
        time.sleep(0.1)
 

times = '2018-10-12 21:00:00.000000'
#时间格式："2018-09-06 11:20:00.000000"

buy(times,handles)
