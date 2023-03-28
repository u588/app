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
from email.mime.text import MIMEText
from email.header import Header

#  adb tcpip 33333
#  adb connect 10.3.68.9:33333
#   python3 -m uiautomator2 init --addr :7912


while is_holiday(datetime.date.today()):
    sys.exit(0)

print('................................................................................')
print('  <1> ' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')+' Cron Being !')

def dings():

    d = u2.connect('10.3.68.9')
    d.press('power')
    time.sleep(15)

    print('  <1> ' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' U2 connented !')
    d.unlock()
    # d.sleep(5)   
    print('  <2> ' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' Unlocked !')

    d(resourceId="com.android.systemui:id/key8").click(timeout=3)
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
    print('  <3> ' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' App started !')
    d.sleep(8)

    print('  <4> '+ datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')+' App Longing !')
    d.sleep(15)
    try:
        d.xpath('//*[@resource-id="android:id/button2"]').click(3)
    except:
        pass
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

def ding():

    print('  <2> ' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')+' Random Time End !')

    d = u2.connect('10.3.68.9')
    print('  <3> ' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' U2 connented !')
    d.press('power')
    d.sleep(15)
    d.unlock()

    print('  <4> ' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' Unlocked !')

    d(resourceId="com.android.systemui:id/key8").click(timeout=5)
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
    d.sleep(18)
    try:
        d.xpath('//*[@resource-id="android:id/button2"]').click(3)
    except:
        pass
    d(text="消息").click(timeout=15)
    d(resourceId="com.alibaba.android.rimet:id/home_bottom_tab_text", text="工作台").click()
    # d.sleep(15)
    # d(text="全员").click(timeout=15)
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

try:
    time.sleep(random.randint(0,7)*60)
    print('..... 1 ding  .....')
    ding()
except:
    try:
        time.sleep(5)
        print('...... 2 dings  ......')
        dings()
    except:
        try:
            time.sleep(5)
            print('..... 3 ding  .....')
            # os.system("curl -X POST http://10.3.68.9:7912/uiautomator")
            os.system("adb connect 10.3.68.9:33333")
            print('POST uiautomator !')
            time.sleep(15)
            ding()
        except:
            dd = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            from_addr = "d10ding58@126.com"
            from_pwd = "SITYLOKONAQMUEEG"

            to_addr = "u588@sina.com"
            smtp_srv = "smtp.126.com"

            msg = MIMEText(dd + "  请处理 !!! ", "plain", "utf-8")
            msg['From'] = "钉钉<d10ding58@126.com>"
            msg['To'] = "u588<u588@sina.com>"
            subject = '恢复失败'
            msg['Subject'] = Header(subject,'utf-8')

            try:
                srv = smtplib.SMTP_SSL(smtp_srv.encode(),465) 
                srv.login(from_addr, from_pwd)
                srv.sendmail(from_addr, [to_addr], msg.as_string())
                srv.quit()
            except Exception as e:
                print(e)    


# sina pop 2836b52fd6310585    126 smtp SITYLOKONAQMUEEG