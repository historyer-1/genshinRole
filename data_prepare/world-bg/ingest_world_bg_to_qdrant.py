from __future__ import annotations

import os
import re
import uuid
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams


# =========================
# 全局配置（按本项目目录结构固定）
# =========================

# 当前脚本位于 data_prepare\world-bg\ 目录下，向上两级就是项目根目录
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# 原始 Markdown 文档目录
SOURCE_DIR = PROJECT_ROOT / "md" / "world-bg"

# 使用项目根目录下的 .env
ENV_PATH = PROJECT_ROOT / ".env"

# Qdrant 集合名
COLLECTION_NAME = "genshin_world_bg"


# - 目标长度：约 900 中文字符
# - 最大长度：约 1200 中文字符
# - 相邻块重叠：约 120 字符
TARGET_CHARS = 900
MAX_CHARS = 1200
OVERLAP_CHARS = 120

# 指定向量维度
EMBEDDING_DIM = 1024

# Embedding 批大小（一次请求多条文本，减少请求次数）
BATCH_SIZE = 10

# Qdrant 写入批大小
UPSERT_BATCH_SIZE = 128


def parse_markdown_sections(markdown_text: str, file_stem: str) -> list[dict]:
    """
    按 Markdown 标题切分为“章节段”：
    1. 以 # / ## / ### ... 作为分段边界；
    2. 维护标题栈，生成完整 heading_path；
    3. 记录行号范围，便于后续追溯来源。
    """
    lines = markdown_text.splitlines()
    sections: list[dict] = []
    heading_stack: dict[int, str] = {}
    current_section: dict | None = None

    for line_no, line in enumerate(lines, start=1):
        heading_match = re.match(r"^(#{1,6})\s+(.*)$", line)

        if heading_match:
            # 遇到新标题时，先收尾上一个 section
            if current_section is not None:
                current_section["line_end"] = line_no - 1
                sections.append(current_section)

            level = len(heading_match.group(1))
            title = heading_match.group(2).strip()

            # 更新当前层级标题
            heading_stack[level] = title

            # 删除更深层旧标题，保证路径准确
            for deep_level in list(heading_stack.keys()):
                if deep_level > level:
                    del heading_stack[deep_level]

            heading_path = [heading_stack[k] for k in sorted(heading_stack.keys())]

            # 新 section 从当前标题行开始
            current_section = {
                "heading_path": heading_path,
                "line_start": line_no,
                "content_lines": [line],
            }
        else:
            # 文件开头若没有标题，也给它一个默认路径（文件名）
            if current_section is None:
                current_section = {
                    "heading_path": [file_stem],
                    "line_start": 1,
                    "content_lines": [],
                }
            current_section["content_lines"].append(line)

    # 处理最后一个 section
    if current_section is not None:
        current_section["line_end"] = len(lines)
        sections.append(current_section)

    return sections


def split_to_paragraphs(section_text: str) -> list[str]:
    """
    将 section 按“空行”拆成段落块：
    - 不切断引用块、表格行、列表行内部内容；
    - 保留原始换行（同一段内用 \\n 连接）。
    """
    lines = section_text.splitlines()
    paragraphs: list[str] = []
    buffer: list[str] = []

    for line in lines:
        if line.strip() == "":
            if buffer:
                paragraphs.append("\n".join(buffer).strip())
                buffer = []
        else:
            buffer.append(line.rstrip())

    if buffer:
        paragraphs.append("\n".join(buffer).strip())

    return paragraphs


def split_long_paragraph(paragraph: str, max_chars: int) -> list[str]:
    """
    单段落过长时，按中文/英文句末标点继续切分，保证每段不超过 max_chars。
    """
    if len(paragraph) <= max_chars:
        return [paragraph]

    # 按句号、问号、叹号、分号等断句；保留标点在前一段末尾
    sentences = re.split(r"(?<=[。！？；!?;])", paragraph)
    sentences = [s.strip() for s in sentences if s.strip()]

    pieces: list[str] = []
    current = ""

    for sentence in sentences:
        add_len = len(sentence) + (1 if current else 0)
        if len(current) + add_len <= max_chars:
            current = f"{current} {sentence}".strip()
        else:
            if current:
                pieces.append(current)
            current = sentence

    if current:
        pieces.append(current)

    # 如果依然有超长句子，按固定长度硬切，确保不会超出上限
    final_pieces: list[str] = []
    for piece in pieces:
        if len(piece) <= max_chars:
            final_pieces.append(piece)
        else:
            for start in range(0, len(piece), max_chars):
                final_pieces.append(piece[start : start + max_chars])

    return final_pieces


