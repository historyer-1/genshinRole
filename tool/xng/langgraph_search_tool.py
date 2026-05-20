from pathlib import Path
import asyncio
import os
from urllib.parse import urlparse, urlunparse

from dotenv import load_dotenv
import httpx
from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient


# 加载项目根目录 .env，用于读取 MCP 服务地址
ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=False)


def get_xng_tools(mcp_url: str = "") -> list[BaseTool]:
    """
    通过 MCP 客户端获取 xng_server 暴露的搜索工具列表。

    Args:
        mcp_url: xng MCP SSE 地址；为空时从 .env 的 xng_mcp_url 读取。
    """
    # 优先使用参数传入的地址，否则使用 .env 配置
    url = mcp_url.strip() if len(mcp_url) > 0 else str(os.getenv("xng_mcp_url", "")).strip()
    if len(url) == 0:
        raise ValueError("xng_mcp_url 未配置，请在 .env 中设置如 http://127.0.0.1:9000/sse")
    if not (url.startswith("http://") or url.startswith("https://")):
        url = f"http://{url}"

    # 未指定路径时默认补上 FastMCP 的 SSE 入口，避免访问根路径导致 404
    parsed = urlparse(url)
    if parsed.path in ("", "/"):
        url = urlunparse(parsed._replace(path="/sse"))

    # 连接 MCP Server 并拉取可供 LangGraph 使用的工具对象
    client = MultiServerMCPClient(
        {
            "xng": {
                "transport": "sse",
                "url": url,
            }
        }
    )
    try:
        return asyncio.run(client.get_tools(server_name="xng"))
    except* httpx.UnsupportedProtocol as exc:
        raise ConnectionError(
            f"xng_mcp_url 协议不正确，请使用 http:// 或 https:// 前缀，当前值：{url}"
        ) from exc
    except* httpx.ConnectError as exc:
        raise ConnectionError(
            f"无法连接 xng MCP 服务（{url}），请先启动：python -m tool.xng.xng_server"
        ) from exc
    except* httpx.HTTPError as exc:
        raise ConnectionError(f"xng MCP 服务请求失败（{url}）：{exc}") from exc
