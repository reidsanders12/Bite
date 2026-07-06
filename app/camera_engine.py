"""
Camera and barcode scanner processing engine using OpenCV natively.
Runs an asynchronous capture loop to update a Flet image control.
"""

import asyncio
import cv2
import base64

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

            # Mirror frame for intuitive viewport viewing
            frame = cv2.flip(frame, 1)

            # 1. Built-in Barcode & QR Detection Routine
            if mode == "barcode" and on_barcode_detect:
                # Try standard UPC/EAN barcodes first
                try:
                    retval, decoded_info, _, _ = self.barcode_detector.detectAndDecode(frame)
                    if retval and decoded_info:
                        for code_data in decoded_info:
                            if code_data.strip():
                                self.stop_camera()
                                await on_barcode_detect(code_data.strip())
                                return
                except Exception:
                    pass # Fallback safely if barcode engine misses

                # Dual checking: Fallback to QR tracking matrix
                qr_data, _, _ = self.qr_detector.detectAndDecode(frame)
                if qr_data and qr_data.strip():
                    self.stop_camera()
                    await on_barcode_detect(qr_data.strip())
                    return

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