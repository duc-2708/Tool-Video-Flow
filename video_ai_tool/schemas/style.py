"""Observed style, reusable presets and renderer defaults; no executable content."""
from typing import Literal
from pydantic import Field, ValidationError, ValidationInfo, field_validator, model_validator
from schemas.base import StrictModel, NonEmptyText
from schemas.style_normalize import StyleObservation,EMPTY,normalize_observation,text


class TranscriptPart(StyleObservation):
    text_field="summary"
    start_sec: float | None = Field(default=None,ge=0)
    end_sec: float | None = Field(default=None,gt=0)
    summary: str = "Không rõ"

    @model_validator(mode="after")
    def ordered(self):
        if self.start_sec is not None and self.end_sec is not None and self.end_sec <= self.start_sec:
            raise ValueError("Mốc kết thúc phải sau mốc bắt đầu.")
        return self


class StyleHook(StyleObservation):
    text_field="technique"
    technique: str = "Không rõ"
    template: str = ""
    word_count: int | None = Field(default=None,ge=0)


class StyleSection(StyleObservation):
    text_field="name"
    name: str = "Không rõ"
    duration_sec: float | None = Field(default=None,gt=0)
    purpose: str = "Không rõ"
    transition: str = "Không rõ"


class NarrationStyle(StyleObservation):
    text_field="voice_emotion"
    pronouns: list[str] = Field(default_factory=list)
    intimacy: str = "Không rõ"
    average_sentence_words: float | None = Field(default=None, gt=0, le=100)
    rhetorical_questions: str = "Không rõ"
    examples: str = "Không rõ"
    catchphrases: list[str] = Field(default_factory=list)
    humor: str = "Không rõ"
    words_per_sec: float | None = Field(default=None, gt=0, le=10)
    voice_gender_estimate: str | None = None
    voice_age_estimate: str | None = None
    voice_emotion: str = "Không rõ"


class StylePacing(StyleObservation):
    text_field="rhythm"
    average_shot_sec: float | None = Field(default=None,gt=0)
    cuts_per_10_sec: float | None = Field(default=None,ge=0)
    pattern_interrupts: list[float] = Field(default_factory=list)
    rhythm: str = "Không rõ"


class VisualStyle(StyleObservation):
    text_field="types"
    types: list[str] = Field(default_factory=list)
    transitions: list[str] = Field(default_factory=list)
    camera_effects: list[str] = Field(default_factory=list)
    aspect_ratio: str = "Không rõ"
    colors: list[str] = Field(default_factory=list)


class CaptionStyle(StyleObservation):
    appearance: Literal["classic", "pill"] = Field(default="classic",exclude_if=lambda v:v=="classic")
    text_field="font_description"
    enabled: bool = True
    mode: Literal["word", "phrase", "sentence"] = "phrase"
    font_description: str = "Chữ đậm dễ đọc"
    font_scale: float = Field(default=.064, ge=.03, le=.10)
    color: str | None = "#FFFFFF"
    highlight_color: str | None = "#FFD741"
    stroke_color: str | None = "#000000"
    color_note: str = ""
    stroke_width_ratio: float = Field(default=.006, ge=.001, le=.02)
    position: Literal["lower", "center", "top"] = "lower"
    emphasis: str = "Tô màu từ đang đọc"
    shadow: str = "Không rõ"

    @model_validator(mode="before")
    @classmethod
    def observed_colors(cls, value):
        from schemas.style_repairs import color_hex
        if not isinstance(value,dict): return value
        value=dict(value)
        warnings=list(value.get("analysis_warnings") or [])
        notes=[text(value["color_note"])] if value.get("color_note") else []
        for key in ("color","highlight_color","stroke_color"):
            if key not in value: continue
            original=value[key]
            if original is None: continue
            normalized=color_hex(original)
            if normalized!=original:
                notes.append(f"{key}: {text(original)}")
                warnings.append(f"{key}: {text(original)} → {normalized or 'None (không nhận diện được màu)'}.")
            value[key]=normalized
        value["color_note"]="; ".join(dict.fromkeys(notes))
        value["analysis_warnings"]=list(dict.fromkeys(warnings))
        return value


class AudioStyle(StyleObservation):
    text_field="details"
    mood: str = "calm"
    music_volume: float = Field(default=.08, ge=0, le=.35)
    sfx_types: list[str] = Field(default_factory=list)
    sfx_per_10_sec: float = Field(default=0, ge=0, le=10)
    sfx_positions: list[float] = Field(default_factory=list)
    ducking: bool = True
    details: str = "Không đủ dữ liệu"


class StyleEnding(StyleObservation):
    text_field="technique"
    technique: str = "Không rõ"
    has_cta: bool | None = None


