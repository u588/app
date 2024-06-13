# test.py
import torch
from PIL import Image
from transformers import AutoModel, AutoTokenizer

path = "/Models/use/MiniCPM-V-2/"
model = AutoModel.from_pretrained(path, trust_remote_code=True, torch_dtype=torch.float16)
# For Nvidia GPUs support BF16 (like A100, H100, RTX3090)
model = model.to(device='cuda', dtype=torch.float16)
# For Nvidia GPUs do NOT support BF16 (like V100, T4, RTX2080)
#model = model.to(device='cuda', dtype=torch.float16)
# For Mac with MPS (Apple silicon or AMD GPUs).
# Run with `PYTORCH_ENABLE_MPS_FALLBACK=1 python test.py`
#model = model.to(device='mps', dtype=torch.float16)

tokenizer = AutoTokenizer.from_pretrained(path, trust_remote_code=True)
model.eval()

image = Image.open('/home/ts/face/6.png').convert('RGB')
question = '识别图片中的身份证。并以json形式输出姓名，性别，出生日期，住址等。不需编造不实信息。'
question = '他们是同一个人吗，并说明各自的面部特征。'
msgs = [{'role': 'user', 'content': question}]

res, context, _ = model.chat(
    image=image,
    msgs=msgs,
    context=None,
    tokenizer=tokenizer,
    sampling=True,
    temperature=0.2
)
print(res)
