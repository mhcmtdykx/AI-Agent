"""测试API响应格式 - 完整响应"""
import requests
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

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
    "messages": [{"role": "user", "content": "你好，简短回复"}],
    "temperature": 0.7,
    "stream": False,
}

url = "{}/chat/completions".format(base_url.rstrip("/"))
try:
    response = requests.post(url, headers=headers, json=data, timeout=30)
    print("状态码:", response.status_code)
    result = response.json()
    print("完整响应:")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    
    # 检查choices结构
    if "choices" in result and len(result["choices"]) > 0:
        message = result["choices"][0].get("message", {})
        print("\nmessage内容:", json.dumps(message, ensure_ascii=False, indent=2))
except Exception as e:
    print("错误:", e)
    import traceback
    traceback.print_exc()