class CategoryGuess(StyleObservation):
    text_field="category_id"
    category_id: str = ""
    confidence: float | None = Field(default=None,ge=0, le=1)
    reason: str = ""


class SceneOverlay(StyleObservation):
    text_field="text"
    text: str = ""
    position: str = "Không rõ"
    emphasis: str = "Không rõ"


class SceneTransition(StyleObservation):
    type: str = "Không rõ"
    connective_template: str = ""

    @model_validator(mode="before")
    @classmethod
    def aliases(cls,value):
        if isinstance(value,str):
            import re
            kind=next((k for k in ("cut","fade","zoom","whip","whoosh","dissolve") if re.search(r"\b"+k+r"\b",value,re.I)),"Không rõ")
            return {"type":kind,"connective_template":"" if value.strip().casefold()==kind else value}
        if isinstance(value,dict):
            value=dict(value)
            for old,new in (("kind","type"),("connective","connective_template")):
                if old in value and new not in value: value[new]=value[old]
        return value

    @property
    def kind(self): return self.type

    @property
    def connective(self): return self.connective_template


class ObservedScene(StyleObservation):
    start_sec: float = Field(ge=0)
    end_sec: float = Field(gt=0)
    purpose: NonEmptyText
    narration_summary: str = "Không rõ"
    word_count: int | None = Field(default=None,ge=0)
    words_per_sec: float | None = Field(default=None, ge=0, le=15)
    shot_count: int | None = Field(default=None,ge=1)
    average_shot_sec: float | None = Field(default=None,gt=0)
    visual_types: list[str] = Field(default_factory=list)
    camera_effects: list[str] = Field(default_factory=list)
    overlays: list[SceneOverlay] = Field(default_factory=list)
    sfx: list[str] = Field(default_factory=list)
    music: str = "Không rõ"
    transition_to_next: SceneTransition | None = None

    @field_validator("transition_to_next",mode="before")
    @classmethod
    def no_transition(cls,value):
        if value is None or isinstance(value,str) and value.strip().casefold() in EMPTY:
            return None
        return value

    @model_validator(mode="after")
    def valid_time(self):
        if self.end_sec <= self.start_sec:
            raise ValueError("Cảnh phải có end_sec sau start_sec.")
        if self.average_shot_sec is None and self.shot_count:
            self.average_shot_sec=(self.end_sec-self.start_sec)/self.shot_count
        if self.words_per_sec is None and self.word_count is not None:
            self.words_per_sec=self.word_count/(self.end_sec-self.start_sec)
        if self.average_shot_sec is not None and self.average_shot_sec > self.end_sec-self.start_sec+.5:
            self.analysis_warnings.append("average_shot_sec vượt độ dài cảnh; tính lại nếu có shot_count, nếu không để None.")
            self.average_shot_sec=(self.end_sec-self.start_sec)/self.shot_count if self.shot_count else None
        return self


