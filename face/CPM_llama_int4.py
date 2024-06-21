# test.py
import torch
from PIL import Image
from transformers import AutoModel, AutoTokenizer

path = "/Models/use/MiniCPM-Llama3-V-2_5-int4/"
path = "/Models/use/MiniCPM-Llama3-V-2_5/"
model = AutoModel.from_pretrained(path, trust_remote_code=True)
tokenizer = AutoTokenizer.from_pretrained(path, trust_remote_code=True)
model.eval()

image = Image.open('/home/ts/face/5.png').convert('RGB')
question = '识别图片中的文字。并以json形式输出。'
question = '他们是同一个人吗，并说明各自的面部特征及他们的相似程度'


msgs = [{'role': 'user', 'content': question}]
res = model.chat(
    image=image,
    msgs=msgs,
    tokenizer=tokenizer,
    sampling=False, # if sampling=False, beam_search will be used by default
    temperature=0.5,
    # system_prompt='' # pass system_prompt if needed
)
print(res)

## if you want to use streaming, please make sure sampling=True and stream=True
## the model.chat will return a generator
res = model.chat(
    image=image,
    msgs=msgs,
    tokenizer=tokenizer,
    sampling=True,
    temperature=0.7,
    stream=True
)

generated_text = ""
for new_text in res:
    generated_text += new_text
    print(new_text, flush=True, end='')
