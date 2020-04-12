import os
from selenium import webdriver
import datetime
import time
from selenium import webdriver
from selenium.webdriver import ActionChains

browser = webdriver.Firefox()

url = "http://www.sina.com.cn"
browser.get(url)
target = browser.find_element_by_link_text("品牌男装领导 黄志")
browser.execute_script("arguments[0].scrollIntoView();", target)
# browser.switch_to.frame('iframeResult')
# source = browser.find_element_by_css_selector('#draggable')
# target = browser.find_element_by_css_selector('#droppable')
# actions = ActionChains(browser)
# actions.drag_and_drop(source, target)
# actions.perform()
# bs = webdriver.Edge()

# bs.get('http://www.taobao.com')

# input_str = bs.find_element_by_id('q')
# input_str.send_keys('ipad')
# time.sleep(1)
# input_str.clear()
# input_str.send_keys('iphone 7')
# button = bs.find_element_by_class_name('btn-search')
# button.click()