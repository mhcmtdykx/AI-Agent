"""测试API响应格式"""
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

headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer {}".format(api_key),
}

# 测试非流式请求
print("=== 测试非流式请求 ===")
data = {
    "model": model,
    "messages": [{"role": "user", "content": "你好"}],
    "temperature": 0.7,
    "stream": False,
}

url = "{}/chat/completions".format(base_url.rstrip("/"))
try:
    response = requests.post(url, headers=headers, json=data, timeout=30)
    print("状态码:", response.status_code)
    print("响应:", json.dumps(response.json(), ensure_ascii=False, indent=2))
except Exception as e:
    print("错误:", e)

print("\n=== 测试流式请求 ===")
data["stream"] = True
try:
    response = requests.post(url, headers=headers, json=data, stream=True, timeout=30)
    print("状态码:", response.status_code)
    count = 0
    for line in response.iter_lines():
        if line:
            line = line.decode("utf-8")
            print("原始行:", line)
            if line.startswith("data: "):
                content = line[6:]
                if content.strip() == "[DONE]":
                    print("收到结束标记")
                    break
                try:
                    chunk = json.loads(content)
                    print("解析后:", json.dumps(chunk, ensure_ascii=False, indent=2))
                    count += 1
                    if count >= 3:
                        print("... (仅显示前3个chunk)")
                        break
                except json.JSONDecodeError as e:
                    print("JSON解析错误:", e)
except Exception as e:
    print("错误:", e)