class StyleAnalysis(StyleObservation):
    entities_in_video: list[str] = Field(default_factory=list)
    normalization_notes: list[str] = Field(default_factory=list)
    category_guess: CategoryGuess | None = None
    suggested_type: Literal["news", "review", "story"] | None = None
    scenes: list[ObservedScene] = Field(default_factory=list, max_length=250)
    narrative_flow: str = ""
    connective_phrases: list[str] = Field(default_factory=list, max_length=12)
    scene_count: int | None = Field(default=None, ge=1)
    avg_scene_sec: float | None = Field(default=None, gt=0)
    duration_sec: float | None = Field(default=None,gt=0, le=3600)
    transcript_outline: list[TranscriptPart] = Field(default_factory=list,max_length=150)
    hook: StyleHook = Field(default_factory=StyleHook)
    structure: list[StyleSection] = Field(default_factory=list,max_length=250)
    narration_style: NarrationStyle = Field(default_factory=NarrationStyle)
    pacing: StylePacing = Field(default_factory=StylePacing)
    visual_style: VisualStyle = Field(default_factory=VisualStyle)
    captions: CaptionStyle = Field(default_factory=CaptionStyle)
    audio: AudioStyle = Field(default_factory=AudioStyle)
    cta_ending: StyleEnding = Field(default_factory=StyleEnding)
    strengths: list[str] = Field(default_factory=list, max_length=5)
    weaknesses: list[str] = Field(default_factory=list, max_length=3)
    reusable_rules: list[str] = Field(default_factory=list, max_length=12)

    @model_validator(mode="before")
    @classmethod
    def normalize_terminal_scene(cls,value,info:ValidationInfo):
        from schemas.style_repairs import repair_timeline,seconds
        value=normalize_observation(cls,value)
        if isinstance(value,dict):
            warnings=list(value.get("analysis_warnings") or [])
            limit=seconds((info.context or {}).get("duration_limit"))
            if limit is None or limit<=0: limit=seconds(value.get("duration_sec"))
            if limit is not None and limit<=0: limit=None
            if limit is not None: value["duration_sec"]=limit
            value["scenes"]=repair_timeline(value.get("scenes",[]),limit,ObservedScene,"scenes",warnings)
            value["transcript_outline"]=repair_timeline(value.get("transcript_outline",[]),limit,TranscriptPart,"transcript_outline",warnings)
            if len(value["scenes"])>250:
                warnings.append("scenes: chỉ giữ 250 cảnh đầu trong phân tích; bản thô giữ nguyên.")
                value["scenes"]=value["scenes"][:250]
            if len(value["transcript_outline"])>150:
                warnings.append("transcript_outline: chỉ giữ 150 mục đầu; bản thô giữ nguyên.")
                value["transcript_outline"]=value["transcript_outline"][:150]
            if value["scenes"]: value["scenes"][-1].transition_to_next=None
            sections=value.get("structure",[])
            if not isinstance(sections,list): sections=[sections] if sections else []
            value["structure"]=[]
            for section in sections[:250]:
                try: value["structure"].append(StyleSection.model_validate(section))
                except ValidationError: warnings.append("structure: bỏ mục phụ không hợp lệ; suy ra từ purpose của cảnh.")
            try: value["hook"]=StyleHook.model_validate(value.get("hook") or {})
            except ValidationError:
                warnings.append("hook: dùng purpose của cảnh đầu do mô tả hook không hợp lệ.")
                value["hook"]=StyleHook()
            value["analysis_warnings"]=warnings
            for name,limit in (("reusable_rules",12),("connective_phrases",12),("strengths",5),("weaknesses",3)):
                if isinstance(value.get(name),list): value[name]=value[name][:limit]
        return value

    @model_validator(mode="after")
    def timeline_bounds(self):
        if self.category_guess and not self.category_guess.category_id:
            self.category_guess=None
        if not self.scenes:
            raise ValueError("scenes: cần ít nhất 1 cảnh hợp lệ có start_sec, end_sec, purpose; không bịa cảnh thay thế.")
        self.transcript_outline=[p for p in self.transcript_outline if p.start_sec is not None and p.end_sec is not None]
        if self.duration_sec is None:
            self.duration_sec=max([s.end_sec for s in self.scenes]+[p.end_sec for p in self.transcript_outline],default=None)
        if self.duration_sec is None:
            raise ValueError("Cần các cảnh có start_sec/end_sec để xác định thời lượng.")
        if self.hook.technique.strip().casefold() in EMPTY and not self.hook.template:
            self.hook.technique=self.scenes[0].purpose
            self.analysis_warnings.append("hook: dùng purpose đã quan sát ở cảnh đầu vì thiếu mô tả riêng.")
        if self.scenes and (not self.structure or any(p.duration_sec is None for p in self.structure)):
            self.structure=[StyleSection(name=s.purpose,purpose=s.purpose,duration_sec=s.end_sec-s.start_sec) for s in self.scenes]
        if self.scenes and not self.transcript_outline:
            self.transcript_outline=[TranscriptPart(start_sec=s.start_sec,end_sec=s.end_sec,summary=s.narration_summary)
                for s in self.scenes if s.narration_summary and s.narration_summary!="Không rõ"]
        self.pacing.pattern_interrupts=[t for t in self.pacing.pattern_interrupts if 0<=t<=self.duration_sec]
        self.audio.sfx_positions=[t for t in self.audio.sfx_positions if 0<=t<=self.duration_sec]
        if self.scenes:
            self.scenes[-1].transition_to_next=None
            if self.scene_count is not None and self.scene_count != len(self.scenes):
                self.normalization_notes.append(f"scene_count={self.scene_count} được đồng bộ về {len(self.scenes)} cảnh có trong dữ liệu.")
            average=sum(s.end_sec-s.start_sec for s in self.scenes)/len(self.scenes)
            if self.avg_scene_sec is not None and abs(self.avg_scene_sec-average) > max(.5,average*.1):
                self.normalization_notes.append("avg_scene_sec được tính lại từ start_sec/end_sec của các cảnh.")
            self.scene_count=len(self.scenes)
            self.avg_scene_sec=average
        from schemas.style_repairs import collect_warnings
        self.analysis_warnings=list(dict.fromkeys(self.analysis_warnings+self.normalization_notes+collect_warnings(self)))
        # Compatibility for existing CLI/profile consumers.
        self.normalization_notes=list(self.analysis_warnings)
        return self


class AnalysisRecord(StrictModel):
    version: int = 1
    filename: str
    file_hash: str
    notes_hash: str
    model: str
    prompt_hash: str
    warnings: list[str] = Field(default_factory=list)
    category_id: str | None = None
    category_confirmed: bool = False
    analysis: StyleAnalysis

    @model_validator(mode="after")
    def observation_warnings(self):
        self.warnings=list(dict.fromkeys(self.warnings+self.analysis.analysis_warnings))
        return self


