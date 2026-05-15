from __future__ import annotations

import os
import re
import uuid
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams


# 当前脚本位于 data_prepare\world-bg\ 目录下，向上两级就是项目根目录
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# 剧情 Markdown 源文件
SOURCE_FILE = PROJECT_ROOT / "data" / "story" / "genshin_story.md"

# .env 配置文件
ENV_PATH = PROJECT_ROOT / ".env"

# Qdrant 集合名
COLLECTION_NAME = "genshin_story"

# 目标长度、最大长度、重叠长度
TARGET_CHARS = 900
MAX_CHARS = 1200
OVERLAP_CHARS = 120

# 向量维度
EMBEDDING_DIM = 1024

# Embedding 批大小
BATCH_SIZE = 10

# Qdrant 写入批大小
UPSERT_BATCH_SIZE = 128


def parse_md(md_text: str) -> list[dict]:
    """按标题切分 Markdown，并保留层级路径。"""
    lines = md_text.splitlines()
    sections: list[dict] = []
    head_map: dict[int, str] = {}
    cur: dict | None = None

    for line_no, line in enumerate(lines, start=1):
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            if cur is not None:
                cur["line_end"] = line_no - 1
                sections.append(cur)

            lvl = len(m.group(1))
            title = m.group(2).strip()
            head_map[lvl] = title
            for k in list(head_map.keys()):
                if k > lvl:
                    del head_map[k]

            cur = {
                "heading_path": [head_map[k] for k in sorted(head_map.keys())],
                "line_start": line_no,
                "content_lines": [line],
            }
            continue

        if cur is None:
            cur = {
                "heading_path": [SOURCE_FILE.stem],
                "line_start": 1,
                "content_lines": [],
            }
        cur["content_lines"].append(line)

    if cur is not None:
        cur["line_end"] = len(lines)
        sections.append(cur)

    return sections


def split_para(section_text: str) -> list[str]:
    """按空行拆段。"""
    paras: list[str] = []
    buf: list[str] = []
    for line in section_text.splitlines():
        if line.strip() == "":
            if buf:
                paras.append("\n".join(buf).strip())
                buf = []
            continue
        buf.append(line.rstrip())
    if buf:
        paras.append("\n".join(buf).strip())
    return paras


def split_long(para: str, max_chars: int) -> list[str]:
    """长段落按句末标点继续拆。"""
    if len(para) <= max_chars:
        return [para]

    parts = re.split(r"(?<=[。！？；!?;])", para)
    parts = [p.strip() for p in parts if p.strip()]

    chunks: list[str] = []
    cur = ""
    for part in parts:
        add_len = len(part) + (1 if cur else 0)
        if len(cur) + add_len <= max_chars:
            cur = f"{cur} {part}".strip()
        else:
            if cur:
                chunks.append(cur)
            cur = part
    if cur:
        chunks.append(cur)

    out: list[str] = []
    for chunk in chunks:
        if len(chunk) <= max_chars:
            out.append(chunk)
        else:
            for start in range(0, len(chunk), max_chars):
                out.append(chunk[start : start + max_chars])
    return out


def chunk_text(paragraphs: list[str], target_chars: int, max_chars: int, overlap_chars: int) -> list[str]:
    """段落级滑动切分。"""
    paras: list[str] = []
    for para in paragraphs:
        paras.extend(split_long(para, max_chars=max_chars))

    chunks: list[str] = []
    start = 0
    while start < len(paras):
        cur_len = 0
        end = start

        while end < len(paras):
            cand = paras[end]
            add_len = len(cand) + (2 if cur_len > 0 else 0)
            if cur_len + add_len > max_chars:
                break
            cur_len += add_len
            end += 1
            if cur_len >= target_chars:
                break

        if end == start:
            end = start + 1

        chunks.append("\n\n".join(paras[start:end]).strip())

        if end >= len(paras):
            break

        back_len = 0
        next_start = end
        while next_start > start and back_len < overlap_chars:
            next_start -= 1
            back_len += len(paras[next_start]) + 2

        if next_start <= start:
            next_start = end - 1
        if next_start <= start:
            next_start = end

        start = next_start

    return chunks


