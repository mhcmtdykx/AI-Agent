"""测试新模型配置"""
import requests
import json

def load_env_file(filepath):
    env_vars = {}
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                env_vars[key.strip()] = value.strip()
    return env_vars

env_vars = load_env_file(".env")
api_key = env_vars.get("OPENAI_API_KEY", "")
base_url = env_vars.get("OPENAI_BASE_URL", "")
model = env_vars.get("MODEL_NAME", "")

print("模型:", model)

headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer {}".format(api_key),
}

data = {
    "model": model,
    "messages": [
        {"role": "user", "content": "你好，请简单介绍一下自己"}
    ],
    "temperature": 0.7,
}

url = "{}/chat/completions".format(base_url.rstrip("/"))
print("请求URL:", url)

try:
    response = requests.post(url, headers=headers, json=data, timeout=30)
    print("状态码:", response.status_code)
    if response.status_code == 200:
        result = response.json()
        print("\n回复:", result["choices"][0]["message"]["content"])
    else:
        print("错误:", response.text)
except Exception as e:
    print("请求失败:", e)