class RuleFrequency(StrictModel):
    rule: NonEmptyText
    video_count: int = Field(ge=1)


class PaceRange(StrictModel):
    mean: float = Field(gt=0)
    minimum: float = Field(gt=0)
    maximum: float = Field(gt=0)


class ProfileSection(StrictModel):
    name: str
    fraction: float = Field(gt=0, le=1)


class SceneDurationProfile(StrictModel):
    duration_sec: float = Field(gt=0)
    scene_count: int = Field(ge=2)
    min_scene_count: int = Field(ge=1)
    max_scene_count: int = Field(ge=1)
    avg_scene_sec: float = Field(gt=0)
    min_scene_sec: float = Field(gt=0)
    max_scene_sec: float = Field(gt=0)
    durations_sec: list[float] = Field(min_length=2)


class ScenePattern(StrictModel):
    purpose: str
    fraction: float = Field(gt=0, le=1)
    shot_count: float | None = Field(default=None,gt=0)
    average_shot_sec: float | None = Field(default=None,gt=0)
    visual_types: list[str]
    effects: list[str]
    overlay_styles: list[str]
    sfx: list[str]
    transition: str
    connective_template: str = ""


class VisualTemplateRatios(StrictModel):
    # Fixed fields keep EditPlan's structured-output schema free of free maps.
    hook_card: float = Field(default=1,ge=0)
    stat_card: float = Field(default=1,ge=0)
    ring_percent: float = Field(default=1,ge=0)
    strike_replace: float = Field(default=1,ge=0)
    versus: float = Field(default=1,ge=0)
    compare_bars: float = Field(default=1,ge=0)
    line_growth: float = Field(default=1,ge=0)
    steps_list: float = Field(default=1,ge=0)
    timeline: float = Field(default=1,ge=0)
    text_focus: float = Field(default=1,ge=0)
    icon_card: float = Field(default=1,ge=0)
    quote_card: float = Field(default=1,ge=0)
    cta_card: float = Field(default=1,ge=0)


class StyleProfile(StrictModel):
    visual_template_ratios: VisualTemplateRatios | None = Field(default=None,exclude_if=lambda v:v is None)
    visual_theme: str = Field(default="studio",exclude_if=lambda v:v=="studio")
    visual_templates: bool = Field(default=True,exclude_if=lambda v:v)
    progress_tracker: bool = Field(default=False,exclude_if=lambda v:not v)
    progress_labels: list[str] = Field(default_factory=list,exclude_if=lambda v:not v)
    reference_entities: list[str] = Field(default_factory=list,exclude_if=lambda value:not value)
    version: int = 1
    name: NonEmptyText
    slug: NonEmptyText
    reference_hashes: list[str]
    reference_files: list[str]
    # Never include these in Director prompts; local comparison only.
    reference_texts: list[str]
    hook_templates: list[str]
    hook_techniques: list[str]
    structure: list[ProfileSection]
    shot_seconds: PaceRange
    speech_words_per_sec: PaceRange
    narration_rules: list[str]
    broll_patterns: list[str]
    visual_effects: list[str]
    transitions: list[str]
    captions: CaptionStyle
    audio: AudioStyle
    ending_techniques: list[str]
    reusable_rules: list[str]
    rule_frequencies: list[RuleFrequency]
    category_id: str | None = None
    video_type: Literal["news", "review", "story"] | None = None
    video_count: int = Field(default=0, ge=0)
    confidence_label: Literal["yếu", "đang tích lũy", "ổn", "mặc định"] = "yếu"
    source_signature: str = ""
    locked_fields: list[Literal["reusable_rules", "connective_phrases"]] = Field(default_factory=list)
    scene_pacing: list[SceneDurationProfile] = Field(default_factory=list)
    narrative_flows: list[str] = Field(default_factory=list)
    connective_phrases: list[str] = Field(default_factory=list)
    connective_frequencies: list[RuleFrequency] = Field(default_factory=list)
    scene_patterns: list[ScenePattern] = Field(default_factory=list)
    shots_per_10_sec: float = Field(default=0, ge=0)
    warnings: list[str] = Field(default_factory=list)


class StyleRenderDefaults(StrictModel):
    theme: str = Field(default="studio",exclude_if=lambda v:v=="studio")
    visual_templates: bool = Field(default=True,exclude_if=lambda v:v)
    progress_tracker: bool = Field(default=False,exclude_if=lambda v:not v)
    progress_labels: list[str] = Field(default_factory=list,exclude_if=lambda v:not v)
    captions: CaptionStyle = Field(default_factory=CaptionStyle)
    ducking: bool = True
