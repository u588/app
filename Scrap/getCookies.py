from selenium import webdriver
from selenium.webdriver import ActionChains
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

web = webdriver.Remote(command_executor='http://10.3.18.65:11111/wd/hub',desired_capabilities=DesiredCapabilities.CHROME)
web.get('https://www.csindex.com.cn/#/')



submit_btn = web.find_element_by_id('nc_1_n1z')

ActionChains(web).drag_and_drop_by_offset(submit_btn,xoffset = 300,yoffset = 0).perform()
cookie = {'acw_tc':''}
cookie['acw_tc'] = web.get_cookie("acw_tc")['value']