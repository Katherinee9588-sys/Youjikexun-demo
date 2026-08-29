from app.services.exercise_projection import project_exercise


def detail_by_name(projection, raw_name: str):
    return next(detail for detail in projection.exercise_details if detail.raw_name == raw_name)


def test_extracts_multiple_types_without_merging_sets() -> None:
    projection = project_exercise(
        "今天做了核心 4 组和有氧 15 分钟。",
        legacy=False,
    )

    assert projection.exercise_type == ["core", "aerobic"]
    assert projection.exercise_duration == 15
    assert projection.exercise_sets is None
    assert detail_by_name(projection, "核心").sets == 4
    assert detail_by_name(projection, "有氧").duration_minutes == 15


def test_yoga_stretching_keeps_source_order_and_unknown_measures() -> None:
    projection = project_exercise("昨晚做了瑜伽拉伸。", legacy=False)

    assert projection.exercise_type == ["yoga", "stretching"]
    assert projection.exercise_duration is None
    assert projection.exercise_sets is None


def test_details_keep_separate_strength_and_stretching_measures() -> None:
    projection = project_exercise(
        "背部力量训练 3 组，背部拉伸 10 分钟。",
        legacy=False,
    )

    assert projection.exercise_type == ["strength", "stretching"]
    assert projection.exercise_duration == 10
    assert projection.exercise_sets is None
    assert detail_by_name(projection, "背部力量训练").sets == 3
    assert detail_by_name(projection, "背部拉伸").duration_minutes == 10


def test_other_names_are_retained_without_growing_enum() -> None:
    projection = project_exercise("早上八段锦，金鸡独立三组。", legacy=False)

    assert projection.exercise_type == ["other"]
    assert projection.exercise_sets is None
    assert [detail.raw_name for detail in projection.exercise_details] == [
        "八段锦",
        "金鸡独立",
    ]
    assert detail_by_name(projection, "金鸡独立").sets == 3


def test_vague_and_negated_activity_is_not_structured() -> None:
    for text in (
        "今天做了点运动，感觉挺累。",
        "出去转了转。",
        "做了几个体式。",
        "今天没运动。",
        "今天没有做有氧。",
    ):
        projection = project_exercise(text, legacy=False)
        assert projection.exercise_type == []
        assert projection.exercise_details == []
        assert projection.exercise_duration is None
        assert projection.exercise_sets is None


def test_vague_activity_keeps_original_expression() -> None:
    projection = project_exercise("今天做了点运动，感觉挺累。", legacy=False)

    assert projection.exercise_type == []
    assert projection.exercise_raw_text == "今天做了点运动，感觉挺累。"


def test_named_enum_outlier_uses_other_and_keeps_name() -> None:
    projection = project_exercise("今天壶铃练臀 3 组。", legacy=False)

    assert projection.exercise_type == ["other"]
    assert detail_by_name(projection, "壶铃练臀").sets == 3


def test_legacy_fields_map_to_details_without_summing_sets() -> None:
    projection = project_exercise(
        """- content：核心训练 + 有氧操
- core_sets：4
- cardio_minutes：15
- arch_training：yes""",
        legacy=True,
    )

    assert projection.exercise_type == ["core", "aerobic", "other"]
    assert projection.exercise_duration == 15
    assert projection.exercise_sets is None
    assert detail_by_name(projection, "核心训练").sets == 4
    assert detail_by_name(projection, "有氧操").duration_minutes == 15
    assert detail_by_name(projection, "足弓训练").type == "other"


def test_empty_legacy_action_fields_do_not_create_activity() -> None:
    projection = project_exercise("提踵：\n鸟狗：无", legacy=True)

    assert projection.exercise_type == []
    assert projection.exercise_details == []
    assert projection.exercise_raw_text is None
