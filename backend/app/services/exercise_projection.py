from __future__ import annotations

import re
from dataclasses import dataclass

from app.models.health import ExerciseDetail, ExerciseType


STRUCTURED_EXERCISE = re.compile(
    r"^(cardio_minutes|core_sets|glute_leg_sets|back_sets|arch_training)[：:]\s*([^\s，,；;]+)",
    re.IGNORECASE,
)
MINUTES = re.compile(r"(?<!\d)(\d{1,4})\s*(?:分钟|分)(?!\d)")
HOURS = re.compile(r"(?<!\d)(\d{1,2}|一)\s*个?小时")
SETS = re.compile(r"(?<!\d)(\d{1,3}|[一二三四五六七八九十]+)\s*组")
SEGMENT_SPLIT = re.compile(r"[，,；;]|\s*(?:\+|和)\s*")
RAW_ACTIVITY = re.compile(
    r"运动|锻炼|活动了一下|动了一下|转了转|体式|壶铃练臀"
)
NEGATION_BEFORE = re.compile(r"(?:没有|没|未|无)(?:做|练|进行|参加)?\s*$")
NEGATION_AFTER = re.compile(r"^\s*[：:]?\s*(?:无|没有|没做|未做|否|no)(?:\s|$)", re.IGNORECASE)

TYPE_PATTERNS: tuple[tuple[ExerciseType, tuple[re.Pattern[str], ...]], ...] = (
    (
        "aerobic",
        tuple(re.compile(value) for value in (r"有氧操", r"跳操", r"有氧")),
    ),
    (
        "strength",
        tuple(
            re.compile(value)
            for value in (
                r"背部力量训练",
                r"背部肌肉训练",
                r"臀腿力量训练",
                r"轻度力量训练",
                r"抗阻训练",
                r"负重训练",
                r"力量训练",
                r"臀腿训练",
                r"背部训练",
                r"举铁",
            )
        ),
    ),
    (
        "core",
        tuple(re.compile(value) for value in (r"核心训练", r"核心")),
    ),
    (
        "stretching",
        tuple(
            re.compile(value)
            for value in (
                r"提肩胛肌拉伸",
                r"上斜方肌拉伸",
                r"门框胸肌拉伸",
                r"肩颈拉伸",
                r"肩颈放松",
                r"小腿部拉伸",
                r"臀腿拉伸",
                r"背部拉伸",
                r"猫式伸展",
                r"拉伸",
                r"伸展",
            )
        ),
    ),
    (
        "yoga",
        tuple(
            re.compile(value)
            for value in (
                r"瑜伽拉伸",
                r"伸展瑜伽",
                r"瑜伽课",
                r"瑜伽练习",
                r"睡前瑜伽",
                r"瑜伽",
            )
        ),
    ),
    (
        "walking",
        tuple(
            re.compile(value)
            for value in (
                r"空腹散步",
                r"晚饭后散步",
                r"散步",
                r"快走",
                r"步行",
                r"走了\s*\d+\s*(?:步|圈)",
            )
        ),
    ),
    (
        "other",
        tuple(
            re.compile(value)
            for value in (
                r"托天理三焦",
                r"金鸡独立",
                r"足弓训练",
                r"足弓练习",
                r"拍八虚",
                r"八段锦",
                r"平板支撑",
                r"深蹲",
                r"臀桥",
                r"鸟狗",
                r"提踵",
                r"慢跑",
                r"节奏跑",
                r"自行车",
                r"骑车",
                r"游泳",
                r"羽毛球",
                r"舞蹈",
                r"壶铃练臀",
            )
        ),
    ),
)

LEGACY_DETAIL: dict[str, tuple[ExerciseType, str, str]] = {
    "cardio_minutes": ("aerobic", "有氧", "duration"),
    "core_sets": ("core", "核心训练", "sets"),
    "glute_leg_sets": ("strength", "臀腿训练", "sets"),
    "back_sets": ("strength", "背部训练", "sets"),
}


@dataclass(frozen=True)
class ExerciseProjection:
    exercise_type: list[ExerciseType]
    exercise_duration: int | None
    exercise_sets: int | None
    exercise_details: list[ExerciseDetail]
    exercise_raw_text: str | None


def _chinese_integer(value: str) -> int | None:
    if value.isdigit():
        return int(value)
    digits = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    if value == "十":
        return 10
    if "十" in value:
        left, right = value.split("十", maxsplit=1)
        tens = digits.get(left, 1) if left else 1
        ones = digits.get(right, 0) if right else 0
        return tens * 10 + ones
    return digits.get(value)


def _duration_minutes(segment: str) -> int | None:
    minute_match = MINUTES.search(segment)
    if minute_match is not None:
        minutes = int(minute_match.group(1))
        return minutes if 1 <= minutes <= 1440 else None
    hour_match = HOURS.search(segment)
    if hour_match is None:
        return None
    hours = 1 if hour_match.group(1) == "一" else int(hour_match.group(1))
    minutes = hours * 60
    return minutes if 1 <= minutes <= 1440 else None


def _sets(segment: str) -> int | None:
    match = SETS.search(segment)
    if match is None:
        return None
    count = _chinese_integer(match.group(1))
    return count if count is not None and 1 <= count <= 200 else None


def _is_positive_match(segment: str, start: int, end: int) -> bool:
    before = segment[max(0, start - 8) : start]
    after = segment[end : end + 8]
    return NEGATION_BEFORE.search(before) is None and NEGATION_AFTER.match(after) is None


