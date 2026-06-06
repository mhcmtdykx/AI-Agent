"""使用subprocess保持服务器运行"""
import subprocess
import sys
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

print("启动服务器...")
print("请在浏览器中访问: http://127.0.0.1:8080")
print("按 Ctrl+C 停止服务器")
sys.stdout.flush()

# 使用subprocess运行服务器，保持stdin打开
process = subprocess.Popen(
    [sys.executable, "-u", "start_web.py"],
    stdin=subprocess.PIPE,
    stdout=sys.stdout,
    stderr=sys.stderr,
)

try:
    process.wait()
except KeyboardInterrupt:
    process.terminate()
    print("\n服务器已停止")
