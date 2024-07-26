
import streamlit as st
from streamlit_option_menu import option_menu
from mootdx.quotes import Quotes
import re

def rag(txt): 
    from langchain.chains.summarize import load_summarize_chain
    from langchain.prompts import PromptTemplate
    from langchain_community.llms import Ollama
    from langchain.docstore.document import Document


    model = Ollama(base_url='http://10.3.68.3:11434', model='llama3.1:8b-instruct-q8_0')

    prompt_template = """Write a professional verbose summary of the following:
    {text}
    PROFESSIONAL VERBOSE SUMMARY IN CHINESE:"""

    PROMPT = PromptTemplate(template=prompt_template, input_variables=["text"])

    chain = load_summarize_chain(model, chain_type="stuff", prompt=PROMPT)

    docs = [Document(page_content=txt)]

    resl = chain.invoke(input=docs, return_only_outputs=True)
    return resl


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
        submitted1 = st.form_submit_button('确认')
if submitted1:
    client = Quotes.factory(market='std')
    txt = client.F10(stockCode, qf10)
    txt = txt.replace('│',' ')                
    txt = re.sub('([\u2500-\u25f7])','',txt) #删除制表符         

    tab1,tab2= st.tabs(['摘要','F10'])
    with tab1:
        text = rag(txt)
        st.text(text['output_text'])

    with tab2:
        st.subheader(qf10)
        st.text(txt)







