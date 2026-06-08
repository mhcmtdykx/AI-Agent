"""
基础工具模块 - 提供常用工具函数
"""
import ast
import math
import operator
from datetime import datetime


# 安全的数学表达式求值器 - 使用 AST 解析替代 eval()
_SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

_SAFE_FUNCTIONS = {
    "abs": abs, "round": round, "min": min, "max": max,
    "pow": pow, "sqrt": math.sqrt, "sin": math.sin,
    "cos": math.cos, "tan": math.tan, "log": math.log,
    "log10": math.log10, "log2": math.log2,
    "ceil": math.ceil, "floor": math.floor,
}

_SAFE_CONSTANTS = {"pi": math.pi, "e": math.e, "tau": math.tau}


def _safe_eval(node):
    """递归安全求值 AST 节点"""
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    elif isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError(f"不支持的常量类型: {type(node.value)}")
    elif isinstance(node, ast.BinOp):
        op = _SAFE_OPERATORS.get(type(node.op))
        if op is None:
            raise ValueError(f"不支持的运算符: {type(node.op).__name__}")
        return op(_safe_eval(node.left), _safe_eval(node.right))
    elif isinstance(node, ast.UnaryOp):
        op = _SAFE_OPERATORS.get(type(node.op))
        if op is None:
            raise ValueError(f"不支持的运算符: {type(node.op).__name__}")
        return op(_safe_eval(node.operand))
    elif isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id in _SAFE_FUNCTIONS:
            args = [_safe_eval(arg) for arg in node.args]
            return _SAFE_FUNCTIONS[node.func.id](*args)
        raise ValueError(f"不支持的函数调用")
    elif isinstance(node, ast.Name):
        if node.id in _SAFE_CONSTANTS:
            return _SAFE_CONSTANTS[node.id]
        raise ValueError(f"未定义的变量: {node.id}")
    else:
        raise ValueError(f"不支持的表达式类型: {type(node).__name__}")


# 工具函数定义
def get_current_time():
    """获取当前时间"""
    now = datetime.now()
    return f"当前时间是: {now.strftime('%Y-%m-%d %H:%M:%S')}"


def calculator(expression):
    """
    计算数学表达式（安全实现，基于 AST 解析）

    Args:
        expression: 数学表达式，如 "2 + 3 * 4"

    Returns:
        计算结果
    """
    try:
        tree = ast.parse(expression, mode='eval')
        result = _safe_eval(tree)
        return f"计算结果: {expression} = {result}"
    except (ValueError, TypeError, ZeroDivisionError) as e:
        return f"计算错误: {e}"
    except SyntaxError:
        return f"计算错误: 表达式语法无效 '{expression}'"


def text_analyzer(text):
    """
    分析文本的基本信息

    Args:
        text: 要分析的文本

    Returns:
        文本分析结果
    """
    word_count = len(text.split())
    char_count = len(text)
    line_count = len(text.split("\n"))
    avg_len = char_count / word_count if word_count > 0 else 0

    return (
        f"文本分析结果:\n"
        f"- 字符数: {char_count}\n"
        f"- 单词数: {word_count}\n"
        f"- 行数: {line_count}\n"
        f"- 平均单词长度: {avg_len:.1f}"
    )


def search(query):
    """
    搜索信息（模拟）

    Args:
        query: 搜索关键词

    Returns:
        搜索结果
    """
    return (
        f"搜索 '{query}' 的结果: 这是一个模拟搜索工具。"
        f"在实际应用中，您可以接入搜索引擎API来获取真实搜索结果。"
    )


# 工具注册表
TOOLS_REGISTRY = {
    "get_current_time": {
        "function": get_current_time,
        "description": "获取当前时间",
        "parameters": {},
    },
    "calculator": {
        "function": calculator,
        "description": "计算数学表达式",
        "parameters": {
            "expression": {
                "type": "string",
                "description": "数学表达式，如 '2 + 3 * 4'",
            }
        },
    },
    "text_analyzer": {
        "function": text_analyzer,
        "description": "分析文本的基本信息（字符数、单词数等）",
        "parameters": {
            "text": {
                "type": "string",
                "description": "要分析的文本",
            }
        },
    },
    "search": {
        "function": search,
        "description": "搜索信息",
        "parameters": {
            "query": {
                "type": "string",
                "description": "搜索关键词",
            }
        },
    },
}


def get_default_tools():
    """获取默认工具名称列表"""
    return list(TOOLS_REGISTRY.keys())


def get_tools_schema():
    """获取工具的OpenAI function calling格式定义"""
    tools = []
    for name, tool_info in TOOLS_REGISTRY.items():
        tool_def = {
            "name": name,
            "description": tool_info["description"],
            "parameters": {
                "type": "object",
                "properties": tool_info["parameters"],
                "required": list(tool_info["parameters"].keys()),
            },
        }
        tools.append(tool_def)
    return tools


def execute_tool(tool_name, **kwargs):
    """
    执行工具函数 - 先查MCP工具，再查技能编排

    Args:
        tool_name: 工具名称
        **kwargs: 工具参数

    Returns:
        工具执行结果
    """
    # 1. 技能调用（skill_ 前缀）
    if tool_name.startswith("skill_"):
        skill_name = tool_name[6:]  # 去掉 "skill_" 前缀
        try:
            from ..skills import get_skill_registry
            skill_registry = get_skill_registry()
            skill = skill_registry.get_skill(skill_name)
            if skill:
                task = kwargs.get("task", "")
                # 返回技能的完整提示词，让LLM基于此继续推理
                prompt = skill.get_full_prompt()
                return f"[启动技能: {skill.name}]\n{prompt}\n\n用户任务: {task}"
        except Exception:
            pass
        return f"未知技能: {skill_name}"

    # 2. MCP工具（内置）
    try:
        from ..mcp import get_mcp_client
        client = get_mcp_client()
        tools = client.list_tools()
        if isinstance(tools, list):
            tool_names = [t.get("name") for t in tools if isinstance(t, dict)]
            if tool_name in tool_names:
                result = client.call_tool(tool_name, kwargs)
                return str(result) if result else "工具执行完成"
    except Exception:
        pass

    # 3. 外部MCP工具
    try:
        from ..mcp_client import get_mcp_client as get_ext_client
        client = get_ext_client()
        for server_name in client.servers:
            try:
                tools = client.list_tools(server_name)
                if isinstance(tools, list) and any(isinstance(t, dict) and t.get("name") == tool_name for t in tools):
                    mcp_result = client.call_tool(server_name, tool_name, kwargs)
                    if mcp_result:
                        if isinstance(mcp_result, dict):
                            content = mcp_result.get("content", [])
                            if isinstance(content, list) and content:
                                texts = [item.get("text", str(item)) for item in content if isinstance(item, dict)]
                                return "\n".join(texts) if texts else str(mcp_result)
                            return str(mcp_result.get("result", mcp_result))
                        return str(mcp_result)
            except Exception:
                continue
    except Exception:
        pass

    return f"未知工具: {tool_name}"
