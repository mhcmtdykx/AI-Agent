"""
核心Agent类 - 直接使用requests调用OpenAI API
"""
import json
import requests
from typing import Optional, List, Dict, Any, Generator

from .config import Config
from .tools import execute_tool
from .skills import get_skill_registry


class Agent:
    """聊天机器人Agent"""

    def __init__(
        self,
        config: Optional[Config] = None,
        system_prompt: Optional[str] = None,
        memory_size: int = 10,
    ):
        """
        初始化Agent

        Args:
            config: 配置对象
            system_prompt: 系统提示词
            memory_size: 记忆窗口大小
        """
        self.config = config or Config()
        self.system_prompt = system_prompt or self._get_default_system_prompt()
        self.memory_size = memory_size

        # API配置
        self.api_key = self.config.api_key
        self.base_url = self.config.base_url or "https://api.openai.com/v1"

        # 工具定义 - 只使用技能系统
        self.tools_schema = self._load_skills_tools()

        # 对话历史
        self.chat_history = []
    
    def _load_skills_tools(self):
        """加载技能系统的工具"""
        try:
            skill_registry = get_skill_registry()
            return skill_registry.get_tools_schema()
        except Exception as e:
            print("加载技能工具失败: {}".format(e))
            return []

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
            "Authorization": "Bearer {}".format(self.api_key),
        }

        data = {
            "model": self.config.model_name,
            "messages": messages,
            "temperature": self.config.temperature,
            "stream": stream,
        }

        if self.tools_schema and not stream:
            # 使用新的tools格式
            data["tools"] = self.tools_schema
            data["tool_choice"] = "auto"

        url = "{}/chat/completions".format(self.base_url.rstrip("/"))
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
                            "tool_call_id": call["id"] or "call_{}".format(function_name),
                            "content": tool_result,
                        }
                        messages.append(tool_message)

                        if self.config.verbose:
                            print("[工具调用] {}({}) -> {}".format(function_name, arguments, tool_result))
                else:
                    # 没有工具调用，返回最终回复
                    reply = assistant_message.get("content", "") or ""
                    reasoning = assistant_message.get("reasoning_content", "") or ""
                    
                    # 如果content为空但有reasoning_content，使用reasoning_content
                    if not reply and reasoning:
                        reply = reasoning
                    
                    # 如果两者都有，组合返回
                    if reply and reasoning:
                        reply = "【思考】{}\n\n【回答】{}".format(reasoning, reply)

                    # 保存到对话历史
                    self.chat_history.append({"role": "user", "content": message})
                    self.chat_history.append({"role": "assistant", "content": reply})

                    return reply

            return "达到最大迭代次数，请重试"

        except Exception as e:
            return "抱歉，处理您的请求时出现了错误: {}".format(str(e))

    def chat_stream(self, message):
        """
        与Agent流式对话

        Args:
            message: 用户消息

        Yields:
            Agent回复的片段
        """
        try:
            messages = self._build_messages(message)
            full_reply = ""

            response = self._call_api(messages, stream=True)

            for line in response.iter_lines():
                if line:
                    line = line.decode("utf-8")
                    if line.startswith("data: "):
                        line = line[6:]
                        if line.strip() == "[DONE]":
                            break
                        try:
                            chunk = json.loads(line)
                            delta = chunk["choices"][0].get("delta", {})
                            if delta.get("content"):
                                content = delta["content"]
                                full_reply += content
                                yield content
                        except json.JSONDecodeError:
                            continue

            # 保存到对话历史
            self.chat_history.append({"role": "user", "content": message})
            self.chat_history.append({"role": "assistant", "content": full_reply})

        except Exception as e:
            yield "抱歉，处理您的请求时出现了错误: {}".format(str(e))

    def clear_memory(self):
        """清除对话历史"""
        self.chat_history.clear()

    def get_chat_history(self):
        """获取对话历史"""
        return self.chat_history.copy()

    def __repr__(self):
        return "Agent(model={}, memory={})".format(self.config.model_name, self.memory_size)


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
    ):
        """
        初始化ReAct Agent

        Args:
            config: 配置对象
            memory_size: 记忆窗口大小
            max_iterations: 最大思考-行动循环次数
        """
        self.config = config or Config()
        self.memory_size = memory_size
        self.max_iterations = max_iterations

        # API配置
        self.api_key = self.config.api_key
        self.base_url = self.config.base_url or "https://api.openai.com/v1"

        # 对话历史
        self.chat_history = []

        # 构建系统提示词
        self.system_prompt = self._build_system_prompt()

    def _build_system_prompt(self):
        """构建ReAct系统提示词"""
        tools_desc = []
        
        # 只加载技能系统描述
        try:
            skill_registry = get_skill_registry()
            for skill in skill_registry.list_skills():
                tools_desc.append("- {}: {}".format(skill["name"], skill["description"]))
        except Exception:
            pass
        
        tools_description = "\n".join(tools_desc)
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
            "Authorization": "Bearer {}".format(self.api_key),
        }

        data = {
            "model": self.config.model_name,
            "messages": messages,
            "temperature": self.config.temperature,
            "stream": stream,
        }

        url = "{}/chat/completions".format(self.base_url.rstrip("/"))
        response = requests.post(url, headers=headers, json=data, stream=stream, timeout=60)
        response.raise_for_status()

        return response

    def _parse_action(self, text):
        """解析Action和Action Input"""
        import re
        
        # 提取Action
        action_match = re.search(r"Action:\s*(\w+)", text)
        if not action_match:
            return None, {}
        
        tool_name = action_match.group(1)
        
        # 提取Action Input
        input_match = re.search(r"Action Input:\s*(\{[^}]+\})", text)
        if input_match:
            try:
                args = json.loads(input_match.group(1))
            except json.JSONDecodeError:
                args = {}
        else:
            args = {}
        
        return tool_name, args

    def _extract_answer(self, text):
        """提取Answer部分"""
        import re
        answer_match = re.search(r"Answer:\s*(.+)", text, re.DOTALL)
        if answer_match:
            return answer_match.group(1).strip()
        return text

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
                        messages.append({"role": "user", "content": "Observation: {}".format(observation)})
                        
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
                        messages.append({"role": "user", "content": "Observation: {}".format(observation)})
                        
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
            
            return {
                "thoughts": thoughts,
                "answer": final_answer
            }

        except Exception as e:
            return {
                "thoughts": [],
                "answer": "抱歉，处理您的请求时出现了错误: {}".format(str(e))
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
                        yield {"type": "observation", "content": "\n\n**执行工具 {}：**\n{}".format(tool_name, observation)}
                        
                        # 添加到消息历史
                        messages.append({"role": "assistant", "content": full_reply})
                        messages.append({"role": "user", "content": "Observation: {}".format(observation)})
                        continue
                
                # 如果AI自己生成了Observation，使用真正的工具结果
                if "Action:" in full_reply and "Observation:" in full_reply:
                    action_part = full_reply.split("Observation:")[0].strip()
                    tool_name, args = self._parse_action(action_part)
                    
                    if tool_name:
                        # 执行工具
                        from .tools import execute_tool
                        observation = execute_tool(tool_name, **args)
                        yield {"type": "observation", "content": "\n\n**执行工具 {}：**\n{}".format(tool_name, observation)}
                        
                        # 添加到消息历史
                        messages.append({"role": "assistant", "content": action_part})
                        messages.append({"role": "user", "content": "Observation: {}".format(observation)})
                        continue
                
                # 直接回答（没有Action）
                final_answer = full_reply
                break
            
            # 保存到对话历史
            if final_answer:
                self.chat_history.append({"role": "user", "content": message})
                self.chat_history.append({"role": "assistant", "content": final_answer})

        except Exception as e:
            yield {"type": "answer", "content": "\n\n抱歉，处理您的请求时出现了错误: {}".format(str(e))}

    def clear_memory(self):
        """清除对话历史"""
        self.chat_history.clear()

    def get_chat_history(self):
        """获取对话历史"""
        return self.chat_history.copy()

    def __repr__(self):
        return "ReActAgent(model={}, max_iterations={})".format(self.config.model_name, self.max_iterations)
