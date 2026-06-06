"""
Web版Agent - 使用Flask提供Web界面
"""
import sys
import os
import json
from http.server import HTTPServer, SimpleHTTPRequestHandler
import threading

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent import Agent, Config


def load_env_file(filepath):
    """加载.env文件"""
    env_vars = {}
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key.strip()] = value.strip()
    return env_vars


# 加载配置
env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
env_vars = load_env_file(env_file)
for key, value in env_vars.items():
    if key not in os.environ:
        os.environ[key] = value

config = Config.from_env()
config.validate()
agent = Agent(config=config)


class AgentHandler(SimpleHTTPRequestHandler):
    """HTTP请求处理器"""

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_CONTENT.encode("utf-8"))
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
            if message:
                response = agent.chat(message)
                result = {"response": response}
            else:
                result = {"error": "消息不能为空"}

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
        """自定义日志格式"""
        print("[{}] {}".format(self.log_date_time_string(), format % args))


HTML_CONTENT = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Agent</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: #f5f5f5;
            height: 100vh;
            display: flex;
            flex-direction: column;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 16px 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .header h1 {
            font-size: 20px;
            font-weight: 600;
        }
        .header-buttons {
            display: flex;
            gap: 10px;
        }
        .btn {
            padding: 8px 16px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            transition: all 0.2s;
        }
        .btn-clear {
            background: rgba(255,255,255,0.2);
            color: white;
        }
        .btn-clear:hover {
            background: rgba(255,255,255,0.3);
        }
        .chat-container {
            flex: 1;
            overflow-y: auto;
            padding: 20px;
            display: flex;
            flex-direction: column;
            gap: 16px;
        }
        .message {
            max-width: 80%;
            padding: 12px 16px;
            border-radius: 12px;
            line-height: 1.5;
            word-wrap: break-word;
        }
        .user-message {
            align-self: flex-end;
            background: #667eea;
            color: white;
            border-bottom-right-radius: 4px;
        }
        .ai-message {
            align-self: flex-start;
            background: white;
            color: #333;
            border-bottom-left-radius: 4px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        .input-container {
            padding: 16px 24px;
            background: white;
            border-top: 1px solid #e0e0e0;
            display: flex;
            gap: 12px;
        }
        .input-container input {
            flex: 1;
            padding: 12px 16px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 15px;
            outline: none;
            transition: border-color 0.2s;
        }
        .input-container input:focus {
            border-color: #667eea;
        }
        .btn-send {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 12px 24px;
            font-weight: 600;
        }
        .btn-send:hover {
            opacity: 0.9;
        }
        .btn-send:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        .typing-indicator {
            display: none;
            align-self: flex-start;
            padding: 12px 16px;
            background: white;
            border-radius: 12px;
            border-bottom-left-radius: 4px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        .typing-indicator span {
            display: inline-block;
            width: 8px;
            height: 8px;
            background: #999;
            border-radius: 50%;
            margin: 0 2px;
            animation: typing 1.4s infinite;
        }
        .typing-indicator span:nth-child(2) { animation-delay: 0.2s; }
        .typing-indicator span:nth-child(3) { animation-delay: 0.4s; }
        @keyframes typing {
            0%, 60%, 100% { transform: translateY(0); }
            30% { transform: translateY(-8px); }
        }
        .welcome-message {
            text-align: center;
            color: #999;
            padding: 40px 20px;
        }
        .welcome-message h2 {
            color: #667eea;
            margin-bottom: 10px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>AI Agent</h1>
        <div class="header-buttons">
            <button class="btn btn-clear" onclick="clearChat()">清空对话</button>
        </div>
    </div>
    
    <div class="chat-container" id="chatContainer">
        <div class="welcome-message">
            <h2>欢迎使用 AI Agent</h2>
            <p>输入你的问题开始对话</p>
        </div>
        <div class="typing-indicator" id="typingIndicator">
            <span></span><span></span><span></span>
        </div>
    </div>
    
    <div class="input-container">
        <input type="text" id="userInput" placeholder="输入你的问题..." onkeypress="handleKeyPress(event)">
        <button class="btn btn-send" id="sendBtn" onclick="sendMessage()">发送</button>
    </div>

    <script>
        const chatContainer = document.getElementById("chatContainer");
        const userInput = document.getElementById("userInput");
        const sendBtn = document.getElementById("sendBtn");
        const typingIndicator = document.getElementById("typingIndicator");
        const welcomeMessage = document.querySelector(".welcome-message");

        function addMessage(content, isUser) {
            if (welcomeMessage) {
                welcomeMessage.style.display = "none";
            }
            
            const messageDiv = document.createElement("div");
            messageDiv.className = "message " + (isUser ? "user-message" : "ai-message");
            messageDiv.textContent = content;
            chatContainer.insertBefore(messageDiv, typingIndicator);
            chatContainer.scrollTop = chatContainer.scrollHeight;
        }

        function handleKeyPress(event) {
            if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                sendMessage();
            }
        }

        async function sendMessage() {
            const message = userInput.value.trim();
            if (!message) return;

            addMessage(message, true);
            userInput.value = "";
            sendBtn.disabled = true;
            typingIndicator.style.display = "block";
            chatContainer.scrollTop = chatContainer.scrollHeight;

            try {
                const response = await fetch("/api/chat", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ message: message })
                });
                const data = await response.json();
                
                typingIndicator.style.display = "none";
                
                if (data.response) {
                    addMessage(data.response, false);
                } else if (data.error) {
                    addMessage("错误: " + data.error, false);
                }
            } catch (error) {
                typingIndicator.style.display = "none";
                addMessage("请求失败: " + error.message, false);
            }

            sendBtn.disabled = false;
            userInput.focus();
        }

        async function clearChat() {
            try {
                await fetch("/api/clear", { method: "POST" });
                chatContainer.innerHTML = `
                    <div class="welcome-message">
                        <h2>欢迎使用 AI Agent</h2>
                        <p>输入你的问题开始对话</p>
                    </div>
                    <div class="typing-indicator" id="typingIndicator">
                        <span></span><span></span><span></span>
                    </div>
                `;
            } catch (error) {
                console.error("清空失败:", error);
            }
        }

        userInput.focus();
    </script>
</body>
</html>'''


def main():
    """启动Web服务器"""
    host = "127.0.0.1"
    port = 8080

    server = HTTPServer((host, port), AgentHandler)
    print("=" * 50)
    print("AI Agent Web界面已启动!")
    print("请在浏览器中访问: http://{}:{}".format(host, port))
    print("按 Ctrl+C 停止服务器")
    print("=" * 50)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务器已停止")
        server.server_close()


if __name__ == "__main__":
    main()
