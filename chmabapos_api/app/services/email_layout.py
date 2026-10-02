"""Reusable, email-client-safe layout for Chmaba marketing mail.

Table-based markup with inline styles and a dark brand header with a violet CTA,
mirroring the web app's palette (``#17181c`` / ``#6957f5`` / ``#c4f27c`` on a
``#f4f4f7`` canvas). Kept dependency-free so the onboarding content module and
the seed migration can both import it.

The layout injects an ``{{unsubscribe}}`` merge token; the mailer replaces it
per recipient with a signed one-click opt-out URL. The hidden preheader div is
what most inboxes show next to the subject line.
"""
from __future__ import annotations

from string import Template

_FONT = "'Inter','Segoe UI',Helvetica,Arial,sans-serif"

_TEMPLATE = Template(
    """<!DOCTYPE html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<meta name="x-apple-disable-message-reformatting" />
<meta name="color-scheme" content="light dark" />
<meta name="supported-color-schemes" content="light dark" />
<title>$heading</title>
<!--[if mso]>
<style>body, table, td, a { font-family: Arial, Helvetica, sans-serif !important; }</style>
<![endif]-->
</head>
<body style="margin:0;padding:0;width:100%;background-color:#f4f4f7;-webkit-text-size-adjust:100%;-ms-text-size-adjust:100%;">
<div style="display:none;font-size:1px;color:#f4f4f7;line-height:1px;max-height:0;max-width:0;opacity:0;overflow:hidden;">$preview</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#f4f4f7;">
<tr>
<td align="center" style="padding:32px 12px;">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="width:100%;max-width:600px;">
<tr>
<td style="background-color:#17181c;border-radius:18px 18px 0 0;padding:22px 32px;">
<span style="font-family:$font;font-size:18px;font-weight:800;letter-spacing:-0.6px;color:#ffffff;">Chmaba<span style="color:#c4f27c;">.</span></span>
<span style="float:right;font-family:$font;font-size:11px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;color:#7d7e88;padding-top:5px;">Run your store</span>
</td>
</tr>
<tr><td style="background-color:#6957f5;height:4px;line-height:4px;font-size:0;" height="4">&nbsp;</td></tr>
<tr>
<td style="background-color:#ffffff;padding:36px 32px 10px 32px;">
<h1 style="margin:0 0 18px 0;font-family:$font;font-size:23px;line-height:1.28;font-weight:800;letter-spacing:-0.5px;color:#202128;">$heading</h1>
<div style="font-family:$font;font-size:15px;line-height:1.68;color:#5d5e68;">$body</div>
<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:28px 0 8px 0;"><tr>
<td align="center" bgcolor="#6957f5" style="border-radius:12px;">
<a href="$cta_href" target="_blank" style="display:inline-block;padding:15px 28px;font-family:$font;font-size:14px;font-weight:700;line-height:1;color:#ffffff;text-decoration:none;border-radius:12px;">$cta_label</a>
</td>
</tr></table>
$footnote
</td>
</tr>
<tr>
<td style="background-color:#ffffff;border-radius:0 0 18px 18px;border-top:1px solid #eeeeF2;padding:20px 32px 30px 32px;">
<p style="margin:0;font-family:$font;font-size:12px;line-height:1.6;color:#92939d;">You are receiving this because you created a Chmaba account.</p>
<p style="margin:10px 0 0 0;font-family:$font;font-size:12px;line-height:1.6;color:#92939d;">
<a href="{{unsubscribe}}" target="_blank" style="color:#6957f5;text-decoration:underline;">Unsubscribe</a>
&nbsp;&nbsp;&middot;&nbsp;&nbsp;Chmaba
</p>
</td>
</tr>
</table>
</td>
</tr>
</table>
</body>
</html>
"""
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
    """Return a complete HTML email for one message.

    ``paragraphs`` are inserted as-is inside styled ``<p>`` tags, so inline
    markup (``<strong>``) and merge tokens (``{{name}}``) both work.
    """
    body = "".join('<p style="margin:0 0 15px 0;">' + text + "</p>" for text in paragraphs)
    footnote_html = (
        '<p style="margin:18px 0 0 0;font-size:13px;line-height:1.6;color:#92939d;">' + footnote + "</p>"
        if footnote
        else ""
    )
    return _TEMPLATE.substitute(
        font=_FONT,
        heading=heading,
        preview=preview,
        body=body,
        cta_href=cta_href,
        cta_label=cta_label,
        footnote=footnote_html,
    )
