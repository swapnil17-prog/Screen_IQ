"""
One plain, accessible layout for every outgoing email: a greeting, a few
paragraphs, an optional button and small print. Returns both text and HTML parts.
"""

from dataclasses import dataclass
from html import escape


@dataclass
class Email:
    subject: str
    text: str
    html: str


def compose(*, subject: str, greeting: str, paragraphs: list[str], button: tuple[str, str] | None = None,
            footnotes: list[str] | None = None, signoff: str) -> Email:
    """`paragraphs` and `footnotes` are plain text; everything is escaped for the HTML part."""
    footnotes = footnotes or []
    text_parts = [greeting, *paragraphs]
    if button:
        text_parts.append(f"{button[0]}:\n{button[1]}")
    text_parts += footnotes
    text_parts.append(signoff)
    text = "\n\n".join(text_parts) + "\n"

    p = '<p style="margin:0 0 16px">'
    small = '<p style="margin:0 0 12px;font-size:13px;color:#6b7280">'
    parts = [f"{p}{escape(greeting)}</p>", *(f"{p}{escape(x)}</p>" for x in paragraphs)]
    if button:
        label, url = button
        parts.append(
            f'<p style="margin:28px 0"><a href="{escape(url, quote=True)}" style="background:#4338ca;color:#ffffff;'
            'text-decoration:none;padding:12px 22px;border-radius:8px;font-weight:bold;display:inline-block">'
            f"{escape(label)}</a></p>"
            f"{small}Or paste this link into your browser:<br>{escape(url)}</p>"
        )
    parts += [f"{small}{escape(x)}</p>" for x in footnotes]
    parts.append(f'<p style="margin:16px 0 0">{escape(signoff).replace(chr(10), "<br>")}</p>')
    html = ('<div style="font-family:Arial,Helvetica,sans-serif;font-size:15px;line-height:1.6;color:#1f2937;'
            'max-width:560px;margin:0 auto;padding:24px">' + "".join(parts) + "</div>")
    return Email(subject=subject, text=text, html=html)


def hello(first_name: str | None) -> str:
    return f"Hi {first_name}," if first_name else "Hi there,"


def first_name_of(full_name: str | None) -> str | None:
    return (full_name or "").split(" ")[0] or None
