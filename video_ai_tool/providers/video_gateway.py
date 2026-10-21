"""Hinton OpenAI-compatible Videos API, separate from chat and Google Gemini.

Protocol reference: https://api.buihuuthang.com/docs/video (2026-10-20).
POST is NEVER retried automatically: a lost response can still represent a paid job.
"""
from typing import Literal
from urllib.parse import urlsplit,quote
import time
import json
import requests
from pydantic import Field,model_validator,field_validator
from schemas.base import StrictModel,NonEmptyText
from utils.diagnostics import Diagnostics
from agents.video_prompt_writer import sanitize_video_prompt

from config.video_models import VIDEO_MODELS as MODELS


def allowed_models(settings):
    return [name for name in settings.gateway_allowed_models if name in MODELS]


def require_allowed_model(settings, model):
    if model not in allowed_models(settings):
        raise GatewayVideoError(f"Model {model} không được phép trong GATEWAY_ALLOWED_MODELS. Model hợp lệ: {', '.join(allowed_models(settings)) or '(trống)'}. Kiểm tra quyền model của key gateway.")


class VideoRequest(StrictModel):
    model: str = "veo-3.1"
    prompt: NonEmptyText = Field(max_length=8000)
    seconds: int = 4
    format: Literal["tiktok","youtube"] = "tiktok"
    resolution: Literal["720p","1080p"] = "720p"

    @field_validator("model")
    @classmethod
    def supported_model(cls, value):
        if value not in MODELS:
            raise ValueError(f"Model {value} không hợp lệ; chọn: {', '.join(MODELS)}. Không tự đổi model của job trả phí.")
        return value

    @model_validator(mode="after")
    def valid_parameters(self):
        if self.seconds not in MODELS[self.model]:
            raise ValueError(f"{self.model} chỉ nhận số giây: {MODELS[self.model]}")
        if self.resolution == "1080p" and self.model != "veo-3.1":
            raise ValueError("1080p chỉ dùng cho Veo 3.1 trên gateway này.")
        return self

    def payload(self):
        body = {"model":self.model,"prompt":self.prompt,"seconds":self.seconds,
                "aspect_ratio":"9:16" if self.format == "tiktok" else "16:9"}
        if self.model == "veo-3.1":
            body["resolution"] = self.resolution
        return body

    @property
    def estimated_cost_vnd(self):
        if self.model == "veo-3.1":
            return 2500
        return {5:2800,10:4300,15:6300}.get(self.seconds,9300)



class GatewayVideoError(RuntimeError):
    pass


class GenerationFailed(GatewayVideoError):
    """Only this confirmed terminal provider error permits one new paid attempt."""


class AmbiguousSubmission(GatewayVideoError):
    """Never issue another paid POST until the original is reconciled."""


