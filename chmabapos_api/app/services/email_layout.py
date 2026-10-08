"""Reusable, email-client-safe layouts for Chmaba mail.

Table-based markup with inline styles and a dark brand header with a violet
accent, mirroring the web app's palette (``#17181c`` / ``#6957f5`` / ``#c4f27c``
on a ``#f4f4f7`` canvas). Kept dependency-free so the onboarding content module
and the seed migration can both import it.

Two entry points share the exact same shell:

* :func:`marketing_email` — the onboarding/drip layout. It injects an
  ``{{unsubscribe}}`` merge token that the mailer replaces per recipient with a
  signed one-click opt-out URL.
* :func:`transactional_email` — the same branded shell for receipts, sale
  alerts and store notifications. These are transactional, so the footer omits
  the unsubscribe link (the store's own Settings → Notifications toggles are
  their control) and no merge tokens are required.

:func:`data_table` and :func:`totals_table` are small helpers for the
receipt-style content those transactional messages use. Cell values must be
pre-escaped HTML, so callers HTML-escape any user-supplied text first.
"""
from __future__ import annotations

from string import Template

# Latin-first stack with widely-installed Khmer families after it, so a Khmer
# store or product name renders with a real Khmer face instead of a fallback
# sans. Custom webfonts (e.g. Niradei) are listed first for clients that have
# them installed, but mail clients mostly cannot load webfonts, so the system
# Khmer families are what actually matter here.
_FONT = (
    "'Inter','Niradei','Noto Sans Khmer','Khmer OS','Khmer OS System',"
    "'Leelawadee UI','Nirmala UI','Khmer UI',Helvetica,Arial,sans-serif"
)

_MUTED = "#92939d"
_BORDER = "#eeeeF2"
_TEXT = "#303139"

_ALIGN = {"left": "left", "right": "right", "center": "center"}


def _header(badge: str) -> str:
    return (
        "<tr>\n"
        '<td style="background-color:#17181c;border-radius:18px 18px 0 0;padding:22px 32px;">\n'
        f'<span style="font-family:{_FONT};font-size:18px;font-weight:800;letter-spacing:-0.6px;color:#ffffff;">'
        f'Chmaba<span style="color:#c4f27c;">.</span></span>\n'
        f'<span style="float:right;font-family:{_FONT};font-size:11px;font-weight:700;letter-spacing:0.08em;'
        f'text-transform:uppercase;color:#7d7e88;padding-top:5px;">{badge}</span>\n'
        "</td>\n"
        "</tr>\n"
        '<tr><td style="background-color:#6957f5;height:4px;line-height:4px;font-size:0;" height="4">&nbsp;</td></tr>'
    )


def _cta(label: str, href: str) -> str:
    return (
        '<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:28px 0 8px 0;"><tr>\n'
        '<td align="center" bgcolor="#6957f5" style="border-radius:12px;">\n'
        f'<a href="{href}" target="_blank" style="display:inline-block;padding:15px 28px;font-family:{_FONT};'
        'font-size:14px;font-weight:700;line-height:1;color:#ffffff;text-decoration:none;border-radius:12px;">'
        f"{label}</a>\n"
        "</td>\n"
        "</tr></table>"
    )


def _footer(*, notes: list[str], unsubscribe: bool) -> str:
    paragraphs = "".join(
        f'<p style="margin:{"0" if index == 0 else "10px 0 0 0"};font-family:{_FONT};font-size:12px;'
        f'line-height:1.6;color:{_MUTED};">{note}</p>'
        for index, note in enumerate(notes)
    )
    if unsubscribe:
        paragraphs += (
            f'<p style="margin:10px 0 0 0;font-family:{_FONT};font-size:12px;line-height:1.6;color:{_MUTED};">\n'
            '<a href="{{unsubscribe}}" target="_blank" style="color:#6957f5;text-decoration:underline;">Unsubscribe</a>\n'
            "&nbsp;&nbsp;&middot;&nbsp;&nbsp;Chmaba\n"
            "</p>"
        )
    return (
        "<tr>\n"
        f'<td style="background-color:#ffffff;border-radius:0 0 18px 18px;border-top:1px solid {_BORDER};'
        'padding:20px 32px 30px 32px;">\n'
        f"{paragraphs}\n"
        "</td>\n"
        "</tr>"
    )


_SHELL = Template(
    """<!DOCTYPE html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<meta name="x-apple-disable-message-reformatting" />
<meta name="color-scheme" content="light dark" />
<meta name="supported-color-schemes" content="light dark" />
<title>$title</title>
<!--[if mso]>
<style>body, table, td, a { font-family: Arial, 'Leelawadee UI', 'Khmer UI', Helvetica, sans-serif !important; }</style>
<![endif]-->
</head>
<body style="margin:0;padding:0;width:100%;background-color:#f4f4f7;-webkit-text-size-adjust:100%;-ms-text-size-adjust:100%;">
<div style="display:none;font-size:1px;color:#f4f4f7;line-height:1px;max-height:0;max-width:0;opacity:0;overflow:hidden;">$preview</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#f4f4f7;">
<tr>
<td align="center" style="padding:32px 12px;">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="width:100%;max-width:600px;">
$header
<tr>
<td style="background-color:#ffffff;padding:36px 32px 10px 32px;">
<h1 style="margin:0 0 18px 0;font-family:$font;font-size:23px;line-height:1.28;font-weight:800;letter-spacing:-0.5px;color:#202128;">$heading</h1>
<div style="font-family:$font;font-size:15px;line-height:1.68;color:#5d5e68;">$body</div>
$cta
$footnote
</td>
</tr>
$footer
</table>
</td>
</tr>
</table>
</body>
</html>
"""
)


