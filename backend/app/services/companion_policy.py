from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.health import StrictModel
from app.models.knowledge import KnowledgePassage


FORBIDDEN_MEDICAL_TERMS = (
    "治愈",
    "治好",
    "治疗",
    "病灶",
    "炎症",
    "病变",
    "康复",
    "药效",
    "确诊",
    "用药",
    "药物",
    "处方",
    "严重",
    "轻微",
)

COMPANION_SYSTEM_PROMPT = """你是面向围绝经期女性的陪伴式健康记录与生活调理助手。
你不具备医疗诊断、治疗、处方能力，只提供生活习惯、作息、情绪、日常养护和记录管理建议。
只返回 JSON：{"empathy":"第一句。","suggestion":"第二句。","outlook":"第三句。"}
三句话每句 10–20 个汉字。第一句鼓励共情；第二句给一项非医疗生活建议；第三句给轻量正向展望。
先在本次单次回答内判断用户意图，不要因为用户原文出现一个医疗词就拒答，也不要调用额外分类流程。
用户只是在记录或描述症状、转述既往说法、表达担心或记录变化时，继续按陪伴式记录回答，不触发医疗边界。
只有用户明确索要诊断、病因、治疗方案、用药建议、处方，或要求替代医生判断时，才触发医疗边界。
触发医疗边界时，必须返回：{"empathy":"我理解你想弄清这次变化。","suggestion":"这部分请带记录到线下门诊咨询医生。","outlook":"我们可以先继续记录变化和当时情境。"}
不得判断症状轻重，不得指导用药，不得替代医生，不得使用医疗禁词。
经期场景只谈记录、作息、日常暖护和规律观察；关节场景只谈保暖、轻度放松、作息和姿势；情绪场景只谈放松、节奏、自我接纳和记录。
出现疑似疾病问题时，只建议持续记录、规律观察，必要时线下就医。"""


def _content_length(value: str) -> int:
    return len(re.sub(r"[\s，。！？；：、,.!?;:]", "", value))


class CompanionOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    empathy: str
    suggestion: str
    outlook: str

    @field_validator("empathy", "suggestion", "outlook")
    @classmethod
    def validate_sentence(cls, value: str) -> str:
        if not value.endswith("。"):
            raise ValueError("each companion line must end with a Chinese full stop")
        if any(mark in value[:-1] for mark in "。！？!?"):
            raise ValueError("each companion field must contain exactly one sentence")
        length = _content_length(value)
        if length < 8 or length > 25:
            raise ValueError("each companion sentence must contain 8-25 characters")
        return value

    @model_validator(mode="after")
    def reject_medical_terms(self) -> "CompanionOutput":
        text = self.as_text()
        found = [term for term in FORBIDDEN_MEDICAL_TERMS if term in text]
        if found:
            raise ValueError(f"companion output contains forbidden terms: {found}")
        return self

    def as_text(self) -> str:
        return "\n".join((self.empathy, self.suggestion, self.outlook))


class GroundedCompanionResponse(StrictModel):
    output: CompanionOutput
    passages: list[KnowledgePassage] = Field(min_length=0, max_length=2)


def companion_fallback_output() -> CompanionOutput:
    """A safe, pre-reviewed reply used when no approved knowledge chunk matches.

    Keeps the three-sentence contract and medical boundary intact without
    surfacing a raw "no match" error to the user.
    """
    return CompanionOutput(
        empathy="你愿意把今天的感受记下来，已经很用心。",
        suggestion="先记下这件事发生的时间、感受和当时情境。",
        outlook="持续记录，慢慢会看清自己的身体节奏。",
    )
