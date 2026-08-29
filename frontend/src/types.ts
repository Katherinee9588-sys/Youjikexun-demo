export type View = "home" | "today" | "track";

export interface Feedback {
  hot: string;
  cold: string[];
}

export interface BloodPressureReading {
  systolic_pressure: number;
  diastolic_pressure: number;
  heart_rate: number | null;
  measurement_context: string[];
}

export interface SleepObservation {
  recorded: boolean;
  raw_text: string | null;
  raw_value: number | null;
  raw_scale: 10 | 100 | null;
  normalized_1_10: number | null;
  comparable: boolean;
  bed_time: string | null;
  wake_time: string | null;
  interruptions: number | null;
  extraction_notes: string[];
}

export interface MorningVitals {
  record_date: string;
  body_weight: number | null;
  body_fat_rate: number | null;
  blood_pressure_readings: BloodPressureReading[];
}

export interface MealEntry {
  meal_time_slot: "breakfast" | "lunch" | "dinner" | "snack";
  meal_raw_text: string;
  meal_tag: string[];
}

export type ExerciseType =
  | "aerobic"
  | "strength"
  | "core"
  | "stretching"
  | "yoga"
  | "walking"
  | "other";

export interface ExerciseDetail {
  type: ExerciseType;
  raw_name: string;
  duration_minutes: number | null;
  sets: number | null;
}

export interface LifestyleInterventions {
  meals: MealEntry[];
  exercise_type: ExerciseType[];
  exercise_duration: number | null;
  exercise_sets: number | null;
  exercise_details: ExerciseDetail[];
  exercise_raw_text: string | null;
  sleep: SleepObservation;
}

export interface PhysicalSignal {
  symptom_location: string | null;
  symptom_desc: string;
  symptom_trend: "better" | "same" | "worse" | "unclear" | null;
  symptom_triggers: string | null;
}

export interface MentalModel {
  today_highlight: string | null;
  tomorrow_one_change: string | null;
  execution_resistance: string | null;
  user_hypothesis: string | null;
}

export interface AIContent {
  ai_daily_summary: string | null;
  ai_hypothesis_validation: string | null;
}

export interface LedgerEntry {
  id: string;
  source: "legacy_import" | "user_entry";
  record_date: string;
  day_number: number | null;
  created_at: string | null;
  original_text: string;
  input_method: "import" | "text" | "voice" | "accessibility";
  extraction_status: "completed" | "partial" | "pending";
  legacy_feedback: Feedback | null;
  morning_vitals: MorningVitals;
  lifestyle: LifestyleInterventions;
  physical_signals: PhysicalSignal[];
  mental_model: MentalModel;
  ai_content: AIContent;
  context: {
    weather_temp: number | null;
    special_stress: string | null;
  };
}

export interface SceneSummary {
  id: "joint_pain" | "menstrual" | "emotion";
  title: string;
  record_count: number;
  latest_date: string | null;
  evidence_text: string;
  boundary: string;
}

export interface IntegrationStatus {
  voice_transcription: "not_configured" | "configuration_error" | "configured";
  language_model: "not_configured" | "configuration_error" | "configured";
  hardware_adapter: "interface_ready_not_configured";
  rag_retriever: "not_loaded" | "loaded_no_approved_chunks" | "ready";
}

export interface KnowledgePassage {
  chunk_id: string;
  title: string;
  content: string;
  source_publisher: string;
  source_title: string;
  source_url: string;
  safety_boundary: string;
  relevance_score: number;
  matched_terms: string[];
}

export interface RAGStatus {
  status: "not_loaded" | "loaded_no_approved_chunks" | "ready";
  total_chunk_count: number;
  approved_chunk_count: number;
}

export interface KnowledgeQuery {
  query: string;
  limit: 1 | 2 | 3;
}

export interface KnowledgePreview {
  query: string;
  passages: KnowledgePassage[];
}

export interface CompanionGenerationRequest {
  user_text: string;
}

export interface CompanionOutput {
  empathy: string;
  suggestion: string;
  outlook: string;
}

export interface GroundedCompanionResponse {
  output: CompanionOutput;
  passages: KnowledgePassage[];
}

export interface AppOverview {
  data_origin: "real";
  profile_display_name: "Amy";
  entry_count: number;
  recorded_day_count: number;
  first_date: string;
  last_date: string;
  calendar_span_days: number;
  missing_calendar_days: number;
  metric_coverage: {
    body_weight: number;
    body_fat_rate: number;
    blood_pressure: number;
    heart_rate: number;
    sleep_record: number;
    comparable_sleep_score: number;
  };
  latest_entry: LedgerEntry;
  recent_entries: LedgerEntry[];
  scene_summaries: SceneSummary[];
  integrations: IntegrationStatus;
}

export interface UserEntryCreate {
  record_date: string;
  original_text: string;
  input_method: "text" | "voice" | "accessibility";
}

export interface VoiceTranscript {
  text: string;
}

export interface DailySummary {
  record_date: string;
  entry_count: number;
  tags: string[];
  copy_lines: string[];
  recommend: string[];
  avoid: string[];
}

export interface MetricValue {
  date: string;
  text: string;
}

export interface SelfReportedPanel {
  anchor_date: string;
  body_weight: MetricValue | null;
  blood_pressure: MetricValue | null;
  basal_body_temp: MetricValue | null;
}

export interface HardwareSnapshot {
  heart_rate_bpm: number | null;
  spo2_percent: number | null;
  received_at: string;
}

export interface WeeklyOverview {
  recorded_days: number;
  hot_flash_count: number;
  hot_flash_change_percent: number | null;
  average_sleep_hours: number | null;
  sleep_change_percent: number | null;
}

export interface TrendsReport {
  anchor_date: string;
  hardware: HardwareSnapshot | null;
  self_reported: SelfReportedPanel;
  weekly: WeeklyOverview;
}
