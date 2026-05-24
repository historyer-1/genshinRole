import os
import sys

from dotenv import find_dotenv, load_dotenv
from fastmcp import FastMCP
import requests

from config import SEARCH_MAX_RESULTS

# 加载项目根目录 .env，用于读取联网搜索地址
load_dotenv(find_dotenv(), override=True)

mcp = FastMCP("searxng")


@mcp.tool()
def search(query: str) -> str:
    """
    当本地知识或普通工具信息不足时，使用联网搜索补充信息。

    Args:
        query: 需要搜索的关键词或问题。
    """
    # 联网搜索日志输出到 stderr，避免与回答内容混在一起
    print(f"[联网搜索] {query}", file=sys.stderr, flush=True)
    # 从 .env 读取 SearXNG 配置
    searxng_host = os.getenv("searxng_host")
    searxng_port = os.getenv("searxng_port")
    if not searxng_host or not searxng_port:
        print("[联网搜索] searxng_host 或 searxng_port 未配置", file=sys.stderr, flush=True)
        return "联网搜索不可用：SearXNG 配置缺失，请不要调用此工具。"
    base_url = f"http://{searxng_host}:{searxng_port}"
    try:
        response = requests.get(
            f"{base_url.rstrip('/')}/search",
            params={"q": query, "format": "json"},
            timeout=25,
            proxies={"http": None, "https": None},
        )
        response.raise_for_status()
        data = response.json().get("results",[])[:SEARCH_MAX_RESULTS]
    except requests.Timeout:
        print(f"[联网搜索] 超时，跳过本次搜索：{query}", file=sys.stderr, flush=True)
        return "联网搜索超时，请稍后重试或换一种方式提问。"
    except requests.ConnectionError:
        print(f"[联网搜索] 连接失败，SearXNG 服务可能未启动：{base_url}", file=sys.stderr, flush=True)
        return "联网搜索不可用：无法连接搜索服务。"
    except requests.RequestException as err:
        print(f"[联网搜索] 请求异常：{type(err).__name__}: {err}", file=sys.stderr, flush=True)
        return f"联网搜索请求失败：{type(err).__name__}。"
    except Exception as err:
        print(f"[联网搜索] 未知异常：{type(err).__name__}: {err}", file=sys.stderr, flush=True)
        return "联网搜索发生内部错误。"

    # 拼接标题、链接与摘要，便于模型引用与复述
    result_list = []
    for item in data:
        title = str(item["title"])
        url = str(item["url"])
        content = str(item["content"])
        result_list.append(f"{title}\n{url}\n{content}")
    return "\n\n".join(result_list)


if __name__ == "__main__":
    mcp_host = os.getenv("mcp_host", "127.0.0.1")
    mcp_port = int(os.getenv("mcp_port", "9000"))
    mcp.run(transport="sse", host=mcp_host, port=mcp_port)