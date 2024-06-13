# -*- coding: utf-8 -*-
import streamlit as st
from PIL import Image
import requests
import json
from read_images import RapidOCRLoader
import sys
import os

# 获取当前文件所在目录的绝对路径 fastapi调用的时候，导包问题解决掉
current_dir = os.path.abspath(os.path.dirname(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, ".."))
ct_utils_path = os.path.abspath(os.path.join(parent_dir))
sys.path.append(ct_utils_path)
# 目录工程
parent_dir2 = os.path.abspath(os.path.join(current_dir, "../.."))
ct_utils_path2 = os.path.abspath(os.path.join(parent_dir2))
sys.path.append(ct_utils_path2)

# 后端处理函数
def process(message):
    # 定义请求的URL和头部
    # url = 'http://10.3.68.3:5000/v1'
    # headers = {'accept': 'application/json', 'Content-Type': 'application/json'}

    # 定义请求的数据
    data = {'content': message}

    # 发送POST请求
    response = requests.post(url, headers=headers, data=json.dumps(data))

    # 如果请求成功，返回响应的内容
    if response.status_code == 200:
        return response.json()
    else:
        return "请求失败，状态码：" + str(response.status_code)


st.set_page_config(page_title="MiniCPM-Llama", page_icon="", layout="wide", )
# 创建侧边栏
st.sidebar.title("识别方式选择")
option = st.sidebar.selectbox("请选择一个功能", ["文本识别", "图片上传识别"])

if option == "文本识别":
    st.title("文本识别")
    user_input = st.text_area("请输入你的消息", height=200)
    confirm_button = st.button("确认")
    if confirm_button:
        response = process(user_input)
        st.text_area("回复", value=response, height=200, max_chars=None, key=None)

elif option == "图片上传识别":
    with st.sidebar:
        st.title("图片上传识别")
        uploaded_file = st.file_uploader("上传你的图片", type=["png", "jpg", "jpeg"])
        if uploaded_file is not None:
            image = Image.open(uploaded_file)
            # 创建一个文件对象
            with open('uploaded_image.jpg', 'wb') as f:
                # 将上传的文件的内容写入到新文件中
                f.write(uploaded_file.getvalue())
            path = './uploaded_image.jpg'

            # 将文件路径传递给img2text函数
            loader = RapidOCRLoader(file_path=path)
            images = loader.load()
            st.write('PIL GPU OCR 识别结果')
            st.write(images)

            # 发送给接口
            response = process(images[0].page_content)

            #展示图片
            st.image(image, caption='模型识别结果')

            # 展示模型结果
            st.write('模型结构化识别结果')
            st.write(response)

