from __future__ import annotations

import os
import re
from typing import Any

import jieba
from openai import OpenAI
from rank_bm25 import BM25Okapi
from qdrant_client import QdrantClient


QDRANT_HOST = "127.0.0.1"
QDRANT_PORT = 6333

# 关键词检索时，每个集合最多拉取多少条文档做 BM25 计算
BM25_SCAN_LIMIT_PER_COLLECTION = 3000


def _tokenize_for_bm25(text: str) -> list[str]:
    """
    BM25 分词：
    1. 中文使用 jieba 分词；
    2. 英文与数字按词切分；
    3. 只保留有信息量的词元，给 BM25 做更稳定的统计。
    """
    normalized_text = text.lower()
    jieba_tokens = [token.strip() for token in jieba.lcut(normalized_text) if token.strip()]
    ascii_tokens = re.findall(r"[a-z0-9_]+", normalized_text)
    return [token for token in (jieba_tokens + ascii_tokens) if re.search(r"[\u4e00-\u9fff]|[a-z0-9_]+", token)]


def _normalize_text(raw_text: str) -> str:
    """
    对原始文本做轻量清洗，减少 md\world-bg 中图片标记等噪声对检索排序的干扰：
    - 过滤 [Image](...) / ![Image](...) 这类图片行；
    - 合并多余空行。
    """
    lines = raw_text.splitlines()
    kept_lines = [
        line
        for line in lines
        if not re.match(r"^\s*!?\[Image\]\(.*\)\s*$", line.strip(), flags=re.IGNORECASE)
    ]
    text = "\n".join(kept_lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _load_documents_from_collections(
    collection_names: list[str],
    scan_limit_per_collection: int,
) -> list[dict[str, Any]]:
    """
    从多个集合滚动读取 payload，用于 BM25 关键词检索。
    返回结构保留了 source_file / heading_path / 行号范围，方便后续注入智能体上下文。
    """
    qdrant = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    documents: list[dict[str, Any]] = []

    for collection_name in collection_names:
        offset: Any = None
        loaded_count = 0

        while loaded_count < scan_limit_per_collection:
            limit = min(256, scan_limit_per_collection - loaded_count)
            points, offset = qdrant.scroll(
                collection_name=collection_name,
                with_payload=True,
                with_vectors=False,
                limit=limit,
                offset=offset,
            )

            for point in points:
                payload = point.payload or {}
                text = _normalize_text(str(payload.get("text", "")))
                documents.append(
                    {
                        "point_id": str(point.id),
                        "source_collection": collection_name,
                        "source_file": str(payload.get("source_file", "")),
                        "heading_path": str(payload.get("heading_path", "")),
                        "line_start": payload.get("line_start"),
                        "line_end": payload.get("line_end"),
                        "text": text,
                    }
                )

            loaded_count += len(points)
            if offset is None or len(points) == 0:
                break

    return documents


def bm25_keyword_search(
    query: str,
    collection_names: list[str],
    top_k: int = 20,
    scan_limit_per_collection: int = BM25_SCAN_LIMIT_PER_COLLECTION,
) -> list[dict[str, Any]]:
    """
    BM25 关键词检索：
    - 接收多个集合名；
    - 使用 rank-bm25 库统一计算 BM25 分值；
    - 输出按 bm25_score 由高到低排序的文档片段。
    """
    documents = _load_documents_from_collections(
        collection_names=collection_names,
        scan_limit_per_collection=scan_limit_per_collection,
    )
    query_tokens = _tokenize_for_bm25(query)
    if len(documents) == 0 or len(query_tokens) == 0:
        return []

    tokenized_docs = [_tokenize_for_bm25(item["text"]) for item in documents]
    bm25_engine = BM25Okapi(tokenized_docs)
    bm25_scores = bm25_engine.get_scores(query_tokens)
    scored_docs: list[dict[str, Any]] = []
    for idx, bm25_score in enumerate(bm25_scores):
        if bm25_score > 0:
            hit = dict(documents[idx])
            hit["bm25_score"] = float(bm25_score)
            scored_docs.append(hit)

    scored_docs.sort(key=lambda x: x["bm25_score"], reverse=True)
    return scored_docs[:top_k]


def vector_search(
    query: str,
    collection_names: list[str],
    top_k: int = 20,
) -> list[dict[str, Any]]:
    """
    向量检索：
    - 先用 embedding_model 把 query 转向量；
    - 再在每个集合中做相似度检索；
    - 输出统一结构，供 RRF 融合。
    """
    openai_client = OpenAI(
        api_key=os.getenv("api_key"),
        base_url=os.getenv("base_url"),
    )
    query_embedding = openai_client.embeddings.create(
        model=os.getenv("embedding_model"),
        input=[query],
    ).data[0].embedding

    qdrant = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    all_hits: list[dict[str, Any]] = []

    for collection_name in collection_names:

        query_response = qdrant.query_points(
            collection_name=collection_name,
            query=query_embedding,
            limit=top_k,
            with_payload=True,
        )
        hits = query_response.points

        for rank, hit in enumerate(hits, start=1):
            payload = hit.payload or {}
            all_hits.append(
                {
                    "point_id": str(hit.id),
                    "source_collection": collection_name,
                    "source_file": str(payload.get("source_file", "")),
                    "heading_path": str(payload.get("heading_path", "")),
                    "line_start": payload.get("line_start"),
                    "line_end": payload.get("line_end"),
                    "text": _normalize_text(str(payload.get("text", ""))),
                    "vector_score": float(hit.score),
                    "vector_rank": rank,
                }
            )

    all_hits.sort(key=lambda x: x["vector_score"], reverse=True)
    return all_hits[:top_k]


def _select_hits_for_context(
    query: str,
    fused_hits: list[dict[str, Any]],
    top_k: int,
) -> list[dict[str, Any]]:
    """
    将融合结果转换为结构化上下文数据：
    1. 先按 RRF 相对阈值筛掉弱相关项；
    2. 再按问题长度动态分配总预算；
    3. 最后按每条片段权重做动态截断，返回结构化列表。
    """
    if len(fused_hits) == 0:
        return []

    best_rrf = fused_hits[0]["rrf_score"]
    min_rrf = best_rrf * 0.55
    selected_hits = [item for item in fused_hits if item["rrf_score"] >= min_rrf][:top_k]

    total_budget = 2800
    if len(query) <= 12:
        total_budget = int(total_budget * 0.72)
    elif len(query) >= 60:
        total_budget = int(total_budget * 1.12)

    remaining_budget = total_budget
    total_rrf_score = sum(item["rrf_score"] for item in selected_hits)
    context_items: list[dict[str, Any]] = []

    for rank, item in enumerate(selected_hits, start=1):
        ratio = item["rrf_score"] / total_rrf_score
        text_budget = int(total_budget * ratio)
        text_budget = max(220, min(text_budget, 900))
        text_budget = min(text_budget, remaining_budget)

        text = str(item["text"]).strip()
        truncated_text = text[:text_budget] if len(text) <= text_budget else f"{text[:text_budget]}..."

        # 这里只做结构化数据生成，不做拼接格式化；
        # 最终给 LLM 的文本格式由 agent 节点在进入模型前统一处理。
        item_cost = len(truncated_text)
        if item_cost > remaining_budget:
            break
        context_items.append(
            {
                "rank": rank,
                "point_id": item["point_id"],
                "source_collection": item["source_collection"],
                "source_file": item["source_file"],
                "heading_path": item["heading_path"],
                "line_start": item["line_start"],
                "line_end": item["line_end"],
                "content": truncated_text,
                "rrf_score": item["rrf_score"],
                "bm25_score": item["bm25_score"],
                "vector_score": item["vector_score"],
                "bm25_rank": item["bm25_rank"],
                "vector_rank": item["vector_rank"],
            }
        )
        remaining_budget -= item_cost
        if remaining_budget < 180:
            break

    return context_items


def hybird_search(
    query: str,
    collection_names: list[str],
    top_k: int = 8,
    bm25_top_k: int = 20,
    vector_top_k: int = 20,
    rrf_k: int = 60,
) -> list[dict[str, Any]]:
    """
    混合检索主函数（hybird-search）：
    1. 独立执行 BM25 关键词检索；
    2. 独立执行向量检索；
    3. 用 RRF 融合两路排序；
    4. 在该文件内完成动态筛选与动态截断；
    5. 返回结构化列表，由 agent 节点在进入 LLM 前再格式化。
    """
    bm25_hits = bm25_keyword_search(
        query=query,
        collection_names=collection_names,
        top_k=bm25_top_k,
    )
    vector_hits = vector_search(
        query=query,
        collection_names=collection_names,
        top_k=vector_top_k,
    )

    fused_map: dict[tuple[str, str], dict[str, Any]] = {}

    # 先写入 BM25 排名贡献：RRF = 1 / (k + rank)
    for rank, hit in enumerate(bm25_hits, start=1):
        key = (hit["source_collection"], hit["point_id"])
        fused_map[key] = {
            "point_id": hit["point_id"],
            "source_collection": hit["source_collection"],
            "source_file": hit.get("source_file", ""),
            "heading_path": hit.get("heading_path", ""),
            "line_start": hit.get("line_start"),
            "line_end": hit.get("line_end"),
            "text": hit.get("text", ""),
            "bm25_score": hit.get("bm25_score", 0.0),
            "vector_score": 0.0,
            "bm25_rank": rank,
            "vector_rank": None,
            "rrf_score": 1.0 / (rrf_k + rank),
        }

    # 合并向量排名贡献；同一文档会在原有 rrf_score 上叠加
    for rank, hit in enumerate(vector_hits, start=1):
        key = (hit["source_collection"], hit["point_id"])
        if key not in fused_map:
            fused_map[key] = {
                "point_id": hit["point_id"],
                "source_collection": hit["source_collection"],
                "source_file": hit.get("source_file", ""),
                "heading_path": hit.get("heading_path", ""),
                "line_start": hit.get("line_start"),
                "line_end": hit.get("line_end"),
                "text": hit.get("text", ""),
                "bm25_score": 0.0,
                "vector_score": hit.get("vector_score", 0.0),
                "bm25_rank": None,
                "vector_rank": rank,
                "rrf_score": 1.0 / (rrf_k + rank),
            }
        else:
            fused_map[key]["vector_score"] = hit.get("vector_score", 0.0)
            fused_map[key]["vector_rank"] = rank
            fused_map[key]["rrf_score"] += 1.0 / (rrf_k + rank)

    fused_hits = list(fused_map.values())
    fused_hits.sort(
        key=lambda x: (x["rrf_score"], x["vector_score"], x["bm25_score"]),
        reverse=True,
    )
    return _select_hits_for_context(
        query=query,
        fused_hits=fused_hits,
        top_k=top_k,
    )

