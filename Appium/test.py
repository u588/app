from appium.webdriver import Remote

Remote.

driver = Remote(command_executor='http://10.3.18.65:11111/wd/hub')

driver.get('http://www.sina.com')