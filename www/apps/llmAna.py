import streamlit as st
from mootdx.quotes import Quotes
import requests
from langchain.chains.summarize import load_summarize_chain
from langchain.prompts import PromptTemplate
from langchain_community.llms import Ollama
from langchain.docstore.document import Document


modls = requests.get("http://10.3.68.3:11434/v1/models", timeout=10).json()['data']

ls = []
n = 0
while n < len(modls):
    ls.append(modls[n]['id'])
    n = n + 1

def rag(txt, model): 
    model = Ollama(base_url='http://10.3.68.3:11434', model=model, num_predict=-1, num_ctx=8192, temperature=0,num_thread=8)
    prompt_template = """根据以下文本给出专业分析报告:
    {text}
    用中文撰写:"""
    # prompt_template = """Write a professional text analysis of the following:
    # {text}
    # PROFESSIONAL TEXT ANALYSIS IN CHINESE:"""
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
                            '价值分析',)
                        )
            modelSel = st.selectbox('选择模型',
                                (
                                    ls
                                ))                          
            submitted2 = st.form_submit_button('确认')
    if submitted2:
        client = Quotes.factory(market='std')
        txt = client.F10(stockCode, qf10)
        try:
            txt = txt[:txt.find('〖免责条款〗')]
        except:
            pass
        model = modelSel
        text = rag(txt,model)
        st.subheader('模型： ' + model)
        i = txt.find('☆')
        st.markdown(qf10+': '+ txt[i+3:i+15])
        st.divider()
        st.markdown(text['output_text'])