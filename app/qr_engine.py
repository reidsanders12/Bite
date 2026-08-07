"""
QR code generation for the sponsor "Redeem" dialog (see home_view.py).

Uses `qrcode`'s pure-Python PNG backend -- deliberately not the default
Pillow-based one, since Pillow has no published Android wheel for some
versions and this app already avoids that trap once for opencv-python (see
requirements.txt). The pure backend needs nothing beyond `qrcode` itself.
"""
import base64
import io

import qrcode
from qrcode.image.pure import PyPNGImage


def qr_base64(data: str) -> str:
    """Renders `data` (e.g. a redeem URL) as a PNG QR code and returns it
    base64-encoded, ready for ft.Image(src_base64=...)."""
    img = qrcode.make(data, image_factory=PyPNGImage, box_size=8, border=2)
    buf = io.BytesIO()
    img.save(buf)
    return base64.b64encode(buf.getvalue()).decode("ascii")
