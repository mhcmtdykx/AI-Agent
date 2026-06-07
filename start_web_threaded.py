"""启动Web服务器 - 使用线程保持运行 (已弃用 - 请使用 flask_server.py)"""
import sys
print("[警告] start_web_threaded.py 已弃用，请使用 flask_server.py 代替:")
print("  python flask_server.py")
print()

import os
import json
import threading

# 添加当前目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)
os.chdir(current_dir)

# 加载.env文件
from agent.utils import load_env_file
env_file = os.path.join(current_dir, ".env")
load_env_file(env_file)

from agent import Agent, Config
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests

config = Config.from_env()
config.validate()
agent = Agent(config=config)


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
                    messages = agent._build_messages(message)
                    
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
                                    self.wfile.write("data: [DONE]\n\n".encode("utf-8"))
                                    self.wfile.flush()
                                    break
                                try:
                                    chunk = json.loads(line)
                                    choices = chunk.get("choices", [])
                                    if not choices:
                                        continue
                                    delta = choices[0].get("delta", {})
                                    if delta.get("reasoning_content"):
                                        reasoning_content += delta["reasoning_content"]
                                        event_data = json.dumps({"reasoning": delta["reasoning_content"]}, ensure_ascii=False)
                                        self.wfile.write("data: {}\n\n".format(event_data).encode("utf-8"))
                                        self.wfile.flush()
                                    if delta.get("content"):
                                        content = delta["content"]
                                        full_reply += content
                                        event_data = json.dumps({"content": content}, ensure_ascii=False)
                                        self.wfile.write("data: {}\n\n".format(event_data).encode("utf-8"))
                                        self.wfile.flush()
                                except (json.JSONDecodeError, IndexError, KeyError):
                                    continue
                    
                    # 保存到对话历史
                    final_reply = full_reply if full_reply else reasoning_content
                    if final_reply:
                        agent.chat_history.append({"role": "user", "content": message})
                        agent.chat_history.append({"role": "assistant", "content": final_reply})
                    
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

server = HTTPServer((host, port), AgentHandler)
print("=" * 50)
print("AI Agent Web界面已启动!")
print("请在浏览器中访问: http://{}:{}".format(host, port))
print("支持流式输出")
print("按 Ctrl+C 停止服务器")
print("=" * 50)
sys.stdout.flush()

# 使用线程运行服务器
server_thread = threading.Thread(target=server.serve_forever)
server_thread.daemon = True
server_thread.start()

try:
    # 主线程等待
    import time
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\n服务器已停止")
    server.shutdown()
