# -*- coding: utf-8 -*-
"""
-------------------------------------------------
# @File     :read_datas
# @Date     :2024/3/13 9:28
# @Author   :wenwenc9
# @Software :PyCharm
-------------------------------------------------
"""

import os
import json
from fastapi.encoders import jsonable_encoder
from langchain.chains import LLMChain
from langchain.chat_models import ChatOpenAI
from langchain.prompts import PromptTemplate
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel

os.environ["OPENAI_API_KEY"] = '你的openaikey'
os.environ["OPENAI_API_BASE"] = "你的代理地址" # 直接用key的忽略这个代理设置

# 构建APP
app = FastAPI()


class BODY(BaseModel):
    content: str


@app.post(path='/cotent')
async def process_content(content: BODY):
    content = jsonable_encoder(content)['content']
    print(content)

    _template = """
        订舱回执:{docs}
        你是一个水单识别助手，专门识别水单，你遵循如下规则：
        规则1-水单内容必须带有银行二字才开始识别
        规则2-主要提取内容为：
            1、付款人账号
            2、付款人名称
            3、付款人开户行
            4、日期
            5、收款人账号
            6、收款人名称
            7、收款人开户行
            8、交易金额
        规则3-返回的结果，请以字典形式返回,请严遵循规则2仅有8个键，如果找不到则值为空字符串
    """
    llm_chain = LLMChain(
        llm=ChatOpenAI(),
        prompt=PromptTemplate(
            template=_template,
            input_variables=["content"]
        ),
    )
    # res = llm_chain.run(content)
    try:
        res = llm_chain.run(content)
        final = json.loads(res)
    except:
        final = '识别失败'

    return final


if __name__ == '__main__':
    uvicorn.run('read_datas:app', host='0.0.0.0', port=10086, reload=True)

