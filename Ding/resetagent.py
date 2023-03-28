import uiautomator2 as u2
from email.mime.text import MIMEText
from email.header import Header
import datetime
import smtplib
import os


try:
    d = u2.connect('10.3.68.9')
    d.press('power')
    # d.sleep(15)
    print('  <1> ' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' U2 connented !')
    d.swipe(150,150,1000,150)
    # d.unlock()
    print('  <2> ' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' Unlocked !')
    # d.sleep(5)
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
    print('  <3> ' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' login !')
    d.sleep(3)
    d.app_start('com.huawei.systemmanager', stop=True)
    d.sleep(5)
    d(resourceId='com.huawei.systemmanager:id/title').click()
    d.sleep(15)
    d(resourceId='com.huawei.systemmanager:id/scan').click()
    print('  <4> ' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' clear !')
    d.sleep(15)
    d(resourceId="com.android.systemui:id/recent_apps").click(timeout=10)
    d(resourceId="com.android.systemui:id/dismiss_task").click(timeout=10)


    # d.sleep(2)
    # d.app_start('com.alibaba.android.rimet', stop=True)
    # print('  <3> ' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' App started !')
    # d.sleep(8)
    # d(resourceId="com.android.systemui:id/recent_apps").click(timeout=10)
    # d(resourceId="com.android.systemui:id/recent_igmbutton_clear_all").click()
    # print("  <4> "+ datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' 清理后台完成 !')
    # dd = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    d.sleep(5)
    d.press('power')
    print('  <0> ' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' All ok !')

    # from_addr = "d10ding58@126.com"
    # from_pwd = "SITYLOKONAQMUEEG"

    # to_addr = "u588@sina.com"
    # smtp_srv = "smtp.126.com"

    # msg = MIMEText(dd + "  重置成功！ ", "plain", "utf-8")
    # msg['From'] = "钉钉<d10ding58@126.com>"
    # msg['To'] = "u588<u588@sina.com>"
    # subject = '重置'
    # msg['Subject'] = Header(subject,'utf-8')

    # try:
    #     srv = smtplib.SMTP_SSL(smtp_srv.encode(),465) 
    #     srv.login(from_addr, from_pwd)
    #     srv.sendmail(from_addr, [to_addr], msg.as_string())
    #     srv.quit()
    # except Exception as e:
    #     print(e)
except:
    # tx = os.system("curl -X POST http://10.3.68.9:7912/uiautomator")
    tx = os.system("adb connect 10.3.68.9:33333")
    dd = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    from_addr = "d10ding58@126.com"
    from_pwd = "SITYLOKONAQMUEEG"

    to_addr = "u588@sina.com"
    smtp_srv = "smtp.126.com"

    msg = MIMEText(dd + str(tx), "plain", "utf-8")
    msg['From'] = "钉钉<d10ding58@126.com>"
    msg['To'] = "u588<u588@sina.com>"
    subject = '重置出错,重启服务'
    msg['Subject'] = Header(subject,'utf-8')

    try:
        srv = smtplib.SMTP_SSL(smtp_srv.encode(),465) 
        srv.login(from_addr, from_pwd)
        srv.sendmail(from_addr, [to_addr], msg.as_string())
        srv.quit()
    except Exception as e:
        print(e)    
