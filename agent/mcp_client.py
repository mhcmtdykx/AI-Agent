"""
MCP客户端 - 连接外部MCP Server
支持stdio和HTTP两种连接方式
"""
import json
import subprocess
import threading
import asyncio
import requests
from typing import Dict, List, Any, Optional
from dataclasses import dataclass


@dataclass
class MCPServerConfig:
    """MCP服务器配置"""
    name: str
    command: str = None  # stdio模式的命令
    args: List[str] = None  # 命令参数
    url: str = None  # HTTP模式的URL
    env: Dict[str, str] = None  # 环境变量
    transport: str = "stdio"  # stdio 或 http


class MCPClient:
    """MCP客户端"""
    
    def __init__(self):
        self.servers: Dict[str, MCPServerConfig] = {}
        self.processes: Dict[str, subprocess.Popen] = {}
        self.server_capabilities: Dict[str, Dict] = {}
    
    def add_server(self, config: MCPServerConfig):
        """添加服务器配置"""
        self.servers[config.name] = config
    
    def remove_server(self, name: str):
        """移除服务器"""
        if name in self.servers:
            self.disconnect(name)
            del self.servers[name]
    
    def connect(self, server_name: str) -> bool:
        """连接到服务器"""
        if server_name not in self.servers:
            raise ValueError(f"服务器未配置: {server_name}")
        
        config = self.servers[server_name]
        
        if config.transport == "stdio":
            return self._connect_stdio(server_name, config)
        elif config.transport == "http":
            return self._connect_http(server_name, config)
        else:
            raise ValueError(f"不支持的传输方式: {config.transport}")
    
    def disconnect(self, server_name: str):
        """断开连接"""
        if server_name in self.processes:
            process = self.processes[server_name]
            process.terminate()
            process.wait(timeout=5)
            del self.processes[server_name]
    
    def _connect_stdio(self, server_name: str, config: MCPServerConfig) -> bool:
        """通过stdio连接"""
        try:
            cmd = [config.command] + (config.args or [])
            env = config.env
            
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                text=True
            )
            
            self.processes[server_name] = process
            
            # 发送初始化请求
            response = self._send_request(server_name, {
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "clientInfo": {
                        "name": "ai-agent",
                        "version": "1.0.0"
                    }
                },
                "id": 1
            })
            
            if "result" in response:
                self.server_capabilities[server_name] = response["result"]
                return True
            
            return False
        except Exception as e:
            print(f"连接失败: {e}")
            return False
    
    def _connect_http(self, server_name: str, config: MCPServerConfig) -> bool:
        """通过HTTP连接"""
        try:
            response = requests.post(
                config.url,
                json={
                    "jsonrpc": "2.0",
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "clientInfo": {
                            "name": "ai-agent",
                            "version": "1.0.0"
                        }
                    },
                    "id": 1
                },
                timeout=10
            )
            
            data = response.json()
            if "result" in data:
                self.server_capabilities[server_name] = data["result"]
                return True
            
            return False
        except Exception as e:
            print(f"连接失败: {e}")
            return False
    
    def _send_request(self, server_name: str, request: Dict) -> Dict:
        """发送请求"""
        config = self.servers[server_name]
        
        if config.transport == "stdio":
            return self._send_stdio_request(server_name, request)
        elif config.transport == "http":
            return self._send_http_request(server_name, request)
        else:
            raise ValueError(f"不支持的传输方式: {config.transport}")
    
    def _send_stdio_request(self, server_name: str, request: Dict, timeout: int = 30) -> Dict:
        """通过stdio发送请求（带超时）"""
        if server_name not in self.processes:
            raise ValueError(f"服务器未连接: {server_name}")

        process = self.processes[server_name]

        # 发送请求
        request_json = json.dumps(request, ensure_ascii=False) + "\n"
        process.stdin.write(request_json)
        process.stdin.flush()

        # 带超时的读取
        result = [None]
        error = [None]

        def _read():
            try:
                result[0] = process.stdout.readline()
            except Exception as e:
                error[0] = e

        thread = threading.Thread(target=_read, daemon=True)
        thread.start()
        thread.join(timeout=timeout)

        if thread.is_alive():
            raise TimeoutError(f"MCP服务器响应超时({timeout}s): {server_name}")
        if error[0]:
            raise error[0]
        if not result[0]:
            raise ValueError("服务器无响应")

        return json.loads(result[0])
    
    def _send_http_request(self, server_name: str, request: Dict) -> Dict:
        """通过HTTP发送请求"""
        config = self.servers[server_name]
        
        response = requests.post(
            config.url,
            json=request,
            timeout=30
        )
        
        return response.json()
    
    def list_tools(self, server_name: str) -> List[Dict]:
        """列出服务器的工具"""
        response = self._send_request(server_name, {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "params": {},
            "id": 2
        })
        
        return response.get("result", {}).get("tools", [])
    
    def call_tool(self, server_name: str, tool_name: str, arguments: Dict = None) -> Any:
        """调用工具"""
        response = self._send_request(server_name, {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments or {}
            },
            "id": 3
        })
        
        if "error" in response:
            raise Exception(response["error"]["message"])
        
        result = response.get("result", {})
        contents = result.get("content", [])
        
        if contents:
            return contents[0].get("text", "")
        return None
    
    def list_resources(self, server_name: str) -> List[Dict]:
        """列出服务器的资源"""
        response = self._send_request(server_name, {
            "jsonrpc": "2.0",
            "method": "resources/list",
            "params": {},
            "id": 4
        })
        
        return response.get("result", {}).get("resources", [])
    
    def read_resource(self, server_name: str, uri: str) -> str:
        """读取资源"""
        response = self._send_request(server_name, {
            "jsonrpc": "2.0",
            "method": "resources/read",
            "params": {"uri": uri},
            "id": 5
        })
        
        if "error" in response:
            raise Exception(response["error"]["message"])
        
        contents = response.get("result", {}).get("contents", [])
        if contents:
            return contents[0].get("text", "")
        return ""
    
    def get_all_tools(self) -> Dict[str, List[Dict]]:
        """获取所有服务器的工具"""
        all_tools = {}
        for server_name in self.servers:
            try:
                tools = self.list_tools(server_name)
                all_tools[server_name] = tools
            except Exception as e:
                all_tools[server_name] = []
        return all_tools
    
    def find_tool(self, tool_name: str) -> Optional[str]:
        """查找工具所在的服务器"""
        for server_name in self.servers:
            try:
                tools = self.list_tools(server_name)
                for tool in tools:
                    if tool.get("name") == tool_name:
                        return server_name
            except:
                continue
        return None
    
    def call_tool_auto(self, tool_name: str, arguments: Dict = None) -> Any:
        """自动查找并调用工具"""
        server_name = self.find_tool(tool_name)
        if not server_name:
            raise ValueError(f"工具不存在: {tool_name}")
        return self.call_tool(server_name, tool_name, arguments)


# 全局MCP客户端实例
mcp_client = MCPClient()

def get_mcp_client() -> MCPClient:
    """获取MCP客户端"""
    return mcp_client

def load_mcp_config(config_path: str = "mcp_config.json"):
    """从配置文件加载MCP服务器"""
    if not os.path.exists(config_path):
        return
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    servers = config.get("mcpServers", {})
    for name, server_config in servers.items():
        mcp_config = MCPServerConfig(
            name=name,
            command=server_config.get("command"),
            args=server_config.get("args", []),
            url=server_config.get("url"),
            env=server_config.get("env"),
            transport=server_config.get("transport", "stdio")
        )
        mcp_client.add_server(mcp_config)


import os
