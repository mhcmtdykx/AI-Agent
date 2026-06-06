"""
基础工具模块 - 提供常用工具函数
"""
import math
import json
from datetime import datetime


# 工具函数定义
def get_current_time():
    """获取当前时间"""
    now = datetime.now()
    return "当前时间是: {}".format(now.strftime('%Y-%m-%d %H:%M:%S'))


def calculator(expression):
    """
    计算数学表达式

    Args:
        expression: 数学表达式，如 "2 + 3 * 4"

    Returns:
        计算结果
    """
    try:
        allowed_names = {
            "abs": abs, "round": round, "min": min, "max": max,
            "pow": pow, "sqrt": math.sqrt, "sin": math.sin,
            "cos": math.cos, "tan": math.tan, "log": math.log,
            "log10": math.log10, "pi": math.pi, "e": math.e,
        }
        result = eval(expression, {"__builtins__": {}}, allowed_names)
        return "计算结果: {} = {}".format(expression, result)
    except Exception as e:
        return "计算错误: {}".format(str(e))


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

    return "文本分析结果:\n- 字符数: {}\n- 单词数: {}\n- 行数: {}\n- 平均单词长度: {:.1f}".format(
        char_count, word_count, line_count, avg_len
    )


def search(query):
    """
    搜索信息（模拟）

    Args:
        query: 搜索关键词

    Returns:
        搜索结果
    """
    return "搜索 '{}' 的结果: 这是一个模拟搜索工具。在实际应用中，您可以接入搜索引擎API来获取真实搜索结果。".format(query)


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
    执行工具函数 - 只使用技能系统

    Args:
        tool_name: 工具名称
        **kwargs: 工具参数

    Returns:
        工具执行结果
    """
    try:
        from ..skills import get_skill_registry
        skill_registry = get_skill_registry()
        result = skill_registry.execute(tool_name, **kwargs)
        if result.get("success"):
            return str(result.get("result", ""))
        else:
            return "未知工具: {}".format(tool_name)
    except Exception as e:
        return "工具执行错误: {}".format(str(e))
