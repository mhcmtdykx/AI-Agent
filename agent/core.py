"""
核心Agent类 - 直接使用requests调用OpenAI API
"""
import os
import json
import requests
from typing import Optional, List, Dict, Any, Generator

from .config import Config
from .tools import execute_tool
from .skills import get_skill_registry

# 对话历史存储目录
_HISTORY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "chat_history")
_MAX_HISTORY = 200  # 最大保存消息条数


class Agent:
    """聊天机器人Agent"""

    def __init__(
        self,
        config: Optional[Config] = None,
        system_prompt: Optional[str] = None,
        memory_size: int = 10,
        history_id: str = "default",
    ):
        """
        初始化Agent

        Args:
            config: 配置对象
            system_prompt: 系统提示词
            memory_size: 记忆窗口大小
            history_id: 对话历史标识，用于持久化文件命名
        """
        self.config = config or Config()
        self.system_prompt = system_prompt or self._get_default_system_prompt()
        self.memory_size = memory_size
        self._history_id = history_id

        # API配置
        self.api_key = self.config.api_key
        self.base_url = self.config.base_url or "https://api.openai.com/v1"

        # 工具定义 - 只使用技能系统
        self.tools_schema = self._load_skills_tools()

        # 对话历史（从文件恢复）
        self.chat_history = self._load_history()

    def _get_history_path(self) -> str:
        """获取对话历史文件路径"""
        os.makedirs(_HISTORY_DIR, exist_ok=True)
        return os.path.join(_HISTORY_DIR, f"{self._history_id}.json")

    def _load_history(self) -> list:
        """从文件加载对话历史"""
        path = self._get_history_path()
        if not os.path.exists(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"警告: 加载对话历史失败({path}): {e}")
            return []

    def _save_history(self):
        """将对话历史保存到文件（自动截断超限部分）"""
        path = self._get_history_path()
        try:
            # 限制历史长度
            if len(self.chat_history) > _MAX_HISTORY:
                self.chat_history = self.chat_history[-_MAX_HISTORY:]
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.chat_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存对话历史失败: {e}")
    
    def _load_skills_tools(self):
        """加载MCP工具和技能编排的schema"""
        tools = []
        # 1. MCP工具（原子操作）
        try:
            from .mcp import get_mcp_client
            client = get_mcp_client()
            mcp_tools = client.list_tools()
            if isinstance(mcp_tools, list):
                for t in mcp_tools:
                    tool_def = {
                        "type": "function",
                        "function": {
                            "name": t.get("name", ""),
                            "description": t.get("description", ""),
                            "parameters": t.get("inputSchema", {"type": "object", "properties": {}})
                        }
                    }
                    tools.append(tool_def)
        except Exception:
            pass

        # 2. 外部MCP工具
        try:
            from .mcp_client import get_mcp_client as get_ext_client
            client = get_ext_client()
            for server_name in client.servers:
                try:
                    mcp_tools = client.list_tools(server_name)
                    if isinstance(mcp_tools, list):
                        for t in mcp_tools:
                            tool_def = {
                                "type": "function",
                                "function": {
                                    "name": t.get("name", ""),
                                    "description": t.get("description", ""),
                                    "parameters": t.get("inputSchema", {"type": "object", "properties": {}})
                                }
                            }
                            tools.append(tool_def)
                except Exception:
                    pass
        except Exception:
            pass

        # 3. 技能编排（上层能力）
        try:
            skill_registry = get_skill_registry()
            tools.extend(skill_registry.get_tools_schema())
        except Exception:
            pass

        return tools

    def _get_default_system_prompt(self):
        """获取默认系统提示词"""
        return "你是一个有用的AI助手。你可以帮助用户完成各种任务，包括回答问题、进行对话、使用工具完成特定任务。请始终保持友好、专业，并尽力帮助用户。请使用中文与用户交流。"

    def _build_messages(self, user_message):
        """构建消息列表"""
        messages = [{"role": "system", "content": self.system_prompt}]

        # 添加历史对话
        history = self.chat_history[-self.memory_size * 2:]
        messages.extend(history)

        # 添加当前用户消息
        messages.append({"role": "user", "content": user_message})

        return messages

    def _call_api(self, messages, stream=False):
        """调用OpenAI API"""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        data = {
            "model": self.config.model_name,
            "messages": messages,
            "temperature": self.config.temperature,
            "stream": stream,
        }

        if self.tools_schema:
            # 使用新的tools格式（流式和非流式都支持）
            data["tools"] = self.tools_schema
            data["tool_choice"] = "auto"

        url = f"{self.base_url.rstrip('/')}/chat/completions"
        response = requests.post(url, headers=headers, json=data, stream=stream, timeout=60)
        response.raise_for_status()

        return response

    def chat(self, message):
        """
        与Agent对话

        Args:
            message: 用户消息

        Returns:
            Agent的回复
        """
        try:
            messages = self._build_messages(message)
            max_iterations = self.config.max_iterations

            for _ in range(max_iterations):
                response = self._call_api(messages)
                result = response.json()
                
                # 检查choices是否存在且不为空
                choices = result.get("choices", [])
                if not choices:
                    return "抱歉，API返回了空响应"
                
                assistant_message = choices[0].get("message", {})

                # 检查是否需要调用工具 - 支持新旧两种格式
                tool_calls = assistant_message.get("tool_calls", [])
                function_call = assistant_message.get("function_call")
                
                if tool_calls or function_call:
                    # 添加助手消息到上下文
                    messages.append(assistant_message)
                    
                    # 处理工具调用列表
                    calls_to_process = []
                    
                    if tool_calls:
                        # 新格式: tool_calls数组
                        for tc in tool_calls:
                            if tc.get("type") == "function":
                                calls_to_process.append({
                                    "id": tc.get("id"),
                                    "name": tc["function"]["name"],
                                    "arguments": tc["function"]["arguments"]
                                })
                    elif function_call:
                        # 旧格式: function_call对象
                        calls_to_process.append({
                            "id": None,
                            "name": function_call["name"],
                            "arguments": function_call["arguments"]
                        })
                    
                    # 处理每个工具调用
                    for call in calls_to_process:
                        function_name = call["name"]
                        arguments = json.loads(call["arguments"]) if isinstance(call["arguments"], str) else call["arguments"]
                        
                        # 使用技能系统执行工具
                        tool_result = execute_tool(function_name, **arguments)

                        # 添加工具结果消息
                        tool_message = {
                            "role": "tool",
                            "tool_call_id": call["id"] or f"call_{function_name}",
                            "content": tool_result,
                        }
                        messages.append(tool_message)

                        if self.config.verbose:
                            print(f"[工具调用] {function_name}({arguments}) -> {tool_result}")
                else:
                    # 没有工具调用，返回最终回复
                    reply = assistant_message.get("content", "") or ""
                    reasoning = assistant_message.get("reasoning_content", "") or ""
                    
                    # 如果content为空但有reasoning_content，使用reasoning_content
                    if not reply and reasoning:
                        reply = reasoning
                    
                    # 如果两者都有，组合返回
                    if reply and reasoning:
                        reply = f"【思考】{reasoning}\n\n【回答】{reply}"

                    # 保存到对话历史
                    self.chat_history.append({"role": "user", "content": message})
                    self.chat_history.append({"role": "assistant", "content": reply})
                    self._save_history()

                    return reply

            return "达到最大迭代次数，请重试"

        except Exception as e:
            return f"抱歉，处理您的请求时出现了错误: {e}"

    def chat_stream(self, message):
        """
        与Agent流式对话（支持function calling工具调用）

        Args:
            message: 用户消息

        Yields:
            包含type和content的字典，或纯文本片段
        """
        try:
            messages = self._build_messages(message)
            max_iterations = self.config.max_iterations

            for iteration in range(max_iterations):
                response = self._call_api(messages, stream=True)
                full_reply = ""
                tool_calls_map = {}
                has_tool_calls = False
                had_previous_tools = (iteration > 0)  # 是否有前几轮的工具调用

                for line in response.iter_lines():
                    if not line:
                        continue
                    line = line.decode("utf-8")
                    if not line.startswith("data: "):
                        continue
                    line = line[6:]
                    if line.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(line)
                        delta = chunk["choices"][0].get("delta", {})

                        # 处理文本内容
                        if delta.get("content"):
                            content = delta["content"]
                            full_reply += content
                            yield {"content": content}

                        # 处理工具调用（流式增量）
                        if delta.get("tool_calls"):
                            has_tool_calls = True
                            for tc_delta in delta["tool_calls"]:
                                idx = tc_delta.get("index", 0)
                                if idx not in tool_calls_map:
                                    tool_calls_map[idx] = {"id": "", "name": "", "arguments": ""}
                                if tc_delta.get("id"):
                                    tool_calls_map[idx]["id"] = tc_delta["id"]
                                func = tc_delta.get("function", {})
                                if func.get("name"):
                                    tool_calls_map[idx]["name"] = func["name"]
                                if func.get("arguments"):
                                    tool_calls_map[idx]["arguments"] += func["arguments"]
                    except json.JSONDecodeError:
                        continue

                # 如果有工具调用，执行它们
                if has_tool_calls and tool_calls_map:
                    # 构建 assistant 消息（包含 tool_calls）
                    assistant_msg = {"role": "assistant", "content": full_reply or None, "tool_calls": []}
                    for idx in sorted(tool_calls_map.keys()):
                        tc = tool_calls_map[idx]
                        assistant_msg["tool_calls"].append({
                            "id": tc["id"],
                            "type": "function",
                            "function": {"name": tc["name"], "arguments": tc["arguments"]}
                        })
                    messages.append(assistant_msg)

                    # 执行每个工具调用
                    for idx in sorted(tool_calls_map.keys()):
                        tc = tool_calls_map[idx]
                        tool_name = tc["name"]
                        try:
                            args = json.loads(tc["arguments"]) if tc["arguments"] else {}
                        except json.JSONDecodeError:
                            args = {}

                        tool_result = execute_tool(tool_name, **args)

                        # 输出工具调用信息给前端
                        yield {"type": "action", "content": f"调用工具 {tool_name}({args})"}
                        yield {"type": "observation", "content": str(tool_result)}

                        # 添加工具结果到消息
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc["id"] or f"call_{tool_name}",
                            "content": str(tool_result)
                        })

                    # 继续下一轮迭代，让 LLM 基于工具结果生成回复
                    continue

                # 没有工具调用，这是最终回复
                if had_previous_tools and full_reply:
                    # 如果之前有工具调用，将最终回复标记为answer
                    yield {"type": "answer", "content": full_reply}
                self.chat_history.append({"role": "user", "content": message})
                self.chat_history.append({"role": "assistant", "content": full_reply})
                self._save_history()
                return

            # 达到最大迭代次数
            yield {"content": "\n\n达到最大迭代次数，请重试"}

        except Exception as e:
            yield {"content": f"抱歉，处理您的请求时出现了错误: {e}"}

    def clear_memory(self):
        """清除对话历史"""
        self.chat_history.clear()
        self._save_history()

    def get_chat_history(self):
        """获取对话历史"""
        return self.chat_history.copy()

    def __repr__(self):
        return f"Agent(model={self.config.model_name}, memory={self.memory_size})"


