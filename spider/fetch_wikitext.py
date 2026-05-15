"""
原神角色 Wikitext 爬虫 —— 从 wiki.biligame.com 拉取角色页面的 wikitext 源码并保存。

模拟浏览器行为：先访问角色页面拿到 Cookie，再带着 Cookie 和 Referer
请求 ?action=raw 接口，绕过 EdgeOne 安全策略。

使用方式：
  python fetch_wikitext.py ./output_folder          # 从默认角色列表拉取
  python fetch_wikitext.py ./output_folder 角色.txt  # 从文件读取角色名列表
"""

import os
import sys
import time
import random
import html
import re
import requests
from pathlib import Path

# ============================================================
# 全局配置
# ============================================================

# 角色名列表（后续由用户提供完整列表，这里先放测试用）
DEFAULT_ROLE_NAMES = [
    # 最新角色（纳塔/月之版本等）
    "尼可", "莉奈娅", "法尔伽", "兹白", "叶洛亚", "哥伦比娅", "杜林",
    "雅珂达", "奈芙尔", "奇偶", "菲林斯", "菈乌玛", "爱诺", "伊涅芙",
    "丝柯克", "塔利雅", "爱可菲", "伊法", "瓦雷莎", "伊安珊",
    "梦见月瑞希", "蓝砚",

    # 纳塔
    "玛薇卡", "茜特菈莉", "恰斯卡", "欧洛伦", "希诺宁", "基尼奇", "玛拉妮", "卡齐娜",

    # 枫丹
    "艾梅莉埃", "希格雯", "克洛琳德", "赛索斯", "阿蕾奇诺", "千织", "闲云", "嘉明",
    "夏沃蕾", "娜维娅", "芙宁娜", "夏洛蒂", "莱欧斯利", "那维莱特", "菲米尼", "林尼", "琳妮特",

    # 须弥
    "绮良良", "白术", "卡维", "米卡", "迪希雅", "艾尔海森", "瑶瑶", "流浪者",
    "珐露珊", "莱依拉", "纳西妲", "妮露", "赛诺", "坎蒂丝", "多莉", "提纳里", "柯莱",

    # 稻妻
    "鹿野院平藏", "久岐忍", "夜兰", "神里绫人", "八重神子", "申鹤", "云堇",
    "荒泷一斗", "五郎", "托马", "珊瑚宫心海", "埃洛伊", "雷电将军", "九条裟罗",
    "宵宫", "早柚", "神里绫华", "枫原万叶", "优菈",

    # 璃月
    "烟绯", "罗莎莉亚", "胡桃", "魈", "甘雨", "阿贝多", "钟离", "辛焱",
    "达达利亚", "迪奥娜", "可莉", "刻晴", "迪卢克", "莫娜", "七七", "砂糖",
    "北斗", "雷泽", "菲谢尔", "丽莎", "凝光", "重云",

    # 蒙德
    "班尼特", "香菱", "安柏", "芭芭拉", "行秋", "诺艾尔", "凯亚", "琴", "温迪",

    # 旅行者（多元素形态，页面单独列出）
    "旅行者",              # 无元素/初始
    "旅行者/风", "旅行者/岩", "旅行者/雷", "旅行者/草", "旅行者/水", "旅行者/火",
]

# BWiki 的基地址
BASE_URL = "https://wiki.biligame.com/ys"

# 基础请求头，模拟 Chrome 浏览器
BASE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

# 请求间隔范围（秒），在此范围内随机取值，模拟人类浏览速度
DELAY_MIN = 3.0
DELAY_MAX = 10.0

# 故事页输入和输出路径
STORY_SRC = Path(__file__).resolve().parents[1] / "data" / "story" / "genshin_story.wikitext"
STORY_DST = Path(__file__).resolve().parents[1] / "data" / "story"


# ============================================================
# 核心逻辑
# ============================================================

def create_session() -> requests.Session:
    """
    创建一个带浏览器伪装头的 Session 对象。
    后续所有请求共用此 Session，自动维护 Cookie。
    """
    session = requests.Session()
    session.headers.update(BASE_HEADERS)
    return session


def visit_page(session: requests.Session, role_name: str) -> str:
    """
    先访问角色详情页面，建立 Cookie 和 Referer 链。
    这一步模拟用户从浏览器打开角色页面的行为。

    返回角色详情页的 URL（供后续请求作为 Referer）。
    """
    page_url = f"{BASE_URL}/{requests.utils.quote(role_name)}"
    session.get(page_url, timeout=15)
    return page_url


def fetch_wikitext(session: requests.Session, role_name: str, referer: str) -> str:
    """
    拉取指定角色的 wikitext 源码。

    带着上一步访问详情页获得的 Cookie 和 Referer 请求 ?action=raw，
    让 EdgeOne 认为这是一个正常的浏览器后续请求。
    """
    raw_url = f"{BASE_URL}/{requests.utils.quote(role_name)}?action=raw"
    headers = {"Referer": referer}
    resp = session.get(raw_url, headers=headers, timeout=15)
    resp.encoding = "utf-8"
    return resp.text


def save_wikitext(content: str, role_name: str, output_dir: str) -> str:
    """
    将 wikitext 内容保存为文件。

    Args:
        content: wikitext 文本内容
        role_name: 角色名，用作文件名
        output_dir: 输出目录路径

    Returns:
        保存的文件完整路径
    """
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)

    # 文件名：角色名.wikitext，替换掉文件名中不允许的字符
    safe_name = role_name.replace("/", "_").replace("\\", "_")
    filepath = os.path.join(output_dir, f"{safe_name}.wikitext")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    return filepath


