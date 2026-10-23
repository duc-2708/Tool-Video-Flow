"""Do not ask Gemini to manufacture private preset snapshots in a generated plan."""
def flat_style_schema(model,*,essential=False):
    """Wire-only JSON schema; Pydantic remains the local source of validation."""
    if essential:
        return {"type":"object","properties":{"duration_sec":{"type":"number"},"scenes":{"type":"array","maxItems":12,
            "items":{"type":"object","properties":{"start_sec":{"type":"number"},"end_sec":{"type":"number"},"purpose":{"type":"string"}},
                "required":["start_sec","end_sec","purpose"]}}},"required":["scenes"]}
    raw=model.model_json_schema();definitions=raw.get("$defs",{})
    def visit(value,seen=()):
        if "$ref" in value:
            name=value["$ref"].rsplit("/",1)[-1]
            if name in seen: raise ValueError("Schema Style không được tham chiếu vòng.")
            return visit(definitions[name],(*seen,name))
        if "anyOf" in value or "oneOf" in value:
            branches=[v for v in value.get("anyOf",value.get("oneOf",[])) if v.get("type")!="null"]
            if len(branches)!=1: raise ValueError("Schema Style wire chỉ nhận một kiểu cụ thể mỗi trường.")
            return visit(branches[0],seen)
        result={k:v for k,v in value.items() if k in {"type","enum","minimum","maximum","minItems","maxItems"}}
        if "properties" in value:
            result["properties"]={k:visit(v,seen) for k,v in value["properties"].items() if k not in {"normalization_notes","analysis_warnings","color_note"}}
            required=[k for k in value.get("required",[]) if k in result["properties"]]
            if required: result["required"]=required
        if "items" in value: result["items"]=visit(value["items"],seen)
        return result
    return visit(raw)


def response_schema(model):
    if model.__name__ in {"StyleAnalysis","CompactStyleAnalysis"}:
        return flat_style_schema(model)
    schema = model.model_json_schema()
    if model.__name__ != "EditPlan":
        return schema
    excluded = {"style_profile", "render_style", "style_preset"}
    for name in excluded:
        schema.get("properties", {}).pop(name, None)
    if "required" in schema:
        schema["required"] = [name for name in schema["required"] if name not in excluded]
    definitions = schema.pop("$defs", {})
    used = set()

    def visit(value):
        if isinstance(value, dict):
            ref = value.get("$ref", "")
            if ref.startswith("#/$defs/"):
                name = ref.split("/")[-1]
                if name not in used:
                    used.add(name)
                    visit(definitions.get(name, {}))
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(schema)
    schema["$defs"] = {name: value for name, value in definitions.items() if name in used}
    return schema
