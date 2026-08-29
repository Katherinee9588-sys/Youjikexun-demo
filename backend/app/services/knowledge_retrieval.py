from __future__ import annotations

import re

from app.models.knowledge import KnowledgeChunk, KnowledgePassage, KnowledgeQuery
from app.repositories.knowledge import KnowledgeRepository


SCENE_QUERY_TERMS = {
    "menstrual": ("经期", "生理期", "月经", "经量", "出血"),
        "joint_pain": ("关节", "膝盖", "手腕", "肩周", "肩膀", "脖", "颈", "腰", "背痛", "背酸", "手臂", "肌肉", "僵硬", "酸痛", "久坐"),
    "emotion": ("情绪", "烦躁", "焦虑", "低落", "压力", "想哭", "心情"),
}

INTENT_QUERY_TERMS = {
    "record": ("记录", "日记", "账本"),
    "observe": ("观察", "变化", "规律"),
    "routine": ("作息", "规律", "节奏"),
    "sleep": ("睡眠", "入睡", "醒来", "起夜"),
    "movement": ("运动", "训练", "拉伸", "力量", "有氧"),
    "warmth": ("保暖", "暖", "热"),
    "emotion": ("情绪", "烦躁", "焦虑", "低落", "压力"),
}


class KnowledgeRetrievalError(RuntimeError):
    pass


def _query_terms(query: str) -> set[str]:
    chinese = "".join(re.findall(r"[\u4e00-\u9fff]", query))
    terms = {
        chinese[index : index + 2]
        for index in range(len(chinese) - 1)
    }
    terms.update(re.findall(r"[a-z0-9_]+", query.lower()))
    return terms


def _searchable_text(chunk: KnowledgeChunk) -> str:
    return "\n".join(
        (
            chunk.title,
            chunk.content,
            chunk.source_title,
            " ".join(chunk.scene_tags),
            " ".join(chunk.intent_tags),
        )
    ).lower()


def _tag_score(query: str, chunk: KnowledgeChunk) -> tuple[int, list[str]]:
    score = 0
    matched: list[str] = []
    for scene_tag, terms in SCENE_QUERY_TERMS.items():
        for term in terms:
            if term in query and scene_tag in chunk.scene_tags:
                score += 3
                matched.append(term)
                break
    for intent_tag, terms in INTENT_QUERY_TERMS.items():
        for term in terms:
            if term in query and intent_tag in chunk.intent_tags:
                score += 2
                matched.append(term)
                break
    return score, matched


def _passage(query: str, chunk: KnowledgeChunk) -> KnowledgePassage | None:
    searchable = _searchable_text(chunk)
    text_matches = [term for term in _query_terms(query) if term in searchable]
    tag_score, tag_matches = _tag_score(query, chunk)
    relevance_score = len(text_matches) + tag_score
    if relevance_score == 0:
        return None
    matched_terms = sorted(set(text_matches + tag_matches))
    return KnowledgePassage(
        chunk_id=chunk.chunk_id,
        title=chunk.title,
        content=chunk.content,
        source_publisher=chunk.source_publisher,
        source_title=chunk.source_title,
        source_url=chunk.source_url,
        safety_boundary=chunk.safety_boundary,
        relevance_score=relevance_score,
        matched_terms=matched_terms,
    )


class ReviewedKnowledgeRetriever:
    """Small, deterministic retrieval for the first approved knowledge pack."""

    def retrieve(self, query: str, limit: int) -> list[KnowledgePassage]:
        passages: list[KnowledgePassage] = []
        for chunk in KnowledgeRepository.approved():
            passage = _passage(query, chunk)
            if passage is not None:
                passages.append(passage)
        passages.sort(key=lambda item: (-item.relevance_score, item.chunk_id))
        return passages[:limit]

    def retrieve_required(self, query: KnowledgeQuery) -> list[KnowledgePassage]:
        passages = self.retrieve(query.query, query.limit)
        if len(passages) == 0:
            raise KnowledgeRetrievalError(
                "no approved knowledge chunk matched this query"
            )
        return passages
