"""获取支持的模型列表"""
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

headers = {
    "Authorization": "Bearer {}".format(api_key),
}

# 尝试获取模型列表
url = "{}/models".format(base_url.rstrip("/"))
print("请求URL:", url)

try:
    response = requests.get(url, headers=headers, timeout=10)
    print("状态码:", response.status_code)
    if response.status_code == 200:
        models = response.json()
        print("\n可用模型:")
        for model in models.get("data", []):
            print("  -", model.get("id", model))
    else:
        print("响应:", response.text[:500])
except Exception as e:
    print("错误:", e)
