import requests
import json

# 测试天气API
url = "https://wttr.in/北京?format=j1"
headers = {"User-Agent": "curl/7.64.1", "Accept": "application/json"}

try:
    response = requests.get(url, headers=headers, timeout=10)
    print(f"状态码: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        current = data.get("current_condition", [{}])[0]
        
        print(f"\n北京实时天气:")
        print(f"  温度: {current.get('temp_C', 'N/A')}°C")
        print(f"  体感温度: {current.get('FeelsLikeC', 'N/A')}°C")
        print(f"  天气: {current.get('weatherDesc', [{}])[0].get('value', 'N/A')}")
        print(f"  湿度: {current.get('humidity', 'N/A')}%")
        print(f"  风速: {current.get('windspeedKmph', 'N/A')} km/h")
        print(f"  观测时间: {current.get('observation_time', 'N/A')}")
    else:
        print(f"请求失败: {response.text[:200]}")
        
except Exception as e:
    print(f"错误: {e}")

# 测试技能系统
print("\n--- 测试技能系统 ---")
from agent.skills import get_skill_registry
registry = get_skill_registry()
result = registry.execute('weather', city='北京')
print(result)
