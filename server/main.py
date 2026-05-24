import asyncio
import base64
import json
import sys
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from config import HISTORY_LOAD_COUNT
from memory.operation import load_recent_chats
from memory.pgcon_pool import close_pool, init_pool
from server.factory import create_agent, list_roles
from server.process import start_mcp, stop_mcp
from server.session import Session, SessionStore
from voice.synthesize import has_voice, init_voice_map, synthesize_voice

load_dotenv()

session_store = SessionStore()
mcp_process = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI 生命周期：启动连接池、MCP 子进程和会话清理任务。"""
    global mcp_process
    await init_pool()
    mcp_process = start_mcp()
    init_voice_map()
    cleanup_task = asyncio.create_task(session_store.cleanup_loop())
    yield
    cleanup_task.cancel()
    session_store.shutdown()
    stop_mcp(mcp_process)
    await close_pool()


app = FastAPI(title="Genshin Role Agent", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── 请求模型 ──

class CreateSessionRequest(BaseModel):
    user_id: str
    role_name: str


class ChatRequest(BaseModel):
    message: str
    voice: bool = False


# ── 内部工具 ──

async def _get_or_create_session(user_id: str, role_name: str) -> Session:
    """获取已有会话，不存在则自动创建。新建时从数据库加载最近 HISTORY_LOAD_COUNT 条消息作为历史。"""
    session = session_store.get(user_id, role_name)
    if session is None:
        agent = await create_agent(role_name, user_id)
        session = Session(user_id=user_id, role_name=role_name, agent=agent)
        # 从数据库加载最近的聊天记录作为会话初始历史
        storage_uid = agent.user_id
        session.history = await load_recent_chats(storage_uid, limit=HISTORY_LOAD_COUNT * 2)
        session_store.put(session)
    return session


# ── 端点 ──

@app.get("/health")
async def health():
    """健康检查，返回服务运行状态。"""
    return {"status": "ok"}


@app.get("/api/roles")
async def get_roles():
    """获取所有可用角色列表。"""
    return {"roles": list_roles()}


@app.post("/api/sessions")
async def create_session(req: CreateSessionRequest):
    """
    创建或获取会话。

    若用户与角色的会话已存在则直接返回，否则新建会话并从数据库加载历史记录。

    请求体:
        user_id: 用户唯一标识。
        role_name: 角色名称（如 "派蒙"）。
    """
    session = await _get_or_create_session(req.user_id, req.role_name)
    return {"user_id": session.user_id, "role_name": session.role_name, "display_name": session.agent.role}


@app.post("/api/sessions/{user_id}/{role_name}/chat")
async def chat(user_id: str, role_name: str, body: ChatRequest):
    """
    发送消息并以 SSE 流式接收回复。

    同一用户同一角色的会话同一时刻只能处理一条消息，若上一条未处理完毕返回 409。

    路径参数:
        user_id: 用户唯一标识。
        role_name: 角色名称。

    请求体:
        message: 用户发送的消息内容。
    """
    session = await _get_or_create_session(user_id, role_name)

    if session.lock.locked():
        raise HTTPException(409, "上一条消息尚未处理完毕")

    async def event_generator():
        try:
            async with session.lock:
                async for event in session.agent.chat_stream(body.message, session.history):
                    if event["type"] == "token":
                        yield {
                            "event": "token",
                            "data": json.dumps({"content": event["content"]}, ensure_ascii=False),
                        }
                    elif event["type"] == "done":
                        session.history.append({"role": "user", "content": body.message})
                        session.history.append({"role": "assistant", "content": event["content"]})
                        yield {
                            "event": "done",
                            "data": json.dumps({"content": event["content"]}, ensure_ascii=False),
                        }
                        # 语音合成（派蒙排除）
                        if body.voice and role_name != "派蒙" and has_voice(session.agent.role):
                            print(f"[voice] voice={body.voice}, role={role_name}, agent_role={session.agent.role}, has_voice={has_voice(session.agent.role)}", file=sys.stderr)
                            try:
                                wav_bytes = await synthesize_voice(event["content"], session.agent.role)
                                audio_b64 = base64.b64encode(wav_bytes).decode()
                                print(f"[voice] 合成成功, 音频大小={len(wav_bytes)}, base64长度={len(audio_b64)}", file=sys.stderr)
                                yield {
                                    "event": "audio",
                                    "data": json.dumps(
                                        {"audio": audio_b64, "format": "wav"},
                                        ensure_ascii=False,
                                    ),
                                }
                            except Exception as voice_err:
                                import traceback
                                traceback.print_exc()
                                yield {
                                    "event": "voice_error",
                                    "data": json.dumps({"detail": str(voice_err)}, ensure_ascii=False),
                                }
        except Exception as e:
            import traceback
            traceback.print_exc()
            yield {
                "event": "error",
                "data": json.dumps({"detail": str(e)}, ensure_ascii=False),
            }

    return EventSourceResponse(event_generator())


@app.get("/api/sessions/{user_id}/{role_name}/history")
async def get_history(user_id: str, role_name: str):
    """
    获取当前会话的内存中的对话历史（最近几轮）。

    路径参数:
        user_id: 用户唯一标识。
        role_name: 角色名称。
    """
    session = session_store.get(user_id, role_name)
    if session is None:
        raise HTTPException(404, "会话不存在")
    return {"history": session.history}


@app.get("/api/sessions/{user_id}/{role_name}/history/batch")
async def get_batch_history(
    user_id: str,
    role_name: str,
    limit: int = Query(default=HISTORY_LOAD_COUNT * 2, ge=1, le=100, description="返回的消息条数"),
    offset: int = Query(default=0, ge=0, description="跳过的消息条数，用于向前翻页"),
):
    """
    分页获取数据库中的历史对话记录，按时间正序返回。

    适用于前端展示历史会话：首次加载 offset=0 取最近 limit 条，
    用户上拉加载更多时增大 offset 继续向前取。

    路径参数:
        user_id: 用户唯一标识。
        role_name: 角色名称。

    查询参数:
        limit: 返回的最大消息条数，默认为 HISTORY_LOAD_COUNT * 2（即 5 轮对话 = 10 条消息）。
        offset: 跳过的消息条数，默认为 0（从最新的消息开始）。
    """
    session = session_store.get(user_id, role_name)
    if session is None:
        raise HTTPException(404, "会话不存在")
    storage_uid = session.agent.user_id
    history = await load_recent_chats(storage_uid, limit=limit, offset=offset)
    return {"history": history, "limit": limit, "offset": offset}


@app.delete("/api/sessions/{user_id}/{role_name}")
async def delete_session(user_id: str, role_name: str):
    """
    销毁指定会话，释放 Agent 和 MCP 连接资源。

    路径参数:
        user_id: 用户唯一标识。
        role_name: 角色名称。
    """
    session_store.remove(user_id, role_name)
    return {"status": "ok"}


@app.get("/api/sessions/{user_id}")
async def list_user_sessions(user_id: str):
    """
    列出指定用户的所有活跃会话。

    路径参数:
        user_id: 用户唯一标识。
    """
    sessions = session_store.list_user_sessions(user_id)
    return {
        "sessions": [
            {"role_name": s.role_name, "display_name": s.agent.role}
            for s in sessions
        ]
    }
