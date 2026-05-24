# 提瓦特Ai伙伴

提瓦特Ai伙伴，采用双模式设计：**派蒙**作为智能管家，提供游戏攻略查询、联网搜索、语音助手等实用功能；还可以自定义原神自机角色，以符合原作设定的语气与玩家对话。基于 LangGraph ReAct 架构，结合 RAG 增强检索、长期记忆和工具调用能力，采用 FastAPI 服务端 + Electron 桌面前端架构。

## 功能特性

- **双模式设计**
  - **派蒙（智能管家）** — 游戏攻略查询、联网搜索资讯、语音播报助手，陪伴玩家探索提瓦特
  - **角色扮演** — 钟离、胡桃等角色，拥有独立人设、语气和知识库，沉浸式角色互动体验
- **RAG 增强对话** — 混合检索（BM25 关键词 + 向量语义，RRF 融合），从世界背景和故事知识库中召回相关上下文，确保回答贴合原作设定
- **长期记忆** — 基于 mem0 框架的持久化记忆系统，跨会话记住与玩家的互动历史
- **联网搜索** — 集成 SearXNG 搜索引擎，获取游戏最新资讯和攻略信息
- **语音合成** — 基于 MiMo-V2.5-TTS-VoiceClone 的角色语音克隆，用角色原声朗读对话内容
- **流式输出** — SSE 协议逐 token 流式返回，打字机效果实时展示回复
- **桌面应用** — Electron + React + Vite 构建的跨平台桌面客户端，开箱即用

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- PostgreSQL 14+
- Qdrant 向量数据库
- SearXNG 搜索引擎
- ffmpeg（语音预处理需要）

### 1. 克隆项目

```bash
git clone https://github.com/your-username/genshinRole.git
cd genshinRole
```

### 2. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

```bash
cp example.env .env
```

