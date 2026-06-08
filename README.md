<div align="center">

# 光子 (GUANGZI)

**智能 AI 助手系统**

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Flask](https://img.shields.io/badge/Flask-2.3+-yellow.svg)](https://flask.palletsprojects.com/)
[![OpenAI](https://img.shields.io/badge/OpenAI-API-lightgrey.svg)](https://platform.openai.com/)

一个基于 Python 的全功能 AI 智能助手系统，支持多种高级功能，提供直观的 Web 界面进行交互。

[功能特性](#功能特性) • [快速开始](#快速开始) • [使用说明](#使用说明) • [API 文档](#api-文档) • [贡献指南](#贡献指南)

</div>

---

## 功能特性

### 核心功能

| 功能 | 描述 |
|------|------|
| 智能对话 | 基于 OpenAI API 的自然语言对话，支持流式输出 |
| ReAct Agent | 支持推理-行动模式的智能代理 |
| 思考模式 | 支持深度思考和推理过程展示 |
| 可配置模型 | 支持 GPT-3.5、GPT-4 等多种模型 |
| Session 隔离 | 多用户并发访问时对话互不干扰 |

### 高级功能

| 功能 | 描述 |
|------|------|
| RAG（检索增强生成） | 基于 TF-IDF 的文档检索和知识库问答 |
| 多 Agent 系统 | 加权关键词任务分配，多 Agent 协作完成复杂任务 |
| 长期记忆 | 基于 TF-IDF 向量检索的对话历史存储和语义搜索 |
| 对话持久化 | 对话历史自动保存到文件，重启后恢复 |
| 评估系统 | 自动评估 Agent 性能和回答质量 |
| 可观测性 | 完整的日志和追踪系统 |

### 扩展功能

| 功能 | 描述 |
|------|------|
| Skills 技能系统 | 可扩展的 YAML 技能插件机制，支持安全沙箱执行 |
| MCP（模型上下文协议） | 支持外部工具和服务集成（stdio/HTTP） |
| Web 搜索 | 集成 DuckDuckGo Instant Answer API |
| 图表生成 | 支持 Mermaid 图表渲染 |
| Web 界面 | 现代化的响应式 Web 界面，支持 Markdown 渲染和代码高亮 |

---

## 快速开始

### 环境要求

- Python 3.8+
- OpenAI API 密钥（或兼容 API）

### 安装步骤

1. **克隆仓库**

```bash
git clone https://github.com/mhcmtdykx/GUANGZI.git
cd GUANGZI
```

2. **安装依赖**

```bash
pip install -r requirements.txt
```

3. **配置环境**

```bash
# 复制配置文件
cp .env.example .env

# 编辑 .env 文件，填入你的配置
```

4. **运行程序**

```bash
# Web 界面模式（推荐）
python flask_server.py

# 或命令行模式
python main.py
```

5. **访问应用**

打开浏览器访问 http://127.0.0.1:8080

---

## 配置说明

### 环境变量

在 `.env` 文件中配置以下变量：

| 变量名 | 说明 | 是否必填 | 默认值 |
|--------|------|----------|--------|
| `OPENAI_API_KEY` | OpenAI API 密钥 | ✅ 是 | - |
| `OPENAI_BASE_URL` | API 基础 URL | ❌ 否 | `https://api.openai.com/v1` |
| `MODEL_NAME` | 模型名称 | ❌ 否 | `gpt-3.5-turbo` |
| `TEMPERATURE` | 生成温度（0-2） | ❌ 否 | `0.7` |
| `MAX_ITERATIONS` | 最大迭代次数 | ❌ 否 | `5` |
| `VERBOSE` | 详细日志模式 | ❌ 否 | `false` |

### 兼容 API

本项目支持所有 OpenAI 兼容的 API，包括：

- [OpenAI](https://platform.openai.com/)
- [DeepSeek](https://platform.deepseek.com/)
- [Moonshot](https://platform.moonshot.cn/)
- [智谱 AI](https://open.bigmodel.cn/)
- [Ollama](https://ollama.ai/)（本地部署）

---

## 使用说明

### Web 界面

Web 界面提供以下功能：

1. **智能对话**：实时流式对话界面，支持 Markdown 渲染和代码高亮
2. **模式切换**：普通对话 / ReAct 推理 / 多 Agent 协作
3. **思考模式**：开启后可查看 AI 的推理过程
4. **功能开关**：RAG 知识库、长期记忆可独立开关
5. **文件上传**：支持上传文件进行分析
6. **对话历史**：自动保存，支持查看和恢复
7. **管理面板**：RAG 文档管理、记忆查看、技能管理、系统监控

### 命令行模式

```bash
python main.py
```

支持的命令：
- `quit` / `exit`：退出程序
- `clear`：清除对话历史
- `tools`：查看可用工具

### Python API

```python
from agent import Agent, Config

# 加载配置
config = Config.from_env()
config.validate()

# 创建 Agent
agent = Agent(config=config)

# 对话
response = agent.chat("你好，请介绍一下你自己")
print(response)

# 流式对话
for chunk in agent.chat_stream("讲一个故事"):
    if "content" in chunk:
        print(chunk["content"], end="", flush=True)
```

### RAG 功能

```python
from agent import RAGSystem

rag = RAGSystem()

# 加载文档
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
```

---

## API 文档

### 对话接口

```
POST /api/chat
```

**请求参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `message` | string | 用户消息 |
| `stream` | boolean | 是否使用流式输出 |
| `react` | boolean | 是否使用 ReAct 模式 |
| `rag` | boolean | 是否启用 RAG |
| `memory` | boolean | 是否启用长期记忆 |

**响应：**

- 流式模式：返回 Server-Sent Events
- 非流式模式：返回 JSON 对象

### 其他接口

| 端点 | 方法 | 说明 |
|------|------|------|
| `/` | GET | Web 界面 |
| `/api/health` | GET | 健康检查 |
| `/api/mode` | GET/POST | 获取/设置运行模式 |
| `/api/clear` | POST | 清空对话历史 |
| `/api/memory/stats` | GET | 记忆统计 |
| `/api/memory/search` | POST | 搜索记忆 |
| `/api/rag/stats` | GET | RAG 统计 |
| `/api/rag/upload` | POST | 上传 RAG 文档 |
| `/api/skills/list` | GET | 技能列表 |
| `/api/skills/execute` | POST | 执行技能 |
| `/api/mcp/tools` | GET | MCP 工具列表 |
| `/api/mcp/tools/call` | POST | 调用 MCP 工具 |

---

## 项目结构

```
GUANGZI/
├── agent/                      # 核心 Agent 模块
│   ├── __init__.py             # 模块初始化
│   ├── core.py                 # Agent / ReActAgent 类
│   ├── config.py               # 配置管理
│   ├── rag.py                  # RAG 系统
│   ├── vector_store.py         # TF-IDF 向量检索
│   ├── multi_agent.py          # 多 Agent 协作系统
│   ├── memory.py               # 长期记忆系统
│   ├── evaluation.py           # 评估系统
│   ├── observability.py        # 可观测性
│   ├── skills.py               # 技能系统
│   ├── mcp.py                  # MCP 服务器
│   ├── mcp_client.py           # MCP 客户端
│   ├── tools/                  # 内置工具集
│   └── utils/                  # 工具函数
├── skills_config/              # 技能配置文件（YAML）
├── index.html                  # Web 前端界面
├── main.py                     # 命令行入口
├── flask_server.py             # Flask Web 服务器（主入口）
├── mcp_server.py               # 独立 MCP Server
├── requirements.txt            # 依赖列表
├── .env.example                # 配置文件示例
├── .gitignore                  # Git 忽略文件
└── README.md                   # 项目说明
```

---

## 技能系统

### 内置技能

| 技能名称 | 描述 |
|----------|------|
| `code_review` | 代码审查 |
| `data_analyzer` | 数据分析 |
| `doc_generator` | 文档生成 |
| `research_assistant` | 研究助手 |

### 自定义技能

在 `skills_config/` 目录下创建 YAML 文件：

```yaml
name: my_skill
description: 我的自定义技能
parameters:
  - name: input
    type: string
    description: 输入参数
execute:
  type: script
  code: |
    return f"处理结果: {input}"
```

---

## MCP 工具

### 内置工具

| 工具名称 | 描述 |
|----------|------|
| `web_search` | 网络搜索（DuckDuckGo） |
| `weather` | 天气查询 |
| `calculator` | 计算器 |
| `text_analyzer` | 文本分析 |
| `json_formatter` | JSON 格式化 |
| `translator` | 翻译 |
| `summarizer` | 文本摘要 |

### 配置外部 MCP

在 `mcp_config.json` 中配置：

```json
{
  "servers": {
    "my_server": {
      "transport": "stdio",
      "command": "python",
      "args": ["my_mcp_server.py"]
    }
  }
}
```

---

## 常见问题

### Q: 如何获取 OpenAI API 密钥？

A: 访问 [OpenAI Platform](https://platform.openai.com/api-keys) 注册并获取 API 密钥。

### Q: 支持哪些模型？

A: 支持所有 OpenAI 兼容的模型，包括 GPT-3.5、GPT-4、DeepSeek、Moonshot 等。

### Q: 如何使用其他 API 服务？

A: 在 `.env` 文件中设置 `OPENAI_BASE_URL` 为对应的 API 地址。

### Q: 如何自定义技能？

A: 参考 [技能系统](#技能系统) 部分，在 `skills_config/` 目录下创建 YAML 配置文件。

### Q: 如何部署到生产环境？

A: 建议使用 Gunicorn 或 uWSGI 部署：

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:8080 flask_server:app
```

---

## 贡献指南

欢迎贡献代码、报告问题或提出建议！

1. Fork 本仓库
2. 创建特性分支：`git checkout -b feature/my-feature`
3. 提交更改：`git commit -m 'Add my feature'`
4. 推送分支：`git push origin feature/my-feature`
5. 提交 Pull Request

### 开发环境

```bash
# 克隆仓库
git clone https://github.com/mhcmtdykx/GUANGZI.git
cd GUANGZI

# 安装开发依赖
pip install -r requirements.txt

# 运行测试
python -m pytest tests/
```

### 代码规范

- 遵循 PEP 8 代码规范
- 添加适当的注释和文档字符串
- 编写单元测试

---

## 许可证

本项目采用 [MIT 许可证](LICENSE) 开源。

---

## 致谢

- [OpenAI](https://openai.com/) - 提供强大的 AI API
- [Flask](https://flask.palletsprojects.com/) - 轻量级 Web 框架
- [Marked](https://marked.js.org/) - Markdown 解析器
- [Highlight.js](https://highlightjs.org/) - 代码高亮库
- [Mermaid](https://mermaid.js.org/) - 图表生成库

---

## 联系方式

- GitHub: [mhcmtdykx/GUANGZI](https://github.com/mhcmtdykx/GUANGZI)
- Issues: [提交问题](https://github.com/mhcmtdykx/GUANGZI/issues)

---

<div align="center">

**如果这个项目对你有帮助，请给一个 ⭐ Star 支持一下！**

</div>
