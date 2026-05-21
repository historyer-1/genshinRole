import threading
from tool.xng import xng_server


def run_mcp(host: str, port: int) -> None:
    """
    启动 xng FastMCP 服务。

    Args:
        host: FastMCP 监听地址。
        port: FastMCP 监听端口。
    """
    # 启动 fastmcp 服务
    xng_server.mcp.run(transport="sse", host=host, port=port)


def start_mcp(host: str = "127.0.0.1", port: int = 9000) -> threading.Thread:
    """
    在独立线程启动 xng FastMCP 服务。

    Args:
        host: FastMCP 监听地址。
        port: FastMCP 监听端口。
    """
    # 独立线程启动 fastmcp
    thread = threading.Thread(target=run_mcp, args=(host, port), daemon=True)
    thread.start()
    return thread



def main() -> None:
    """
    统一启动入口。

    Args:
        无。
    """
    # 先启动 fastmcp 服务
    start_mcp()
    from agent.Paimon import start_paimon
    from agent.run.role import start_role

    choice = input("选择 1=派蒙，2=角色：").strip()
    if choice == "1":
        start_paimon()
    else:
        role_name = input("输入角色名：").strip()
        start_role(role_name)


if __name__ == "__main__":
    main()