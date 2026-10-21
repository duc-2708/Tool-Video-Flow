"""Do not ask Gemini to manufacture private preset snapshots in a generated plan."""
def response_schema(model):
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
