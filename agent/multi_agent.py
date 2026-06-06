"""
多Agent协作系统 - 支持多个Agent分工合作
"""
import json
import uuid
from typing import Dict, List, Optional, Callable
from datetime import datetime
from .core import Agent, ReActAgent
from .config import Config


class AgentRole:
    """Agent角色定义"""
    def __init__(self, name: str, description: str, system_prompt: str, tools: List[str] = None):
        self.name = name
        self.description = description
        self.system_prompt = system_prompt
        self.tools = tools or []
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "description": self.description,
            "system_prompt": self.system_prompt,
            "tools": self.tools
        }


# 预定义角色
PREDEFINED_ROLES = {
    "researcher": AgentRole(
        name="研究员",
        description="负责信息收集和研究分析",
        system_prompt="""你是一个专业的研究员，负责：
1. 收集和整理信息
2. 分析数据和趋势
3. 提供有深度的见解
4. 回答专业问题

请用中文回答，保持专业和客观。""",
        tools=["search", "text_analyzer"]
    ),
    "writer": AgentRole(
        name="写作者",
        description="负责内容创作和文案撰写",
        system_prompt="""你是一个优秀的写作者，负责：
1. 撰写文章和报告
2. 优化文本表达
3. 创作创意内容
4. 总结和归纳信息

请用中文创作，注意文笔流畅。""",
        tools=["text_analyzer"]
    ),
    "analyst": AgentRole(
        name="分析师",
        description="负责数据分析和问题诊断",
        system_prompt="""你是一个专业的分析师，负责：
1. 分析复杂问题
2. 提供解决方案
3. 评估风险和机会
4. 给出建议和结论

请用中文回答，逻辑清晰。""",
        tools=["calculator", "text_analyzer"]
    ),
    "assistant": AgentRole(
        name="助手",
        description="负责日常任务和问题解答",
        system_prompt="""你是一个贴心的助手，负责：
1. 回答日常问题
2. 提供实用建议
3. 协助完成任务
4. 保持友好和耐心

请用中文回答，友好专业。""",
        tools=["get_current_time", "calculator"]
    )
}


class Task:
    """任务定义"""
    def __init__(self, task_id: str, description: str, assigned_to: str = None):
        self.task_id = task_id
        self.description = description
        self.assigned_to = assigned_to
        self.status = "pending"  # pending, in_progress, completed, failed
        self.result = None
        self.created_at = datetime.now().isoformat()
        self.completed_at = None
    
    def to_dict(self) -> Dict:
        return {
            "task_id": self.task_id,
            "description": self.description,
            "assigned_to": self.assigned_to,
            "status": self.status,
            "result": self.result,
            "created_at": self.created_at,
            "completed_at": self.completed_at
        }


class ConversationMessage:
    """协作消息"""
    def __init__(self, sender: str, receiver: str, content: str, message_type: str = "message"):
        self.message_id = str(uuid.uuid4())[:8]
        self.sender = sender
        self.receiver = receiver
        self.content = content
        self.message_type = message_type  # message, task, result, question
        self.timestamp = datetime.now().isoformat()
    
    def to_dict(self) -> Dict:
        return {
            "message_id": self.message_id,
            "sender": self.sender,
            "receiver": self.receiver,
            "content": self.content,
            "message_type": self.message_type,
            "timestamp": self.timestamp
        }


