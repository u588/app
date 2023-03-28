import smtplib
from email.mime.text import MIMEText
from email.header import Header
import datetime

# from_addr = "32234365@qq.com"
# from_pwd = "yqwjfqwogdvrbjja"

# to_addr = "u588@sina.com"
# smtp_srv = "smtp.qq.com"


from_addr = "d10ding58@126.com"
from_pwd = "COFFFTNGEJXXOJVP"

to_addr = "u588@sina.com"
smtp_srv = "smtp.126.com"

dd = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
msg = MIMEText(dd + "  打卡成功！ ", "plain", "utf-8")
msg['From'] = "Ding<d10ding58@126.com>"
msg['To'] = "u588<u588@sina.com>"
subject = '考勤'
msg['Subject'] = Header(subject,'utf-8')


try:
    # 两个参数
    # 第一个是服务器地址，但一定是bytes格式，所以需要编码
    # 第二个参数是服务器的接受访问端口
    srv = smtplib.SMTP_SSL(smtp_srv.encode(),465) #SMTP协议默认端口25
    #登录邮箱发送
    srv.login(from_addr, from_pwd)
    # 发送邮件
    # 三个参数
    # 1. 发送地址
    # 2. 接受地址，必须是list形式
    # 3. 发送内容，作为字符串发送
    srv.sendmail(from_addr, [to_addr], msg.as_string())
    srv.quit()
except Exception as e:
    print(e)
