"""获取支持的模型列表"""
import requests
from agent.utils import load_env_file

env_vars = load_env_file(".env")
api_key = env_vars.get("OPENAI_API_KEY", "")
base_url = env_vars.get("OPENAI_BASE_URL", "")

headers = {
    "Authorization": f"Bearer {api_key}",
}

url = f"{base_url.rstrip('/')}/models"
print(f"请求URL: {url}")

try:
    response = requests.get(url, headers=headers, timeout=10)
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        models = response.json()
        print("\n可用模型:")
        for model in models.get("data", []):
            print(f"  - {model.get('id', model)}")
    else:
        print(f"响应: {response.text[:500]}")
except Exception as e:
    print(f"错误: {e}")
