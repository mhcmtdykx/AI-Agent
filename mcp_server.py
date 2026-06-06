"""
独立的MCP Server - 可以作为独立进程运行
支持标准MCP协议，可以被Claude Code等客户端调用
"""
import sys
import os
import json
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# MCP协议类型定义
class MCPTool:
    """MCP工具定义"""
    def __init__(self, name: str, description: str, input_schema: Dict):
        self.name = name
        self.description = description
        self.input_schema = input_schema
    
    def to_dict(self):
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema
        }

class MCPResource:
    """MCP资源定义"""
    def __init__(self, uri: str, name: str, description: str, mime_type: str = "text/plain"):
        self.uri = uri
        self.name = name
        self.description = description
        self.mime_type = mime_type
    
    def to_dict(self):
        return {
            "uri": self.uri,
            "name": self.name,
            "description": self.description,
            "mimeType": self.mime_type
        }


class StdioMCPServer:
    """基于标准输入输出的MCP服务器"""
    
    def __init__(self, name: str, version: str = "1.0.0"):
        self.name = name
        self.version = version
        self.tools: Dict[str, MCPTool] = {}
        self.resources: Dict[str, MCPResource] = {}
        self.tool_handlers: Dict[str, callable] = {}
        self.resource_handlers: Dict[str, callable] = {}
        
        # 注册内置工具
        self._register_builtin_tools()
        self._register_builtin_resources()
    
    def _register_builtin_tools(self):
        """注册内置工具"""
        
        # 获取当前时间
        self.register_tool(
            name="get_time",
            description="获取当前时间",
            input_schema={
                "type": "object",
                "properties": {},
                "required": []
            },
            handler=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        
        # 计算器
        self.register_tool(
            name="calculate",
            description="计算数学表达式",
            input_schema={
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "数学表达式，如 2+3*4"
                    }
                },
                "required": ["expression"]
            },
            handler=self._calculate
        )
        
        # 文本分析
        self.register_tool(
            name="text_analyze",
            description="分析文本信息",
            input_schema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "要分析的文本"
                    }
                },
                "required": ["text"]
            },
            handler=self._text_analyze
        )
        
        # JSON格式化
        self.register_tool(
            name="json_format",
            description="格式化JSON字符串",
            input_schema={
                "type": "object",
                "properties": {
                    "json_str": {
                        "type": "string",
                        "description": "JSON字符串"
                    }
                },
                "required": ["json_str"]
            },
            handler=self._json_format
        )
        
        # 读取文件
        self.register_tool(
            name="read_file",
            description="读取文件内容",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "文件路径"
                    }
                },
                "required": ["path"]
            },
            handler=self._read_file
        )
        
        # 写入文件
        self.register_tool(
            name="write_file",
            description="写入文件内容",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "文件路径"
                    },
                    "content": {
                        "type": "string",
                        "description": "文件内容"
                    }
                },
                "required": ["path", "content"]
            },
            handler=self._write_file
        )
    
    def _register_builtin_resources(self):
        """注册内置资源"""
        
        # 系统信息
        self.register_resource(
            uri="system://info",
            name="系统信息",
            description="获取系统基本信息",
            handler=lambda: json.dumps({
                "系统": "AI Agent MCP Server",
                "版本": self.version,
                "Python版本": sys.version,
                "工作目录": os.getcwd(),
                "时间": datetime.now().isoformat()
            }, ensure_ascii=False, indent=2)
        )
        
        # 工具列表
        self.register_resource(
            uri="tools://list",
            name="工具列表",
            description="获取所有可用工具",
            handler=lambda: json.dumps([t.to_dict() for t in self.tools.values()], ensure_ascii=False, indent=2)
        )
    
    def register_tool(self, name: str, description: str, input_schema: Dict, handler: callable):
        """注册工具"""
        self.tools[name] = MCPTool(name, description, input_schema)
        self.tool_handlers[name] = handler
    
    def register_resource(self, uri: str, name: str, description: str, handler: callable, mime_type: str = "text/plain"):
        """注册资源"""
        self.resources[uri] = MCPResource(uri, name, description, mime_type)
        self.resource_handlers[uri] = handler
    
    # ========== 工具实现 ==========
    
    def _calculate(self, expression: str) -> str:
        """计算数学表达式"""
        import math
        safe_dict = {
            "__builtins__": {},
            "abs": abs, "round": round, "min": min, "max": max,
            "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos,
            "pi": math.pi, "e": math.e
        }
        try:
            result = eval(expression, safe_dict)
            return str(result)
        except Exception as e:
            return f"计算错误: {str(e)}"
    
    def _text_analyze(self, text: str) -> str:
        """分析文本"""
        words = text.split()
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        result = {
            "字符数": len(text),
            "单词数": len(words),
            "中文字符数": chinese_chars,
            "行数": text.count('\n') + 1
        }
        return json.dumps(result, ensure_ascii=False)
    
    def _json_format(self, json_str: str) -> str:
        """格式化JSON"""
        try:
            data = json.loads(json_str)
            return json.dumps(data, indent=2, ensure_ascii=False)
        except Exception as e:
            return f"JSON错误: {str(e)}"
    
    def _read_file(self, path: str) -> str:
        """读取文件"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            return f"读取失败: {str(e)}"
    
    def _write_file(self, path: str, content: str) -> str:
        """写入文件"""
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            return f"成功写入: {path}"
        except Exception as e:
            return f"写入失败: {str(e)}"
    
    # ========== MCP协议处理 ==========
    
    def handle_request(self, request: Dict) -> Dict:
        """处理MCP请求"""
        method = request.get("method", "")
        params = request.get("params", {})
        request_id = request.get("id")
        
        try:
            if method == "initialize":
                result = self._handle_initialize(params)
            elif method == "tools/list":
                result = self._handle_list_tools()
            elif method == "tools/call":
                result = self._handle_call_tool(params)
            elif method == "resources/list":
                result = self._handle_list_resources()
            elif method == "resources/read":
                result = self._handle_read_resource(params)
            elif method == "ping":
                result = {}
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32601, "message": f"方法不存在: {method}"}
                }
            
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": result
            }
        
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32603, "message": str(e)}
            }
    
    def _handle_initialize(self, params: Dict) -> Dict:
        """处理初始化"""
        return {
            "protocolVersion": "2024-11-05",
            "serverInfo": {
                "name": self.name,
                "version": self.version
            },
            "capabilities": {
                "tools": {"listChanged": True},
                "resources": {"subscribe": False, "listChanged": True}
            }
        }
    
    def _handle_list_tools(self) -> Dict:
        """列出工具"""
        return {
            "tools": [tool.to_dict() for tool in self.tools.values()]
        }
    
    def _handle_call_tool(self, params: Dict) -> Dict:
        """调用工具"""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        if tool_name not in self.tools:
            return {
                "content": [{"type": "text", "text": f"工具不存在: {tool_name}"}],
                "isError": True
            }
        
        try:
            handler = self.tool_handlers[tool_name]
            result = handler(**arguments)
            
            if isinstance(result, dict) or isinstance(result, list):
                text = json.dumps(result, ensure_ascii=False)
            else:
                text = str(result)
            
            return {
                "content": [{"type": "text", "text": text}]
            }
        except Exception as e:
            return {
                "content": [{"type": "text", "text": f"执行错误: {str(e)}"}],
                "isError": True
            }
    
    def _handle_list_resources(self) -> Dict:
        """列出资源"""
        return {
            "resources": [resource.to_dict() for resource in self.resources.values()]
        }
    
    def _handle_read_resource(self, params: Dict) -> Dict:
        """读取资源"""
        uri = params.get("uri")
        
        if uri not in self.resources:
            raise ValueError(f"资源不存在: {uri}")
        
        handler = self.resource_handlers[uri]
        content = handler()
        
        return {
            "contents": [{
                "uri": uri,
                "mimeType": self.resources[uri].mime_type,
                "text": content
            }]
        }
    
    async def run_stdio(self):
        """通过标准输入输出运行"""
        # 读取stdin，写入stdout
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin)
        
        writer_transport, writer_protocol = await asyncio.get_event_loop().connect_write_pipe(
            asyncio.streams.FlowControlMixin, sys.stdout
        )
        writer = asyncio.StreamWriter(writer_transport, writer_protocol, None, asyncio.get_event_loop())
        
        while True:
            try:
                # 读取一行JSON
                line = await reader.readline()
                if not line:
                    break
                
                line = line.decode('utf-8').strip()
                if not line:
                    continue
                
                # 解析请求
                request = json.loads(line)
                
                # 处理请求
                response = self.handle_request(request)
                
                # 写入响应
                response_json = json.dumps(response, ensure_ascii=False)
                writer.write((response_json + '\n').encode('utf-8'))
                await writer.drain()
            
            except json.JSONDecodeError:
                continue
            except Exception as e:
                print(f"Error: {e}", file=sys.stderr)
                continue


def main():
    """主函数"""
    server = StdioMCPServer("ai-agent-tools", "1.0.0")
    
    print(f"MCP Server '{server.name}' v{server.version} 已启动", file=sys.stderr)
    print(f"工具数量: {len(server.tools)}", file=sys.stderr)
    print(f"资源数量: {len(server.resources)}", file=sys.stderr)
    print("等待请求...", file=sys.stderr)
    
    # 运行服务器
    asyncio.run(server.run_stdio())


if __name__ == "__main__":
    main()
