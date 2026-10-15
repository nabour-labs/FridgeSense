"""HTML for the Ring account link page. No JavaScript; inline CSS only."""

from html import escape

_STYLE = """
body{font-family:system-ui,sans-serif;background:#f6f7f9;color:#1d2330;margin:0;
display:flex;min-height:100vh;align-items:center;justify-content:center;padding:16px}
main{background:#fff;border-radius:12px;padding:28px;max-width:380px;width:100%;
box-shadow:0 2px 12px rgba(0,0,0,.08)}
h1{font-size:1.3rem;margin:0 0 8px}p{line-height:1.5}
label{display:block;font-weight:600;margin:16px 0 6px}
input[type=password]{width:100%;box-sizing:border-box;padding:10px;font-size:1rem;
border:1px solid #c7ccd6;border-radius:8px}
button{margin-top:16px;width:100%;padding:11px;font-size:1rem;border:0;border-radius:8px;
background:#1f6feb;color:#fff;cursor:pointer}
a.button{display:block;margin-top:20px;padding:11px;border-radius:8px;background:#1f6feb;
color:#fff;text-align:center;text-decoration:none;font-weight:600}
.error{color:#b42318;font-weight:600}ul{padding-left:20px}
"""


def page(title: str, body: str) -> str:
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{escape(title)} · FridgeSense</title><style>{_STYLE}</style></head>"
        f"<body><main><h1>{escape(title)}</h1>{body}</main></body></html>"
    )


def sign_in_form(nonce: str, time_ms: str, error: str | None = None) -> str:
    err = f'<p class="error">{escape(error)}</p>' if error else ""
    return page(
        "Link your camera",
        "<p>Enter your FridgeSense passcode to connect your camera.</p>"
        f"{err}"
        '<form method="post" action="/ring/link">'
        f'<input type="hidden" name="nonce" value="{escape(nonce)}">'
        f'<input type="hidden" name="time" value="{escape(time_ms)}">'
        '<label for="passcode">Passcode</label>'
        '<input type="password" id="passcode" name="passcode" autocomplete="current-password"'
        " required autofocus>"
        '<button type="submit">Link</button></form>',
    )


def message(title: str, text: str) -> str:
    return page(title, f"<p>{escape(text)}</p>")


def linked(device_names: list[str] | None, app_url: str | None = None) -> str:
    if device_names is None:
        devices = "<p>Your devices could not be loaded yet. They will show up in the app.</p>"
    elif not device_names:
        devices = "<p>No cameras were found on this account yet.</p>"
    else:
        items = "".join(f"<li>{escape(n)}</li>" for n in device_names)
        devices = f"<p>Cameras found:</p><ul>{items}</ul>"
    open_app = f'<a class="button" href="{escape(app_url)}">Open FridgeSense</a>' if app_url else ""
    return page(
        "Camera linked", "<p>Your Ring account is linked to FridgeSense.</p>" + devices + open_app
    )
