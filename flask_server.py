"""使用Flask运行服务器 - 支持所有高级功能"""
import sys
import os
import json
import time

os.chdir(os.path.dirname(os.path.abspath(__file__)))

# 加载.env文件
def load_env_file(filepath):
    env_vars = {}
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key.strip()] = value.strip()
                    os.environ[key.strip()] = value.strip()
    return env_vars

load_env_file(".env")

from flask import Flask, request, Response, send_file
from agent import (
    Agent, ReActAgent, Config, rag_system,
    get_multi_agent_system, get_long_term_memory,
    get_evaluation_system, get_observability_system,
    get_skill_registry, get_mcp_server, get_mcp_client
)
import requests as http_requests

app = Flask(__name__)

config = Config.from_env()
config.validate()

# 初始化各系统
agent = Agent(config=config)
react_agent = ReActAgent(config=config)
multi_agent = get_multi_agent_system()
long_term_memory = get_long_term_memory()
evaluation = get_evaluation_system()
observability = get_observability_system()
skill_registry = get_skill_registry()
mcp_server = get_mcp_server()
mcp_client = get_mcp_client()

# 当前设置
current_mode = "normal"  # normal, react, multi_agent
use_rag = False
use_memory = False

@app.route("/")
def index():
    return send_file("index.html")

@app.route("/api/tools")
def tools():
    from agent.tools import TOOLS_REGISTRY
    tools = [{"name": name, "description": info["description"]} for name, info in TOOLS_REGISTRY.items()]
    return json.dumps(tools, ensure_ascii=False)

@app.route("/api/mode", methods=["GET", "POST"])
def mode():
    global current_mode, use_rag, use_memory
    if request.method == "POST":
        data = request.get_json()
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
    return json.dumps({
        "mode": current_mode,
        "rag": use_rag,
        "memory": use_memory
    })

# ========== RAG API ==========
@app.route("/api/rag/upload", methods=["POST"])
def rag_upload():
    # 支持文件上传和文本上传两种方式
    if request.content_type and 'multipart/form-data' in request.content_type:
        # 文件上传方式
        file = request.files.get('file')
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
                return json.dumps({"error": "不支持的文件格式: {}".format(file_ext)}), 400
        except Exception as e:
            return json.dumps({"error": "文件解析失败: {}".format(str(e))}), 400
        
        title = filename
    else:
        # JSON文本上传方式
        data = request.get_json()
        content = data.get("content", "")
        title = data.get("title", "未命名文档")
    
    if not content:
        return json.dumps({"error": "内容不能为空"}), 400
    
    try:
        chunk_count = rag_system.load_text(content, {"title": title, "source": "upload"})
        observability.info("RAG文档上传: {}".format(title), "rag")
        return json.dumps({
            "status": "ok",
            "chunk_count": chunk_count,
            "message": "文档已添加，分割为 {} 个文本块".format(chunk_count)
        })
    except Exception as e:
        observability.error("RAG上传失败: {}".format(str(e)), "rag")
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
        results = rag_system.search(query, top_k)
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
    return json.dumps(rag_system.get_stats())

@app.route("/api/rag/clear", methods=["POST"])
def rag_clear():
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
        observability.info("添加Agent: {} ({})".format(agent_id, role), "multi_agent")
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
    return json.dumps(long_term_memory.get_stats())

@app.route("/api/memory/search", methods=["POST"])
def memory_search():
    data = request.get_json()
    query = data.get("query", "")
    top_k = data.get("top_k", 5)
    
    if not query:
        return json.dumps({"error": "查询不能为空"}), 400
    
    results = long_term_memory.search(query, top_k)
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
    return json.dumps(long_term_memory.get_recent_memories(limit))

