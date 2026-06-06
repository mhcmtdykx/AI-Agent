"""测试支持的模型"""
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
    "Content-Type": "application/json",
    "Authorization": "Bearer {}".format(api_key),
}

# 测试不同的模型名称
models_to_test = [
    "gpt-3.5-turbo",
    "gpt-4",
    "gpt-4-turbo",
    "gpt-4o",
    "gpt-4o-mini",
    "claude-3-sonnet",
    "claude-3-haiku",
    "deepseek-chat",
    "qwen-turbo",
    "yi-34b-chat",
]

for model in models_to_test:
    data = {
        "model": model,
        "messages": [{"role": "user", "content": "hi"}],
        "temperature": 0.7,
    }
    url = "{}/chat/completions".format(base_url.rstrip("/"))
    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)
        if response.status_code == 200:
            print("[OK] {}".format(model))
            result = response.json()
            print("     回复:", result["choices"][0]["message"]["content"][:50])
            break
        else:
            error_msg = response.json().get("error", {}).get("message", "")
            print("[FAIL] {} - {}".format(model, error_msg))
    except Exception as e:
        print("[ERROR] {} - {}".format(model, str(e)[:50]))
