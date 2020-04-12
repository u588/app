"""
启动谷歌浏览器
from selenium import webdriver
browser = webdriver.Chrome()
browser.get('http://www.baidu.com/')

启动火狐浏览器
from selenium import webdriver
browser = webdriver.Firefox()
browser.get('http://www.baidu.com/')

启动IE浏览器
from selenium import webdriver
browser = webdriver.Edge()
browser.get('http://www.baidu.com/')
if driver.find_element_by_id("J_SelectAll1"):
   driver.find_element_by_id("J_SelectAll1").click()

"""
#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from selenium import webdriver
import datetime
import time
from os import path
 

driver = webdriver.Firefox()

 
def login():
    # 打开淘宝登录页，并进行扫码登录
    driver.get("https://www.taobao.com")
    time.sleep(5)
    if driver.find_element_by_link_text("登录"):
        driver.find_element_by_link_text("登录").click()
        print("请在20秒内完成扫码")
        time.sleep(20)
        driver.get("https://cart.taobao.com/cart.htm")
    time.sleep(5)
    
    try:
        target = driver.find_element_by_link_text("品牌男装领导 黄志")
        driver.execute_script("arguments[0].scrollIntoView();", target)

    except:
        pass
    # 点击购物车里全选按钮J_CheckBox_901492205379  900826491689 901269604068 
    # /html/body/div[1]/div[2]/div[2]/div/div[2]/div[2]/div[1]/div/div[2]/div/div/div[2]/div/div[2]/div/ul/li[1]/div/div/label
    # /html/body/div[1]/div[2]/div[2]/div/div[2]/div[2]/div[1]/div/div[2]/div/div/div[2]/div/div[3]/div/ul/li[1]/div/div/label

    # if driver.find_element_by_id("J_CheckShop_s_42862518_1"):
    #     driver.find_element_by_id("J_CheckShop_s_42862518_1").click()
    
    # if driver.find_element_by_xpath("/html/body/div[1]/div[2]/div[2]/div/div[2]/div[2]/div[1]/div/div[2]/div/div/div[2]/div/div[1]/div/ul/li[1]/div/div/label"):
    #     driver.find_element_by_xpath("/html/body/div[1]/div[2]/div[2]/div/div[2]/div[2]/div[1]/div/div[2]/div/div/div[2]/div/div[1]/div/ul/li[1]/div/div/label").click()

    # if driver.find_element_by_xpath('/html/body/div[1]/div[2]/div[2]/div/div[2]/div[2]/div[1]/div/div[2]/div/div/div[2]/div/div[2]/div/ul/li[1]/div/div/label'):
    #     driver.find_element_by_xpath('/html/body/div[1]/div[2]/div[2]/div/div[2]/div[2]/div[1]/div/div[2]/div/div/div[2]/div/div[2]/div/ul/li[1]/div/div/label').click()

    # if driver.find_element_by_xpath('/html/body/div[1]/div[2]/div[2]/div/div[2]/div[2]/div[1]/div/div[2]/div/div/div[2]/div/div[3]/div/ul/li[1]/div/div/label'):
    #     driver.find_element_by_xpath('/html/body/div[1]/div[2]/div[2]/div/div[2]/div[2]/div[1]/div/div[2]/div/div/div[2]/div/div[3]/div/ul/li[1]/div/div/label').click()



    LabelLists = driver.find_elements_by_tag_name('label')
    # print(LabelLists)

    for i in LabelLists:
        try:
            if i.get_attribute('for')=='J_CheckBox_901492205379':
                i.click()
            elif i.get_attribute('for')=='J_CheckBox_900826491689':
                i.click()
            elif i.get_attribute('for')=='J_CheckBox_901269604068':
                i.click()
            else:
                pass
        except:
            pass
    



    # if driver.find_element_by_tag_name("label"):
    #     driver.find_element_by_link_text("J_CheckBox_901492205379").click()

    # if driver.find_element_by_link_text('for="J_CheckBox_900826491689"'):
    #     driver.find_element_by_link_text('for="J_CheckBox_900826491689"').click()

    # if driver.find_element_by_link_text('for="J_CheckBox_901269604068"'):
    #     driver.find_element_by_link_text('for="J_CheckBox_901269604068"').click()



    # if driver.find_element_by_id("J_CheckBox_901492205379"):
    #     driver.find_element_by_id("J_CheckBox_901492205379").click()

    # if driver.find_element_by_id("J_CheckBox_900826491689"):
    #     driver.find_element_by_id("J_CheckBox_900826491689").click()

    # if driver.find_element_by_id("J_CheckBox_901269604068"):
    #     driver.find_element_by_id("J_CheckBox_901269604068").click()

   
    now = datetime.datetime.now()
    print('login success:', now.strftime('%Y-%m-%d %H:%M:%S'))
 
def buy(buytime):
    while True:
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
        # 对比时间，时间到的话就点击结算
        if now > buytime:
            try:
                # 点击结算按钮
                if driver.find_element_by_id("J_Go"):
                    driver.find_element_by_id("J_Go").click()
                driver.find_element_by_link_text('提交订单').click()
            except:
                time.sleep(0.1)
        print(now)
        time.sleep(0.1)
 
if __name__ == "__main__":
    times = '2018-10-12 21:00:00.200000'
    #时间格式："2018-09-06 11:20:00.000000"
    login()
    buy(times)
