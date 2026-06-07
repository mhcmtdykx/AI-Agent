"""使用Flask运行服务器 - 支持所有高级功能"""
import sys
import os
import json
import time
import uuid
import threading
from collections import OrderedDict

os.chdir(os.path.dirname(os.path.abspath(__file__)))

# 加载.env文件
from agent.utils import load_env_file
load_env_file(".env")

from flask import Flask, request, Response, send_file
from agent import (
    Agent, ReActAgent, Config, rag_system,
    get_multi_agent_system, get_long_term_memory,
    get_evaluation_system, get_observability_system,
    get_skill_registry, get_mcp_server, get_mcp_client
)
from agent.auth import get_user_manager
import requests as http_requests

app = Flask(__name__)

config = Config.from_env()
config.validate()

# 初始化各系统（共享资源）
multi_agent = get_multi_agent_system()
long_term_memory = get_long_term_memory()
evaluation = get_evaluation_system()
observability = get_observability_system()
skill_registry = get_skill_registry()
mcp_server = get_mcp_server()
mcp_client = get_mcp_client()


class SessionManager:
    """按 session 隔离 Agent 实例，避免多用户对话串扰"""

    def __init__(self, config, max_sessions=50, ttl_seconds=3600):
        self._config = config
        self._max_sessions = max_sessions
        self._ttl = ttl_seconds
        self._sessions = OrderedDict()  # sid -> (agent, react_agent, last_access)
        self._lock = threading.Lock()

    def get_agents(self, sid=None):
        """获取或创建 session 对应的 Agent 实例，返回 (sid, agent, react_agent)"""
        if not sid:
            sid = str(uuid.uuid4())
        with self._lock:
            if sid in self._sessions:
                entry = self._sessions[sid]
                entry[2] = time.time()  # 更新 last_access
                self._sessions.move_to_end(sid)
                return sid, entry[0], entry[1]
            # 清理过期 session
            self._evict()
            # 创建新实例
            agent = Agent(config=self._config)
            react_agent = ReActAgent(config=self._config)
            self._sessions[sid] = [agent, react_agent, time.time()]
            return sid, agent, react_agent

    def clear_session(self, sid):
        with self._lock:
            self._sessions.pop(sid, None)

    def _evict(self):
        """淘汰过期和超限的 session"""
        now = time.time()
        # 淘汰过期
        expired = [k for k, v in self._sessions.items() if now - v[2] > self._ttl]
        for k in expired:
            del self._sessions[k]
        # 淘汰超限（LRU）
        while len(self._sessions) > self._max_sessions:
            self._sessions.popitem(last=False)


session_mgr = SessionManager(config)

# ========== RAG 提示词模板 ==========
RAG_PROMPT_TEMPLATES = {
    "default": """请基于以下参考资料回答用户的问题。

指南：
1. 答案必须完全基于提供的参考资料，不要添加任何不在参考资料中的内容。
2. 尽可能使用参考资料中的原文，保持答案的准确性。
3. 保持回答简洁，不超过参考资料的1.5倍长度，绝对不超过2.5倍长度。
4. 如果涉及数字、日期或具体数据，务必准确包含。
5. 如果参考资料不足以回答问题，请直接说明"根据提供的信息无法回答该问题"。
6. 不要使用"根据提供的信息"、"参考资料显示"等前缀，直接给出答案。

参考资料：
···
{context}
···

问题：{question}

回答：""",

    "precise": """作为一个精确的RAG系统助手，请严格按照以下指南回答用户问题：

1. 仔细分析问题，识别关键词和核心概念。
2. 从提供的参考资料中精确定位相关信息，优先使用完全匹配的内容。
3. 构建回答时，确保包含所有必要的关键词。
4. 保持回答与原文的语义相似度。
5. 控制回答长度，理想情况下不超过参考资料长度的1.5倍，最多不超过2.5倍。
6. 对于表格查询或需要多段落综合的问题，给予特别关注并提供更全面的回答。
7. 如果参考资料信息不足，可以进行合理推理，但要明确指出推理部分。
8. 回答应简洁、准确、完整，直接解答问题，避免不必要的解释。
9. 不要输出"检索到的文本块"、"根据"、"信息"等前缀修饰句，直接输出答案。
10. 不要使用"根据提供的信息"、"参考资料显示"等前缀，直接给出答案。

问题: {question}

参考资料：
···
{context}
···

请提供准确、相关且简洁的回答：""",

    "concise": """请结合参考资料回答用户问题，确保答案的准确性、全面性和权威性。
如果参考资料不能支撑用户问题，或者没有相关信息，请明确说明问题无法回答，避免生成虚假信息。
只输出答案，尽量包括关键词，不要输出额外内容，不要过多解释，不要输出额外无关文字以及过多修饰。
如果给定的参考资料无法让你做出回答，请直接回答："无法回答。"，不要输出额外内容。

问题: {question}
参考资料：
···
{context}
···
简明准确的回答："""
}

