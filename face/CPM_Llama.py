
import torch
from PIL import Image
# from transformers import AutoModel, AutoTokenizer
from llama_cpp import Llama


path = "/Models/use/MiniCPM-Llama3-V-2_5-gguf/ggml-model-Q5_K_M.gguf"
model = Llama(model_path=path, n_ctx=8192, n_gpu_layer=40, n_batch=512)

image = Image.open('/home/ts/face/6.png').convert('RGB')
ques = '识别图片中的身份证。并以json形式输出姓名，性别，出生日期，住址等。不需编造不实信息。'
ans = model(ques) 
ans['choices'][0]['text']

# model = AutoModel.from_pretrained(path, trust_remote_code=True, torch_dtype=torch.float16)
# For Nvidia GPUs support BF16 (like A100, H100, RTX3090)
model = model.to(device='cuda', dtype=torch.float16)
# For Nvidia GPUs do NOT support BF16 (like V100, T4, RTX2080)
#model = model.to(device='cuda', dtype=torch.float16)
# For Mac with MPS (Apple silicon or AMD GPUs).
# Run with `PYTORCH_ENABLE_MPS_FALLBACK=1 python test.py`
#model = model.to(device='mps', dtype=torch.float16)

# tokenizer = AutoTokenizer.from_pretrained(path, trust_remote_code=True)
# model.eval()

image = Image.open('/home/ts/face/6.png').convert('RGB')

question = '他们是同一个人吗，并说明各自的面部特征。'

msgs = [{'role': 'user', 'content': question}]
sampling_params = SamplingParams(
    temperature=0.7,
    top_p=0.8,
    top_k=100,
    seed=3472,
    max_tokens=1024,
    min_tokens=150,
    # temperature=0,
    # use_beam_search=True,
    # length_penalty=1.2,
    # best_of=3
)
res, context, _ = model.chat(
    image=image,
    msgs=msgs,
    context=None,
    tokenizer=tokenizer,
    sampling=True,
    temperature=0.2
)
print(res)