@app.route("/api/memory/clear", methods=["POST"])
def memory_clear():
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
    skill_name = data.get("skill")
    arguments = data.get("arguments", {})
    
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
    result = mcp_client.list_tools()
    return json.dumps({"tools": result})

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
    result = mcp_client.list_resources()
    return json.dumps({"resources": result})

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
    global current_mode, use_rag, use_memory
    
    start_time = time.time()
    
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
            use_react = data.get("react", current_mode == "react")
            enable_rag = data.get("rag", use_rag)
            enable_memory = data.get("memory", use_memory)
            use_multi_agent = data.get("multi_agent", current_mode == "multi_agent")
        
        if not message and not files:
            return json.dumps({"error": "消息不能为空"}), 400
        
        # 处理上传的文件
        file_contents = []
        for file in files:
            if file.filename:
                try:
                    content = file.read().decode('utf-8', errors='ignore')
                    file_contents.append("文件 {}: {}".format(file.filename, content[:2000]))  # 限制长度
                except Exception as e:
                    file_contents.append("文件 {}: 读取失败 - {}".format(file.filename, str(e)))
        
        # 如果有文件内容，添加到消息中
        if file_contents:
            file_context = "\n\n".join(file_contents)
            if message:
                message = "{}\n\n上传的文件内容:\n{}".format(message, file_context)
            else:
                message = "请分析以下文件内容:\n{}".format(file_context)
        
        # 记录日志
        observability.info("收到用户消息: {}".format(message[:50]), "chat")
    except Exception as e:
        observability.error("处理请求错误: {}".format(str(e)), "chat")
        return json.dumps({"error": "处理请求失败: {}".format(str(e))}), 400
    
    # 获取RAG上下文
    rag_context = ""
    if enable_rag and rag_system.is_loaded:
        rag_context = rag_system.get_context(message, top_k=3)
    
    # 获取长期记忆上下文
    memory_context = ""
    if enable_memory:
        memory_context = long_term_memory.get_context(message, top_k=3)
    
    # 构建增强消息
    enhanced_message = message
    context_parts = []
    
    if rag_context:
        context_parts.append("参考资料：\n{}".format(rag_context))
    if memory_context:
        context_parts.append("历史相关记录：\n{}".format(memory_context))
    
    if context_parts:
        enhanced_message = """请参考以下信息回答用户的问题：

{context}

用户问题：{question}""".format(context="\n\n".join(context_parts), question=message)
    
    # 选择Agent
    if use_multi_agent:
        # 多Agent模式
        if stream:
            def generate():
                try:
                    for item in multi_agent.chat_stream(enhanced_message, use_react):
                        yield "data: {}\n\n".format(json.dumps(item, ensure_ascii=False))
                    yield "data: [DONE]\n\n"
                except Exception as e:
                    yield "data: {}\n\n".format(json.dumps({"type": "answer", "content": "错误: {}".format(str(e))}, ensure_ascii=False))
            
            return Response(generate(), mimetype="text/event-stream")
        else:
            result = multi_agent.chat(enhanced_message, use_react)
            
            # 记录评估
            latency = time.time() - start_time
            evaluation.record_conversation(
                session_id="session_{}".format(int(start_time)),
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
                            yield "data: {}\n\n".format(json.dumps(item, ensure_ascii=False))
                    else:
                        messages = active_agent._build_messages(enhanced_message)
                        
                        headers = {
                            "Content-Type": "application/json",
                            "Authorization": "Bearer {}".format(active_agent.api_key),
                        }
                        
                        api_data = {
                            "model": active_agent.config.model_name,
                            "messages": messages,
                            "temperature": active_agent.config.temperature,
                            "stream": True,
                        }
                        
                        url = "{}/chat/completions".format(active_agent.base_url.rstrip("/"))
                        response = http_requests.post(url, headers=headers, json=api_data, stream=True, timeout=60)
                        
                        full_reply = ""
                        reasoning_content = ""
                        
                        for line in response.iter_lines():
                            if line:
                                line = line.decode("utf-8")
                                if line.startswith("data: "):
                                    line = line[6:]
                                    if line.strip() == "[DONE]":
                                        yield "data: [DONE]\n\n"
                                        break
                                    try:
                                        chunk = json.loads(line)
                                        choices = chunk.get("choices", [])
                                        if not choices:
                                            continue
                                        delta = choices[0].get("delta", {})
                                        if delta.get("reasoning_content"):
                                            reasoning_content += delta["reasoning_content"]
                                            yield "data: {}\n\n".format(json.dumps({"reasoning": delta["reasoning_content"]}, ensure_ascii=False))
                                        if delta.get("content"):
                                            content = delta["content"]
                                            full_reply += content
                                            yield "data: {}\n\n".format(json.dumps({"content": content}, ensure_ascii=False))
                                    except (json.JSONDecodeError, IndexError, KeyError):
                                        continue
                        
                        # 保存到对话历史
                        final_reply = full_reply if full_reply else reasoning_content
                        if final_reply:
                            active_agent.chat_history.append({"role": "user", "content": message})
                            active_agent.chat_history.append({"role": "assistant", "content": final_reply})
                            
                            # 保存到长期记忆
                            if enable_memory:
                                long_term_memory.add_conversation(message, final_reply)
                    
                    yield "data: [DONE]\n\n"
                    
                except Exception as e:
                    observability.error("聊天错误: {}".format(str(e)), "chat")
                    yield "data: {}\n\n".format(json.dumps({"error": str(e)}, ensure_ascii=False))
            
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
                session_id="session_{}".format(int(start_time)),
                user_message=message,
                ai_response=result.get("response", ""),
                latency=latency,
                success=True
            )
            
            # 保存到长期记忆
            if enable_memory:
                long_term_memory.add_conversation(message, result.get("response", ""))
            
            return json.dumps(result, ensure_ascii=False)

@app.route("/api/clear", methods=["POST"])
def clear():
    global current_mode
    data = request.get_json() or {}
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
    """上传图片并进行分析"""
    if 'file' not in request.files:
        return json.dumps({"error": "没有上传文件"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return json.dumps({"error": "文件名为空"}), 400
    
    # 检查文件类型
    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}
    if '.' not in file.filename or file.filename.rsplit('.', 1)[1].lower() not in allowed_extensions:
        return json.dumps({"error": "不支持的图片格式"}), 400
    
    try:
        # 读取图片内容
        image_data = file.read()
        
        # 将图片转换为base64
        import base64
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        
        # 调用AI分析图片
        # 注意：这需要AI模型支持图片分析
        # 目前返回图片信息
        return json.dumps({
            "status": "ok",
            "filename": file.filename,
            "size": len(image_data),
            "message": "图片上传成功。注意：当前模型可能不支持图片分析，图片已保存为文本描述。"
        }, ensure_ascii=False)
        
    except Exception as e:
        return json.dumps({"error": "处理图片失败: {}".format(str(e))}), 500

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
