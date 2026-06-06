"""测试API连接"""
import requests
import json

# 加载配置
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

print("API Key:", api_key[:10] + "...")
print("Base URL:", base_url)

# 测试简单请求
headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer {}".format(api_key),
}

data = {
    "model": "gpt-3.5-turbo",
    "messages": [
        {"role": "user", "content": "你好"}
    ],
    "temperature": 0.7,
}

url = "{}/chat/completions".format(base_url.rstrip("/"))
print("\n请求URL:", url)
print("请求数据:", json.dumps(data, ensure_ascii=False, indent=2))

try:
    response = requests.post(url, headers=headers, json=data, timeout=30)
    print("\n状态码:", response.status_code)
    print("响应内容:", response.text)
except Exception as e:
    print("\n错误:", e)
