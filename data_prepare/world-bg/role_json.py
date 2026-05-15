from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path


# 当前脚本所在目录向上两级就是项目根目录
ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "data" / "role"
DST = SRC / "role_json"


def split_pipe(text: str) -> list[str]:
    """按顶层竖线拆分模板内容。"""
    parts: list[str] = []
    buf: list[str] = []
    tpl = 0
    link = 0
    i = 0
    while i < len(text):
        pair = text[i : i + 2]
        if pair == "{{":
            tpl += 1
            buf.append(pair)
            i += 2
            continue
        if pair == "}}":
            tpl -= 1
            buf.append(pair)
            i += 2
            continue
        if pair == "[[":
            link += 1
            buf.append(pair)
            i += 2
            continue
        if pair == "]]":
            link -= 1
            buf.append(pair)
            i += 2
            continue
        if text[i] == "|" and tpl == 0 and link == 0:
            parts.append("".join(buf))
            buf = []
            i += 1
            continue
        buf.append(text[i])
        i += 1
    parts.append("".join(buf))
    return parts


def tpl_to(text: str) -> str:
    """把简单模板压成更易读的文本。"""
    parts = [p.strip() for p in split_pipe(text)]
    name = parts[0] if parts else ""
    if not name:
        return ""
    if name in {"颜色", "黑幕"}:
        return parts[-1] if len(parts) > 1 else ""
    if name == "图标":
        if len(parts) >= 4:
            return f"{parts[-2]}{parts[-1]}"
        return parts[-1] if len(parts) > 1 else ""
    if len(parts) > 1:
        return "|".join(parts[1:])
    return name


def fix_txt(text: str) -> str:
    """清理常见 wiki 标记。"""
    text = html.unescape(text.replace("\r\n", "\n").replace("\r", "\n"))
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"\{\{([^{}]+)\}\}", lambda m: tpl_to(m.group(1)), text)
    text = re.sub(r"\[\[([^|\]]+)\|([^\]]+)\]\]", r"\2", text)
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    text = text.replace("'''", "").replace("''", "")
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"<ref[^>]*?/?>.*?</ref>", "", text, flags=re.S | re.I)
    text = re.sub(r"<ref[^>]*/>", "", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"__[^_]+__", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    return text.strip()


def key_val(text: str) -> dict[str, str]:
    """把模板参数拆成键值对。"""
    data: dict[str, str] = {}
    for part in split_pipe(text)[1:]:
        part = part.strip()
        if not part:
            continue
        if "=" in part:
            key, val = part.split("=", 1)
            data[fix_txt(key)] = fix_txt(val)
    return data


def is_head(line: str) -> re.Match[str] | None:
    """识别标题行。"""
    return re.match(r"^(=+)\s*(.*?)\s*\1$", line.strip())


def blk(lines: list[str]) -> dict[str, str] | None:
    """把普通文本块清洗成段落。"""
    text = fix_txt("\n".join(lines))
    if not text:
        return None
    return {"type": "text", "text": text}


def tpl_blk(lines: list[str]) -> dict[str, object]:
    """把模板块解析成结构化 JSON。"""
    raw = "".join(lines).strip()
    body = raw[2:-2].strip()
    parts = split_pipe(body)
    name = fix_txt(parts[0].strip())
    args = [fix_txt(p) for p in parts[1:] if p.strip() and "=" not in p]
    data = key_val(body)
    return {"type": "template", "name": name, "args": args, "data": data, "text": fix_txt(body)}


def skip_tpl(name: str, args: list[str]) -> bool:
    """过滤技能段里的流程模板。"""
    if name != "角色技能" or not args:
        return False
    first = args[0]
    return first in {"开始", "结束"} or (first.startswith("内容") and (first.endswith("开始") or first.endswith("结束")))


def parse(txt: str, src: str) -> dict[str, object]:
    """把单个 wikitext 文件拆成顺序块。"""
    txt = re.sub(r"<!--.*?-->", "", txt, flags=re.S)
    blocks: list[dict[str, object]] = []
    buf: list[str] = []
    tpl_lines: list[str] = []
    in_tpl = False
    dep = 0

    def put_txt() -> None:
        nonlocal buf
        if buf:
            block = blk(buf)
            if block is not None:
                blocks.append(block)
            buf = []

    for line in txt.splitlines():
        head = is_head(line)
        if not in_tpl and head:
            put_txt()
            blocks.append({"type": "heading", "level": len(head.group(1)), "text": fix_txt(head.group(2))})
            continue

        line_txt: list[str] = []
        j = 0
        while j < len(line):
            if not in_tpl and line.startswith("{{", j):
                buf.append("".join(line_txt))
                line_txt = []
                put_txt()
                in_tpl = True
                tpl_lines = ["{{"]
                dep = 1
                j += 2
                continue

            if in_tpl:
                pair = line[j : j + 2]
                if pair == "{{":
                    dep += 1
                    tpl_lines.append("{{")
                    j += 2
                    continue
                if pair == "}}":
                    dep -= 1
                    tpl_lines.append("}}")
                    j += 2
                    if dep == 0:
                        block = tpl_blk(tpl_lines)
                        if not skip_tpl(str(block["name"]), list(block["args"])):
                            blocks.append(block)
                        in_tpl = False
                    continue
                tpl_lines.append(line[j])
                j += 1
                continue

            line_txt.append(line[j])
            j += 1

        if not in_tpl:
            buf.append("".join(line_txt))
            if line == "":
                buf.append("")
        elif line_txt:
            buf.append("".join(line_txt))

        if in_tpl:
            tpl_lines.append("\n")

    put_txt()

    return {"source_file": src, "blocks": blocks}


def one(src: Path, dst: Path) -> Path:
    """清洗单个角色文件。"""
    txt = src.read_text(encoding="utf-8")
    data = parse(txt, src.name)
    dst.parent.mkdir(parents=True, exist_ok=True)
    out = dst / f"{src.stem}.json"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def run(src_dir: Path, dst_dir: Path, pick: Path | None = None) -> None:
    """批量清洗或只清洗单个文件。"""
    if pick is not None:
        out = one(pick, dst_dir)
        print(out)
        return
    for src in sorted(src_dir.glob("*.wikitext")):
        one(src, dst_dir)


if __name__ == "__main__":
    if len(sys.argv) == 2:
        p = Path(sys.argv[1])
        if p.exists():
            run(SRC, DST, p)
        else:
            run(SRC, DST, SRC / f"{sys.argv[1]}.wikitext")
    else:
        run(SRC, DST)
