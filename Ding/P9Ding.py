import uiautomator2 as u2
import sys
from chinese_calendar import is_holiday
import time
import datetime
import random
import smtplib
from email.mime.text import MIMEText
from email.header import Header

while is_holiday(datetime.date.today()):
    sys.exit(0)

print('................................................................................')
print('  <1> ' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')+' Cron Being !')
try:
    d = u2.connect('10.3.69.9')

    time.sleep(random.randint(0,12)*60)
    print('  <2> ' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')+' Random Time End !')

    d = u2.connect('10.3.69.9')
    print('  <3> ' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' U2 connented !')
    d.unlock()
    d.sleep(10)
    d.unlock()
    print('  <4> ' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' Unlocked !')
    d.sleep(3)
    d(resourceId="com.android.systemui:id/key8").click()
    d.sleep(1)
    d(resourceId="com.android.systemui:id/key8").click()
    d.sleep(1)
    d(resourceId="com.android.systemui:id/key8").click()
    d.sleep(1)
    d(resourceId="com.android.systemui:id/key8").click()
    d.sleep(1)
    d(resourceId="com.android.systemui:id/key8").click()
    d.sleep(1)
    d(resourceId="com.android.systemui:id/key8").click()

    d.sleep(2)
    d.app_start('com.alibaba.android.rimet', stop=True)
    print('  <5> ' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' App started !')
    d.sleep(8)
    d(resourceId="com.alibaba.android.rimet:id/et_pwd_login").click()
    d.sleep(3)
    d(focused=True).set_text('dd11111111')
    d.sleep(3)
    d.press('back')
#    d(resourceId="com.huawei.secime:id/char_keyboard_hide_btn").click()
    d.sleep(2)
    d.xpath('//*[@resource-id="com.alibaba.android.rimet:id/cb_privacy"]').click()
    d.xpath('//*[@resource-id="com.alibaba.android.rimet:id/btn_next"]').click()
    print('  <6> '+ datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')+' App Longing !')
    d.sleep(15)
    try:
        d.xpath('//*[@resource-id="android:id/button2"]').click(3)
    except:
        pass
    d(text="消息").click(timeout=15)
    d(resourceId="com.alibaba.android.rimet:id/home_bottom_tab_text", text="工作台").click()
    d.sleep(15)
    d(text="全员").click(timeout=15)
    time.sleep(random.randint(0,10))
    d(text="考勤打卡").click(timeout=10)
    d.sleep(15)
    d(textContains="班打卡").click(timeout=10)
    dd = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print("  <7> "+ datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')+' 打卡完成 !')
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
    print("  <8> "+ datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' 退出登录 !')
    d.sleep(5)

    d(resourceId="com.android.systemui:id/recent_apps").click(timeout=10)
    d(resourceId="com.android.systemui:id/dismiss_task").click(timeout=10)
    # d(resourceId="com.android.systemui:id/recent_igmbutton_clear_all").click()
    print("  <9> "+ datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' 清理后台完成 !')
    # d.sleep(8)
    d.press('power')
    print('  <0> ' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' All ok !')

    from_addr = "d10ding58@126.com"
    from_pwd = "SITYLOKONAQMUEEG"

    to_addr = "u588@sina.com"
    smtp_srv = "smtp.126.com"

    msg = MIMEText(dd + "  打卡成功！ ", "plain", "utf-8")
    msg['From'] = "钉钉<d10ding58@126.com>"
    msg['To'] = "u588<u588@sina.com>"
    subject = 'OK'
    msg['Subject'] = Header(subject,'utf-8')

    try:
        srv = smtplib.SMTP_SSL(smtp_srv.encode(),465) 
        srv.login(from_addr, from_pwd)
        srv.sendmail(from_addr, [to_addr], msg.as_string())
        srv.quit()
    except Exception as e:
        print(e)
except:
    dd = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    from_addr = "d10ding58@126.com"
    from_pwd = "SITYLOKONAQMUEEG"

    to_addr = "u588@sina.com"
    smtp_srv = "smtp.126.com"

    msg = MIMEText(dd + "  出错！ ", "plain", "utf-8")
    msg['From'] = "钉钉<d10ding58@126.com>"
    msg['To'] = "u588<u588@sina.com>"
    subject = '出错'
    msg['Subject'] = Header(subject,'utf-8')

    try:
        srv = smtplib.SMTP_SSL(smtp_srv.encode(),465) 
        srv.login(from_addr, from_pwd)
        srv.sendmail(from_addr, [to_addr], msg.as_string())
        srv.quit()
    except Exception as e:
        print(e)    
