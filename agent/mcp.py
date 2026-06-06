"""
MCP (Model Context Protocol) 协议支持
实现标准化的AI模型与工具交互协议
"""
import json
import uuid
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, asdict
from datetime import datetime
from abc import ABC, abstractmethod


# ========== MCP核心类型 ==========

@dataclass
class MCPTool:
    """MCP工具定义"""
    name: str
    description: str
    input_schema: Dict
    
    def to_dict(self):
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema
        }

@dataclass
class MCPResource:
    """MCP资源定义"""
    uri: str
    name: str
    description: str
    mime_type: str = "text/plain"
    
    def to_dict(self):
        return {
            "uri": self.uri,
            "name": self.name,
            "description": self.description,
            "mimeType": self.mime_type
        }

@dataclass
class MCPPrompt:
    """MCP提示定义"""
    name: str
    description: str
    arguments: List[Dict] = None
    
    def to_dict(self):
        return {
            "name": self.name,
            "description": self.description,
            "arguments": self.arguments or []
        }

@dataclass
class MCPMessage:
    """MCP消息"""
    role: str  # user, assistant, system
    content: str
    timestamp: str = None
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
    
    def to_dict(self):
        return asdict(self)


# ========== MCP请求/响应 ==========

class MCPRequest:
    """MCP请求"""
    def __init__(self, method: str, params: Dict = None, request_id: str = None):
        self.jsonrpc = "2.0"
        self.method = method
        self.params = params or {}
        self.id = request_id or str(uuid.uuid4())[:8]
    
    def to_dict(self):
        return {
            "jsonrpc": self.jsonrpc,
            "method": self.method,
            "params": self.params,
            "id": self.id
        }
    
    def to_json(self):
        return json.dumps(self.to_dict())


class MCPResponse:
    """MCP响应"""
    def __init__(self, request_id: str, result: Any = None, error: Dict = None):
        self.jsonrpc = "2.0"
        self.id = request_id
        self.result = result
        self.error = error
    
    def to_dict(self):
        resp = {"jsonrpc": self.jsonrpc, "id": self.id}
        if self.error:
            resp["error"] = self.error
        else:
            resp["result"] = self.result
        return resp
    
    def to_json(self):
        return json.dumps(self.to_dict())


class MCPError:
    """MCP错误"""
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    
    @staticmethod
    def create(code: int, message: str, data: Any = None) -> Dict:
        error = {"code": code, "message": message}
        if data:
            error["data"] = data
        return error


# ========== MCP服务器 ==========

