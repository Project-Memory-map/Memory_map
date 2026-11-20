"""Xóa siêu dữ liệu (EXIF, GPS, XMP...) khỏi ảnh trước khi lưu – bảo vệ vị trí của người dùng.

Ảnh chụp điện thoại thường chứa tọa độ GPS trong EXIF; khi ký ức (hoặc ảnh đại diện) công khai, ai tải ảnh về
cũng đọc được vị trí chính xác. Hàm này bỏ các khối siêu dữ liệu nhưng giữ nguyên dữ liệu điểm ảnh
(không nén lại ảnh, không cần Pillow). Định dạng không nhận ra thì trả nguyên.
"""
from __future__ import annotations

import struct

# JPEG: APP1 (EXIF/XMP), APP2..APP15 trừ APP2 ICC (giữ màu), COM (chú thích)
_JPEG_DROP = {0xE1, *range(0xE3, 0xF0), 0xFE}
_PNG_DROP = {b"eXIf", b"tEXt", b"zTXt", b"iTXt", b"tIME"}
_WEBP_DROP = {b"EXIF", b"XMP "}


def _strip_jpeg(data: bytes) -> bytes:
    out = bytearray(data[:2])  # SOI
    i = 2
    while i + 4 <= len(data):
        if data[i] != 0xFF:
            return data  # cấu trúc lạ: giữ nguyên còn hơn làm hỏng ảnh
        marker = data[i + 1]
        if marker == 0xDA:  # SOS: phần còn lại là dữ liệu ảnh
            out += data[i:]
            return bytes(out)
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:  # marker không có độ dài
            out += data[i:i + 2]
            i += 2
            continue
        length = struct.unpack(">H", data[i + 2:i + 4])[0]
        segment = data[i:i + 2 + length]
        if marker not in _JPEG_DROP:
            out += segment
        i += 2 + length
    return data


def _strip_png(data: bytes) -> bytes:
    out = bytearray(data[:8])
    i = 8
    while i + 8 <= len(data):
        length = struct.unpack(">I", data[i:i + 4])[0]
        kind = data[i + 4:i + 8]
        chunk = data[i:i + 12 + length]
        if kind not in _PNG_DROP:
            out += chunk
        i += 12 + length
        if kind == b"IEND":
            return bytes(out)
    return data


def _strip_webp(data: bytes) -> bytes:
    chunks = bytearray()
    i = 12
    while i + 8 <= len(data):
        kind = data[i:i + 4]
        length = struct.unpack("<I", data[i + 4:i + 8])[0]
        padded = length + (length & 1)
        chunk = bytearray(data[i:i + 8 + padded])
        if kind == b"VP8X" and len(chunk) >= 9:
            chunk[8] &= ~0x0C  # bỏ cờ "có EXIF" và "có XMP"
        if kind not in _WEBP_DROP:
            chunks += chunk
        i += 8 + padded
    return b"RIFF" + struct.pack("<I", 4 + len(chunks)) + b"WEBP" + bytes(chunks)


def strip_metadata(data: bytes, extension: str) -> bytes:
    try:
        if extension in (".jpg", ".jpeg") and data.startswith(b"\xff\xd8"):
            return _strip_jpeg(data)
        if extension == ".png" and data.startswith(b"\x89PNG\r\n\x1a\n"):
            return _strip_png(data)
        if extension == ".webp" and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
            return _strip_webp(data)
    except (struct.error, IndexError):
        pass
    return data
