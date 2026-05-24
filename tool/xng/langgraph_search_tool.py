from __future__ import annotations

import asyncio
import os
from urllib.parse import urlparse, urlunparse

from dotenv import find_dotenv, load_dotenv
import httpx
from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient


# 加载项目根目录 .env，用于读取 MCP 服务地址
load_dotenv(find_dotenv(), override=True)


def _normalize_url(mcp_url: str = "") -> str:
    """
    读取并标准化 xng MCP 地址。

    Args:
        mcp_url: xng MCP SSE 地址；为空时从 .env 读取 mcp_host 和 mcp_port。
    """
    if len(mcp_url.strip()) > 0:
        url = mcp_url.strip()
    else:
        host = os.getenv("mcp_host")
        port = os.getenv("mcp_port")
        if not host or not port:
            raise ValueError("mcp_host 或 mcp_port 未配置，请在 .env 中设置")
        url = f"http://{host}:{port}"

    if not (url.startswith("http://") or url.startswith("https://")):
        url = f"http://{url}"

    parsed = urlparse(url)
    if parsed.path in ("", "/"):
        url = urlunparse(parsed._replace(path="/sse"))
    return url


async def create_xng_tools_async(mcp_url: str = "") -> tuple[MultiServerMCPClient, list[BaseTool]]:
    """
    创建新的 MCP 客户端连接并获取工具列表。调用方负责保持客户端存活。

    Args:
        mcp_url: xng MCP SSE 地址；为空时从 .env 读取 mcp_host 和 mcp_port。

    Returns:
        (client, tools) 元组，client 需保持引用以维持连接。
    """
    url = _normalize_url(mcp_url)
    client = MultiServerMCPClient(
        {
            "xng": {
                "transport": "sse",
                "url": url,
            }
        }
    )
    try:
        tools = await client.get_tools(server_name="xng")
    except* httpx.UnsupportedProtocol as exc:
        raise ConnectionError(
            f"MCP 地址协议不正确，请使用 http:// 或 https:// 前缀，当前值：{url}"
        ) from exc
    except* httpx.ConnectError as exc:
        raise ConnectionError(
            f"无法连接 xng MCP 服务（{url}），请先启动：python -m tool.xng.xng_server"
        ) from exc
    except* httpx.HTTPError as exc:
        raise ConnectionError(f"xng MCP 服务请求失败（{url}）：{exc}") from exc

    return client, tools


def get_xng_tools(mcp_url: str = "") -> list[BaseTool]:
    """
    同步获取 xng_server 暴露的搜索工具列表（供遗留同步调用使用）。

    Args:
        mcp_url: xng MCP SSE 地址；为空时从 .env 读取 mcp_host 和 mcp_port。
    """
    async def _fetch():
        _, tools = await create_xng_tools_async(mcp_url)
        return tools
    return asyncio.run(_fetch())
