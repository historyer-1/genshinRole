import multiprocessing
import os

from dotenv import load_dotenv
from tool.xng import xng_server

load_dotenv()


def run_mcp(host: str, port: int) -> None:
    """
    启动 xng FastMCP 服务。

    Args:
        host: FastMCP 监听地址。
        port: FastMCP 监听端口。
    """
    xng_server.mcp.run(transport="sse", host=host, port=port)


def start_mcp() -> multiprocessing.Process:
    """
    在独立进程启动 xng FastMCP 服务。
    """
    host = os.getenv("mcp_host", "127.0.0.1")
    port = int(os.getenv("mcp_port", "9000"))
    ctx = multiprocessing.get_context("spawn")
    process = ctx.Process(target=run_mcp, args=(host, port), daemon=True)
    process.start()
    return process


def stop_mcp(process: multiprocessing.Process | None) -> None:
    """
    停止 MCP 子进程。

    Args:
        process: start_mcp 返回的进程对象。
    """
    if process is None:
        return
    if process.is_alive():
        process.terminate()
        process.join(timeout=3)
        if process.is_alive() and hasattr(process, "kill"):
            process.kill()
            process.join(timeout=3)
