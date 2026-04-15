"""
Gemini Image Generation — edição de imagens via prompt.
Modelo: gemini-2.0-flash-preview-image-generation
Usa google-genai SDK (novo, substituiu google-generativeai).
"""
import base64
import os
from pathlib import Path


def edit_image(image_path: str, prompt: str, api_key: str = "") -> str:
    """
    Edita uma imagem usando Gemini.
    Retorna a nova imagem como data URI base64 (pronta para usar como src).
    """
    key = api_key or os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise ValueError("GEMINI_API_KEY não configurada")

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=key)

    img_path = Path(image_path)
    if not img_path.exists():
        raise FileNotFoundError(f"Imagem não encontrada: {image_path}")

    img_bytes = img_path.read_bytes()
    if len(img_bytes) > 4 * 1024 * 1024:
        raise ValueError(f"Imagem muito grande ({len(img_bytes)/1024/1024:.1f}MB). Limite: 4MB.")

    ext = img_path.suffix.lower()
    mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                ".webp": "image/webp", ".gif": "image/gif"}
    mime_type = mime_map.get(ext, "image/jpeg")

    full_prompt = (
        f"{prompt}\n\n"
        "IMPORTANTE: Gere a imagem em português brasileiro. "
        "Não adicione texto em inglês. Mantenha a mesma composição e estilo da imagem original."
    )

    response = client.models.generate_content(
        model="gemini-2.0-flash-preview-image-generation",
        contents=[
            types.Part.from_bytes(data=img_bytes, mime_type=mime_type),
            full_prompt,
        ],
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"]
        ),
    )

    for part in response.candidates[0].content.parts:
        if part.inline_data:
            data_b64 = base64.b64encode(part.inline_data.data).decode("ascii")
            return f"data:{part.inline_data.mime_type};base64,{data_b64}"

    raise ValueError("Gemini não retornou imagem na resposta")
