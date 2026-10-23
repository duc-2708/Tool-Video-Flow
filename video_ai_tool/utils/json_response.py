"""Conservative JSON object recovery. No eval, generated facts or missing fields."""
import ast
import json


class TruncatedJSONError(ValueError):
    """An object/string was started but not closed; never invent its tail."""


def normalize_quotes(text):
    """Only fix quote delimiters; keep curly quotes inside JSON strings intact."""
    result=[];quote=None;escaped=False
    for char in text:
        if quote:
            if escaped:
                result.append(char);escaped=False
            elif char=="\\":
                result.append(char);escaped=True
            elif char==quote or quote=="”" and char=="”":
                result.append('"' if quote=="”" else char);quote=None
            else:
                result.append(char)
        elif char in {'"',"'"}:
            quote=char;result.append(char)
        elif char=="“":
            quote="”";result.append('"')
        else:
            result.append(char)
    return "".join(result)


def object_block(text):
    start=text.find("{")
    if start<0:
        raise ValueError("Phản hồi không có khối JSON {...}.")
    depth=0;quote=None;escaped=False
    for index in range(start,len(text)):
        char=text[index]
        if quote:
            if escaped: escaped=False
            elif char=="\\": escaped=True
            elif char==quote: quote=None
        elif char in {'"',"'"}: quote=char
        elif char=="{": depth+=1
        elif char=="}":
            depth-=1
            if depth==0:
                return text[start:index+1]
    raise TruncatedJSONError("Khối JSON chưa cân bằng (có thể đã bị cắt). Giữ bản thô để sửa, không tự bịa phần thiếu.")


def without_trailing_commas(text):
    result=[];quote=None;escaped=False
    for index,char in enumerate(text):
        if quote:
            result.append(char)
            if escaped: escaped=False
            elif char=="\\": escaped=True
            elif char==quote: quote=None
        elif char in {'"',"'"}:
            quote=char;result.append(char)
        elif char=="," and text[index+1:].lstrip().startswith(("}","]")):
            continue
        else:
            result.append(char)
    return "".join(result)


class JsonNames(ast.NodeTransformer):
    def visit_Name(self,node):
        if node.id not in {"true","false","null"}:
            raise ValueError("Tên không hợp lệ trong JSON.")
        return ast.copy_location(ast.Constant({"true":True,"false":False,"null":None}[node.id]),node)


def parse_json_object(raw):
    if not isinstance(raw,str) or not raw.strip():
        raise ValueError("Gemini trả phản hồi trống.")
    text=raw.lstrip("\ufeff").strip()
    try:
        value=json.loads(text)
    except json.JSONDecodeError:
        block=object_block(normalize_quotes(text))
        try:
            value=json.loads(without_trailing_commas(block))
        except json.JSONDecodeError as error:
            try:
                # Handles simple single-quoted dictionaries safely. Calls,
                # attributes, comprehensions etc. are rejected by literal_eval.
                tree=JsonNames().visit(ast.parse(block,mode="eval"))
                value=ast.literal_eval(tree)
                value=json.loads(json.dumps(value,ensure_ascii=False,allow_nan=False))
            except (SyntaxError,ValueError,TypeError,RecursionError):
                raise ValueError(f"JSON không hợp lệ tại dòng {error.lineno}, cột {error.colno}: {error.msg}.") from None
    if not isinstance(value,dict):
        raise ValueError("Phản hồi phải là JSON object.")
    return value