def _render(*, title: str, preview: str, heading: str, body: str, badge: str, footer: str, cta: str = "", footnote: str = "") -> str:
    return _SHELL.substitute(
        font=_FONT,
        title=title,
        preview=preview,
        heading=heading,
        body=body,
        header=_header(badge),
        cta=cta,
        footnote=footnote,
        footer=footer,
    )


def _paragraph(text: str, *, margin: str = "0 0 15px 0") -> str:
    return f'<p style="margin:{margin};">{text}</p>'


def data_table(columns: list[str], rows: list[list[str]], *, aligns: list[str] | None = None, show_header: bool = True) -> str:
    """A compact, email-safe table for line items and lists.

    ``rows`` and ``columns`` accept HTML (they are inserted as-is), so callers
    must escape product names and other user-supplied text. Set
    ``show_header=False`` for a bare key/value block.
    """
    widths = len(columns)
    aligns = aligns or ["left"] * widths
    head = "".join(
        f'<th style="padding:0 12px 8px 0;text-align:{_ALIGN.get(aligns[index], "left")};font-family:{_FONT};'
        f'font-size:10px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;color:{_MUTED};'
        'border-bottom:2px solid #e6e6ec;white-space:nowrap;">'
        f"{columns[index]}</th>"
        for index in range(widths)
    )
    head_row = f"<tr>{head}</tr>" if show_header else ""
    body = "".join(
        "<tr>"
        + "".join(
            f'<td style="padding:11px 12px 11px 0;text-align:{_ALIGN.get(aligns[index], "left")};font-family:{_FONT};'
            f'font-size:13px;line-height:1.5;color:{_TEXT};border-bottom:1px solid {_BORDER};vertical-align:top;">'
            f"{row[index]}</td>"
            for index in range(widths)
        )
        + "</tr>"
        for row in rows
    )
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        'style="width:100%;border-collapse:collapse;margin:22px 0 6px 0;">'
        f"{head_row}{body}</table>"
    )


def totals_table(rows: list[tuple[str, str]]) -> str:
    """A right-aligned label/value block for money totals; the last row is bold."""
    body = ""
    for index, (label, value) in enumerate(rows):
        last = index == len(rows) - 1
        weight = "800" if last else "400"
        color = "#202128" if last else "#71727d"
        size = "15px" if last else "13px"
        body += (
            "<tr>"
            f'<td style="padding:4px 14px 4px 0;text-align:right;font-family:{_FONT};font-size:{size};color:{color};">'
            f"{label}</td>"
            f'<td style="padding:4px 0;text-align:right;font-family:{_FONT};font-size:{size};font-weight:{weight};'
            f'color:#202128;white-space:nowrap;">{value}</td>'
            "</tr>"
        )
    return (
        '<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
        'style="width:100%;border-collapse:collapse;margin:16px 0 4px 0;">'
        f"{body}</table>"
    )


def code_block(code: str) -> str:
    """A large, centred confirmation code for account mail.

    Rendered as a single-cell table (Outlook ignores flex/grid) so the code
    stays centred and selectable across mail clients. ``code`` is a trusted
    literal (a generated six-digit string), inserted as-is.
    """
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        'style="width:100%;margin:10px 0 6px 0;">'
        "<tr>"
        f'<td align="center" style="background-color:#f4f4f7;border:1px solid #e6e6ec;border-radius:14px;'
        f'padding:20px 16px;font-family:{_FONT};font-size:32px;font-weight:800;letter-spacing:0.32em;'
        f'color:#202128;">{code}</td>'
        "</tr></table>"
    )


def marketing_email(
    *,
    heading: str,
    preview: str,
    paragraphs: list[str] | tuple[str, ...],
    cta_label: str,
    cta_href: str,
    footnote: str | None = None,
) -> str:
    """Return a complete HTML marketing email for one message.

    ``paragraphs`` are inserted as-is inside styled ``<p>`` tags, so inline
    markup (``<strong>``) and merge tokens (``{{name}}``) both work.
    """
    body = "".join(_paragraph(text) for text in paragraphs)
    footnote_html = (
        f'<p style="margin:18px 0 0 0;font-size:13px;line-height:1.6;color:{_MUTED};">{footnote}</p>'
        if footnote
        else ""
    )
    return _render(
        title=heading,
        preview=preview,
        heading=heading,
        body=body,
        badge="Run your store",
        footer=_footer(notes=["You are receiving this because you created a Chmaba account."], unsubscribe=True),
        cta=_cta(cta_label, cta_href),
        footnote=footnote_html,
    )


def transactional_email(
    *,
    heading: str,
    preview: str,
    body: str,
    badge: str = "Store notice",
    footnote: str | None = None,
    cta_label: str | None = None,
    cta_href: str | None = None,
) -> str:
    """Return a complete HTML transactional email using the shared brand shell.

    ``body`` is raw, pre-escaped HTML. There is no unsubscribe link on purpose:
    these messages are transactional and controlled by the store's own
    notification settings.
    """
    footnote_html = (
        f'<p style="margin:18px 0 0 0;font-size:13px;line-height:1.6;color:{_MUTED};">{footnote}</p>' if footnote else ""
    )
    return _render(
        title=heading,
        preview=preview,
        heading=heading,
        body=body,
        badge=badge,
        footer=_footer(
            notes=[
                "This is an automated message about your store from Chmaba. "
                "Manage these alerts in Settings &rarr; Notifications.",
                "Sent by Chmaba",
            ],
            unsubscribe=False,
        ),
        cta=_cta(cta_label, cta_href) if cta_label and cta_href else "",
        footnote=footnote_html,
    )
