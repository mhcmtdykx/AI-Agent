# AI Agent - 智能助手系统

基于 Python 的全功能 AI 智能助手系统，支持多种高级功能，提供直观的 Web 界面进行交互。

## 功能特性

### 核心功能
- **智能对话**：基于 OpenAI API 的自然语言对话，支持流式输出
- **ReAct Agent**：支持推理-行动模式的智能代理
- **可配置模型**：支持 GPT-3.5、GPT-4 等多种模型
- **Session 隔离**：多用户并发访问时对话互不干扰

### 高级功能
- **RAG（检索增强生成）**：基于 TF-IDF 的文档检索和知识库问答
- **多 Agent 系统**：加权关键词任务分配，多 Agent 协作完成复杂任务
- **长期记忆**：基于 TF-IDF 向量检索的对话历史存储和语义搜索
- **对话持久化**：对话历史自动保存到文件，重启后恢复
- **评估系统**：自动评估 Agent 性能和回答质量
- **可观测性**：完整的日志和追踪系统

### 扩展功能
- **Skills 技能系统**：可扩展的 YAML 技能插件机制，支持安全沙箱执行
- **MCP（模型上下文协议）**：支持外部工具和服务集成（stdio/HTTP）
- **Web 搜索**：集成 DuckDuckGo Instant Answer API
- **图表生成**：支持 Mermaid 图表渲染
- **Web 界面**：现代化的响应式 Web 界面，支持 Markdown 渲染和代码高亮

## 快速开始

### 1. 环境要求
- Python 3.8+
- OpenAI API 密钥（或兼容 API）

### 2. 安装依赖
```bash
pip install -r requirements.txt
```

### 3. 配置环境
```bash
# 复制配置文件
cp .env.example .env

# 编辑 .env 文件，填入你的配置
# 必填：OPENAI_API_KEY
# 可选：OPENAI_BASE_URL, MODEL_NAME, TEMPERATURE 等
```

### 4. 运行程序

#### Web 界面模式（推荐）
```bash
python flask_server.py
```
访问 http://127.0.0.1:8080 查看 Web 界面。

#### 命令行模式
```bash
python main.py
```

#### 健康检查
```bash
curl http://127.0.0.1:8080/api/health
# 返回: {"status": "ok", "active_sessions": 0, "mode": "normal"}
```

## 项目结构

```
vibecoding/
├── agent/                      # 核心 Agent 模块
│   ├── __init__.py             # 模块初始化
│   ├── core.py                 # Agent / ReActAgent 类
│   ├── config.py               # 配置管理
│   ├── rag.py                  # RAG 系统
│   ├── vector_store.py         # 公共 TF-IDF 向量检索（RAG/记忆共用）
│   ├── multi_agent.py          # 多 Agent 协作系统
│   ├── memory.py               # 长期记忆系统
│   ├── evaluation.py           # 评估系统
│   ├── observability.py        # 可观测性
│   ├── skills.py               # 技能系统（YAML 加载 + 安全沙箱）
│   ├── mcp.py                  # MCP 服务器
│   ├── mcp_client.py           # MCP 客户端（stdio/HTTP）
│   ├── tools/                  # 内置工具集
│   └── utils/                  # 工具函数（load_env_file 等）
├── skills_config/              # 技能配置文件（YAML）
├── chat_history/               # 对话历史持久化（运行时生成）
├── memory_storage/             # 长期记忆存储（运行时生成）
├── index.html                  # Web 前端界面
├── main.py                     # 命令行入口
├── flask_server.py             # Flask Web 服务器（主入口）
├── mcp_server.py               # 独立 MCP Server
├── requirements.txt            # 依赖列表
├── .env.example                # 配置文件示例
└── README.md                   # 项目说明
```

## 配置说明

### 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `OPENAI_API_KEY` | OpenAI API 密钥（必填） | - |
| `OPENAI_BASE_URL` | API 基础 URL | `https://api.openai.com/v1` |
| `MODEL_NAME` | 模型名称 | `gpt-3.5-turbo` |
| `TEMPERATURE` | 生成温度（0-2） | `0.7` |
| `MAX_ITERATIONS` | 最大迭代次数 | `5` |
| `VERBOSE` | 详细日志模式 | `false` |

### 技能配置

技能配置文件位于 `skills_config/` 目录，支持 YAML 格式。每个技能可以定义：
- 技能名称和描述
- 输入参数及类型
- 执行逻辑（API 调用或 Python 脚本沙箱执行）

## 使用示例

### 命令行对话
```python
from agent import Agent, Config

config = Config.from_env()
agent = Agent(config)
response = agent.chat("你好，请介绍一下你自己")
print(response)
```

### 使用 RAG 功能
```python
from agent import RAGSystem

rag = RAGSystem()

# 加载文档（支持 .txt、.md 等文本文件）
rag.load_file("path/to/document.txt")

# 或加载整个目录
rag.load_directory("path/to/docs/")

# 检索相关上下文
context = rag.get_context("文档的主要内容是什么？", top_k=3)
print(context)
```

### 多 Agent 协作
```python
from agent import get_multi_agent_system

system = get_multi_agent_system()
result = system.chat("分析这段代码并提供优化建议")

print(result["final_answer"])
print(result["coordinator_response"])
```

### 流式对话
```python
agent = Agent(config)
for chunk in agent.chat_stream("讲一个故事"):
    if "content" in chunk:
        print(chunk["content"], end="", flush=True)
```

## Web 界面功能

Web 界面提供以下功能：

1. **智能对话**：实时流式对话界面，支持 Markdown 渲染和代码高亮
2. **模式切换**：普通对话 / ReAct 推理 / 多 Agent 协作
3. **功能开关**：RAG 知识库、长期记忆可独立开关
4. **文件上传**：支持上传文件进行分析
5. **对话历史**：自动保存，支持查看和恢复
6. **管理面板**：RAG 文档管理、记忆查看、技能管理、系统监控

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/` | GET | Web 界面 |
| `/api/chat` | POST | 对话接口（支持流式） |
| `/api/health` | GET | 健康检查 |
| `/api/mode` | GET/POST | 获取/设置运行模式 |
| `/api/clear` | POST | 清空对话历史 |
| `/api/memory/stats` | GET | 记忆统计 |
| `/api/memory/search` | POST | 搜索记忆 |
| `/api/rag/status` | GET | RAG 状态 |
| `/api/rag/upload` | POST | 上传 RAG 文档 |

## 常见问题

### Q: 如何获取 OpenAI API 密钥？
A: 访问 https://platform.openai.com/api-keys 注册并获取 API 密钥。也可以通过配置 `OPENAI_BASE_URL` 使用其他兼容 API（如 DeepSeek、Moonshot 等）。

### Q: 支持哪些模型？
A: 支持所有 OpenAI 兼容的模型，包括 GPT-3.5、GPT-4、DeepSeek、Moonshot 等。

### Q: 如何自定义技能？
A: 在 `skills_config/` 目录创建 YAML 配置文件，参考已有示例定义技能名称、参数和执行逻辑，重启服务即可加载。

### Q: 数据存储在哪里？
A: 对话历史存储在 `chat_history/` 目录，长期记忆存储在 `memory_storage/` 目录，技能配置在 `skills_config/` 目录。

## 许可证

MIT License
