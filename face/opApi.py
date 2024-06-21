import requests
from PIL import Image
import json
import base64
from io import BytesIO


url = "http://10.3.68.3:5000/v1/chat/completions"

headers = {
    "Content-Type": "application/json"
}

image_path = '/home/ts/face/6.png'
 
with Image.open(image_path) as img:
    img_byte_arr = BytesIO()
    img.convert('RGB').save(img_byte_arr, format='JPEG')
    img_bytes = img_byte_arr.getvalue()
 
 
encoded_string = base64.b64encode(img_bytes).decode('utf-8')

question = '用中文回答。识别图片中的身份证。并以json形式输出姓名，性别，出生日期，住址等。不需编造不实信息。'

msgs = [{'role': 'user', 'content': question}]
data = {
    "mode": "chat",
    "character": "Example",
    "messages": msgs,
    "image" : encoded_string,
    "temperature" : 0.2
}

response = requests.post(url, headers=headers, json=data, verify=False)
assistant_message = response.json()['choices'][0]['message']['content']
history.append({"role": "assistant", "content": assistant_message})
print(assistant_message)

