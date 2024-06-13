import requests
import json
import base64
# 加载图像文件
with open('g:/face/5.png' ,'rb') as f:
    image_data = f.read()
# 将图像转换为base64编码字符串
image_base64 = base64.b64encode(image_data).decode('utf-8')
# 制作API请求
url = 'https://10.3.68.3:5000/v1/images/generations'
headers = {'Content-Type': 'application/json'}
data = {
    'model': '',
    'prompt': '生成一张猫的图片',
    'height': 256,
    'width': 256,
    'n': 1,
    'data': [image_base64]
}

data = { "messages": [
        {
            "role": "user",
            "image_url": f"data:image/jpeg;base64,{image_base64}"
        },
        {
            "role": "user",
            "content": "提取图片中的文字"
        }
    ]
}
response = requests.post('http://10.3.68.3:5000/v1/chat/completions',headers=headers, json=data)

response = requests.post(url, headers=headers, json=data)
# 处理API响应
response_json = response.json()
generated_image = response_json['data'][0]['image']
# 处理生成的图像
...

from openai import OpenAI

client = OpenAI(base_url="http://10.3.68.2:8000/v1", api_key="sk-1111") 
response = client.chat.completions.create(
    model="MiniCPM-Llama3",
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{image_base64}"
                    },
                },
                {"type": "text", "text": "提取图片中的文字"},
            ],
        }
    ],
)