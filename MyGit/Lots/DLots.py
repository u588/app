import requests
import json
import time
from sqlalchemy import create_engine

class Lottery(object):

    def __init__(self):
        self.db = eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.55:5432/Lottery')

        self.baseUrl = "http://www.cwl.gov.cn/cwl_admin/kjxx/findDrawNotice?name=ssq"
        self.headers = {
            'Referer': 'http://www.cwl.gov.cn/kjxx/ssq/kjgg/',
                    }
        self.session = requests.Session()
        # 定义起止期号 以及数据间隔期数
        self.lastIssue = 157
        self.firstIssue = 1
        self.page = 50
   

#传入int 类型的期号 返回期号str  处理期号  返回三位期号
    def getIssueStr( self,issue):
        issue = int(issue)
        isStr = ''
        if issue == 0:
            return '001'

        if issue < 10:
            isStr = '00' + str( issue )
        if issue <100 and issue >= 10:
            isStr = '0' + str(issue)
        if issue >= 100 and issue <self.lastIssue:
            isStr = str(issue)
        if issue > self.lastIssue:
            return str(self.lastIssue)
        return isStr

    #获取目标url
    def getUrl(self, year, startIssue, lastIssue):
        endIssue = self.getIssueStr(lastIssue)
        Url = self.baseUrl + '&issueStart='+ str(year) +\
              self.getIssueStr(startIssue)+'&issueEnd='+ str(year) + endIssue
        print("Url:", Url)
        return Url

    def getResponse(self, url):
        response = requests.get(url,headers=self.headers)
        if response.status_code != 200:
            return 'error'
        else:
            return response

    def run(self):
        list = range(2013, 2015) # 生成年份 官网只有从13年开始的数据  注意range函数的边界值
        #这里时间跨度三年左右不会有问题 结束年为19年 传入2018的话  不会包括18年的数据
        issueList = range(self.firstIssue, self.lastIssue, self.page + 1)#生成期号
        data = ''
        for year in list:
            for issue in issueList:
                data = self.getResponse( self.getUrl(year,issue,issue+self.page))
                if data == 'error':
                    print("response error")
                    continue
                else:
                    self.saveData(data)
                    time.sleep(5)




    def saveData(self,response):
        res = json.loads(response.text)
        resultList = res['result']
        state = res['state']
        if int(state) != 0:
            print("无数据")
            return
        for result in resultList:
            code = result['code']
            date = result['date']
            redballs = result['red']
            blueball = result['blue']
            sales = result['sales']
            poolmoney = result['poolmoney']
            content = result['content']
            prizegrades = result['prizegrades']#中奖信息列表
            for pri in prizegrades:
                type = pri['type']
                typenum = pri['typenum']
                typemoney = pri['typemoney']
                if int(type) == 7:#该字段数据为空 没有该奖项 跳过
                    continue
                self.cursor.execute('insert into bingo (code,level,num,money) VALUES (%s,%s,%s,%s)',(code,int(type),int(typenum),typemoney))
            self.cursor.execute('insert into base (code,redballs,blueball,date,sales,poolmoney,content) VALUES (%s,%s,%s,%s,%s,%s,%s)',(code,redballs
                                 ,blueball,date,int(sales),int(poolmoney),content))
            self.db.commit()


if __name__ == '__main__':
    lottery = Lottery()
    lottery.run()



