import uiautomator2 as u2
import sys
from chinese_calendar import is_workday, is_holiday
import time
import datetime
import random
import smtplib
from email.mime.text import MIMEText
from email.header import Header


d = u2.connect('10.3.68.199')

d.app_start('com.tdx.AndroidNew', stop=True)

d.xpath('//*[@content-desc="今日有 3 只新股可申购"]/android.widget.ImageView[3]').click()
d(description="股票/功能/资讯").click()
d(focused=True).set_text('881001')
d(description="确定").click()
d(scrollable=True).scroll.toEnd()

d.xpath('//android.widget.ScrollView/android.widget.LinearLayout[1]/android.widget.LinearLayout[3] \
        /android.widget.LinearLayout[2]/android.widget.LinearLayout[1]/android.widget.LinearLayout[2] \
        /android.view.View[1]').info['bounds']['bottom']
d.click(10, 1600)


d.click(786, 2172)

d.xpath('//android.widget.HorizontalScrollView').info['childCount']

d.xpath('//android.widget.HorizontalScrollView/android.view.View[48]/android.view.View').info['contentDescription'] 
d.xpath('//android.widget.HorizontalScrollView/android.view.View[1]/android.view.View').info


