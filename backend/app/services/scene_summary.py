from __future__ import annotations

from datetime import date

from app.models.health import LedgerEntry, SceneSummary


SCENES = (
    (
        "joint_pain",
        "关节不适",
        ("关节", "膝盖", "手腕", "肩周", "肩膀", "脖", "颈", "腰", "背痛", "背酸", "手臂", "肌肉", "僵硬", "酸痛", "久坐"),
    ),
    (
        "menstrual",
        "经期变化",
        ("经期", "生理期", "月经", "经量", "出血"),
    ),
    (
        "emotion",
        "情绪波动",
        ("情绪", "烦躁", "焦虑", "低落", "压力", "想哭", "心情"),
    ),
)


def build_scene_summaries(entries: tuple[LedgerEntry, ...]) -> list[SceneSummary]:
    summaries: list[SceneSummary] = []
    for scene_id, title, keywords in SCENES:
        dates: list[date] = []
        for entry in entries:
            if any(keyword in entry.original_text for keyword in keywords):
                dates.append(entry.record_date)

        count = len(dates)
        evidence_text = (
            f"现有原始记录中有 {count} 条包含相关表达。"
            if count > 0
            else "现有原始记录中尚未出现可识别的相关表达。"
        )
        summaries.append(
            SceneSummary(
                id=scene_id,
                title=title,
                record_count=count,
                latest_date=max(dates) if dates else None,
                evidence_text=evidence_text,
                boundary="这里只统计关键词出现次数，不判断症状、原因或严重程度。",
            )
        )
    return summaries
