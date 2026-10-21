# file: test_gemini.py
# Diagnostic chay tay; import khong nap cau hinh hay goi API.

def main() -> None:
    # file: test_gemini.py
    import os
    from dotenv import load_dotenv
    from google import genai

    load_dotenv()
    key = os.getenv("GEMINI_API_KEY")
    model = os.getenv("GEMINI_MODEL")
    print("Có key:", bool(key), "| Độ dài key:", len(key or ""))
    print("GEMINI_MODEL =", repr(model))

    client = genai.Client(api_key=key)

    print("\nCác model gọi được generateContent:")
    try:
        for m in client.models.list():
            actions = getattr(m, "supported_actions", None) or []
            if "generateContent" in actions:
                print(" -", m.name)
    except Exception as e:
        print("LỖI khi liệt kê model:", type(e).__name__, "-", e)

    if model:
        try:
            r = client.models.generate_content(
                model=model, contents="Trả lời đúng 1 từ: OK"
            )
            print("\nGọi thử thành công:", r.text)
        except Exception as e:
            print("\nLỖI THẬT:", type(e).__name__, "-", e)
    else:
        print("\nGEMINI_MODEL đang trống, hãy điền vào .env")

if __name__ == "__main__":
    main()
