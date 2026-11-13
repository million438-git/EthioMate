import html
import re


def format_telegram_html(text: str) -> str:
    """
    Safely convert common Markdown formatting into Telegram HTML.

    HTML supplied in the original text is escaped.
    Supported formatting:
    - Headings
    - Bold and italic text
    - Strikethrough
    - Inline code
    - Fenced code blocks
    - Simple unordered lists
    """

    if not text:
        return ""

    protected = []

    def store(value):
        token = f"\x00PROTECTED{len(protected)}\x00"
        protected.append(value)
        return token

    # Protect fenced code blocks before processing other Markdown.
    def protect_code_block(match):
        code = match.group(2)
        return store(
            "<pre><code>" + html.escape(code, quote=False)
            + "</code></pre>"
        )

    text = re.sub(
        r"```([^\n`]*)\n(.*?)```",
        protect_code_block,
        text,
        flags=re.DOTALL
    )

    # Protect inline code.
    def protect_inline_code(match):
        code = match.group(1)
        return store(
            "<code>" + html.escape(code, quote=False) + "</code>"
        )

    text = re.sub(r"`([^`\n]+)`", protect_inline_code, text)

    # Escape all remaining text. Never trust generated HTML.
    text = html.escape(text, quote=False)

    # Convert headings to bold lines.
    text = re.sub(
        r"(?m)^#{1,3}[ \t]+(.+?)[ \t]*#*[ \t]*$",
        r"<b>\1</b>",
        text
    )

    # Convert bold text.
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"__(.+?)__", r"<b>\1</b>", text)

    # Convert strikethrough.
    text = re.sub(r"~~(.+?)~~", r"<s>\1</s>", text)

    # Convert italic text without treating list markers as emphasis.
    text = re.sub(
        r"(?<!\*)\*([^*\n]+)\*(?!\*)",
        r"<i>\1</i>",
        text
    )

    # Convert simple unordered list markers.
    text = re.sub(r"(?m)^([ \t]*)[-*][ \t]+", r"\1• ", text)

    # Restore protected code blocks and inline code.
    for index, value in enumerate(protected):
        text = text.replace(f"\x00PROTECTED{index}\x00", value)

    return text
