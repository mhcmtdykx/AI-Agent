"""启动Web服务器 - 支持流式输出"""
import sys
import os
import json
import time

# 添加当前目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)
os.chdir(current_dir)

# 加载.env文件
def load_env_file(filepath):
    env_vars = {}
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key.strip()] = value.strip()
                    os.environ[key.strip()] = value.strip()
    return env_vars

env_file = os.path.join(current_dir, ".env")
load_env_file(env_file)

from agent import Agent, Config
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests

config = Config.from_env()
config.validate()
agent = Agent(config=config)

# 保存原始的chat方法
original_chat = agent.chat


class AgentHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            with open("index.html", "r", encoding="utf-8") as f:
                self.wfile.write(f.read().encode("utf-8"))
        elif self.path == "/api/tools":
            self.send_response(200)
            self.send_header("Content-type", "application/json; charset=utf-8")
            self.end_headers()
            from agent.tools import TOOLS_REGISTRY
            tools = [{"name": name, "description": info["description"]} for name, info in TOOLS_REGISTRY.items()]
            self.wfile.write(json.dumps(tools, ensure_ascii=False).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/api/chat":
            content_length = int(self.headers["Content-Length"])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode("utf-8"))
            message = data.get("message", "")
            stream = data.get("stream", False)

            if not message:
                self.send_response(400)
                self.send_header("Content-type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "消息不能为空"}).encode("utf-8"))
                return

            if stream:
                # 流式输出
                self.send_response(200)
                self.send_header("Content-type", "text/event-stream; charset=utf-8")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()

                try:
                    # 构建消息
                    print("当前对话历史长度:", len(agent.chat_history))
                    messages = agent._build_messages(message)
                    print("发送消息数量:", len(messages))
                    
                    # 调用API获取流式响应
                    headers = {
                        "Content-Type": "application/json",
                        "Authorization": "Bearer {}".format(agent.api_key),
                    }
                    
                    api_data = {
                        "model": agent.config.model_name,
                        "messages": messages,
                        "temperature": agent.config.temperature,
                        "stream": True,
                    }
                    
                    url = "{}/chat/completions".format(agent.base_url.rstrip("/"))
                    response = requests.post(url, headers=headers, json=api_data, stream=True, timeout=60)
                    
                    full_reply = ""
                    reasoning_content = ""
                    for line in response.iter_lines():
                        if line:
                            line = line.decode("utf-8")
                            if line.startswith("data: "):
                                line = line[6:]
                                if line.strip() == "[DONE]":
                                    # 发送完成标记
                                    self.wfile.write("data: [DONE]\n\n".encode("utf-8"))
                                    self.wfile.flush()
                                    break
                                try:
                                    chunk = json.loads(line)
                                    # 检查choices是否存在且不为空
                                    choices = chunk.get("choices", [])
                                    if not choices:
                                        continue
                                    delta = choices[0].get("delta", {})
                                    # 处理reasoning_content（思考过程）
                                    if delta.get("reasoning_content"):
                                        reasoning_content += delta["reasoning_content"]
                                        # 发送思考过程
                                        event_data = json.dumps({"reasoning": delta["reasoning_content"]}, ensure_ascii=False)
                                        self.wfile.write("data: {}\n\n".format(event_data).encode("utf-8"))
                                        self.wfile.flush()
                                    # 处理content（最终回复）
                                    if delta.get("content"):
                                        content = delta["content"]
                                        full_reply += content
                                        # 发送每个chunk
                                        event_data = json.dumps({"content": content}, ensure_ascii=False)
                                        self.wfile.write("data: {}\n\n".format(event_data).encode("utf-8"))
                                        self.wfile.flush()
                                except (json.JSONDecodeError, IndexError, KeyError) as e:
                                    print("解析chunk错误:", e)
                                    continue
                    
                    # 保存到对话历史 - 确保保存有效内容
                    final_reply = full_reply if full_reply else reasoning_content
                    if final_reply:
                        agent.chat_history.append({"role": "user", "content": message})
                        agent.chat_history.append({"role": "assistant", "content": final_reply})
                        print("已保存对话历史 - 用户:", message[:30], "| AI:", final_reply[:30])
                    
                except Exception as e:
                    error_data = json.dumps({"error": str(e)}, ensure_ascii=False)
                    self.wfile.write("data: {}\n\n".format(error_data).encode("utf-8"))
                    self.wfile.flush()
            else:
                # 普通输出
                response = agent.chat(message)
                result = {"response": response}
                self.send_response(200)
                self.send_header("Content-type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(result, ensure_ascii=False).encode("utf-8"))
        elif self.path == "/api/clear":
            agent.clear_memory()
            self.send_response(200)
            self.send_header("Content-type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        print("[{}] {}".format(self.log_date_time_string(), format % args))


host = "127.0.0.1"
port = 8080

try:
    server = HTTPServer((host, port), AgentHandler)
    print("=" * 50)
    print("AI Agent Web界面已启动!")
    print("请在浏览器中访问: http://{}:{}".format(host, port))
    print("支持流式输出")
    print("按 Ctrl+C 停止服务器")
    print("=" * 50)
    sys.stdout.flush()
    
    server.serve_forever()
except KeyboardInterrupt:
    print("\n服务器已停止")
    server.server_close()
except Exception as e:
    print("服务器启动失败:", e)
    import traceback
    traceback.print_exc()