def build_chunks(md_path: Path) -> list[dict]:
    """把剧情 Markdown 变成可向量化的 chunk。"""
    md_text = md_path.read_text(encoding="utf-8")
    sections = parse_md(md_text)

    all_chunks: list[dict] = []
    for sec_idx, sec in enumerate(sections, start=1):
        sec_text = "\n".join(sec["content_lines"]).strip()
        if not sec_text:
            continue

        paras = split_para(sec_text)
        if not paras:
            continue

        sec_chunks = chunk_text(
            paragraphs=paras,
            target_chars=TARGET_CHARS,
            max_chars=MAX_CHARS,
            overlap_chars=OVERLAP_CHARS,
        )

        heading_path_list = sec["heading_path"]
        heading_path = " > ".join(heading_path_list)
        for chunk_idx, chunk_text_item in enumerate(sec_chunks, start=1):
            seed = f"{md_path.name}|{sec_idx}|{chunk_idx}"
            all_chunks.append(
                {
                    "point_id": str(uuid.uuid5(uuid.NAMESPACE_URL, seed)),
                    "source_file": md_path.name,
                    "heading_path": heading_path,
                    "h1": heading_path_list[0] if len(heading_path_list) > 0 else "",
                    "h2": heading_path_list[1] if len(heading_path_list) > 1 else "",
                    "h3": heading_path_list[2] if len(heading_path_list) > 2 else "",
                    "line_start": sec["line_start"],
                    "line_end": sec["line_end"],
                    "section_index": sec_idx,
                    "chunk_index_in_section": chunk_idx,
                    "text": chunk_text_item,
                }
            )

    return all_chunks


def get_qdrant() -> QdrantClient:
    """从 .env 读取 Qdrant 连接信息。"""
    qdrant_url = os.getenv("qdrant_url")
    host, port = qdrant_url.split(":", 1)
    return QdrantClient(host=host, port=int(port))


def embed_chunks(client: OpenAI, model: str, chunks: list[dict]) -> list[list[float]]:
    """批量向量化文本。"""
    vectors: list[list[float]] = []
    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i : i + BATCH_SIZE]
        resp = client.embeddings.create(
            model=model,
            input=[item["text"] for item in batch],
            dimensions=EMBEDDING_DIM,
        )
        vectors.extend([item.embedding for item in resp.data])
    return vectors


def write_qdrant(chunks: list[dict], vectors: list[list[float]]) -> None:
    """写入 Qdrant 并重建集合。"""
    qdrant = get_qdrant()

    if qdrant.collection_exists(collection_name=COLLECTION_NAME):
        qdrant.delete_collection(collection_name=COLLECTION_NAME)

    qdrant.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
    )

    points: list[PointStruct] = []
    for chunk, vector in zip(chunks, vectors):
        payload = {
            "source_file": chunk["source_file"],
            "heading_path": chunk["heading_path"],
            "h1": chunk["h1"],
            "h2": chunk["h2"],
            "h3": chunk["h3"],
            "line_start": chunk["line_start"],
            "line_end": chunk["line_end"],
            "section_index": chunk["section_index"],
            "chunk_index_in_section": chunk["chunk_index_in_section"],
            "text": chunk["text"],
        }
        points.append(PointStruct(id=chunk["point_id"], vector=vector, payload=payload))

    for i in range(0, len(points), UPSERT_BATCH_SIZE):
        qdrant.upsert(
            collection_name=COLLECTION_NAME,
            points=points[i : i + UPSERT_BATCH_SIZE],
            wait=True,
        )


def main() -> None:
    """主流程。"""
    load_dotenv(dotenv_path=ENV_PATH, override=True)

    md_path = SOURCE_FILE
    chunks = build_chunks(md_path)

    client = OpenAI(
        api_key=os.getenv("api_key"),
        base_url=os.getenv("base_url"),
    )
    model = os.getenv("embedding_model")

    vectors = embed_chunks(client=client, model=model, chunks=chunks)
    write_qdrant(chunks=chunks, vectors=vectors)

    print(f"完成：{md_path.name}，切分 {len(chunks)} 个 chunks，已写入 {COLLECTION_NAME}。")


if __name__ == "__main__":
    main()