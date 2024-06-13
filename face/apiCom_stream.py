import json
import requests
import sseclient  # pip install sseclient-py

url = "http://10.3.68.3:5000/v1/completions"

headers = {
    "Content-Type": "application/json"
}

data = {
    "prompt": "This is a cake recipe:\n\n1.",
    "max_tokens": 200,
    "temperature": 1,
    "top_p": 0.9,
    "seed": 10,
    "stream": True,
}

stream_response = requests.post(url, headers=headers, json=data, verify=False, stream=True)
client = sseclient.SSEClient(stream_response)

print(data['prompt'], end='')
for event in client.events():
    payload = json.loads(event.data)
    print(payload['choices'][0]['text'], end='')

print()