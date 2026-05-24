"""
项目全局配置常量。

所有模块应从本文件导入配置，避免硬编码分散在各处。
环境变量相关配置（如 API 密钥、数据库地址）仍从 .env 加载。
"""

from pathlib import Path

# ── BM25 关键词检索 ──
# 每个集合最多拉取多少条文档做 BM25 计算
BM25_SCAN_LIMIT_PER_COLLECTION = 3000

# ── 混合检索 ──
# 最终返回给上下文注入阶段的片段数量上限
HYBRID_SEARCH_TOP_K = 8
# BM25 关键词检索阶段保留的候选数量上限
BM25_TOP_K = 20
# 向量检索阶段保留的候选数量上限
VECTOR_TOP_K = 20
# RRF 融合中的平滑常数
RRF_K = 60

# ── 上下文预算 ──
# 检索结果注入 LLM 的总 token 预算
CONTEXT_TOTAL_BUDGET = 2800
# 单个片段最小 token 数
CONTEXT_MIN_CHUNK_SIZE = 220
# 单个片段最大 token 数
CONTEXT_MAX_CHUNK_SIZE = 900
# 剩余预算低于此值时停止追加
CONTEXT_MIN_REMAINING = 180

# ── 长期记忆 (mem0) ──
# 每次检索最多返回几条记忆
MEMORY_TOP_K = 4

# ── 对话历史 ──
# 保留的近期对话轮数，超过后会触发历史压缩
MEMORY_ROUNDS = 7
# 新建会话时从数据库加载的最近消息条数
HISTORY_LOAD_COUNT = 5

# ── 联网搜索 ──
# 搜索结果最大条数
SEARCH_MAX_RESULTS = 10

# ── 会话管理 ──
# 会话过期时间（秒）
SESSION_TTL_SECONDS = 3600
# 会话清理检查间隔（秒）
SESSION_CLEANUP_INTERVAL = 60

# ── PostgreSQL 连接池 ──
PG_POOL_MIN_SIZE = 2
PG_POOL_MAX_SIZE = 10
PG_POOL_MAX_IDLE = 300

# ── RAG 向量集合 ──
# 默认用于角色扮演的向量知识库集合
RAG_COLLECTIONS = ["genshin_world_bg", "genshin_story"]

# ── 语音合成 (MiMo TTS VoiceClone) ──
# 角色语音素材根目录（含各角色 MP3 文件）
SOUND_DIR = Path(__file__).resolve().parent / "data" / "role" / "sound"
# 语音风格提示词模板，{role_name} 会在调用时替换为角色名
TTS_STYLE_PROMPT = "我给你上传了原神角色「{role_name}」的声音素材，请你根据素材模仿「{role_name}」的语气和说话风格，语气自然。"
# TTS API 超时（秒）
TTS_TIMEOUT = 120
# 单次合成最大文本长度（字符），超过则分段
TTS_MAX_TEXT_LENGTH = 500
# 参考音频截取时长（秒）
TTS_REF_DURATION = 60
