# AI Agent - 智能助手系统

基于 Python 的全功能 AI 智能助手系统，支持多种高级功能，提供直观的 Web 界面进行交互。

## 功能特性

### 核心功能
- **智能对话**：基于 OpenAI API 的自然语言对话
- **ReAct Agent**：支持推理-行动模式的智能代理
- **可配置模型**：支持 GPT-3.5、GPT-4 等多种模型

### 高级功能
- **RAG（检索增强生成）**：支持文档检索和知识库问答
- **多 Agent 系统**：多个 Agent 协作完成复杂任务
- **长期记忆**：支持对话历史和长期记忆存储
- **评估系统**：自动评估 Agent 性能和回答质量
- **可观测性**：完整的日志和追踪系统

### 扩展功能
- **Skills 技能系统**：可扩展的技能插件机制
- **MCP（模型上下文协议）**：支持外部工具和服务集成
- **图表生成**：支持 Mermaid 图表渲染
- **Web 界面**：现代化的响应式 Web 界面

## 快速开始

### 1. 环境要求
- Python 3.8+
- OpenAI API 密钥

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

#### 命令行模式
```bash
python main.py
```

#### Web 界面模式
```bash
# 方式1：使用 Flask 服务器
python flask_server.py

# 方式2：使用简单 HTTP 服务器
python simple_server.py

# 方式3：使用多线程服务器
python start_web_threaded.py
```

访问 http://localhost:5000 或 http://localhost:8000 查看 Web 界面。

## 项目结构

```
vibecoding/
├── agent/                    # 核心 Agent 模块
│   ├── __init__.py          # 模块初始化
│   ├── core.py              # 核心 Agent 类
│   ├── config.py            # 配置管理
│   ├── rag.py               # RAG 系统
│   ├── multi_agent.py       # 多 Agent 系统
│   ├── memory.py            # 长期记忆
│   ├── evaluation.py        # 评估系统
│   ├── observability.py     # 可观测性
│   ├── skills.py            # 技能系统
│   ├── mcp.py               # MCP 服务器
│   ├── mcp_client.py        # MCP 客户端
│   ├── tools/               # 工具集
│   └── utils/               # 工具函数
├── skills_config/           # 技能配置文件
├── memory_storage/          # 记忆存储
├── index.html               # Web 前端界面
├── main.py                  # 命令行入口
├── flask_server.py          # Flask Web 服务器
├── simple_server.py         # 简单 HTTP 服务器
├── requirements.txt         # 依赖列表
├── .env.example             # 配置文件示例
└── README.md                # 项目说明
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
| `LOG_LEVEL` | 日志级别 | `INFO` |

### 技能配置

技能配置文件位于 `skills_config/` 目录，支持 YAML 格式。每个技能可以定义：
- 技能名称和描述
- 输入参数
- 执行逻辑
- 返回格式

## 使用示例

### 命令行对话
```python
from agent import Agent, Config

# 加载配置
config = Config.from_env()

# 创建 Agent
agent = Agent(config)

# 进行对话
response = agent.chat("你好，请介绍一下你自己")
print(response)
```

### 使用 RAG 功能
```python
from agent import RAGSystem

# 初始化 RAG 系统
rag = RAGSystem()

# 添加文档
rag.add_document("path/to/document.pdf")

# 查询
answer = rag.query("文档的主要内容是什么？")
print(answer)
```

### 多 Agent 协作
```python
from agent import MultiAgentSystem

# 创建多 Agent 系统
system = MultiAgentSystem()

# 分配任务
result = system.execute_task("分析这段代码并提供优化建议")
print(result)
```

## Web 界面功能

Web 界面提供以下功能：

1. **智能对话**：实时对话界面，支持 Markdown 渲染
2. **管理面板**：配置和管理各项功能
   - RAG 文档管理
   - 记忆查看和清理
   - 多 Agent 配置
   - 技能管理
   - MCP 配置
   - 图表生成
   - 系统监控
3. **对话历史**：保存和管理对话记录
4. **响应式设计**：支持桌面和移动端

## 开发指南

### 添加新技能
1. 在 `skills_config/` 目录创建 YAML 配置文件
2. 定义技能的输入输出格式
3. 实现技能逻辑
4. 重启服务加载新技能

### 扩展 MCP 服务
1. 在 `mcp_config.json` 中配置 MCP 服务器
2. 实现 MCP 协议接口
3. 注册到 MCP 客户端

## 常见问题

### Q: 如何获取 OpenAI API 密钥？
A: 访问 https://platform.openai.com/api-keys 注册并获取 API 密钥。

### Q: 支持哪些模型？
A: 支持所有 OpenAI 兼容的模型，包括 GPT-3.5、GPT-4 等。也可以通过配置 `OPENAI_BASE_URL` 使用其他兼容 API。

### Q: 如何自定义技能？
A: 参考 `skills_config/` 目录中的示例文件，按照 YAML 格式定义新技能。

### Q: 数据存储在哪里？
A: 对话历史和记忆存储在 `memory_storage/` 目录，技能配置在 `skills_config/` 目录。

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！

## 联系方式

如有问题，请通过 GitHub Issues 反馈。
