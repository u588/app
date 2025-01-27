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
    prompt_template = """Write a professional text analysis of the following:
    {text}
    PROFESSIONAL TEXT ANALYSIS IN CHINESE:"""
    # prompt_template = """Write a professional verbose summary of the following:
    # {text}
    # PROFESSIONAL VERBOSE SUMMARY IN CHINESE:"""
    PROMPT = PromptTemplate(template=prompt_template, input_variables=["text"])
    chain = load_summarize_chain(model, chain_type="stuff", prompt=PROMPT)
    docs = [Document(page_content=txt)]
    resl = chain.invoke(input=docs, return_only_outputs=True)
    return resl

def app():

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
                            '研报评级',)
                        )
            modelSel = st.selectbox('选择模型',
                                (
                                    ls
                                ))                          
            submitted2 = st.form_submit_button('确认')
    if submitted2:
        client = Quotes.factory(market='std')
        txt = client.F10(stockCode, qf10)
        # txt = txt.replace('│',' ')                
        # txt = re.sub('([\u2500-\u25f7])','',txt) #删除制表符   
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
        st.subheader(stockCode+' : '+qf10)
        st.markdown(txtt)
        st.divider()
        st.markdown(text['output_text'])