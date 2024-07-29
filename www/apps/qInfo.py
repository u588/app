import streamlit as st
from streamlit_echarts import st_pyecharts
from chart import Kpro,indexChart,d3plt,detailChart
from mootdx.quotes import Quotes
import re

import requests

modls = requests.get("http://10.3.68.3:11434/v1/models").json()['data']

ls = []
n = 0
while n < len(modls):
    ls.append(modls[n]['id'])
    n = n + 1


def cut_text(text,length=60):
    newtext = ''
    if len(text)>length:
        while True:
            cutA = text[:length]
            cutB = text[length:]
            newtext += cutA + '\n'
            if len(cutB)>length:
                text = cutB
            else:
                newtext += cutB
                break
        return newtext
    
    return text

def rag(txt, model): 
    from langchain.chains.summarize import load_summarize_chain
    from langchain.prompts import PromptTemplate
    from langchain_community.llms import Ollama
    from langchain.docstore.document import Document
    model = Ollama(base_url='http://10.3.68.3:11434', model=model)
    prompt_template = """Write a professional verbose summary of the following:
    {text}
    PROFESSIONAL VERBOSE SUMMARY IN CHINESE:"""
    PROMPT = PromptTemplate(template=prompt_template, input_variables=["text"])
    chain = load_summarize_chain(model, chain_type="stuff", prompt=PROMPT)
    docs = [Document(page_content=txt)]
    resl = chain.invoke(input=docs, return_only_outputs=True)
    return resl

def app():
    with st.form('form1'):
        with st.sidebar:
            indexCode = st.text_input(label='指数查询',value='')
            submitted = st.form_submit_button('确认')
    if submitted:
        st_pyecharts(indexChart.Kchart(indexCode),height='600px')
    
    with st.form('form2'):
        with st.sidebar:
            stockCode = st.text_input(label='股票查询', value='')
            qf10 = st.selectbox(
                            'F10信息',
                            ('最新提示',
                            '公司概况',
                            '财务分析',
                            '股本结构',
                            '股东研究',
                            '机构持股',
                            '分红融资',
                            '高管治理',                                
                            '资金动向',
                            '资本运作',
                            '热点题材',
                            '公司公告',
                            '公司报道',
                            '经营分析',
                            '行业分析',
                            '价值分析',)
                        )
            modelSel = st.selectbox('选择模型',
                                (
                                    ls
                                ))                          
            submitted1 = st.form_submit_button('确认')
    if submitted1:
        client = Quotes.factory(market='std')
        txt = client.F10(stockCode, qf10)
        txt = txt.replace('│',' ')                
        txt = re.sub('([\u2500-\u25f7])','',txt) #删除制表符         

        tab1,tab2 ,tab3,tab0= st.tabs(['Kpro','D3plt','F10','摘要'])
        with tab1:
            st_pyecharts(Kpro.Kchart(stockCode),height='750px')
            st.header('财务分析')
            st_pyecharts(detailChart.line(stockCode))
        with tab2:
            st.bokeh_chart(d3plt.d3(stockCode),use_container_width=True)
        with tab3:
            st.subheader(qf10)
            st.text(txt)
        with tab0:
            txtt = ''
            model = modelSel
            text = rag(txt,model)
            d = text['output_text'].split('\n\n')
            n= 0
            while n<len(d):
                tx = ''
                h = d[n].split('\n')
                m = 0
                while m< len(h):
                    tx = tx + cut_text(h[m],) 
                    m = m + 1
                txtt = txtt + tx + '\n\n'
                n = n + 1
            st.subheader('模型： ' + model)
            st.divider()
        st.text(txtt)