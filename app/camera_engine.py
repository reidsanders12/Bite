"""
Camera and barcode scanner processing engine using OpenCV natively.
Runs an asynchronous capture loop to update a Flet image control.
"""

import asyncio
import base64
import logging

import cv2

logger = logging.getLogger(__name__)

# A 1x1 transparent PNG, base64-encoded. Flet's Image control shows a red
# Flutter debug error ("Either src or src_base64 must be specified") for any
# frame it's visible without one, which happens briefly whenever an Image
# meant to stream camera frames is shown before the first frame has arrived.
# Views that use one for camera preview should set this as the initial
# src_base64 so there's always something valid to show.
BLANK_FRAME_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY"
    "42YAAAAASUVORK5CYII="
)

class CameraEngine:
    def __init__(self):
        self.cap = None
        self.is_running = False
        self.latest_frame_bytes = None
        
        # Correct sub-namespaces for OpenCV's built-in detectors
        self.barcode_detector = cv2.barcode.BarcodeDetector()
        self.qr_detector = cv2.QRCodeDetector()

    def start_camera(self):
        """Initialize hardware camera."""
        if not self.cap or not self.cap.isOpened():
            self.cap = cv2.VideoCapture(0)  # 0 is typically the built-in webcam
            self.is_running = True

    def stop_camera(self):
        """Release hardware camera hooks."""
        self.is_running = False
        if self.cap and self.cap.isOpened():
            self.cap.release()
        self.cap = None

    async def stream_views(self, image_control, mode="snap", on_barcode_detect=None):
        """
        Streams frames to a Flet Image control.
        mode="snap" -> standard viewport for photo capturing.
        mode="barcode" -> actively scans frames for UPC/EAN matrices or QR codes.
        """
        self.start_camera()
        
        while self.is_running:
            if not self.cap:
                break
                
            ret, frame = self.cap.read()
            if not ret:
                await asyncio.sleep(0.03)
                continue

            # 1. Built-in Barcode & QR Detection Routine -- runs on the raw,
            # unmirrored frame. 1D barcodes (UPC/EAN) are left-right
            # asymmetric (their guard patterns differ by side), so decoding
            # a mirrored frame reliably fails; only the frame we display
            # gets mirrored, below.
            if mode == "barcode" and on_barcode_detect:
                # Only the decoder calls themselves are guarded here -- they
                # can raise on an odd/corrupt frame and that's fine to skip
                # and retry next frame. The on_barcode_detect callback below
                # (which drives the actual lookup + UI update) used to be
                # inside this same try/except, so any failure in *it* --
                # not just a decoder hiccup -- was silently discarded: the
                # camera would stop (detection succeeded) but nothing would
                # visibly happen next. It's called outside the guard now so
                # its caller can see and surface any failure.
                #
                # detectAndDecode() (singular) only returns 3 values in this
                # OpenCV build (retval, points, straight_code), not the
                # 4-value (retval, decoded_info, decoded_type, points) shape
                # this code was written against -- every call was raising
                # ValueError on the unpack and getting swallowed right here,
                # so detection had never actually run once. detectAndDecodeMulti()
                # is the method with the 4-value signature this code expects.
                detected_code = None
                try:
                    retval, decoded_info, _, _ = self.barcode_detector.detectAndDecodeMulti(frame)
                    if retval and decoded_info:
                        for code_data in decoded_info:
                            if code_data.strip():
                                detected_code = code_data.strip()
                                break
                except Exception:
                    logger.debug("Barcode detector raised on this frame, skipping", exc_info=True)

                if not detected_code:
                    # Dual checking: Fallback to QR tracking matrix
                    qr_data, _, _ = self.qr_detector.detectAndDecode(frame)
                    if qr_data and qr_data.strip():
                        detected_code = qr_data.strip()

                if detected_code:
                    self.stop_camera()
                    # Freeze the view on the exact frame the barcode was
                    # recognized in (mirrored, matching the live preview)
                    # before handing off to the lookup -- otherwise this
                    # frame is never displayed at all (we return before the
                    # display step below) and the preview just vanishes with
                    # no visual confirmation that anything was scanned.
                    display_frame = cv2.flip(frame, 1)
                    success, buffer = cv2.imencode('.jpg', display_frame)
                    if success:
                        self.latest_frame_bytes = buffer.tobytes()
                        image_control.src_base64 = base64.b64encode(self.latest_frame_bytes).decode("utf-8")
                        image_control.update()
                    await on_barcode_detect(detected_code)
                    return

            # Mirror only for display -- detection above already ran on the
            # unflipped frame.
            frame = cv2.flip(frame, 1)

            # 2. Compress and encode frame to JPEG for Flet display
            success, buffer = cv2.imencode('.jpg', frame)
            if success:
                self.latest_frame_bytes = buffer.tobytes()
                img_b64 = base64.b64encode(self.latest_frame_bytes).decode("utf-8")
                image_control.src_base64 = img_b64
                image_control.update()

            # Maintain roughly 30 FPS playback rate
            await asyncio.sleep(0.03)

    def get_captured_photo(self) -> bytes:
        """Returns raw bytes of the last frame captured by the camera stream."""
        return self.latest_frame_bytes