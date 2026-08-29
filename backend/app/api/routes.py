from fastapi import APIRouter, Body, HTTPException, Query, status
from pydantic import ValidationError

from app.integrations.openai_compatible_llm import (
    LanguageModelRequestError,
    OpenAICompatibleLanguageModelAdapter,
)
from app.integrations.zhipu_asr import (
    SpeechToTextRequestError,
    ZhipuSpeechToTextAdapter,
)
from app.models.health import (
    AppOverview,
    DailySummary,
    IntegrationStatus,
    LedgerEntry,
    TrendsReport,
    UserEntryCreate,
    VoiceTranscript,
)
from app.services.asr_settings import ASRConfigurationError, ASRSettings
from app.models.hardware import MAX30102SampleCreate, StoredMAX30102Sample
from app.models.knowledge import (
    CompanionGenerationRequest,
    KnowledgePreview,
    KnowledgeQuery,
    RAGStatus,
)
from app.repositories.entries import EntryRepository
from app.repositories.hardware import MAX30102Repository
from app.repositories.knowledge import (
    KnowledgeBaseUnavailable,
    KnowledgeDataError,
    KnowledgeRepository,
)
from app.services.companion_policy import (
    GroundedCompanionResponse,
    companion_fallback_output,
)
from app.services.daily_summary import build_daily_summaries
from app.services.journal_projection import all_ledger, ledger_by_id, project_user_entry
from app.services.knowledge_retrieval import (
    KnowledgeRetrievalError,
    ReviewedKnowledgeRetriever,
)
from app.services.llm_settings import LLMConfigurationError, LLMSettings
from app.services.overview import build_overview, integration_status
from app.services.trends import build_trends


router = APIRouter(prefix="/api")


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/overview", response_model=AppOverview)
def overview() -> AppOverview:
    return build_overview()


@router.get("/ledger", response_model=list[LedgerEntry])
def ledger(limit: int = Query(default=40, ge=1, le=100)) -> list[LedgerEntry]:
    entries = all_ledger()
    return list(reversed(entries[-limit:]))


@router.get("/daily-summaries", response_model=list[DailySummary])
def daily_summaries() -> list[DailySummary]:
    """Full-page cards for the 「今日记录」 view: the three most recent recorded days."""
    return build_daily_summaries()


@router.get("/trends", response_model=TrendsReport)
def trends() -> TrendsReport:
    return build_trends()


@router.get("/ledger/{entry_id}", response_model=LedgerEntry)
def ledger_entry(entry_id: str) -> LedgerEntry:
    entry = ledger_by_id(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Ledger entry does not exist")
    return entry


@router.post(
    "/entries",
    response_model=LedgerEntry,
    status_code=status.HTTP_201_CREATED,
)
def create_entry(payload: UserEntryCreate) -> LedgerEntry:
    return project_user_entry(EntryRepository.append(payload))


@router.post("/voice/transcriptions", response_model=VoiceTranscript)
def transcribe_voice(audio: bytes = Body(min_length=44, media_type="audio/wav")) -> VoiceTranscript:
    """Turn one browser-captured WAV recording into text.

    This endpoint deliberately accepts only raw WAV bytes. It neither buffers
    recordings on disk nor creates a ledger entry; the caller decides whether
    to save the returned text through POST /api/entries.
    """
    try:
        settings = ASRSettings.from_environment()
    except ASRConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    try:
        text = ZhipuSpeechToTextAdapter(settings).transcribe_wav(audio)
    except SpeechToTextRequestError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    return VoiceTranscript(text=text)


@router.post(
    "/hardware/max30102/readings",
    response_model=StoredMAX30102Sample,
    status_code=status.HTTP_201_CREATED,
)
def create_max30102_reading(payload: MAX30102SampleCreate) -> StoredMAX30102Sample:
    if payload.signal_quality != "valid":
        raise HTTPException(
            status_code=422,
            detail="Only signal_quality=valid MAX30102 samples may be stored",
        )
    return MAX30102Repository.append(payload)


@router.get(
    "/hardware/max30102/latest",
    response_model=StoredMAX30102Sample,
)
def latest_max30102_reading() -> StoredMAX30102Sample:
    sample = MAX30102Repository.latest_valid()
    if sample is None:
        raise HTTPException(status_code=404, detail="No valid MAX30102 sample exists")
    return sample


@router.get("/integrations", response_model=IntegrationStatus)
def integrations() -> IntegrationStatus:
    return integration_status()


@router.get("/knowledge/status", response_model=RAGStatus)
def knowledge_status() -> RAGStatus:
    try:
        return KnowledgeRepository.status()
    except KnowledgeDataError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/knowledge/preview", response_model=KnowledgePreview)
def knowledge_preview(payload: KnowledgeQuery) -> KnowledgePreview:
    try:
        passages = ReviewedKnowledgeRetriever().retrieve(payload.query, payload.limit)
    except KnowledgeBaseUnavailable as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except KnowledgeDataError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return KnowledgePreview(query=payload.query, passages=passages)


@router.post("/companion", response_model=GroundedCompanionResponse)
def companion(payload: CompanionGenerationRequest) -> GroundedCompanionResponse:
    query = KnowledgeQuery(query=payload.user_text, limit=2)
    retriever = ReviewedKnowledgeRetriever()
    try:
        passages = retriever.retrieve(query.query, query.limit)
    except KnowledgeBaseUnavailable as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except KnowledgeDataError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    if len(passages) == 0:
        # No approved knowledge matched this free-form input. Instead of
        # surfacing a raw retrieval error, return a safe pre-reviewed reply so
        # the conversation keeps flowing; the model is not called.
        return GroundedCompanionResponse(
            output=companion_fallback_output(),
            passages=[],
        )

    try:
        settings = LLMSettings.from_environment()
    except LLMConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    try:
        output = OpenAICompatibleLanguageModelAdapter(settings).generate_companion_output(
            payload.user_text,
            passages,
        )
    except (LanguageModelRequestError, ValidationError) as error:
        # The model timed out, returned an upstream error, or produced output
        # that violates the companion contract. Fall back to a safe pre-reviewed
        # reply instead of surfacing a raw 502, so the conversation keeps flowing.
        output = companion_fallback_output()
    return GroundedCompanionResponse(output=output, passages=passages)
