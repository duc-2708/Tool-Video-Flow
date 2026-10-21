"""Optional Gemini interpretation of signals; never an input to fact grounding."""
import json
from pydantic import ValidationError
from schemas.research_brief import TrendInsights
from utils.cache import cache_key


def summarize_trends(signals,provider,settings,cache,diagnostics):
    if not signals:
        return TrendInsights(),[]
    try:
        template = (settings.prompts_dir/"trend_insights.txt").read_text(encoding="utf-8")
        data = [signal.model_dump(mode="json") for signal in signals]
        inputs = {"signals":data,"model":provider.model_name,"prompt":cache_key(template)}
        allowed = {str(signal.url) for signal in signals}
        commented = {str(signal.url) for signal in signals if signal.top_comments}
        def validate(value):
            result = TrendInsights.model_validate(value)
            for name in ("hook_patterns","keywords","common_questions","angles"):
                for insight in getattr(result,name):
                    urls = {str(url) for url in insight.evidence_urls}
                    if not urls <= allowed or (name == "common_questions" and not urls <= commented):
                        raise ValueError(f"{name}: evidence_urls phải là video INPUT có tín hiệu tương ứng; câu hỏi cần bình luận thật.")
            return result
        cached = cache.get("trend-insights-v1",inputs)
        if isinstance(cached,dict):
            try:
                return validate(cached),[]
            except (ValidationError,ValueError):
                pass
        prompt = template+"\nINPUT_DATA_JSON:\n"+json.dumps(data,ensure_ascii=False)
        for attempt in range(1,settings.retry_attempts+1):
            try:
                raw = provider.generate_json(prompt,TrendInsights)
                insights = validate(json.loads(raw))
                cache.set("trend-insights-v1",inputs,insights.model_dump(mode="json"))
                return insights,[]
            except Exception as error:
                diagnostics.record_exception(error,f"Gemini trend_insights, attempt={attempt}")
                prompt += "\nRETRY: Trả lại JSON đúng schema, chỉ tham chiếu URL trong INPUT; không thêm fact."
                if not isinstance(error,(ValidationError,ValueError)):
                    break
    except Exception as error:
        diagnostics.record_exception(error,"Bỏ qua trend_insights do lỗi phụ trợ")
    return TrendInsights(),["Không tổng hợp được trend_insights; vẫn giữ facts web và metadata YouTube, tiếp tục Research."]