class ReActAgent:
    """ReAct模式Agent - 结合推理和行动"""

    # ReAct提示词模板
    REACT_PROMPT = """你是一个智能助手，使用ReAct模式来解决问题。

可用工具：
{tools_description}

请严格按以下格式回答，每次只执行一个步骤：

Thought: [你的思考过程，分析问题并决定下一步行动]
Action: [工具名称]
Action Input: [工具参数，JSON格式]

重要：不要自己生成Observation！系统会自动执行工具并返回真正的结果。

当你收到Observation后，继续思考：
Thought: [基于Observation的思考]
Answer: [最终回答]

重要规则：
1. 每次只调用一个工具
2. Action Input必须是有效的JSON格式
3. 绝对不要自己编造Observation，等待系统返回真正的工具执行结果
4. 如果不需要工具，可以直接给出Answer
5. 使用中文回答
6. 只输出Thought和Action，不要输出Observation
"""

    def __init__(
        self,
        config: Optional[Config] = None,
        memory_size: int = 10,
        max_iterations: int = 5,
        history_id: str = "react",
    ):
        """
        初始化ReAct Agent

        Args:
            config: 配置对象
            memory_size: 记忆窗口大小
            max_iterations: 最大思考-行动循环次数
            history_id: 对话历史标识
        """
        self.config = config or Config()
        self.memory_size = memory_size
        self.max_iterations = max_iterations
        self._history_id = history_id

        # API配置
        self.api_key = self.config.api_key
        self.base_url = self.config.base_url or "https://api.openai.com/v1"

        # 对话历史（从文件恢复）
        self.chat_history = self._load_history()

        # 构建系统提示词
        self.system_prompt = self._build_system_prompt()

    def _get_history_path(self) -> str:
        os.makedirs(_HISTORY_DIR, exist_ok=True)
        return os.path.join(_HISTORY_DIR, f"{self._history_id}.json")

    def _load_history(self) -> list:
        path = self._get_history_path()
        if not os.path.exists(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"警告: 加载对话历史失败({path}): {e}")
            return []

    def _save_history(self):
        path = self._get_history_path()
        try:
            if len(self.chat_history) > _MAX_HISTORY:
                self.chat_history = self.chat_history[-_MAX_HISTORY:]
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.chat_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存对话历史失败: {e}")

    def _build_system_prompt(self):
        """构建ReAct系统提示词"""
        tools_desc = []
        
        # 加载技能系统描述
        try:
            skill_registry = get_skill_registry()
            for skill in skill_registry.list_skills():
                tools_desc.append(f"- {skill['name']}: {skill['description']}")
        except Exception:
            pass
        
        # 加载MCP工具描述
        mcp_desc = self._get_mcp_tools_description()
        if mcp_desc:
            tools_desc.append(mcp_desc)
        
        tools_description = "\n".join(tools_desc) if tools_desc else "暂无可用工具"
        return self.REACT_PROMPT.format(tools_description=tools_description)

    def _build_messages(self, user_message):
        """构建消息列表"""
        messages = [{"role": "system", "content": self.system_prompt}]

        # 添加历史对话
        history = self.chat_history[-self.memory_size * 2:]
        messages.extend(history)

        # 添加当前用户消息
        messages.append({"role": "user", "content": user_message})

        return messages

    def _call_api(self, messages, stream=False):
        """调用API"""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        data = {
            "model": self.config.model_name,
            "messages": messages,
            "temperature": self.config.temperature,
            "stream": stream,
        }

        url = f"{self.base_url.rstrip('/')}/chat/completions"
        response = requests.post(url, headers=headers, json=data, stream=stream, timeout=60)
        response.raise_for_status()

        return response

    def _parse_action(self, text):
        """解析Action和Action Input（增强版，支持多行JSON）"""
        import re

        # 提取Action名称
        action_match = re.search(r"Action\s*:\s*(\w+)", text)
        if not action_match:
            return None, {}

        tool_name = action_match.group(1)

        # 提取Action Input（支持多行JSON）
        input_match = re.search(r"Action\s*Input\s*:\s*(\{[\s\S]*?\})(?:\s*$|\s*(?:Thought|Action|Observation|Answer)\s*:)", text)
        if not input_match:
            # 回退：尝试匹配单行JSON
            input_match = re.search(r"Action\s*Input\s*:\s*(\{[^}]+\})", text)
        if not input_match:
            # 再次回退：匹配到最后一个}
            input_match = re.search(r"Action\s*Input\s*:\s*(\{[\s\S]*\})", text)
            if input_match:
                # 贪婪匹配，尝试找到最后一个完整的JSON
                raw = input_match.group(1)
                # 尝试从左到右找到第一个合法JSON
                depth = 0
                end = 0
                for i, c in enumerate(raw):
                    if c == '{': depth += 1
                    elif c == '}': depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
                if end > 0:
                    input_match = type('Match', (), {'group': lambda self, n: raw[:end]})()

        if input_match:
            try:
                args = json.loads(input_match.group(1))
            except (json.JSONDecodeError, AttributeError):
                args = {}
        else:
            args = {}

        return tool_name, args

    def _extract_answer(self, text):
        """提取Answer部分"""
        import re
        answer_match = re.search(r"Answer\s*:\s*(.+)", text, re.DOTALL)
        if answer_match:
            return answer_match.group(1).strip()
        return text

    def _get_mcp_tools_description(self):
        """获取所有MCP工具描述（内置+外部）"""
        desc = []
        # 1. 内置MCP工具
        try:
            from .mcp import get_mcp_client
            client = get_mcp_client()
            tools = client.list_tools()
            if isinstance(tools, list):
                for t in tools:
                    name = t.get("name", "")
                    d = t.get("description", "")
                    desc.append(f"- {name}: {d}")
        except Exception:
            pass
        # 2. 外部MCP工具
        try:
            from .mcp_client import get_mcp_client as get_ext_client
            client = get_ext_client()
            for server_name in client.servers:
                try:
                    tools = client.list_tools(server_name)
                    if isinstance(tools, list):
                        for t in tools:
                            name = t.get("name", "")
                            d = t.get("description", "")
                            desc.append(f"- {name}: {d}")
                except Exception:
                    pass
        except Exception:
            pass
        return "\n".join(desc)

    def chat(self, message):
        """
        使用ReAct模式与Agent对话

        Args:
            message: 用户消息

        Returns:
            包含思考过程和最终答案的字典
        """
        try:
            messages = self._build_messages(message)
            
            # 记录思考过程
            thoughts = []
            final_answer = ""
            
            for i in range(self.max_iterations):
                response = self._call_api(messages)
                result = response.json()
                
                choices = result.get("choices", [])
                if not choices:
                    return {"thoughts": thoughts, "answer": "抱歉，API返回了空响应"}
                
                reply = choices[0].get("message", {}).get("content", "")
                
                # 检查是否有Answer
                if "Answer:" in reply:
                    thoughts.append(reply)
                    final_answer = self._extract_answer(reply)
                    break
                
                # 检查是否有Action（但排除已经包含Observation的情况）
                if "Action:" in reply and "Observation:" not in reply:
                    thoughts.append(reply)
                    
                    # 解析工具调用
                    tool_name, args = self._parse_action(reply)
                    
                    if tool_name:
                        # 使用技能系统执行工具
                        from .tools import execute_tool
                        observation = execute_tool(tool_name, **args)
                        
                        # 添加到消息历史 - 只添加Thought和Action部分
                        action_part = reply.split("Observation:")[0].strip() if "Observation:" in reply else reply
                        messages.append({"role": "assistant", "content": action_part})
                        messages.append({"role": "user", "content": f"Observation: {observation}"})
                        
                        continue
                
                # 如果AI自己生成了Observation，截取到Action Input并执行真正的工具
                if "Action:" in reply and "Observation:" in reply:
                    # 截取到Action Input之前的部分
                    action_part = reply.split("Observation:")[0].strip()
                    thoughts.append(action_part)
                    
                    # 解析工具调用
                    tool_name, args = self._parse_action(action_part)
                    
                    if tool_name:
                        # 使用技能系统执行工具
                        from .tools import execute_tool
                        observation = execute_tool(tool_name, **args)
                        
                        # 添加到消息历史 - 使用真正的Observation
                        messages.append({"role": "assistant", "content": action_part})
                        messages.append({"role": "user", "content": f"Observation: {observation}"})
                        
                        continue
                
                # 如果既没有Answer也没有Action，直接返回
                final_answer = reply
                thoughts.append(reply)
                break
            
            if not final_answer:
                final_answer = "达到最大迭代次数，无法完成任务"
            
            # 保存到对话历史
            self.chat_history.append({"role": "user", "content": message})
            self.chat_history.append({"role": "assistant", "content": final_answer})
            self._save_history()

            return {
                "thoughts": thoughts,
                "answer": final_answer
            }

        except Exception as e:
            return {
                "thoughts": [],
                "answer": f"抱歉，处理您的请求时出现了错误: {e}"
            }

    def chat_stream(self, message):
        """
        使用ReAct模式流式对话

        Args:
            message: 用户消息

        Yields:
            包含type和content的字典
        """
        try:
            messages = self._build_messages(message)
            final_answer = ""
            
            for i in range(self.max_iterations):
                # 流式获取响应
                response = self._call_api(messages, stream=True)
                full_reply = ""
                
                # 流式读取响应
                for line in response.iter_lines():
                    if line:
                        line = line.decode("utf-8")
                        if line.startswith("data: "):
                            line = line[6:]
                            if line.strip() == "[DONE]":
                                break
                            try:
                                chunk = json.loads(line)
                                choices = chunk.get("choices", [])
                                if choices:
                                    delta = choices[0].get("delta", {})
                                    if delta.get("content"):
                                        content = delta["content"]
                                        full_reply += content
                                        # 实时输出每个字符 - 只返回content，不带type
                                        yield {"content": content}
                            except json.JSONDecodeError:
                                continue
                
                # 完整响应获取后，检查是否需要执行工具
                # 检查是否有Answer
                if "Answer:" in full_reply:
                    final_answer = self._extract_answer(full_reply)
                    yield {"type": "answer", "content": "\n\n**最终回答：**\n" + final_answer}
                    break
                
                # 检查是否有Action（且没有Observation，说明AI没有自己编造）
                if "Action:" in full_reply and "Observation:" not in full_reply:
                    # 解析工具调用
                    tool_name, args = self._parse_action(full_reply)
                    
                    if tool_name:
                        # 执行工具
                        from .tools import execute_tool
                        observation = execute_tool(tool_name, **args)
                        yield {"type": "observation", "content": f"\n\n**执行工具 {tool_name}：**\n{observation}"}

                        # 添加到消息历史
                        messages.append({"role": "assistant", "content": full_reply})
                        messages.append({"role": "user", "content": f"Observation: {observation}"})
                        continue

                # 如果AI自己生成了Observation，使用真正的工具结果
                if "Action:" in full_reply and "Observation:" in full_reply:
                    action_part = full_reply.split("Observation:")[0].strip()
                    tool_name, args = self._parse_action(action_part)

                    if tool_name:
                        # 执行工具
                        from .tools import execute_tool
                        observation = execute_tool(tool_name, **args)
                        yield {"type": "observation", "content": f"\n\n**执行工具 {tool_name}：**\n{observation}"}

                        # 添加到消息历史
                        messages.append({"role": "assistant", "content": action_part})
                        messages.append({"role": "user", "content": f"Observation: {observation}"})
                        continue
                
                # 直接回答（没有Action）
                final_answer = full_reply
                break
            
            # 保存到对话历史
            if final_answer:
                self.chat_history.append({"role": "user", "content": message})
                self.chat_history.append({"role": "assistant", "content": final_answer})
                self._save_history()

        except Exception as e:
            yield {"type": "answer", "content": f"\n\n抱歉，处理您的请求时出现了错误: {e}"}

    def clear_memory(self):
        """清除对话历史"""
        self.chat_history.clear()
        self._save_history()

    def get_chat_history(self):
        """获取对话历史"""
        return self.chat_history.copy()

    def __repr__(self):
        return f"ReActAgent(model={self.config.model_name}, max_iter={self.max_iterations})"