class MultiAgentSystem:
    """多Agent协作系统"""
    
    def __init__(self, config: Config = None):
        self.config = config or Config.from_env()
        self.agents: Dict[str, Agent] = {}
        self.roles: Dict[str, AgentRole] = {}
        self.tasks: Dict[str, Task] = {}
        self.messages: List[ConversationMessage] = []
        self.coordinator_name = "coordinator"
        
        # 初始化协调者Agent
        self._init_coordinator()
    
    def _init_coordinator(self):
        """初始化协调者Agent"""
        coordinator_prompt = """你是多Agent协作系统的协调者，负责：
1. 理解用户需求，分解任务
2. 分配任务给合适的Agent
3. 收集和整合各Agent的结果
4. 向用户汇报最终结果

可用的Agent角色：
{available_roles}

请用中文回答。当需要其他Agent协助时，请说明需要哪个角色完成什么任务。"""
        
        # 获取可用角色描述
        roles_desc = "\n".join([
            "- {}: {}".format(name, role.description) 
            for name, role in PREDEFINED_ROLES.items()
        ])
        
        system_prompt = coordinator_prompt.format(available_roles=roles_desc)
        
        self.agents[self.coordinator_name] = Agent(
            config=self.config,
            system_prompt=system_prompt
        )
        self.roles[self.coordinator_name] = AgentRole(
            name="协调者",
            description="负责任务分配和结果整合",
            system_prompt=system_prompt
        )
    
    def add_agent(self, agent_id: str, role_name: str) -> bool:
        """添加Agent"""
        if role_name not in PREDEFINED_ROLES:
            return False
        
        role = PREDEFINED_ROLES[role_name]
        self.roles[agent_id] = role
        
        self.agents[agent_id] = Agent(
            config=self.config,
            system_prompt=role.system_prompt
        )
        
        return True
    
    def remove_agent(self, agent_id: str) -> bool:
        """移除Agent"""
        if agent_id == self.coordinator_name:
            return False
        
        if agent_id in self.agents:
            del self.agents[agent_id]
            del self.roles[agent_id]
            return True
        return False
    
    def get_agent_list(self) -> List[Dict]:
        """获取所有Agent列表"""
        agents_list = []
        for agent_id, role in self.roles.items():
            agents_list.append({
                "id": agent_id,
                "name": role.name,
                "description": role.description,
                "is_coordinator": agent_id == self.coordinator_name
            })
        return agents_list
    
    def send_message(self, sender: str, receiver: str, content: str, message_type: str = "message"):
        """发送消息"""
        message = ConversationMessage(sender, receiver, content, message_type)
        self.messages.append(message)
        return message
    
    def get_messages(self, agent_id: str = None, limit: int = 50) -> List[Dict]:
        """获取消息"""
        messages = self.messages
        if agent_id:
            messages = [m for m in messages if m.sender == agent_id or m.receiver == agent_id]
        return [m.to_dict() for m in messages[-limit:]]
    
    def create_task(self, description: str, assigned_to: str = None) -> Task:
        """创建任务"""
        task_id = str(uuid.uuid4())[:8]
        task = Task(task_id, description, assigned_to)
        self.tasks[task_id] = task
        return task
    
    def update_task_status(self, task_id: str, status: str, result: str = None):
        """更新任务状态"""
        if task_id in self.tasks:
            self.tasks[task_id].status = status
            if result:
                self.tasks[task_id].result = result
            if status == "completed":
                self.tasks[task_id].completed_at = datetime.now().isoformat()
    
    def get_tasks(self, status: str = None) -> List[Dict]:
        """获取任务列表"""
        tasks = list(self.tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        return [t.to_dict() for t in tasks]
    
    def chat(self, message: str, use_react: bool = False) -> Dict:
        """
        与多Agent系统对话
        
        Args:
            message: 用户消息
            use_react: 是否使用ReAct模式
        
        Returns:
            包含各Agent响应的结果
        """
        result = {
            "user_message": message,
            "coordinator_response": "",
            "agent_responses": {},
            "tasks_created": [],
            "final_answer": ""
        }
        
        # 1. 协调者分析需求
        coordinator = self.agents[self.coordinator_name]
        coordinator_response = coordinator.chat(message)
        result["coordinator_response"] = coordinator_response
        
        # 2. 检查是否需要其他Agent协助
        # 优化的任务分配逻辑：根据关键词分配，增加权重和默认角色
        agent_keywords = {
            "researcher": ["研究", "调查", "搜索", "查找", "了解", "探索", "学习"],
            "writer": ["写", "撰写", "创作", "文章", "报告", "文案", "编写", "生成"],
            "analyst": ["分析", "评估", "诊断", "解决", "方案", "优化", "改进", "评估"],
            "assistant": ["帮助", "协助", "请问", "怎么", "如何", "是什么", "什么是", "介绍"]
        }
        
        # 找出最匹配的角色
        matched_role = None
        max_matches = 0
        
        for role, keywords in agent_keywords.items():
            matches = sum(1 for keyword in keywords if keyword in message)
            if matches > max_matches:
                max_matches = matches
                matched_role = role
        
        # 如果没有匹配到任何角色，默认使用助手
        if matched_role is None:
            matched_role = "assistant"
        
        # 3. 如果匹配到角色，分配任务
        if matched_role and matched_role in PREDEFINED_ROLES:
            # 自动创建Agent（如果不存在）
            agent_id = "agent_{}".format(matched_role)
            if agent_id not in self.agents:
                self.add_agent(agent_id, matched_role)
            
            # 创建任务
            task = self.create_task(message, agent_id)
            result["tasks_created"].append(task.to_dict())
            
            # 执行任务
            self.update_task_status(task.task_id, "in_progress")
            
            agent = self.agents[agent_id]
            agent_response = agent.chat(message)
            
            self.update_task_status(task.task_id, "completed", agent_response)
            result["agent_responses"][agent_id] = {
                "role": self.roles[agent_id].name,
                "response": agent_response
            }
            
            # 4. 协调者整合结果
            integration_prompt = """用户问题：{user_message}

协调者分析：{coordinator_response}

{role}的回答：{agent_response}

请整合以上信息，给出一个完整的最终回答。""".format(
                user_message=message,
                coordinator_response=coordinator_response,
                role=self.roles[agent_id].name,
                agent_response=agent_response
            )
            
            final_response = coordinator.chat(integration_prompt)
            result["final_answer"] = final_response
        else:
            # 没有匹配的角色，直接用协调者回答
            result["final_answer"] = coordinator_response
        
        # 记录消息
        self.send_message("user", self.coordinator_name, message)
        self.send_message(self.coordinator_name, "user", result["final_answer"])
        
        return result
    
    def chat_stream(self, message: str, use_react: bool = False):
        """
        流式对话
        
        Args:
            message: 用户消息
            use_react: 是否使用ReAct模式
        
        Yields:
            包含type和content的字典
        """
        # 简化版本：直接使用协调者
        coordinator = self.agents[self.coordinator_name]
        
        yield {"type": "status", "content": "协调者正在分析..."}
        
        # 分析是否需要其他Agent
        agent_keywords = {
            "researcher": ["研究", "调查", "搜索", "查找", "了解", "探索", "学习"],
            "writer": ["写", "撰写", "创作", "文章", "报告", "文案", "编写", "生成"],
            "analyst": ["分析", "评估", "诊断", "解决", "方案", "优化", "改进", "评估"],
            "assistant": ["帮助", "协助", "请问", "怎么", "如何", "是什么", "什么是", "介绍"]
        }
        
        matched_role = None
        max_matches = 0
        
        for role, keywords in agent_keywords.items():
            matches = sum(1 for keyword in keywords if keyword in message)
            if matches > max_matches:
                max_matches = matches
                matched_role = role
        
        # 如果没有匹配到任何角色，默认使用助手
        if matched_role is None:
            matched_role = "assistant"
        
        if matched_role:
            yield {"type": "status", "content": "正在调用{}处理...".format(PREDEFINED_ROLES[matched_role].name)}
            
            # 创建Agent并执行
            agent_id = "agent_{}".format(matched_role)
            if agent_id not in self.agents:
                self.add_agent(agent_id, matched_role)
            
            agent = self.agents[agent_id]
            
            if use_react:
                for item in agent.chat_stream(message):
                    yield item
            else:
                response = agent.chat(message)
                yield {"type": "content", "content": response}
        else:
            # 直接使用协调者
            if use_react:
                for item in coordinator.chat_stream(message):
                    yield item
            else:
                response = coordinator.chat(message)
                yield {"type": "content", "content": response}
    
    def clear_all(self):
        """清空所有Agent的记忆"""
        for agent in self.agents.values():
            agent.clear_memory()
        self.tasks.clear()
        self.messages.clear()


# 全局多Agent系统实例
multi_agent_system = None

def get_multi_agent_system() -> MultiAgentSystem:
    """获取多Agent系统实例"""
    global multi_agent_system
    if multi_agent_system is None:
        multi_agent_system = MultiAgentSystem()
    return multi_agent_system