class VideoGateway:
    def __init__(self,settings,diagnostics=None,session=None):
        self.settings = settings
        self.key = settings.gateway_api_key.get_secret_value().strip()
        self.base = settings.gateway_base_url.rstrip("/")
        parsed = urlsplit(self.base)
        # Bind this credential to its intended host; never send it to redirects.
        if parsed.scheme != "https" or parsed.netloc != "api.buihuuthang.com" or parsed.path != "/v1" or parsed.query or parsed.fragment:
            raise ValueError("GATEWAY_BASE_URL phải là https://api.buihuuthang.com/v1")
        if not self.key:
            raise ValueError("Thiếu GATEWAY_API_KEY. Điền key gateway trong cấu hình local.")
        self.diagnostics = diagnostics or Diagnostics(settings.logs_dir,filename="gateway_video_errors.log",secrets=[self.key])
        if self.key not in self.diagnostics.secrets:
            self.diagnostics.secrets.append(self.key)
        self.session = session or requests.Session()

    def close(self):
        self.session.close()

    def _request(self,method,path,*,params=None,body=None,stream=False):
        attempts = self.settings.retry_attempts if method == "GET" else 1
        for attempt in range(attempts):
            response = None
            try:
                response = self.session.request(method,self.base+path,
                    headers={"Authorization":"Bearer "+self.key,"Accept":"video/mp4" if stream else "application/json"},
                    params=params,json=body,stream=stream,allow_redirects=False,
                    timeout=(min(10,self.settings.request_timeout_sec),self.settings.request_timeout_sec))
                code = response.status_code
                if code >= 400 or 300 <= code < 400:
                    try:
                        raw_error = response.json()
                        message = raw_error.get("error",raw_error.get("message",raw_error)) if isinstance(raw_error,dict) else raw_error
                        message = message.get("message",message) if isinstance(message,dict) else message
                    except (ValueError,AttributeError):
                        message = "Phản hồi không phải JSON."
                        raw_error = getattr(response, "text", "")
                    self.diagnostics.record(json.dumps({"event":"gateway_http_error", "http_status":code,
                        "remote_id":path.split("/")[2] if method == "GET" and path.startswith("/videos/") else None,
                        "request":body or params, "response":raw_error}, ensure_ascii=False, default=str))
                    detail = self.diagnostics.redact(str(message))[:1500]
                    if code == 403:
                        model = (body or params or {}).get("model", "đã yêu cầu")
                        detail = (f"Key gateway chưa có quyền dùng model {model} hoặc tài nguyên này. "
                                  f"Model được cấu hình: {', '.join(allowed_models(self.settings))}. "
                                  f"Kiểm tra quyền model trên dashboard. Lỗi gốc: {detail}")
                    error = GatewayVideoError(f"Gateway HTTP {code}: {detail}")
                    self.diagnostics.record_exception(error,f"Videos API {method} {path}")
                    response.close()
                    if method == "GET" and (code in {408,429} or code >= 500) and attempt+1 < attempts:
                        time.sleep(min(4,2**attempt))
                        continue
                    if method == "POST" and (code >= 500 or code in {408,429} or 300 <= code < 400):
                        raise AmbiguousSubmission(f"{error} Chưa chắc yêu cầu đã tạo job; không tự gửi lại. Kiểm tra dashboard gateway.")
                    raise error
                return response
            except requests.RequestException as error:
                if response is not None:
                    response.close()
                self.diagnostics.record_exception(error,f"Videos API {method} {path}")
                if method == "POST":
                    if isinstance(error,requests.Timeout):
                        raise AmbiguousSubmission("Timeout khi gửi tạo video. Có thể đã tính phí; kiểm tra dashboard để lấy ID, không gửi lại tự động.") from None
                    raise AmbiguousSubmission("Mất kết nối khi gửi tạo video. Có thể đã tính phí; kiểm tra dashboard để lấy ID, không gửi lại tự động.") from None
                if attempt+1 == attempts:
                    raise GatewayVideoError("Không kết nối được gateway sau các lần thử; xem logs/gateway_video_errors.log.") from None
                time.sleep(min(4,2**attempt))

    def _json(self,method,path,**kwargs):
        response = self._request(method,path,**kwargs)
        try:
            data = response.json()
            if not isinstance(data,dict):
                raise ValueError("Videos API không trả JSON object.")
            if method == "GET" and (data.get("status") in {"failed","error","generation_failed","cancelled","canceled"} or data.get("error")):
                self.diagnostics.record(json.dumps({"event":"gateway_error_response", "http_status":response.status_code,
                    "remote_id":data.get("id") or path.split("/")[-1],"request":kwargs.get("body") or kwargs.get("params"),
                    "response":data},ensure_ascii=False,default=str))
            return data,response.headers.get("x-buihuuthang-cost-vnd")
        except (ValueError,TypeError) as error:
            self.diagnostics.record_exception(error,"Parse phản hồi Videos API")
            if method == "POST":
                raise AmbiguousSubmission("Gateway đã nhận POST nhưng phản hồi không đọc được. Kiểm tra dashboard; không tự gửi lại.") from None
            raise GatewayVideoError("Không đọc được JSON từ gateway; xem log lỗi gốc.") from None
        finally:
            response.close()

    def models(self):
        data,_ = self._json("GET","/models")
        return [item for item in data.get("data",[]) if isinstance(item,dict) and item.get("id") in allowed_models(self.settings)]

    def create(self,request):
        request = request.model_copy(update={"prompt":sanitize_video_prompt(request.prompt)})
        self.diagnostics.record(json.dumps({"event":"gateway_submit", "request":request.payload(), "remote_id":None}, ensure_ascii=False))
        require_allowed_model(self.settings, request.model)
        data,cost = self._json("POST","/videos",body=request.payload())
        if not isinstance(data.get("id"),str) or not data["id"].strip():
            raise AmbiguousSubmission("POST tạo video thiếu ID. Kiểm tra dashboard; không gửi lại tự động.")
        return data,cost

    def status(self,job_id,model):
        data,_ = self._json("GET",f"/videos/{quote(job_id,safe='')}",params={"model":model})
        return data

    def download(self,job_id,model):
        return self._request("GET",f"/videos/{quote(job_id,safe='')}/content",params={"model":model,"variant":"video"},stream=True)
