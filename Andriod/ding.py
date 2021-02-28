import uiautomator2 as u2
import datetime
import time
import sys
import os


d = u2.connect('192.168.124.9')

d.press('power')
d.swipe_ext("right")

d.unlock()

d(resourceId="com.android.keyguard:id/key1").click()
d(resourceId="com.android.keyguard:id/key3").click()
d(resourceId="com.android.keyguard:id/key9").click()
d(resourceId="com.android.keyguard:id/key4").click()

 d.app_start('com.alibaba.android.rimet')
d(resourceId="com.alibaba.android.rimet:id/home_bottom_tab_text", text="工作台").click()
d(text="考勤打卡").click()
d(text="统计").click()
d(text="外勤打卡").click()
d(resourceId="com.android.systemui:id/recent_apps").click()
d(resourceId="com.android.systemui:id/recent_igmbutton_clear_all").click()


# sess = d.session("com.netease.cloudmusic")
# 'com.ss.android.article.news'
# 'com.taobao.taobao'
# 'air.tv.douyu.android'
# 'com.youku.phone'

# sess.close()
#'com.alibaba.android.rimet'
# d.session("com.netease.cloudmusic")
# sess(resourceId="com.netease.cloudmusic:id/b2z").click()

# d(resourceId="com.taobao.taobao:id/button_cart_charge").click()

# d(resourceId="com.taobao.taobao:id/btn_confirm").click()

buytime = '2018-10-26 20:59:59.000000'
a= True
now = datetime.datetime.now()
print('现在时间： ', now.strftime('%Y-%m-%d %H:%M:%S'))
 
#
while a:
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
    # 对比时间，时间到的话就点击结算
    if now > buytime:
        try:
            d(resourceId="com.taobao.taobao:id/button_cart_charge").click()
            # time.sleep(0.1)
            d(resourceId="com.taobao.taobao:id/btn_confirm").click()
            print('订单OK ！')            
            a = False
                
        except:
            time.sleep(0.1)
    print(now)
    
    time.sleep(0.1)
 


#时间格式："2018-09-06 11:20:00.000000"
