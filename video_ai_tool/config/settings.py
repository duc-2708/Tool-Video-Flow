# file: config/settings.py

"""Nạp cấu hình local, không yêu cầu API key cho bước kiểm tra offline."""

import os

import json

from pathlib import Path

from typing import Literal



from dotenv import dotenv_values

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, SecretStr, ValidationError, field_validator, model_validator



from config.video_models import VIDEO_MODELS



ROOT_DIR = Path(__file__).resolve().parents[1]

DEFAULT_ENV_FILE = ROOT_DIR / ".env"





class Settings(BaseModel):

    model_config = ConfigDict(extra="forbid", frozen=True)



    root_dir: Path = ROOT_DIR

    render_width: int = Field(default=1080,ge=240,le=3840)

    render_height: int = Field(default=1920,ge=240,le=3840)

    motion_enabled: bool = False

    motion_fps: int = Field(default=30,ge=1,le=60)

    motion_scale: float = Field(default=1.,ge=.25,le=1.)

    motion_workers: int = Field(default=2,ge=1,le=4)

    motion_theme: str = "auto"

    mascot_enabled: bool = True

    motion_scenes_enabled: bool = True

    min_card_hold_sec: float = Field(default=1.2,ge=.3,le=5)

    script_v3_enabled: bool = False

    max_elements_on_screen: int = Field(default=3, ge=1, le=10)

    grounding_mode: Literal["fix", "warn", "block"] = "fix"

    stage_engine_enabled: bool = False
    depth_3d_enabled: bool = False
    motion_recipes_enabled: bool = True

    @field_validator('motion_scenes_enabled','min_card_hold_sec','script_v3_enabled','max_elements_on_screen','grounding_mode','stage_engine_enabled','depth_3d_enabled','motion_recipes_enabled',mode='before')

    @classmethod

    def optional_scenes(cls,value,info):

        if value is None or isinstance(value,str) and not value.strip():

            return {'motion_scenes_enabled':True,'min_card_hold_sec':1.2,'script_v3_enabled':False,'max_elements_on_screen':3,'grounding_mode':'fix','stage_engine_enabled':False,'depth_3d_enabled':False,'motion_recipes_enabled':True}[info.field_name]

        return value

    @field_validator("motion_enabled","motion_fps","motion_scale","motion_workers","motion_theme","mascot_enabled",mode="before")

    @classmethod

    def optional_motion_defaults(cls,value,info):

        if value is None or isinstance(value,str) and not value.strip():

            return {"motion_enabled":False,"motion_fps":30,"motion_scale":1.,"motion_workers":2,"motion_theme":"auto","mascot_enabled":True}[info.field_name]

        return value

    openai_api_key: SecretStr = SecretStr("")

    openai_model: str = ""

    openai_director_model: str = ""

    openai_script_model: str = ""

    openai_timeout_sec: float = Field(default=120,gt=0,le=600)

    openai_rpm_limit: int = Field(default=20,ge=1,le=1000)

    openai_max_retries: int = Field(default=3,ge=0,le=8)

    llm_provider_researcher: str = "gemini"

    llm_provider_director: str = "gemini"

    llm_provider_trend: str = "gemini"

    llm_provider_script: str = ""

    llm_provider_visual: str = ""

    llm_fallback_provider: str = ""

    _llm_configuration_warnings: tuple[str,...] = PrivateAttr(default=())

    gemini_api_key: SecretStr = SecretStr("")

    gemini_model: str = ""

    gemini_director_model: str = ""

    gemini_fallback_model: str = ""

    gemini_timeout_sec: float = Field(default=120,gt=0,le=600)

    gemini_style_model: str = ""
    style_analysis_model: str = ""

    style_max_videos_per_run: int = Field(default=5, ge=1, le=20)

    style_max_file_mb: int = Field(default=200, ge=1, le=2000)

    style_max_duration_sec: float = Field(default=600, ge=1, le=3600)

    style_timeout_sec: float = Field(default=180, ge=10, le=300)

    style_max_output_tokens: int = Field(default=8192,ge=1024,le=65536)

    style_media_resolution: Literal["low","medium","none"] = "low"

    style_use_response_schema: bool = True

    style_schema_mode: Literal["flat","essential"] = "flat"

    style_compact_output: bool = False

    style_max_video_sec: float = Field(default=180,gt=0,le=600)

    style_video_fps: float = Field(default=.5, gt=0, le=1)

    style_tpm_limit: int = Field(default=250000, ge=1000)

    style_rpm_limit: int = Field(default=2, ge=1, le=1000)

    style_request_interval_sec: float = Field(default=5, ge=0, le=300)

    scan_max_video_sec: float = Field(default=180, ge=1, le=3600)

    scan_max_age_days: int = Field(default=180, ge=1, le=3650)

    scan_max_new_videos: int = Field(default=5, ge=1, le=20)

    gateway_api_key: SecretStr = SecretStr("")

    gateway_base_url: str = "https://api.buihuuthang.com/v1"

    gateway_video_model: str = "veo-3.1"

    gateway_allowed_models: list[str] = Field(default_factory=lambda: ["veo-3.1", "seedance-2.5-30s"])

    ai_clip_seconds: int = Field(default=4, ge=1, le=30)

    ai_clip_max_per_run: int = Field(default=3, ge=0, le=20)

    ai_clips_per_video: int = Field(default=0,ge=0,le=20)
    ai_clips_max_per_video: int = Field(default=2, ge=0, le=10)
    ai_clip_mode: str = Field(default="off")
    ai_clip_auto_approve: bool = Field(default=False)
    ai_clip_daily_limit: int = Field(default=5, ge=0, le=100)
    ai_clip_stall_sec: int = Field(default=120, ge=30, le=600)
    scene_director_enabled: bool = Field(default=True)

    ai_clip_model: str = ""

    ai_clip_max_sec: int = Field(default=6,ge=1,le=30)

    ai_clip_budget_per_day: int = Field(default=3,ge=0,le=100)

    @field_validator('ai_clips_per_video','ai_clip_model','ai_clip_max_sec','ai_clip_budget_per_day',mode='before')

    @classmethod

    def optional_controlled_ai(cls,value,info):

        if value is None or isinstance(value,str) and not value.strip():

            return {'ai_clips_per_video':0,'ai_clip_model':'','ai_clip_max_sec':6,'ai_clip_budget_per_day':3}[info.field_name]

        return value

    @field_validator('ai_clip_mode')
    @classmethod
    def validate_ai_clip_mode(cls, value):
        v = str(value or "off").strip().lower()
        if v not in {"off", "auto", "manual"}:
            return "off"
        return v

    @field_validator('ai_clip_model')

    @classmethod

    def controlled_model(cls,value):

        if value and value not in VIDEO_MODELS: raise ValueError('AI_CLIP_MODEL chỉ nhận veo-3.1 hoặc seedance-2.5-30s.')

        return value

    youtube_api_key: SecretStr = SecretStr("")

    scrapecreators_api_key: SecretStr = SecretStr("")

    pexels_api_key: SecretStr = SecretStr("")

    pixabay_api_key: SecretStr = SecretStr("")

    default_voice: Literal["vi-VN-HoaiMyNeural", "vi-VN-NamMinhNeural"] = "vi-VN-HoaiMyNeural"

    default_voice_fallback: Literal["vi-VN-HoaiMyNeural", "vi-VN-NamMinhNeural"] = "vi-VN-NamMinhNeural"

    request_timeout_sec: float = Field(default=30, gt=0, le=300)

    retry_attempts: int = Field(default=3, ge=1, le=8)

    cache_ttl_sec: int = Field(default=86400, ge=1)

    youtube_daily_quota: int = Field(default=10000, ge=1, le=10000)

    youtube_max_searches_per_run: int = Field(default=2, ge=0, le=10)

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"



    @model_validator(mode="wrap")

    @classmethod

    def optional_llm_configuration(cls, data, handler):

        """Blank/new invalid options cannot prevent unrelated local pages loading."""

        if not isinstance(data,dict): return handler(data)

        data=dict(data);warnings=[]

        for name,default in (("openai_timeout_sec",120),("openai_rpm_limit",20),("openai_max_retries",3)):

            value=data.get(name)

            if value is None or isinstance(value,str) and not value.strip():

                data[name]=default;continue

            try:

                number=float(value)

                maximum=600 if name=="openai_timeout_sec" else 1000 if name=="openai_rpm_limit" else 8

                minimum=0 if name in {"openai_max_retries","openai_timeout_sec"} else 1

                if isinstance(value,bool) or not minimum<=number<=maximum or name=="openai_timeout_sec" and number==0 or name!="openai_timeout_sec" and not number.is_integer(): raise ValueError

                data[name]=number if name=="openai_timeout_sec" else int(number)

            except (TypeError,ValueError,OverflowError):

                data[name]=default;warnings.append(f"{name.upper()} không hợp lệ; dùng mặc định {default}.")

        for name in ("llm_provider_researcher","llm_provider_director","llm_provider_trend","llm_provider_script","llm_provider_visual","llm_fallback_provider"):

            value=str(data.get(name) or "").strip().lower()

            if not value and name in {"llm_provider_researcher","llm_provider_director","llm_provider_trend"}: value="gemini"

            if value not in {"gemini","openai",""}:

                warnings.append(f"{name.upper()} chỉ chấp nhận gemini/openai; lựa chọn này đã tắt.")

            data[name]=value

        for name in ("openai_model","openai_director_model","openai_script_model"): data[name]=str(data.get(name) or "").strip()

        if data.get("openai_api_key") is None: data["openai_api_key"]=""

        result=handler(data)

        result._llm_configuration_warnings=tuple(warnings)

        return result



    @property

    def llm_configuration_warnings(self): return list(self._llm_configuration_warnings)



    @field_validator("gateway_allowed_models", mode="before")

    @classmethod

    def parse_allowed_models(cls, value):

        if isinstance(value, str):

            value = json.loads(value) if value.strip().startswith("[") else value.split(",")

        return list(dict.fromkeys(item.strip() for item in value if item.strip()))



    @model_validator(mode="after")

    def validate_gateway_defaults(self):

        if self.gateway_video_model not in VIDEO_MODELS:

            raise ValueError("GATEWAY_VIDEO_MODEL chỉ nhận veo-3.1 hoặc seedance-2.5-30s.")

        if "ai_clip_seconds" not in self.model_fields_set:

            object.__setattr__(self, "ai_clip_seconds", VIDEO_MODELS[self.gateway_video_model][0])

        if self.ai_clip_seconds not in VIDEO_MODELS[self.gateway_video_model]:

            raise ValueError(f"AI_CLIP_SECONDS không hợp lệ cho {self.gateway_video_model}; chọn {VIDEO_MODELS[self.gateway_video_model]}.")

        if any(model not in VIDEO_MODELS for model in self.gateway_allowed_models):

            raise ValueError("GATEWAY_ALLOWED_MODELS chỉ nhận veo-3.1, seedance-2.5-30s.")

        return self



    @property

    def cache_dir(self) -> Path:

        return self.root_dir / ".cache"



    @property

    def output_dir(self) -> Path:

        return self.root_dir / "output"



    @property

    def logs_dir(self) -> Path:

        return self.root_dir / "logs"



    @property

    def prompts_dir(self) -> Path:

        return self.root_dir / "prompts"



    def ensure_directories(self) -> None:

        for path in (self.cache_dir, self.output_dir, self.logs_dir):

            path.mkdir(parents=True, exist_ok=True)



    def require_key(self, provider: Literal["gemini", "youtube", "pexels", "pixabay"]) -> str:

        value = getattr(self, f"{provider}_api_key").get_secret_value().strip()

        if not value:

            raise ValueError(f"Thiếu {provider.upper()}_API_KEY. Hãy điền trong {self.root_dir / '.env'}.")

        return value



    def require_gemini_model(self) -> str:

        if not self.gemini_model.strip():

            raise ValueError("Thiếu GEMINI_MODEL. Hãy chọn model đang có trong tài khoản và điền vào .env.")

        return self.gemini_model.strip()



    def require_director_model(self) -> str:

        return self.gemini_director_model.strip() or self.require_gemini_model()



    def require_style_model(self) -> str:

        return self.style_analysis_model.strip() or self.gemini_style_model.strip() or self.require_gemini_model()





def read_configuration_values(env_file: Path | None = None) -> dict[str, str | None]:

    """Một nơi chọn file cấu hình; không gọi load_dotenv hoặc sửa os.environ."""

    path = DEFAULT_ENV_FILE if env_file is None else env_file

    return {**dotenv_values(path), **os.environ}





def get_settings(env_file: Path | None = None) -> Settings:

    """Biến môi trường ưu tiên hơn file chỉ định; không nạp thêm .env khác."""

    values = read_configuration_values(env_file)

    fields = Settings.model_fields.keys() - {"root_dir"}

    return Settings(**{key: values[key.upper()] for key in fields if values.get(key.upper()) is not None})





if __name__ == "__main__":

    from utils.console import configure_console



    configure_console()

    try:

        settings = get_settings()

        settings.ensure_directories()

    except (ValidationError, ValueError, OSError):

        raise SystemExit("Cấu hình không hợp lệ hoặc không thể ghi thư mục. Kiểm tra .env theo .env.example.") from None

    print(f"Cấu hình hợp lệ. Thư mục dự án: {settings.root_dir}")

    print("API key không được in ra log. Kiểm tra offline không cần key.")

