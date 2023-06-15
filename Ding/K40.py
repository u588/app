from re import T
from socket import timeout
import uiautomator2 as u2
import sys
import os
from chinese_calendar import is_holiday
import time
import datetime
import random
import smtplib
import pandas as pd
from email.mime.text import MIMEText
from email.header import Header

#  adb tcpip 33333
#  adb connect 10.3.68.9:33333
#   python3 -m uiautomator2 init --addr :7912
IndesLists = pd.read_excel('F:/GiteeApp/App/Data/TDXdata/tdxIndexs.xlsx')
d = u2.connect('192.168.124.13')

d.app_start('com.tdx.AndroidNew', stop=True)
d(description="股票/功能/资讯").click()
d(focused=True).set_text('881001')
d(description="确定").click()
d(text="成份股").click()
d(scrollable=True).scroll.toEnd()
d.click(0.345, 0.915)





d(resourceId="com.tdx.AndroidNew:id/hqmainview").click()















print('  <3> ' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' App started !')
d.sleep(8)

print('  <4> '+ datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')+' App Longing !')
d.sleep(15)

d(text="消息").click(timeout=15)
d(resourceId="com.alibaba.android.rimet:id/home_bottom_tab_text", text="工作台").click()
d.sleep(15)

d(text="考勤打卡").click(timeout=10)
d.sleep(15)
d(textContains="班打卡").click(timeout=10)
dd = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
print("  <5> "+ datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')+' 打卡完成 !')
d.sleep(15)
d(resourceId="com.alibaba.android.rimet:id/close_text").click()
d.sleep(3)
d(text="消息").click(timeout=15)
d(text="我的").click(timeout=15)
d.sleep(2)
d(scrollable=True).scroll.toEnd()
d.sleep(2)
d(text="设置").click(timeout=15)
d.sleep(3)
d(scrollable=True).scroll.toEnd()
d.sleep(3)
d(text="退出登录").click(timeout=15)
d.sleep(3)
d(resourceId="android:id/button1").click(timeout=10)
print("  <6> "+ datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' 退出登录 !')
d.sleep(5)

d(resourceId="com.android.systemui:id/recent_apps").click(timeout=10)
d(resourceId="com.android.systemui:id/dismiss_task").click(timeout=10)

print("  <7> "+ datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' 清理后台完成 !')

d.press('power')
print('  <0> ' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' All ok !')

# from_addr = "d10ding58@126.com"
# from_pwd = "SITYLOKONAQMUEEG"

# to_addr = "u588@sina.com"
# smtp_srv = "smtp.126.com"

# msg = MIMEText(dd + "  打卡成功！ ", "plain", "utf-8")
# msg['From'] = "钉钉<d10ding58@126.com>"
# msg['To'] = "u588<u588@sina.com>"
# subject = 'OK'
# msg['Subject'] = Header(subject,'utf-8')

# try:
#     srv = smtplib.SMTP_SSL(smtp_srv.encode(),465) 
#     srv.login(from_addr, from_pwd)
#     srv.sendmail(from_addr, [to_addr], msg.as_string())
#     srv.quit()
# except Exception as e:
#     print(e)
