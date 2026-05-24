"""python -m server 入口：设置 Windows 事件循环策略后启动 uvicorn。"""
import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import uvicorn

uvicorn.run("server.main:app", host="127.0.0.1", port=8000)
