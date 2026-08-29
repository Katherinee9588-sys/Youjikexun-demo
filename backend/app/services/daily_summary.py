"""Keyword-evidence daily cards for the 「今日记录」 view.

Tags, copy, 「推荐继续做」and「不建议做」come from the reviewed copy deck in
docs/PRD alignment (UIUX doc section 5). No language model is involved: the
backend only decides which preset card matches the day's keyword evidence.
"""

from __future__ import annotations

from datetime import date

from app.models.health import DailySummary, LedgerEntry
from app.services.journal_projection import all_ledger
from app.services.scene_summary import SCENES

HOT_FLASH_KEYWORDS = ("潮热", "盗汗", "燥热")

SCENE_TAG = {
    "joint_pain": "关节不适",
    "menstrual": "经期变化",
    "emotion": "容易烦躁",
}

SCENE_COPY: dict[str, dict[str, list[str]]] = {
    "joint_pain": {
        "copy_lines": [
            "你已经把模糊的不适，变成了清晰的记录。",
            "每一次记录，都在帮助你更好地了解自己。",
        ],
        "recommend": ["继续记录不适出现的时间、部位、持续时长和当时正在做的事，以及休息后的变化。"],
        "avoid": ["疼痛时不要勉强加大活动量；若持续加重、出现肿胀或活动受限，请及时就医。"],
    },
    "menstrual": {
        "copy_lines": [
            "月经的变化不容易说清楚，",
            "但你的持续记录，正在帮你一点点理清规律。",
        ],
        "recommend": ["记录每次月经的开始和结束日期、持续天数、出血量、血块及伴随症状，保持连续记录。"],
        "avoid": ["不要仅凭记录自行判断原因或处理；若经期持续偏长、出血明显增多或头晕乏力，请及时就医。"],
    },
    "emotion": {
        "copy_lines": [
            "你把情绪变化中的细节记录了下来，",
            "让每一次情绪起伏都变得有迹可循。",
        ],
        "recommend": ["记录情绪发生的时间、诱因、持续时长和当时感受，也一并记下睡眠和月经情况。"],
        "avoid": ["不要因为情绪波动责备自己，也不要在情绪激烈时勉强沟通。"],
    },
}

def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _tags(entries: list[LedgerEntry]) -> list[str]:
    positive: list[str] = []
    negative: list[str] = []
    for entry in entries:
        sleep = entry.lifestyle.sleep
        if sleep.comparable and sleep.normalized_1_10 is not None:
            if sleep.normalized_1_10 >= 8:
                positive.append("睡眠良好")
            elif sleep.normalized_1_10 < 7:
                negative.append("睡眠不佳")
        if entry.lifestyle.exercise_type:
            positive.append("坚持运动")
        if len(entry.lifestyle.meals) >= 3:
            positive.append("三餐规律")

        text = entry.original_text
        for scene_id, _title, keywords in SCENES:
            if any(keyword in text for keyword in keywords):
                negative.append(SCENE_TAG[scene_id])
        if any(keyword in text for keyword in HOT_FLASH_KEYWORDS):
            negative.append("潮热出现")

    return _dedupe(positive + negative)[:3]


def _dominant_scene(entries: list[LedgerEntry]) -> str | None:
    counts = {
        scene_id: sum(
            any(keyword in entry.original_text for keyword in keywords)
            for entry in entries
        )
        for scene_id, _title, keywords in SCENES
    }
    best_scene = max(counts, key=lambda scene_id: counts[scene_id])
    return best_scene if counts[best_scene] > 0 else None


def build_daily_summary(record_date: date, entries: list[LedgerEntry]) -> DailySummary:
    scene = _dominant_scene(entries)
    deck = SCENE_COPY[scene] if scene is not None else None
    return DailySummary(
        record_date=record_date,
        entry_count=len(entries),
        tags=_tags(entries),
        copy_lines=[] if deck is None else deck["copy_lines"],
        recommend=[] if deck is None else deck["recommend"],
        avoid=[] if deck is None else deck["avoid"],
    )


def build_daily_summaries() -> list[DailySummary]:
    """Cards for the three most recent recorded dates, newest first."""
    entries_by_date: dict[date, list[LedgerEntry]] = {}
    for entry in all_ledger():
        entries_by_date.setdefault(entry.record_date, []).append(entry)

    recent_dates = sorted(entries_by_date, reverse=True)[:3]
    return [
        build_daily_summary(record_date, entries_by_date[record_date])
        for record_date in recent_dates
    ]