def chunk_paragraphs(
    paragraphs: list[str],
    target_chars: int,
    max_chars: int,
    overlap_chars: int,
) -> list[str]:
    """
    段落级滑动窗口分块：
    1. 每块尽量靠近 target_chars，不超过 max_chars；
    2. 相邻块保留 overlap_chars 左右的段落重叠；
    3. 以段落为单位切，不在段落中间断开（除非单段过长）。
    """
    expanded_paragraphs: list[str] = []
    for para in paragraphs:
        expanded_paragraphs.extend(split_long_paragraph(para, max_chars=max_chars))

    chunks: list[str] = []
    start = 0

    while start < len(expanded_paragraphs):
        current_len = 0
        end = start

        while end < len(expanded_paragraphs):
            candidate = expanded_paragraphs[end]
            add_len = len(candidate) + (2 if current_len > 0 else 0)

            # 达到上限就停止，避免块过大
            if current_len + add_len > max_chars:
                break

            current_len += add_len
            end += 1

            # 已达到目标长度，优先收束成块
            if current_len >= target_chars:
                break

        # 兜底：至少要放入一个段落
        if end == start:
            end = start + 1

        chunk_text = "\n\n".join(expanded_paragraphs[start:end]).strip()
        chunks.append(chunk_text)

        # 到末尾就结束
        if end >= len(expanded_paragraphs):
            break

        # 计算下一块起点：向后回退到 overlap_chars 左右，实现重叠
        back_len = 0
        next_start = end
        while next_start > start and back_len < overlap_chars:
            next_start -= 1
            back_len += len(expanded_paragraphs[next_start]) + 2

        # 确保索引推进，避免死循环
        if next_start <= start:
            next_start = end - 1
        if next_start <= start:
            next_start = end

        start = next_start

    return chunks


def build_file_chunks(md_path: Path) -> list[dict]:
    """
    对单个 md 文件执行：
    标题分段 -> 段落切分 -> 语义分块 -> 生成 chunk 元数据。
    """
    markdown_text = md_path.read_text(encoding="utf-8")
    sections = parse_markdown_sections(markdown_text, file_stem=md_path.stem)

    file_chunks: list[dict] = []
    for section_index, section in enumerate(sections, start=1):
        section_text = "\n".join(section["content_lines"]).strip()
        if not section_text:
            continue

        paragraphs = split_to_paragraphs(section_text)
        if not paragraphs:
            continue

        section_chunks = chunk_paragraphs(
            paragraphs=paragraphs,
            target_chars=TARGET_CHARS,
            max_chars=MAX_CHARS,
            overlap_chars=OVERLAP_CHARS,
        )

        heading_path_list = section["heading_path"]
        heading_path = " > ".join(heading_path_list)

        for chunk_index_in_section, chunk_text in enumerate(section_chunks, start=1):
            point_seed = f"{md_path.name}|{section_index}|{chunk_index_in_section}"
            point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, point_seed))

            file_chunks.append(
                {
                    "point_id": point_id,
                    "source_file": md_path.name,
                    "region": md_path.stem,
                    "heading_path": heading_path,
                    "h1": heading_path_list[0] if len(heading_path_list) > 0 else "",
                    "h2": heading_path_list[1] if len(heading_path_list) > 1 else "",
                    "h3": heading_path_list[2] if len(heading_path_list) > 2 else "",
                    "line_start": section["line_start"],
                    "line_end": section["line_end"],
                    "section_index": section_index,
                    "chunk_index_in_section": chunk_index_in_section,
                    "text": chunk_text,
                }
            )

    return file_chunks


def embed_chunks(
    openai_client: OpenAI,
    embedding_model: str,
    chunks: list[dict],
    embedding_dim: int,
    batch_size: int,
) -> list[list[float]]:
    """
    调用千问 text-embedding-v4 进行向量化：
    - 使用 OpenAI 兼容接口；
    - 每批多条文本；
    - 向量维度固定为 1024。
    """
    vectors: list[list[float]] = []

    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        batch_texts = [item["text"] for item in batch]

        response = openai_client.embeddings.create(
            model=embedding_model,
            input=batch_texts,
            dimensions=embedding_dim,
        )

        vectors.extend([item.embedding for item in response.data])

    return vectors


def write_to_qdrant(chunks: list[dict], vectors: list[list[float]], collection_name: str) -> None:
    """
    将 chunk + embedding 写入 Qdrant：
    1. 若集合已存在则删除；
    2. 以 1024 维 Cosine 向量重新建集合；
    3. 批量 upsert 点位。
    """
    qdrant = QdrantClient(host=os.getenv("qdrant_host"), port=int(os.getenv("qdrant_port")))

    if qdrant.collection_exists(collection_name=collection_name):
        qdrant.delete_collection(collection_name=collection_name)

    qdrant.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
    )

    points: list[PointStruct] = []
    for chunk, vector in zip(chunks, vectors):
        payload = {
            "source_file": chunk["source_file"],
            "region": chunk["region"],
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
            collection_name=collection_name,
            points=points[i : i + UPSERT_BATCH_SIZE],
            wait=True,
        )


def main() -> None:
    """
    主流程：
    1. 读取 .env；
    2. 扫描 md\world-bg 下所有 md；
    3. 分块；
    4. 调用千问 embedding；
    5. 写入本地 6333 端口的 Qdrant。
    """
    load_dotenv(dotenv_path=ENV_PATH, override=True)

    embedding_model = os.getenv("embedding_model")
    openai_client = OpenAI(
        api_key=os.getenv("embedding_key"),
        base_url=os.getenv("embedding_url"),
    )

    md_files = sorted(SOURCE_DIR.glob("*.md"))
    all_chunks: list[dict] = []
    for md_file in md_files:
        all_chunks.extend(build_file_chunks(md_file))

    vectors = embed_chunks(
        openai_client=openai_client,
        embedding_model=embedding_model,
        chunks=all_chunks,
        embedding_dim=EMBEDDING_DIM,
        batch_size=BATCH_SIZE,
    )

    write_to_qdrant(
        chunks=all_chunks,
        vectors=vectors,
        collection_name=COLLECTION_NAME,
    )

    print(f"完成：共处理 {len(md_files)} 个文件，切分 {len(all_chunks)} 个 chunks，已写入集合 {COLLECTION_NAME}。")


if __name__ == "__main__":
    main()