def load_role_names(filepath: str) -> list[str]:
    """
    从文本文件读取角色名列表（每行一个角色名）。
    跳过空行和以 # 开头的注释行。
    """
    names = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                names.append(line)
    return names


def clean_story(text: str) -> str:
    """清理剧情页里的常见 wiki 标记。"""
    text = html.unescape(text.replace("\r\n", "\n").replace("\r", "\n"))
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"<ref[^>]*>.*?</ref>", "", text, flags=re.S | re.I)
    text = re.sub(r"<ref[^>]*/>", "", text, flags=re.I)
    text = re.sub(r"<sup[^>]*>.*?</sup>", "", text, flags=re.S | re.I)
    text = re.sub(r"\[\[([^|\]]+)\|([^\]]+)\]\]", r"\2", text)
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    text = text.replace("'''", "**").replace("''", "*")
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"__[^_]+__", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    return text.strip()


def story_md() -> str:
    """把提瓦特编年史转成 markdown。"""
    src = STORY_SRC
    dst = STORY_DST
    text = src.read_text(encoding="utf-8")
    title = re.search(r"pageTitle\s*=\s*#(.*?)#", text).group(1)
    lines = text.splitlines()
    out: list[str] = [f"# {title}", ""]
    buf: list[str] = []
    started = False

    def put_buf() -> None:
        nonlocal buf
        if buf:
            out.append("\n".join(buf).strip())
            out.append("")
            buf = []

    for line in lines:
        if not started:
            if re.match(r"^=+", line.strip()):
                started = True
            else:
                continue

        if line.strip() == "== 来源 ==":
            put_buf()
            break

        m = re.match(r"^(=+)\s*(.*?)\s*\1$", line.strip())
        if m:
            put_buf()
            lvl = len(m.group(1))
            head = clean_story(m.group(2))
            if head:
                md_lvl = max(2, lvl - 1)
                out.append(f"{'#' * md_lvl} **{head}**")
                out.append("")
            continue

        raw = line.strip()
        if not raw or raw.startswith("<div") or raw.startswith("</div>") or raw.startswith("<center>") or raw.startswith("</center>") or raw.startswith("__"):
            if raw == "":
                put_buf()
            continue
        if raw.startswith("{{"):
            continue
        if raw.startswith("·"):
            put_buf()
            txt = clean_story(raw.lstrip("·").strip())
            if txt:
                out.append(f"- **{txt}**")
                out.append("")
            continue

        txt = clean_story(line)
        if txt:
            buf.append(txt)

    put_buf()
    md = "\n".join(line for line in out if line is not None).strip() + "\n"
    dst.mkdir(parents=True, exist_ok=True)
    out_path = dst / "genshin_story.md"
    out_path.write_text(md, encoding="utf-8")
    return str(out_path)


def run(role_names: list[str], output_dir: str) -> None:
    """
    主流程：遍历角色名列表，逐个拉取 wikitext 并保存。

    对每个角色：
      1. 先访问角色详情页面，建立 Cookie
      2. 带着 Cookie + Referer 请求 ?action=raw
      3. 保存为 .wikitext 文件

    Args:
        role_names: 角色名列表，如 ["法尔伽", "钟离", "妮可"]
        output_dir: 输出目录路径
    """
    total = len(role_names)
    # 创建 Session，后续所有请求共用（自动维护 Cookie）
    session = create_session()

    print(f"共 {total} 个角色待拉取，输出目录：{output_dir}")
    print(f"请求间隔：{DELAY_MIN}s ~ {DELAY_MAX}s（随机）")

    for i, name in enumerate(role_names, 1):
        # ---- 第一步：访问角色详情页，建立 Cookie 和 Referer 链 ----
        print(f"[{i}/{total}] {name} ...", end=" ", flush=True)
        referer = visit_page(session, name)

        # 短暂停顿，模拟人类浏览行为
        time.sleep(random.uniform(1.0, 2.0))

        # ---- 第二步：带着 Cookie + Referer 拉取 wikitext ----
        wikitext = fetch_wikitext(session, name, referer)

        # 检查是否被拦截（EdgeOne 567 页面不含 {{ 模板标记）
        if "{{" not in wikitext[:500]:
            print(f"[被拦截] 响应不是 wikitext，长度={len(wikitext)}")
            print(f"  响应头: {wikitext[:100]}")
            continue

        # ---- 第三步：保存文件 ----
        saved_path = save_wikitext(wikitext, name, output_dir)
        print(f"[OK] {len(wikitext)} 字符 -> {saved_path}")

        # 随机间隔，避免触发频率限制
        if i < total:
            delay = random.uniform(DELAY_MIN, DELAY_MAX)
            print(f"  等待 {delay:.1f}s ...")
            time.sleep(delay)

    print(f"\n完成！共处理 {total} 个角色。")


# ============================================================
# 入口
# ============================================================

if __name__ == "__main__":
    # 解析命令行参数
    if len(sys.argv) >= 2 and sys.argv[1] == "--story":
        print(story_md())
        sys.exit(0)

    if len(sys.argv) < 2:
        print("用法: python fetch_wikitext.py <输出目录> [角色名列表文件]")
        print("示例: python fetch_wikitext.py ./wikitext")
        print("示例: python fetch_wikitext.py ./wikitext roles.txt")
        print("示例: python fetch_wikitext.py --story")
        sys.exit(1)

    output_dir = sys.argv[1]

    if len(sys.argv) >= 3:
        # 从文件读取角色名列表
        role_names = load_role_names(sys.argv[2])
    else:
        # 使用默认列表（后续替换为完整列表）
        role_names = DEFAULT_ROLE_NAMES

    run(role_names, output_dir)
