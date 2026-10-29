# 🎓 CampusQA-System — 校园智答 · 高校多租户智能咨询系统

> 基于 RAG + 规则引擎 + Agent 的高校招生/教务一体化 AI 咨询系统，支持多学校（多租户）独立知识库。

## ✨ 特性

- **多租户架构**：不同学校独立知识库，互不干扰
- **RAG 检索增强**：基于 ChromaDB 向量检索，精准匹配校规校纪
- **规则引擎**：结构化规则优先匹配，兜底 LLM 生成
- **流式对话**：SSE 流式输出，体验流畅
- **Docker 一键部署**：开箱即用

## 🛠 技术栈

| 组件 | 技术 |
|------|------|
| 后端框架 | FastAPI + Uvicorn |
| 大模型 | Ollama（本地 qwen2.5）/ 兼容 OpenAI API |
| 向量检索 | ChromaDB + Sentence-Transformers |
| 编排引擎 | LangGraph + LangChain |
| 数据库 | MySQL（多租户持久化）|
| 容器化 | Docker + Docker Compose |

## 📂 项目结构

```
CampusQA-System/
├── app/
│   ├── agent.py       # LangGraph Agent 编排
│   ├── config.py      # 全局配置（模型、数据库）
│   ├── db.py          # MySQL 连接管理
│   ├── llm.py         # LLM 流式调用封装
│   ├── main.py        # FastAPI 入口
│   ├── rag.py         # RAG 检索引擎
│   ├── rules.py       # 规则引擎
│   ├── search.py      # 向量搜索
│   └── tenant.py      # 多租户管理
├── docker-compose.yml
├── Dockerfile
├── eval.py            # 评测脚本
├── index.html         # Web 前端
├── requirements.txt
├── run.py             # 启动入口
└── test_agent.py      # Agent 测试
```

## 🚀 快速开始

### 1. 环境准备

```bash
# 安装依赖
pip install -r requirements.txt

# 启动 Ollama（本地模型）
ollama pull qwen2.5:7b
ollama serve
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env`，按需修改：

```env
LLM_BASE_URL=http://127.0.0.1:11434/v1
LLM_MODEL=qwen2.5:7b
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=campus_qa
```

### 3. 启动服务

```bash
# 直接运行
python run.py

# 或 Docker Compose 一键启动
docker-compose up -d
```

### 4. 访问

- Web 界面：http://localhost:8000/index.html
- API 文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health

## 📡 API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/chat` | POST | 流式对话（SSE） |
| `/admin/tenant` | POST | 创建/更新学校知识库 |
| `/admin/tenants` | GET | 查看所有学校 |

## 📝 License

MIT
