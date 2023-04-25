from selenium.webdriver import ChromeOptions
from selenium import webdriver
from selenium.webdriver import ActionChains
import requests

option = ChromeOptions()
option.add_experimental_option('excludeSwitches', ['enable-automation'])
option.add_experimental_option('useAutomationExtension', False)
option.set_capability('browserName','MicrosoftEdge')
option.set_capability('browserName','firefox')
option.set_capability('pageLoadStrategy','none')
option.set_capability('platformName', 'Linux')
web = webdriver.Remote(command_executor='http://10.3.18.55:11111/wd/hub',options=option)

header = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.99 Safari/537.36 Edg/97.0.1072.69'}
web.get('https://www.csindex.com.cn')

searchBtn = web.find_element_by_id('nc_1_n1z')
ActionChains(web).drag_and_drop_by_offset(searchBtn,xoffset = 300,yoffset = 0).perform()