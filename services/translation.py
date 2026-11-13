from services.ai_assistant import generate_reply


LANGUAGE_NAMES = {
    "am": "Amharic",
    "en": "English",
    "om": "Afaan Oromo"
}


async def translate_text(text, target_language):
    """Translate text into the selected language."""

    if target_language not in LANGUAGE_NAMES:
        raise ValueError("Unsupported target language.")

    if not text or not text.strip():
        raise ValueError("Translation text cannot be empty.")

    if len(text) > 12000:
        raise ValueError("Text is too long. Maximum is 12000 characters.")

    target = LANGUAGE_NAMES[target_language]

    prompt = (
        f"Translate the following text into {target}.\n"
        "Automatically detect the source language.\n"
        "Preserve the original meaning, tone and formatting.\n"
        "Do not summarize or omit information.\n"
        "Return only the translated text, without explanations.\n\n"
        f"TEXT TO TRANSLATE:\n{text}"
    )

    history = [
        {
            "role": "user",
            "parts": [{"text": prompt}]
        }
    ]

    return await generate_reply(
        history=history,
        language=target_language
    )
