=========== 代码 ============
1、深圳
    股票    主板00 创业板30
    指数    39    
    2、上海
    股票    主板60 科创板68    
    指数    00 88 



1、StockCode来源
通达信软件 J:\new_tdx\T0002\hq_cache\
infoharbor*


2、csIndexs及成分股 来源
https://www.csindex.com.cn/#/indices/family/list -->导出列表

3、tdxBolckIndexs及成分股 来源
通达信软件 -->选项 -->数据导出-->板块导出

4、tdxIndex 来源
中证指数  -->其他-->中证指数--> 导出数据
通达信软件 J:\new_tdx\T0002\hq_cache\
shm.tnf  szm.tnf 


======================= 每年 6.20  12.20 日 更新 =====================
1、中证列表(2)导出 编辑后存==> G:/Gitee/App/TDXapp/tdxAppData/csIndex.xlsx
2、tdx板块列表(3)导出后 运行==>       python  G:\Gitee\App\TDXapp\DataProject\tdxBLKIndex_StcokCode.py
3、tdx中证指数列表(4)导出 编辑后存==> G:/Gitee/App/TDXapp/tdxAppData/tdxZZindexs.xlsx
4、tdx上证、深证指数列表生成 运行==>   python G:\Gitee\App\TDXapp\DataProject\tdxSHSZIndex.py

5、生成指数列表 运行==>               python G:\Gitee\App\TDXapp\DataProject\IndexMerg.py
6、生成最终指数列表  更新数据库 ==>    python G:\Gitee\App\TDXapp\DataProject\Finalndex.py
7、获取cs成分股列表 ==>               python G:\Gitee\App\TDXapp\pgTDXCons.py
8、生成股票成分股 更新数据库==>        python G:\Gitee\App\TDXapp\MergeCsTdxCons.py