# 当前使用的 RAG 提示词模板
rag_prompt_mode = "default"

# ========== 用户级资源管理 ==========
class UserResourceManager:
    """按用户隔离 RAG 和长期记忆"""

    def __init__(self, base_path="user_storage"):
        self.base_path = base_path
        self._rag_instances = {}   # user_id -> RAGSystem
        self._memory_instances = {}  # user_id -> LongTermMemory
        self._lock = threading.Lock()
        os.makedirs(base_path, exist_ok=True)

    def get_rag(self, user_id: str):
        """获取用户的 RAG 实例"""
        if not user_id:
            return rag_system  # 未登录用户使用全局实例
        with self._lock:
            if user_id not in self._rag_instances:
                from agent.rag import RAGSystem
                instance = RAGSystem()
                # 尝试加载用户数据
                user_rag_path = os.path.join(self.base_path, user_id, "rag")
                if os.path.exists(user_rag_path):
                    self._load_user_rag(instance, user_rag_path)
                self._rag_instances[user_id] = instance
            return self._rag_instances[user_id]

    def get_memory(self, user_id: str):
        """获取用户的长期记忆实例"""
        if not user_id:
            return long_term_memory  # 未登录用户使用全局实例
        with self._lock:
            if user_id not in self._memory_instances:
                from agent.memory import LongTermMemory
                user_memory_path = os.path.join(self.base_path, user_id, "memory")
                instance = LongTermMemory(storage_path=user_memory_path)
                self._memory_instances[user_id] = instance
            return self._memory_instances[user_id]

    def _load_user_rag(self, instance, path):
        """加载用户的 RAG 数据"""
        data_file = os.path.join(path, "documents.json")
        if os.path.exists(data_file):
            try:
                import json as _json
                with open(data_file, 'r', encoding='utf-8') as f:
                    docs_data = _json.load(f)
                from agent.rag import Document
                docs = [Document(d["content"], d.get("metadata", {})) for d in docs_data]
                if docs:
                    instance.load_documents(docs)
            except Exception as e:
                print(f"加载用户RAG数据失败: {e}")

    def save_user_rag(self, user_id: str):
        """保存用户的 RAG 数据"""
        if not user_id or user_id not in self._rag_instances:
            return
        instance = self._rag_instances[user_id]
        user_rag_path = os.path.join(self.base_path, user_id, "rag")
        os.makedirs(user_rag_path, exist_ok=True)
        data_file = os.path.join(user_rag_path, "documents.json")
        try:
            import json as _json
            docs_data = [{"content": d.content, "metadata": d.metadata} for d in instance.vector_store.documents]
            with open(data_file, 'w', encoding='utf-8') as f:
                _json.dump(docs_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存用户RAG数据失败: {e}")

    def clear_user_rag(self, user_id: str):
        """清空用户的 RAG 数据"""
        if user_id and user_id in self._rag_instances:
            self._rag_instances[user_id].clear()
            self.save_user_rag(user_id)

    def clear_user_memory(self, user_id: str):
        """清空用户的记忆数据"""
        if user_id and user_id in self._memory_instances:
            self._memory_instances[user_id].clear()


user_resources = UserResourceManager()


# 当前设置（使用锁保护，确保线程安全）
_settings_lock = threading.Lock()
current_mode = "normal"  # normal, react, multi_agent
use_rag = False
use_memory = False


@app.after_request
def set_session_cookie(response):
    """确保客户端持有 session_id cookie"""
    if not request.cookies.get("session_id"):
        response.set_cookie("session_id", str(uuid.uuid4()), max_age=86400, httponly=False, samesite="Lax")
    return response


@app.route("/")
def index():
    return send_file("index.html")


# ========== Auth API ==========
@app.route("/api/auth/register", methods=["POST"])
def auth_register():
    data = request.get_json()
    username = data.get("username", "").strip()
    password = data.get("password", "")
    email = data.get("email")

    user_mgr = get_user_manager()
    result = user_mgr.register(username, password, email)
    return json.dumps(result, ensure_ascii=False)


@app.route("/api/auth/login", methods=["POST"])
def auth_login():
    data = request.get_json()
    username = data.get("username", "").strip()
    password = data.get("password", "")

    user_mgr = get_user_manager()
    result = user_mgr.login(username, password)
    return json.dumps(result, ensure_ascii=False)


def get_current_user():
    """从请求中获取当前用户信息"""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        user_mgr = get_user_manager()
        payload = user_mgr.verify_token(token)
        if payload:
            return {"user_id": payload["sub"], "username": payload["username"]}
    # 也支持从 query 参数或 body 获取 token
    token = request.args.get("token") or (request.get_json(silent=True) or {}).get("token")
    if token:
        user_mgr = get_user_manager()
        payload = user_mgr.verify_token(token)
        if payload:
            return {"user_id": payload["sub"], "username": payload["username"]}
    return None


@app.route("/api/health")
def health():
    return json.dumps({
        "status": "ok",
        "active_sessions": len(session_mgr._sessions),
        "mode": current_mode,
    })


@app.route("/api/tools")
def tools():
    all_tools = []
    # MCP内置工具
    try:
        from agent.mcp import get_mcp_client
        client = get_mcp_client()
        mcp_tools = client.list_tools()
        if isinstance(mcp_tools, list):
            for t in mcp_tools:
                all_tools.append({"name": t.get("name", ""), "description": t.get("description", ""), "source": "mcp"})
    except Exception:
        pass
    return json.dumps(all_tools, ensure_ascii=False)

@app.route("/api/mode", methods=["GET", "POST"])
def mode():
    global current_mode, use_rag, use_memory
    if request.method == "POST":
        data = request.get_json()
        with _settings_lock:
            new_mode = data.get("mode", current_mode)
            if new_mode in ["normal", "react", "multi_agent"]:
                current_mode = new_mode
            use_rag = data.get("rag", use_rag)
            use_memory = data.get("memory", use_memory)
            return json.dumps({
                "mode": current_mode,
                "rag": use_rag,
                "memory": use_memory,
                "status": "ok"
            })
    with _settings_lock:
        return json.dumps({
            "mode": current_mode,
            "rag": use_rag,
            "memory": use_memory
        })

# ========== RAG API ==========
@app.route("/api/rag/prompt-mode", methods=["GET", "POST"])
def rag_prompt_mode_api():
    global rag_prompt_mode
    if request.method == "POST":
        data = request.get_json()
        new_mode = data.get("mode", "default")
        if new_mode in RAG_PROMPT_TEMPLATES:
            rag_prompt_mode = new_mode
            return json.dumps({"status": "ok", "mode": rag_prompt_mode})
        return json.dumps({"error": "无效的模式"}), 400
    return json.dumps({"mode": rag_prompt_mode, "available": list(RAG_PROMPT_TEMPLATES.keys())})

@app.route("/api/rag/upload", methods=["POST"])
@app.route("/api/rag/add-text", methods=["POST"])
def rag_upload():
    # 支持文件上传和文本上传两种方式
    if request.content_type and 'multipart/form-data' in request.content_type:
        # 文件上传方式 - 支持 'file' 和 'files' 两种字段名
        file = request.files.get('file') or request.files.get('files')
        if not file:
            return json.dumps({"error": "没有上传文件"}), 400
        
        filename = file.filename
        file_ext = os.path.splitext(filename)[1].lower()
        
        # 根据文件类型解析内容
        try:
            if file_ext == '.pdf':
                # PDF文件解析
                content = extract_pdf_text(file)
            elif file_ext in ['.txt', '.md', '.csv', '.json', '.log', '.py', '.js', '.html', '.css']:
                # 文本文件
                try:
                    content = file.read().decode('utf-8')
                except UnicodeDecodeError:
                    file.seek(0)
                    content = file.read().decode('gbk')
            else:
                return json.dumps({"error": f"不支持的文件格式: {file_ext}"}), 400
        except Exception as e:
            return json.dumps({"error": f"文件解析失败: {e}"}), 400
        
        title = filename
    else:
        # JSON文本上传方式
        data = request.get_json()
        content = data.get("content", "")
        title = data.get("title", "未命名文档")
    
    if not content:
        return json.dumps({"error": "内容不能为空"}), 400
    
    try:
        # 获取当前用户的RAG实例
        current_user = get_current_user()
        user_id = current_user["user_id"] if current_user else None
        user_rag = user_resources.get_rag(user_id)
        
        chunk_count = user_rag.load_text(content, {"title": title, "source": "upload"})
        
        # 保存用户RAG数据
        if user_id:
            user_resources.save_user_rag(user_id)
        
        observability.info(f"RAG文档上传: {title} (user: {user_id or 'global'})", "rag")
        return json.dumps({
            "status": "ok",
            "chunk_count": chunk_count,
            "message": f"文档已添加，分割为 {chunk_count} 个文本块"
        })
    except Exception as e:
        observability.error(f"RAG上传失败: {e}", "rag")
        return json.dumps({"error": str(e)}), 500


def extract_pdf_text(file):
    """从PDF文件提取文本"""
    import PyPDF2
    import io
    
    pdf_reader = PyPDF2.PdfReader(io.BytesIO(file.read()))
    text_parts = []
    
    for page_num in range(len(pdf_reader.pages)):
        page = pdf_reader.pages[page_num]
        text = page.extract_text()
        if text:
            text_parts.append(text)
    
    return "\n\n".join(text_parts)

@app.route("/api/rag/search", methods=["POST"])
def rag_search():
    data = request.get_json()
    query = data.get("query", "")
    top_k = data.get("top_k", 3)
    
    if not query:
        return json.dumps({"error": "查询不能为空"}), 400
    
    try:
        current_user = get_current_user()
        user_id = current_user["user_id"] if current_user else None
        user_rag = user_resources.get_rag(user_id)
        
        results = user_rag.search(query, top_k)
        formatted_results = []
        for doc, score in results:
            formatted_results.append({
                "content": doc.content[:200] + "..." if len(doc.content) > 200 else doc.content,
                "score": round(score, 4),
                "metadata": doc.metadata
            })
        return json.dumps({"results": formatted_results})
    except Exception as e:
        return json.dumps({"error": str(e)}), 500

@app.route("/api/rag/stats", methods=["GET"])
def rag_stats():
    current_user = get_current_user()
    user_id = current_user["user_id"] if current_user else None
    user_rag = user_resources.get_rag(user_id)
    return json.dumps(user_rag.get_stats())

@app.route("/api/rag/clear", methods=["POST"])
def rag_clear():
    current_user = get_current_user()
    user_id = current_user["user_id"] if current_user else None
    if user_id:
        user_resources.clear_user_rag(user_id)
    else:
        rag_system.clear()
    return json.dumps({"status": "ok", "message": "知识库已清空"})

# ========== Multi-Agent API ==========
@app.route("/api/multi-agent/list", methods=["GET"])
def multi_agent_list():
    return json.dumps(multi_agent.get_agent_list())

@app.route("/api/multi-agent/add", methods=["POST"])
def multi_agent_add():
    data = request.get_json()
    agent_id = data.get("agent_id")
    role = data.get("role")
    
    if not agent_id or not role:
        return json.dumps({"error": "缺少参数"}), 400
    
    success = multi_agent.add_agent(agent_id, role)
    if success:
        observability.info(f"添加Agent: {agent_id} ({role})", "multi_agent")
        return json.dumps({"status": "ok"})
    return json.dumps({"error": "无效的角色"}), 400

@app.route("/api/multi-agent/remove", methods=["POST"])
def multi_agent_remove():
    data = request.get_json()
    agent_id = data.get("agent_id")
    
    success = multi_agent.remove_agent(agent_id)
    if success:
        return json.dumps({"status": "ok"})
    return json.dumps({"error": "无法移除该Agent"}), 400

@app.route("/api/multi-agent/tasks", methods=["GET"])
def multi_agent_tasks():
    return json.dumps(multi_agent.get_tasks())

@app.route("/api/multi-agent/messages", methods=["GET"])
def multi_agent_messages():
    agent_id = request.args.get("agent_id")
    limit = int(request.args.get("limit", 50))
    return json.dumps(multi_agent.get_messages(agent_id, limit))

# ========== Memory API ==========
@app.route("/api/memory/stats", methods=["GET"])
def memory_stats():
    current_user = get_current_user()
    user_id = current_user["user_id"] if current_user else None
    user_memory = user_resources.get_memory(user_id)
    return json.dumps(user_memory.get_stats())

@app.route("/api/memory/search", methods=["POST"])
def memory_search():
    data = request.get_json()
    query = data.get("query", "")
    top_k = data.get("top_k", 5)
    
    if not query:
        return json.dumps({"error": "查询不能为空"}), 400
    
    current_user = get_current_user()
    user_id = current_user["user_id"] if current_user else None
    user_memory = user_resources.get_memory(user_id)
    
    results = user_memory.search(query, top_k)
    formatted_results = [
        {
            "content": entry.content,
            "metadata": entry.metadata,
            "timestamp": entry.timestamp,
            "score": round(score, 4)
        }
        for entry, score in results
    ]
    return json.dumps({"results": formatted_results})

@app.route("/api/memory/recent", methods=["GET"])
def memory_recent():
    limit = int(request.args.get("limit", 10))
    current_user = get_current_user()
    user_id = current_user["user_id"] if current_user else None
    user_memory = user_resources.get_memory(user_id)
    return json.dumps(user_memory.get_recent_memories(limit))

@app.route("/api/memory/clear", methods=["POST"])
def memory_clear():
    current_user = get_current_user()
    user_id = current_user["user_id"] if current_user else None
    if user_id:
        user_resources.clear_user_memory(user_id)
    else:
        long_term_memory.clear()
    return json.dumps({"status": "ok", "message": "长期记忆已清空"})

# ========== Evaluation API ==========
@app.route("/api/evaluation/stats", methods=["GET"])
def evaluation_stats():
    return json.dumps(evaluation.get_stats())

@app.route("/api/evaluation/report", methods=["GET"])
def evaluation_report():
    return json.dumps(evaluation.get_performance_report())

@app.route("/api/evaluation/recent", methods=["GET"])
def evaluation_recent():
    limit = int(request.args.get("limit", 10))
    return json.dumps(evaluation.get_recent_conversations(limit))

@app.route("/api/evaluation/rate", methods=["POST"])
def evaluation_rate():
    data = request.get_json()
    session_id = data.get("session_id")
    rating = data.get("rating")
    feedback = data.get("feedback")
    
    if not session_id or not rating:
        return json.dumps({"error": "缺少参数"}), 400
    
    success = evaluation.rate_conversation(session_id, rating, feedback)
    if success:
        return json.dumps({"status": "ok"})
    return json.dumps({"error": "未找到该会话"}), 404

@app.route("/api/evaluation/clear", methods=["POST"])
def evaluation_clear():
    evaluation.clear()
    return json.dumps({"status": "ok", "message": "评估数据已清空"})

# ========== Observability API ==========
@app.route("/api/observability/health", methods=["GET"])
def observability_health():
    return json.dumps(observability.get_system_health())

@app.route("/api/observability/logs", methods=["GET"])
def observability_logs():
    level = request.args.get("level")
    module = request.args.get("module")
    limit = int(request.args.get("limit", 100))
    return json.dumps(observability.get_logs(level, module, limit))

@app.route("/api/observability/traces", methods=["GET"])
def observability_traces():
    limit = int(request.args.get("limit", 10))
    return json.dumps(observability.get_traces(limit))

@app.route("/api/observability/metrics", methods=["GET"])
def observability_metrics():
    return json.dumps(observability.get_metrics())

@app.route("/api/observability/stats", methods=["GET"])
def observability_stats():
    return json.dumps(observability.get_stats())

@app.route("/api/observability/clear", methods=["POST"])
def observability_clear():
    observability.clear()
    return json.dumps({"status": "ok", "message": "可观测性数据已清空"})

# ========== Skills API ==========
@app.route("/api/skills/list", methods=["GET"])
def skills_list():
    category = request.args.get("category")
    skills = skill_registry.list_skills(category=category)
    return json.dumps({"skills": skills, "categories": skill_registry.get_categories()})

@app.route("/api/skills/<skill_name>", methods=["GET"])
def skills_get(skill_name):
    skill = skill_registry.get_skill(skill_name)
    if skill:
        return json.dumps(skill.to_dict())
    return json.dumps({"error": "技能不存在"}), 404

@app.route("/api/skills/execute", methods=["POST"])
def skills_execute():
    data = request.get_json()
    skill_name = data.get("skill_name") or data.get("skill")
    arguments = data.get("parameters") or data.get("arguments", {})
    
    if not skill_name:
        return json.dumps({"error": "缺少技能名称"}), 400
    
    result = skill_registry.execute(skill_name, **arguments)
    return json.dumps(result, ensure_ascii=False)

@app.route("/api/skills/<skill_name>/enable", methods=["POST"])
def skills_enable(skill_name):
    skill_registry.enable_skill(skill_name)
    return json.dumps({"status": "ok"})

@app.route("/api/skills/<skill_name>/disable", methods=["POST"])
def skills_disable(skill_name):
    skill_registry.disable_skill(skill_name)
    return json.dumps({"status": "ok"})

@app.route("/api/skills/reload", methods=["POST"])
def skills_reload():
    """重新加载技能配置"""
    from agent import reload_skills
    reload_skills()
    return json.dumps({"status": "ok", "message": "技能配置已重新加载"})

# ========== 图表生成 API ==========
@app.route("/api/diagram/generate", methods=["POST"])
def diagram_generate():
    """生成论文框架图"""
    data = request.get_json()
    title = data.get("title", "论文框架")
    content = data.get("content", "")
    diagram_type = data.get("diagram_type", "flowchart")
    
    # 使用diagram_generator技能
    from agent.skills import skill_registry
    result = skill_registry.execute("diagram_generator", 
        title=title, 
        content=content, 
        diagram_type=diagram_type
    )
    
    return json.dumps(result)

# ========== MCP API ==========
@app.route("/api/mcp/info", methods=["GET"])
def mcp_info():
    return json.dumps(mcp_server.server_info)

@app.route("/api/mcp/tools", methods=["GET"])
def mcp_tools():
    try:
        tools = mcp_client.list_tools()
        return json.dumps({"tools": tools})
    except Exception:
        return json.dumps({"tools": []})

@app.route("/api/mcp/tools/call", methods=["POST"])
def mcp_tools_call():
    data = request.get_json()
    tool_name = data.get("tool")
    arguments = data.get("arguments", {})
    
    if not tool_name:
        return json.dumps({"error": "缺少工具名称"}), 400
    
    try:
        result = mcp_client.call_tool(tool_name, arguments)
        return json.dumps({"result": result})
    except Exception as e:
        return json.dumps({"error": str(e)}), 500

@app.route("/api/mcp/resources", methods=["GET"])
def mcp_resources():
    try:
        resources = mcp_client.list_resources()
        return json.dumps({"resources": resources})
    except Exception:
        return json.dumps({"resources": []})

@app.route("/api/mcp/resources/read", methods=["POST"])
def mcp_resources_read():
    data = request.get_json()
    uri = data.get("uri")
    
    if not uri:
        return json.dumps({"error": "缺少资源URI"}), 400
    
    try:
        content = mcp_client.read_resource(uri)
        return json.dumps({"content": content})
    except Exception as e:
        return json.dumps({"error": str(e)}), 500

@app.route("/api/mcp/protocol", methods=["POST"])
def mcp_protocol():
    """处理MCP协议请求"""
    data = request.get_json()
    response = mcp_server.handle_request(data)
    return json.dumps(response)

# ========== Chat API ==========
@app.route("/api/chat", methods=["POST"])
def chat():
    start_time = time.time()

    # 获取当前用户（支持认证）
    current_user = get_current_user()
    user_id = current_user["user_id"] if current_user else None

    # 获取 session 隔离的 Agent 实例
    sid = request.cookies.get("session_id", "")
    sid, agent, react_agent = session_mgr.get_agents(sid or None)

    # 在锁保护下读取全局设置的快照
    with _settings_lock:
        mode_snapshot = current_mode
        rag_snapshot = use_rag
        memory_snapshot = use_memory

    try:
        # 处理文件上传
        files = []
        if request.content_type and 'multipart/form-data' in request.content_type:
            # FormData格式（包含文件）
            message = request.form.get("message", "")
            stream = request.form.get("stream", "false").lower() == "true"
            use_react = request.form.get("react", "true").lower() == "true"
            enable_rag = request.form.get("rag", "true").lower() == "true"
            enable_memory = request.form.get("memory", "true").lower() == "true"
            use_multi_agent = request.form.get("multi_agent", "false").lower() == "true"

            # 获取上传的文件
            if 'files' in request.files:
                files = request.files.getlist('files')
        else:
            # JSON格式（无文件）
            data = request.get_json()
            message = data.get("message", "")
            stream = data.get("stream", False)
            use_react = data.get("react", mode_snapshot == "react")
            enable_rag = data.get("rag", rag_snapshot)
            enable_memory = data.get("memory", memory_snapshot)
            use_multi_agent = data.get("multi_agent", mode_snapshot == "multi_agent")
        
        if not message and not files:
            return json.dumps({"error": "消息不能为空"}), 400
        
        # 处理上传的文件
        file_contents = []
        for file in files:
            if file.filename:
                try:
                    content = file.read().decode('utf-8', errors='ignore')
                    file_contents.append(f"文件 {file.filename}: {content[:2000]}")  # 限制长度
                except Exception as e:
                    file_contents.append(f"文件 {file.filename}: 读取失败 - {e}")
        
        # 如果有文件内容，添加到消息中
        if file_contents:
            file_context = "\n\n".join(file_contents)
            if message:
                message = f"{message}\n\n上传的文件内容:\n{file_context}"
            else:
                message = f"请分析以下文件内容:\n{file_context}"
        
        # 记录日志
        observability.info(f"收到用户消息: {message[:50]}", "chat")
    except Exception as e:
        observability.error(f"处理请求错误: {e}", "chat")
        return json.dumps({"error": f"处理请求失败: {e}"}), 400
    
    # 获取RAG上下文（使用用户级资源）
    rag_context = ""
    user_rag = user_resources.get_rag(user_id)
    if enable_rag and user_rag.is_loaded:
        rag_context = user_rag.get_context(message, top_k=3)
    
    # 获取长期记忆上下文（使用用户级资源）
    memory_context = ""
    if enable_memory:
        user_memory = user_resources.get_memory(user_id)
        memory_context = user_memory.get_context(message, top_k=3)
    
    # 构建增强消息（使用专业RAG提示词模板）
    enhanced_message = message
    
    if rag_context:
        # 使用RAG提示词模板
        template = RAG_PROMPT_TEMPLATES.get(rag_prompt_mode, RAG_PROMPT_TEMPLATES["default"])
        enhanced_message = template.format(context=rag_context, question=message)
    elif memory_context:
        # 仅有记忆上下文时
        enhanced_message = (
            f"请参考以下历史相关记录回答当前问题：\n\n"
            f"历史相关记录：\n{memory_context}\n\n"
            f"当前问题：{message}"
        )
    
    # 选择Agent
    if use_multi_agent:
        # 多Agent模式
        if stream:
            def generate():
                try:
                    for item in multi_agent.chat_stream(enhanced_message, use_react):
                        yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
                    yield "data: [DONE]\n\n"
                except Exception as e:
                    yield f"data: {json.dumps({'type': 'answer', 'content': f'错误: {e}'}, ensure_ascii=False)}\n\n"
            
            return Response(generate(), mimetype="text/event-stream")
        else:
            result = multi_agent.chat(enhanced_message, use_react)
            
            # 记录评估
            latency = time.time() - start_time
            evaluation.record_conversation(
                session_id=f"session_{int(start_time)}",
                user_message=message,
                ai_response=result.get("final_answer", ""),
                latency=latency,
                success=True
            )
            
            return json.dumps(result, ensure_ascii=False)
    else:
        # 单Agent模式
        active_agent = react_agent if use_react else agent
        
        if stream:
            def generate():
                try:
                    if use_react:
                        for item in active_agent.chat_stream(enhanced_message):
                            yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
                    else:
                        # 使用Agent.chat_stream()（支持function calling工具调用）
                        for item in active_agent.chat_stream(enhanced_message):
                            if isinstance(item, dict):
                                yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
                            else:
                                # 兼容旧格式（纯文本）
                                yield f"data: {json.dumps({'content': item}, ensure_ascii=False)}\n\n"
                    
                    yield "data: [DONE]\n\n"
                    
                    # 保存到长期记忆
                    if enable_memory:
                        # 从agent获取最后的回复
                        history = active_agent.get_chat_history()
                        if len(history) >= 2:
                            last_reply = history[-1].get("content", "")
                            if last_reply:
                                user_memory = user_resources.get_memory(user_id)
                                user_memory.add_conversation(message, last_reply)
                    
                except Exception as e:
                    import traceback, sys
                    marker = f"[GENERATE_ERR:{type(e).__name__}:{e}]"
                    print(marker, file=sys.stderr, flush=True)
                    traceback.print_exc(file=sys.stderr)
                    observability.error(f"聊天错误: {e}", "chat")
                    yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
            
            return Response(generate(), mimetype="text/event-stream")
        else:
            if use_react:
                response = active_agent.chat(enhanced_message)
                result = {"response": response.get("answer", response) if isinstance(response, dict) else response}
            else:
                response = active_agent.chat(enhanced_message)
                result = {"response": response}
            
            # 记录评估
            latency = time.time() - start_time
            evaluation.record_conversation(
                session_id=f"session_{int(start_time)}",
                user_message=message,
                ai_response=result.get("response", ""),
                latency=latency,
                success=True
            )
            
            # 保存到长期记忆
            if enable_memory:
                user_memory = user_resources.get_memory(user_id)
                user_memory.add_conversation(message, result.get("response", ""))
            
            return json.dumps(result, ensure_ascii=False)

@app.route("/api/clear", methods=["POST"])
def clear():
    data = request.get_json() or {}
    sid = request.cookies.get("session_id", "")
    sid, agent, react_agent = session_mgr.get_agents(sid or None)
    mode = data.get("mode", current_mode)

    if mode == "multi_agent":
        multi_agent.clear_all()
    elif mode == "react":
        react_agent.clear_memory()
    else:
        agent.clear_memory()
    
    return json.dumps({"status": "ok"})

@app.route("/api/status", methods=["GET"])
def status():
    """系统状态"""
    return json.dumps({
        "mode": current_mode,
        "rag": use_rag,
        "memory": use_memory,
        "health": observability.get_system_health(),
        "stats": {
            "rag": rag_system.get_stats(),
            "memory": long_term_memory.get_stats(),
            "evaluation": evaluation.get_stats()
        }
    })

@app.route("/api/upload/image", methods=["POST"])
def upload_image():
    """上传图片并使用视觉模型进行分析"""
    if 'file' not in request.files:
        return json.dumps({"error": "没有上传文件"}), 400

    file = request.files['file']
    if file.filename == '':
        return json.dumps({"error": "文件名为空"}), 400

    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}
    ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
    if ext not in allowed_extensions:
        return json.dumps({"error": f"不支持的图片格式: {ext}"}), 400

    try:
        import base64
        image_data = file.read()
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        mime_type = f"image/{'jpeg' if ext in ('jpg', 'jpeg') else ext}"

        # 获取用户提示词（可选）
        prompt = request.form.get("prompt", "请描述并分析这张图片的内容。")

        # 调用支持视觉的模型
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.api_key}",
        }
        payload = {
            "model": config.model_name,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{image_base64}"},
                        },
                    ],
                }
            ],
            "max_tokens": 1024,
        }

        url = f"{config.base_url or 'https://api.openai.com/v1'}/chat/completions"
        resp = http_requests.post(url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        result = resp.json()

        choices = result.get("choices", [])
        answer = choices[0].get("message", {}).get("content", "") if choices and isinstance(choices, list) and len(choices) > 0 and isinstance(choices[0], dict) else ""
        return json.dumps({
            "status": "ok",
            "filename": file.filename,
            "size": len(image_data),
            "analysis": answer,
        }, ensure_ascii=False)

    except http_requests.exceptions.HTTPError as e:
        return json.dumps({"error": f"视觉模型调用失败（模型可能不支持图片）: {e}"}), 502
    except Exception as e:
        return json.dumps({"error": f"处理图片失败: {e}"}), 500

if __name__ == "__main__":
    observability.info("服务器启动", "server")
    print("=" * 50)
    print("AI Agent Web界面已启动!")
    print("请在浏览器中访问: http://127.0.0.1:8080")
    print("支持功能:")
    print("  - 普通对话模式")
    print("  - ReAct推理模式")
    print("  - 多Agent协作")
    print("  - RAG知识库")
    print("  - 长期记忆")
    print("  - 评估指标")
    print("  - 可观测性")
    print("=" * 50)
    sys.stdout.flush()
    app.run(host="127.0.0.1", port=8080, debug=False, threaded=True)