def _natural_details(segment: str) -> tuple[list[ExerciseDetail], int | None, int | None]:
    matches: list[tuple[int, ExerciseType, str]] = []
    for exercise_type, patterns in TYPE_PATTERNS:
        first_match = next(
            (
                match
                for pattern in patterns
                if (match := pattern.search(segment)) is not None
                and _is_positive_match(segment, match.start(), match.end())
            ),
            None,
        )
        if first_match is not None:
            matches.append((first_match.start(), exercise_type, first_match.group(0)))

    detected_types = {item[1] for item in matches}
    if "other" in detected_types and ({"core", "strength"} & detected_types):
        matches = [item for item in matches if item[1] != "other"]
    matches.sort(key=lambda item: (item[0], item[1]))

    duration = _duration_minutes(segment)
    sets = _sets(segment)
    one_type = len(matches) == 1
    details = [
        ExerciseDetail(
            type=exercise_type,
            raw_name=raw_name,
            duration_minutes=duration if one_type else None,
            sets=sets if one_type else None,
        )
        for _, exercise_type, raw_name in matches
    ]
    return details, duration, sets


def _candidate_line(line: str, *, legacy: bool) -> str | None:
    stripped = line.strip().lstrip("-").strip()
    if not stripped:
        return None
    if not legacy:
        return stripped
    if STRUCTURED_EXERCISE.match(stripped) is not None:
        return stripped
    prefixes = ("运动：", "运动:", "训练内容：", "训练内容:", "content：", "content:")
    prefix = next((value for value in prefixes if stripped.startswith(value)), None)
    if prefix is not None:
        return stripped[len(prefix) :].strip()
    decorated_exercise = re.match(r"^运动(?:（[^）]+）|\([^\)]+\))[：:]\s*(.+)$", stripped)
    if decorated_exercise is not None:
        return decorated_exercise.group(1).strip()
    action_field = re.match(r"^(?:提踵|鸟狗)[：:]\s*(.*)$", stripped)
    if action_field is not None:
        value = action_field.group(1).strip()
        return stripped if value not in {"", "无", "没有", "没做", "未做"} else None
    if re.match(r"^(?:提肩胛肌|上斜方肌|门框胸肌|肩颈|小腿部|臀腿|背部).*(?:拉伸|伸展)", stripped):
        return stripped
    return None


def project_exercise(text: str, *, legacy: bool) -> ExerciseProjection:
    details: list[ExerciseDetail] = []
    raw_lines: list[str] = []
    explicit_durations: list[int] = []

    for source_line in text.splitlines():
        candidate = _candidate_line(source_line, legacy=legacy)
        if candidate is None:
            continue

        structured = STRUCTURED_EXERCISE.match(candidate)
        if structured is not None:
            field = structured.group(1).lower()
            value = structured.group(2).lower()
            if field == "arch_training":
                if value == "yes":
                    details.append(ExerciseDetail(type="other", raw_name="足弓训练"))
                    raw_lines.append(source_line.strip())
                continue
            number = int(value)
            if number <= 0:
                continue
            exercise_type, raw_name, measure = LEGACY_DETAIL[field]
            detail = ExerciseDetail(
                type=exercise_type,
                raw_name=raw_name,
                duration_minutes=number if measure == "duration" else None,
                sets=number if measure == "sets" else None,
            )
            details.append(detail)
            raw_lines.append(source_line.strip())
            if detail.duration_minutes is not None:
                explicit_durations.append(detail.duration_minutes)
            continue

        line_has_detail = False
        for segment in SEGMENT_SPLIT.split(candidate):
            normalized = segment.strip()
            if not normalized:
                continue
            segment_details, duration, _ = _natural_details(normalized)
            if not segment_details:
                continue
            details.extend(segment_details)
            line_has_detail = True
            if duration is not None:
                explicit_durations.append(duration)
        if line_has_detail or RAW_ACTIVITY.search(candidate) is not None:
            raw_lines.append(source_line.strip())

    merged_details: list[ExerciseDetail] = []
    for detail in details:
        merge_index = next(
            (
                index
                for index, current in enumerate(merged_details)
                if current.type == detail.type
                and (
                    current.raw_name == detail.raw_name
                    or (
                        detail.type == "aerobic"
                        and {current.raw_name, detail.raw_name} <= {"有氧", "有氧操"}
                    )
                )
                and (current.duration_minutes is None or detail.duration_minutes is None)
                and (current.sets is None or detail.sets is None)
            ),
            None,
        )
        if merge_index is None:
            merged_details.append(detail)
            continue
        current = merged_details[merge_index]
        merged_details[merge_index] = ExerciseDetail(
            type=current.type,
            raw_name=current.raw_name if current.raw_name != "有氧" else detail.raw_name,
            duration_minutes=current.duration_minutes or detail.duration_minutes,
            sets=current.sets or detail.sets,
        )

    unique_details: list[ExerciseDetail] = []
    seen_details: set[tuple[ExerciseType, str, int | None, int | None]] = set()
    for detail in merged_details:
        key = (detail.type, detail.raw_name, detail.duration_minutes, detail.sets)
        if key in seen_details:
            continue
        seen_details.add(key)
        unique_details.append(detail)

    exercise_types: list[ExerciseType] = []
    for detail in unique_details:
        if detail.type not in exercise_types:
            exercise_types.append(detail.type)

    exercise_duration = sum(explicit_durations) if explicit_durations else None
    if exercise_duration is not None and exercise_duration > 1440:
        exercise_duration = None
    exercise_sets = (
        unique_details[0].sets
        if len(unique_details) == 1 and unique_details[0].sets is not None
        else None
    )
    exercise_raw_text = "\n".join(dict.fromkeys(raw_lines)) if raw_lines else None
    return ExerciseProjection(
        exercise_type=exercise_types,
        exercise_duration=exercise_duration,
        exercise_sets=exercise_sets,
        exercise_details=unique_details,
        exercise_raw_text=exercise_raw_text,
    )
