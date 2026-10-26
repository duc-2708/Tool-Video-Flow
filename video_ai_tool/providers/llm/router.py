"""Per-stage text routing; at most one explicit cross-provider failover per call."""
import importlib.util
import json
from providers.llm.base import LLMClient, TransientError, ConfigurationError, OutputError
from providers.llm_base import LLMProvider
from utils.diagnostics import Diagnostics


def model_for(settings,provider,step):
    if provider=="gemini":
        return (settings.gemini_director_model.strip() if step in {"director","script","visual"} else "") or settings.gemini_model.strip()
    if provider=="openai":
        if step=="script" and getattr(settings,"openai_script_model",""):
            return settings.openai_script_model.strip()
        return (settings.openai_director_model.strip() if step in {"director","script","visual"} else "") or settings.openai_model.strip()
    return ""


def unavailable_reason(settings,provider,step):
    if provider not in {"gemini","openai"}:
        return f"LLM_PROVIDER_{step.upper()} không hợp lệ; chỉ nhận gemini/openai."
    names=[]
    if not getattr(settings,provider+"_api_key").get_secret_value().strip(): names.append(provider.upper()+"_API_KEY")
    if not model_for(settings,provider,step):
        names.append(provider.upper()+"_DIRECTOR_MODEL hoặc "+provider.upper()+"_MODEL" if step in {"director","script","visual"} else provider.upper()+"_MODEL")
    if names: return f"Provider {provider} đã tắt: thiếu "+", ".join(names)+"."
    if provider=="openai" and importlib.util.find_spec("openai") is None:
        return "Provider openai đã tắt: thiếu SDK openai; cài requirements.txt."
    return None


def route_ready(settings,step):
    primary=getattr(settings,"llm_provider_"+step,"") or settings.llm_provider_director if step in {"script","visual"} else getattr(settings,"llm_provider_"+step)
    fallback=settings.llm_fallback_provider
    return not unavailable_reason(settings,primary,step) or fallback in {"gemini","openai"} and fallback!=primary and not unavailable_reason(settings,fallback,step)


def require_route(settings,step):
    if not route_ready(settings,step):
        primary=getattr(settings,"llm_provider_"+step,"") or settings.llm_provider_director if step in {"script","visual"} else getattr(settings,"llm_provider_"+step)
        raise ConfigurationError(unavailable_reason(settings,primary,step)+" Kiểm tra cấu hình LLM và LLM_FALLBACK_PROVIDER.")