class MCPServer:
    """MCP服务器 - 提供工具和资源"""
    
    def __init__(self, name: str, version: str = "1.0.0"):
        self.name = name
        self.version = version
        self.tools: Dict[str, MCPTool] = {}
        self.resources: Dict[str, MCPResource] = {}
        self.prompts: Dict[str, MCPPrompt] = {}
        self.tool_handlers: Dict[str, Callable] = {}
        self.resource_handlers: Dict[str, Callable] = {}
        
        # 服务器信息
        self.server_info = {
            "name": name,
            "version": version,
            "capabilities": {
                "tools": True,
                "resources": True,
                "prompts": True
            }
        }
    
    def tool(self, name: str = None, description: str = None):
        """装饰器：注册工具"""
        def decorator(func):
            tool_name = name or func.__name__
            tool_desc = description or func.__doc__ or ""
            
            # 从函数签名生成参数模式
            input_schema = self._generate_schema(func)
            
            self.register_tool(
                name=tool_name,
                description=tool_desc,
                input_schema=input_schema,
                handler=func
            )
            return func
        return decorator
    
    def register_tool(self, name: str, description: str, input_schema: Dict, handler: Callable):
        """注册工具"""
        tool = MCPTool(name=name, description=description, input_schema=input_schema)
        self.tools[name] = tool
        self.tool_handlers[name] = handler
    
    def register_resource(self, uri: str, name: str, description: str, handler: Callable, mime_type: str = "text/plain"):
        """注册资源"""
        resource = MCPResource(uri=uri, name=name, description=description, mime_type=mime_type)
        self.resources[uri] = resource
        self.resource_handlers[uri] = handler
    
    def register_prompt(self, name: str, description: str, arguments: List[Dict] = None):
        """注册提示"""
        prompt = MCPPrompt(name=name, description=description, arguments=arguments)
        self.prompts[name] = prompt
    
    def _generate_schema(self, func: Callable) -> Dict:
        """从函数生成JSON Schema"""
        import inspect
        
        sig = inspect.signature(func)
        properties = {}
        required = []
        
        for param_name, param in sig.parameters.items():
            if param_name == 'self':
                continue
            
            param_type = "string"
            if param.annotation != inspect.Parameter.empty:
                if param.annotation == int:
                    param_type = "integer"
                elif param.annotation == float:
                    param_type = "number"
                elif param.annotation == bool:
                    param_type = "boolean"
                elif param.annotation == list:
                    param_type = "array"
                elif param.annotation == dict:
                    param_type = "object"
            
            properties[param_name] = {
                "type": param_type,
                "description": ""
            }
            
            if param.default == inspect.Parameter.empty:
                required.append(param_name)
        
        return {
            "type": "object",
            "properties": properties,
            "required": required
        }
    
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
            elif method == "prompts/list":
                result = self._handle_list_prompts()
            elif method == "prompts/get":
                result = self._handle_get_prompt(params)
            else:
                return MCPResponse(
                    request_id=request_id,
                    error=MCPError.create(MCPError.METHOD_NOT_FOUND, "方法不存在: {}".format(method))
                ).to_dict()
            
            return MCPResponse(request_id=request_id, result=result).to_dict()
        
        except Exception as e:
            return MCPResponse(
                request_id=request_id,
                error=MCPError.create(MCPError.INTERNAL_ERROR, str(e))
            ).to_dict()
    
    def _handle_initialize(self, params: Dict) -> Dict:
        """处理初始化请求"""
        return {
            "protocolVersion": "2024-11-05",
            "serverInfo": self.server_info,
            "capabilities": self.server_info["capabilities"]
        }
    
    def _handle_list_tools(self) -> Dict:
        """列出所有工具"""
        return {
            "tools": [tool.to_dict() for tool in self.tools.values()]
        }
    
    def _handle_call_tool(self, params: Dict) -> Dict:
        """调用工具"""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        if tool_name not in self.tools:
            return {
                "content": [{"type": "text", "text": "工具不存在: {}".format(tool_name)}],
                "isError": True
            }
        
        try:
            handler = self.tool_handlers[tool_name]
            result = handler(**arguments)
            
            # 格式化结果
            if isinstance(result, str):
                content = [{"type": "text", "text": result}]
            elif isinstance(result, dict) or isinstance(result, list):
                content = [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]
            else:
                content = [{"type": "text", "text": str(result)}]
            
            return {"content": content}
        
        except Exception as e:
            return {
                "content": [{"type": "text", "text": "执行错误: {}".format(str(e))}],
                "isError": True
            }
    
    def _handle_list_resources(self) -> Dict:
        """列出所有资源"""
        return {
            "resources": [resource.to_dict() for resource in self.resources.values()]
        }
    
    def _handle_read_resource(self, params: Dict) -> Dict:
        """读取资源"""
        uri = params.get("uri")
        
        if uri not in self.resources:
            raise ValueError("资源不存在: {}".format(uri))
        
        handler = self.resource_handlers[uri]
        content = handler()
        
        return {
            "contents": [{
                "uri": uri,
                "mimeType": self.resources[uri].mime_type,
                "text": content
            }]
        }
    
    def _handle_list_prompts(self) -> Dict:
        """列出所有提示"""
        return {
            "prompts": [prompt.to_dict() for prompt in self.prompts.values()]
        }
    
    def _handle_get_prompt(self, params: Dict) -> Dict:
        """获取提示"""
        prompt_name = params.get("name")
        arguments = params.get("arguments", {})
        
        if prompt_name not in self.prompts:
            raise ValueError("提示不存在: {}".format(prompt_name))
        
        prompt = self.prompts[prompt_name]
        return {
            "description": prompt.description,
            "messages": [
                {"role": "user", "content": {"type": "text", "text": json.dumps(arguments)}}
            ]
        }


# ========== MCP客户端 ==========

