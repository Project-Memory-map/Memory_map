# Quy trình tự động quay & dựng Video Demo 100 giây — "Bản đồ Ký ức"

Thư mục này hoàn toàn cô lập khỏi mã nguồn chính (`app/`, `database/`, `tests/`) và cơ sở dữ liệu làm việc (`ban_do_ky_uc`).
Quá trình quay tạo và sử dụng database riêng `ban_do_ky_uc_demo` cùng thư mục upload tạm `docs/demo_video/.work/uploads/`.

## Lệnh chạy nhanh (2 dòng trong PowerShell tại thư mục gốc dự án)

```powershell
.\venv\Scripts\python.exe docs\demo_video\record_demo.py
.\venv\Scripts\python.exe docs\demo_video\build_video.py
```

### Tùy chọn nâng cao cho `build_video.py`

- Đổi giọng đọc nữ (`vi-VN-HoaiMyNeural`) hoặc tốc độ đọc:
  ```powershell
  .\venv\Scripts\python.exe docs\demo_video\build_video.py --voice vi-VN-HoaiMyNeural --rate +5%
  ```
- Ghép thêm nhạc nền ở mức `-22dB`: chỉ cần đặt 1 file `.mp3`, `.wav` hoặc `.m4a` vào `docs/demo_video/` (hoặc truyền `--bgm path\to\music.mp3`) rồi chạy lại `build_video.py`.

## Đầu ra chính
- `docs/demo_video/demo_ban_do_ky_uc_100s.mp4` — Video hoàn chỉnh 1920×1080, 30fps, thời lượng 100 giây, kèm Intro/Outro OpenDesign, Lower-third badge, phụ đề tiếng Việt và thuyết minh TTS.
- `docs/demo_video/subtitles.srt` — Phụ đề tiếng Việt chuẩn UTF-8 đồng bộ theo từng mốc thời gian.
- `docs/demo_video/od_cards/` — Bộ thẻ đồ họa chuyển động (Intro Card 3s, Outro Card 8s, Lower-Third Badge) tạo qua OpenDesign.