编辑 `.env` 文件，填入各项配置（详见下方[配置说明](#配置说明)）。

### 4. 启动基础服务

确保以下服务已启动：

```bash
# PostgreSQL（默认端口 5432，数据库 genshin_chat）
# Qdrant（默认端口 6333）
# SearXNG（默认端口 8887）
```

### 5. 导入知识库数据（可选）

```bash
# 导入世界背景
python -m data_prepare.world_bg.ingest_world_bg_to_qdrant

# 导入故事剧情
python -m data_prepare.world_bg.invest_story_to_qdrant
```

### 6. 语音预处理（可选，如需使用语音合成功能）

```bash
python -m voice.preprocess
```

将角色语音 MP3 文件放入 `data/role/sound/`，脚本会自动转换为 WAV 并截取参考音频。

### 7. 启动应用

**方式一：Electron 桌面应用（推荐）**

```bash
cd electron
npm install
npm run electron:dev
```

自动拉起后端和前端，打开桌面窗口。

**方式二：仅启动后端**

```bash
python -m server
```

访问 `http://127.0.0.1:8000/docs` 查看 API 文档。

## 配置说明

项目通过根目录 `.env` 文件管理配置，复制 `example.env` 并填入对应值：

### LLM 配置

| 变量 | 说明 | 示例 |
|------|------|------|
| `model` | LLM 模型名称 | `MiMo-7B-Chat` |
| `api_key` | API 密钥 | `sk-xxx` |
| `base_url` | API 地址（OpenAI 兼容） | `https://api.example.com/v1` |

### Embedding 配置

| 变量 | 说明 | 示例 |
|------|------|------|
| `embedding_model` | 向量嵌入模型 | `text-embedding-3-small` |

### TTS 语音合成

| 变量 | 说明 | 示例 |
|------|------|------|
| `tts_model` | TTS 模型名称 | `MiMo-V2.5-TTS-VoiceClone` |
| `tts_api_key` | TTS API 密钥 | `sk-xxx` |
| `tts_base_url` | TTS API 地址 | `https://api.example.com/v1` |

### 数据库配置

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `qdrant_host` | Qdrant 向量数据库地址 | `127.0.0.1` |
| `qdrant_port` | Qdrant 向量数据库端口 | `6333` |
| `postgres_host` | PostgreSQL 连接地址 | `127.0.0.1` |
| `postgres_port` | PostgreSQL 连接端口 | `5432` |
| `postgres_db` | 数据库名称 | `genshin_chat` |
| `postgres_user` | 数据库用户名 | — |
| `postgres_password` | 数据库密码 | — |

### 外部服务

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `searxng_host` | SearXNG 搜索引擎地址 | `127.0.0.1` |
| `searxng_port` | SearXNG 搜索引擎端口 | `8887` |
| `mcp_host` | FastMCP 服务地址 | `127.0.0.1` |
| `mcp_port` | FastMCP 服务端口 | `9000` |

## 项目结构

```
genshinRole/
├── agent/                          # 智能体核心
│   ├── BasicRole.py                # LangGraph ReAct 图实现
│   ├── Paimon.py                   # 派蒙智能管家入口
│   ├── PaimonPrompt.yaml           # 派蒙系统提示词
│   └── run/
│       ├── agent_prompt.yaml       # 角色扮演通用提示词
│       └── role.py                 # 角色扮演入口
│
├── server/                         # FastAPI 服务端
│   ├── main.py                     # 应用入口与路由定义
│   ├── session.py                  # 会话管理
│   ├── factory.py                  # Agent 工厂（加载提示词、组装工具）
│   └── process.py                  # MCP 子进程管理
│
├── memory/                         # 长期记忆系统
│   ├── mem.py                      # mem0 封装
│   ├── config.py                   # mem0 配置组装
│   ├── operation.py                # 数据库读写操作
│   └── pgcon_pool.py               # PostgreSQL 连接池
│
├── search/                         # 混合检索
│   └── hybird_search.py            # BM25 + 向量检索 + RRF 融合
│
├── tool/                           # 工具集
│   ├── role/
│   │   └── role_tool.py            # 角色数据查询工具（7 个）
│   └── xng/
│       ├── xng_server.py           # SearXNG FastMCP 服务
│       └── langgraph_search_tool.py # MCP 客户端封装
│
├── voice/                          # 语音合成模块
│   ├── preprocess.py               # MP3→WAV 转换 + 参考音频截取
│   └── synthesize.py               # MiMo TTS 调用
│
├── data/                           # 数据资源
│   ├── role/
│   │   ├── role_json/              # 角色 JSON 数据（100+ 角色）
│   │   └── sound/                  # 角色语音 MP3 素材
│   ├── world-bg/                   # 世界背景 Markdown
│   └── story/                      # 剧情故事 Markdown
│
├── data_prepare/                   # 数据预处理脚本
│   └── world-bg/
│       ├── ingest_world_bg_to_qdrant.py  # 世界背景入库
│       ├── invest_story_to_qdrant.py     # 故事剧情入库
│       └── role_json.py                  # 角色数据清洗
│
├── spider/                         # 数据爬虫
│   └── fetch_wikitext.py           # wiki 角色数据抓取
│
├── electron/                       # Electron 前端
│   ├── main.js                     # 主进程
│   ├── package.json
│   └── src/
│       ├── App.jsx                 # 根组件
│       ├── components/             # UI 组件
│       ├── hooks/                  # 自定义 Hook
│       └── api/                    # API 封装
│
├── config.py                       # 全局常量配置
├── example.env                     # 环境变量模板
├── requirements.txt                # Python 依赖
└── README.md
```

## 致谢

### 内容创作

所有游戏内容版权归**原神项目组**所有。

### 数据来源

- **世界观与世界背景**
  - 诗漱（B站：诗漱_小他者水母）
  - 日月前事网站：genshinlore.cn
  - 原神 Wiki：wiki.biligame.com/ys
- **角色语音素材**
  - B站阿婆的猪