class Router(LLMClient):
    def __init__(self,settings,step,*,diagnostics=None,clients=None):
        if step not in {"researcher","director","trend","script","visual"}:
            raise ConfigurationError("Router chỉ dành cho text Researcher/Director/Trend; Style Learner chỉ dùng Gemini.")
        self.settings,self.step=settings,step
        self.primary=(getattr(settings,"llm_provider_"+step,"") or settings.llm_provider_director) if step in {"script","visual"} else getattr(settings,"llm_provider_"+step)
        self.fallback=settings.llm_fallback_provider
        self.diagnostics=diagnostics or Diagnostics(settings.logs_dir,filename="llm_errors.log",secrets=[
            settings.openai_api_key.get_secret_value(),settings.gemini_api_key.get_secret_value()])
        self._secure_diagnostics()
        self.progress=lambda message:None
        self.request_observer=None
        self.warnings=[];self.clients=dict(clients or {})
        for warning in settings.llm_configuration_warnings: self.warn(warning)

    def _secure_diagnostics(self):
        self.diagnostics.secrets=sorted(set(self.diagnostics.secrets) | {key for key in (
            self.settings.openai_api_key.get_secret_value(),self.settings.gemini_api_key.get_secret_value()) if key},key=len,reverse=True)

    @property
    def model_name(self):
        # Existing Gemini-only checkpoint/cache identities remain reusable on upgrade.
        if self.primary=="gemini" and not self.fallback:
            return model_for(self.settings,"gemini",self.step)
        identity=f"{self.primary}:{model_for(self.settings,self.primary,self.step)}"
        if self.fallback in {"gemini","openai"} and self.fallback!=self.primary:
            identity+=f"|fallback={self.fallback}:{model_for(self.settings,self.fallback,self.step)}"
        if self.primary=="gemini" and self.settings.gemini_fallback_model:
            identity+="|gemini_fallback="+self.settings.gemini_fallback_model.strip()
        return identity

    def warn(self,message):
        message=self.diagnostics.redact(message)
        if message not in self.warnings: self.warnings.append(message)
        self.diagnostics.record(message);self.progress(message)

    def _client(self,name):
        if name not in self.clients:
            if name=="gemini":
                from providers.llm.gemini_client import GeminiClient
                cls=GeminiClient
            else:
                from providers.llm.openai_client import OpenAIClient
                cls=OpenAIClient
            self.clients[name]=cls(self.settings,model=model_for(self.settings,name,self.step),diagnostics=self.diagnostics)
        self._secure_diagnostics()
        client=self.clients[name]
        client.diagnostics=self.diagnostics;client.progress=self.progress;client.request_observer=self.request_observer
        return client

    def _call(self,method,prompt,kwargs):
        primary_missing=unavailable_reason(self.settings,self.primary,self.step)
        fallback_ready=self.fallback in {"gemini","openai"} and self.fallback!=self.primary and not unavailable_reason(self.settings,self.fallback,self.step)
        if primary_missing:
            if not fallback_ready: raise ConfigurationError(primary_missing)
            self.warn(f"LLM {self.step}: {primary_missing} Dùng provider dự phòng {self.fallback} theo cấu hình.")
            return getattr(self._client(self.fallback),method)(prompt,**kwargs)
        try:
            return getattr(self._client(self.primary),method)(prompt,**kwargs)
        except TransientError as error:
            if not fallback_ready: raise
            self.warn(f"LLM {self.step}: {self.primary} lỗi tạm thời ({error.code}) sau retry; chuyển dự phòng {self.fallback} đúng một lần cho lời gọi này.")
            return getattr(self._client(self.fallback),method)(prompt,**kwargs)

    def generate_json(self,prompt,*,system=None,schema=None,max_output_tokens=8192,temperature=None,timeout=None):
        return self._call("generate_json",prompt,dict(system=system,schema=schema,max_output_tokens=max_output_tokens,temperature=temperature,timeout=timeout))

    def generate_text(self,prompt,*,system=None,max_output_tokens=8192,temperature=None,timeout=None):
        return self._call("generate_text",prompt,dict(system=system,max_output_tokens=max_output_tokens,temperature=temperature,timeout=timeout))

    def close(self):
        for client in self.clients.values(): client.close()


class RoutedProvider(LLMProvider):
    """Compatibility facade: current agents still receive JSON text, no schema change."""
    def __init__(self,settings,step,*,diagnostics=None):
        self.router=Router(settings,step,diagnostics=diagnostics)
        self.output_token_budget=8192
    @property
    def model_name(self): return self.router.model_name
    @property
    def diagnostics(self): return self.router.diagnostics
    @diagnostics.setter
    def diagnostics(self,value):
        self.router.diagnostics=value
        self.router._secure_diagnostics()
    @property
    def progress(self): return self.router.progress
    @progress.setter
    def progress(self,value): self.router.progress=value
    @property
    def request_observer(self): return self.router.request_observer
    @request_observer.setter
    def request_observer(self,value): self.router.request_observer=value
    @property
    def warnings(self): return self.router.warnings

    def generate_json(self,prompt,schema):
        from schemas.research_brief import ResearchBrief
        from providers.research_payload import ResearchFactsResponse,compact_facts_json
        wire=ResearchFactsResponse if schema is ResearchBrief else schema
        try:
            data=self.router.generate_json(prompt,schema=wire,max_output_tokens=self.output_token_budget)
            result=json.dumps(data,ensure_ascii=False,allow_nan=False)
            return compact_facts_json(result) if schema is ResearchBrief else result
        except OutputError as error:
            if error.retryable and error.finish_reason=="MAX_TOKENS": self.output_token_budget=min(self.output_token_budget*2,32768)
            raise
        except ValueError as error:
            # Preserve existing agent-side JSON repair catches without leaking raw output.
            raise json.JSONDecodeError(self.diagnostics.redact(str(error)),"",0) from None

    def close(self): self.router.close()


def provider_for_step(settings,step,*,diagnostics=None):
    require_route(settings,step)
    return RoutedProvider(settings,step,diagnostics=diagnostics)


def add_provider_notes(result,provider):
    warnings=getattr(provider,"warnings",[])
    if not isinstance(warnings,list): return
    for name in ("review_notes","risks"):
        notes=getattr(result,name,None)
        if isinstance(notes,list):
            for note in warnings:
                if note not in notes: notes.append(note)
            return