class MCPClient:
    """MCP客户端 - 调用MCP服务器"""
    
    def __init__(self, server: MCPServer = None):
        self.server = server
        self.initialized = False
    
    def connect(self, server: MCPServer):
        """连接到服务器"""
        self.server = server
        self.initialized = True
    
    def initialize(self) -> Dict:
        """初始化连接"""
        if not self.server:
            raise ValueError("未连接到服务器")
        
        request = MCPRequest("initialize", {
            "protocolVersion": "2024-11-05",
            "clientInfo": {"name": "ai-agent", "version": "1.0.0"}
        })
        
        response = self.server.handle_request(request.to_dict())
        self.initialized = True
        return response
    
    def list_tools(self) -> List[Dict]:
        """列出可用工具"""
        self._ensure_connected()
        request = MCPRequest("tools/list")
        response = self.server.handle_request(request.to_dict())
        return response.get("result", {}).get("tools", [])
    
    def call_tool(self, tool_name: str, arguments: Dict = None) -> Any:
        """调用工具"""
        self._ensure_connected()
        request = MCPRequest("tools/call", {
            "name": tool_name,
            "arguments": arguments or {}
        })
        response = self.server.handle_request(request.to_dict())
        
        if "error" in response:
            raise Exception(response["error"]["message"])
        
        result = response.get("result", {})
        contents = result.get("content", [])
        
        if contents:
            return contents[0].get("text", "")
        return None
    
    def list_resources(self) -> List[Dict]:
        """列出可用资源"""
        self._ensure_connected()
        request = MCPRequest("resources/list")
        response = self.server.handle_request(request.to_dict())
        return response.get("result", {}).get("resources", [])
    
    def read_resource(self, uri: str) -> str:
        """读取资源"""
        self._ensure_connected()
        request = MCPRequest("resources/read", {"uri": uri})
        response = self.server.handle_request(request.to_dict())
        
        if "error" in response:
            raise Exception(response["error"]["message"])
        
        contents = response.get("result", {}).get("contents", [])
        if contents:
            return contents[0].get("text", "")
        return ""
    
    def _ensure_connected(self):
        """确保已连接"""
        if not self.server:
            raise ValueError("未连接到MCP服务器")


# ========== 默认MCP服务器 ==========

def create_default_mcp_server() -> MCPServer:
    """创建默认的MCP服务器"""
    server = MCPServer("ai-agent-tools", "1.0.0")
    
    # 注册工具
    @server.tool(name="get_time", description="获取当前时间")
    def get_time() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    @server.tool(name="calculate", description="计算数学表达式")
    def calculate(expression: str) -> str:
        try:
            import math
            safe_dict = {
                "__builtins__": {},
                "abs": abs, "round": round, "min": min, "max": max,
                "sqrt": math.sqrt, "pi": math.pi, "e": math.e
            }
            result = eval(expression, safe_dict)
            return str(result)
        except Exception as e:
            return "计算错误: {}".format(str(e))
    
    @server.tool(name="text_analyze", description="分析文本信息")
    def text_analyze(text: str) -> Dict:
        return {
            "字符数": len(text),
            "单词数": len(text.split()),
            "行数": text.count('\n') + 1
        }
    
    @server.tool(name="json_format", description="格式化JSON")
    def json_format(json_str: str) -> str:
        try:
            data = json.loads(json_str)
            return json.dumps(data, indent=2, ensure_ascii=False)
        except Exception as e:
            return "JSON错误: {}".format(str(e))
    
    # 注册资源
    def get_system_info() -> str:
        return json.dumps({
            "系统": "AI Agent",
            "版本": "1.0.0",
            "状态": "运行中"
        }, ensure_ascii=False)
    
    server.register_resource(
        uri="agent://system/info",
        name="系统信息",
        description="获取系统基本信息",
        handler=get_system_info
    )
    
    # 注册提示
    server.register_prompt(
        name="code_review",
        description="代码审查提示",
        arguments=[
            {"name": "code", "description": "要审查的代码", "required": True}
        ]
    )
    
    server.register_prompt(
        name="summarize",
        description="文本总结提示",
        arguments=[
            {"name": "text", "description": "要总结的文本", "required": True}
        ]
    )
    
    return server


# 全局MCP实例
mcp_server = create_default_mcp_server()
mcp_client = MCPClient(mcp_server)

def get_mcp_server() -> MCPServer:
    """获取MCP服务器"""
    return mcp_server

def get_mcp_client() -> MCPClient:
    """获取MCP客户端"""
    return mcp_client
