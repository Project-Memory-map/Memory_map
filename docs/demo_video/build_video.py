"""Hậu kỳ tự động tạo thuyết minh tiếng Việt (edge-tts), phụ đề (.srt), badge & ghép video 100s bằng FFmpeg."""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import edge_tts
import imageio_ffmpeg

sys.path.insert(0, str(Path(__file__).resolve().parent))
import demo_config as cfg  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
AUDIO_RE = re.compile(r"Stream #\d+:\d+.*Audio:")


def get_ffmpeg() -> str:
    return shutil.which("ffmpeg") or imageio_ffmpeg.get_ffmpeg_exe()


def run_ffmpeg(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    ffmpeg = get_ffmpeg()
    res = subprocess.run(
        [ffmpeg, "-y", *args],
        cwd=str(cwd or cfg.WORK_DIR),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if res.returncode != 0:
        raise RuntimeError(f"FFmpeg thất bại ({res.returncode}):\n{' '.join(args)}\n{res.stderr}")
    return res


def probe_media(path: Path) -> dict[str, object]:
    """Đọc thời lượng và trạng thái luồng âm thanh bằng `ffmpeg -i` (không cần ffprobe)."""
    ffmpeg = get_ffmpeg()
    res = subprocess.run(
        [ffmpeg, "-hide_banner", "-i", str(path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    stderr = res.stderr or ""
    m = DURATION_RE.search(stderr)
    duration = 0.0
    if m:
        h, mn, sec = int(m.group(1)), int(m.group(2)), float(m.group(3))
        duration = h * 3600 + mn * 60 + sec
    return {
        "duration": duration,
        "has_audio": bool(AUDIO_RE.search(stderr)),
        "raw": stderr,
    }


def fmt_srt_time(seconds: float) -> str:
    ms_total = max(0, int(round(seconds * 1000)))
    h, rem = divmod(ms_total, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def wrap_subtitle(text: str, width: int = 56) -> str:
    lines = textwrap.wrap(text.strip(), width=width)
    if len(lines) <= 2:
        return "\n".join(lines)
    mid = len(text) // 2
    split_at = text.rfind(" ", 0, mid + 8)
    if split_at <= 0:
        return "\n".join(lines)
    return text[:split_at].strip() + "\n" + text[split_at + 1 :].strip()


async def _tts_save(text: str, out_mp3: Path, voice: str, rate: str) -> None:
    tts_text = re.sub(r"\s*[—–]\s*", ", ", text).replace("→", " sang ").strip()
    delays = (0.6, 1.2, 2.0, 3.0, 4.0)
    last_err: Exception | None = None
    for attempt in range(6):
        try:
            communicate = edge_tts.Communicate(text=tts_text, voice=voice, rate=rate)
            await communicate.save(str(out_mp3))
            if out_mp3.exists() and out_mp3.stat().st_size > 1000:
                await asyncio.sleep(0.3)
                return
        except Exception as exc:
            last_err = exc
        if attempt < len(delays):
            await asyncio.sleep(delays[attempt])
    raise RuntimeError(f"edge-tts thất bại sau 6 lần thử cho câu: {tts_text!r}") from last_err


def build_audio_and_subtitles(voice: str, rate: str) -> tuple[Path, list[tuple[float, float, str]]]:
    """Tạo file thoại cho từng phân đoạn, co dãn nhẹ nếu vượt khung giờ, và xuất subtitles.srt."""
    cfg.AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    seg_wavs: list[Path] = []
    subtitles: list[tuple[float, float, str]] = []
    global_cursor = 0.0

    for seg in cfg.SEGMENTS:
        lead_in = 0.15 if seg.id == "s1_intro" else 0.35
        tail_guard = 0.15 if seg.id == "s1_intro" else 0.35
        gap = 0.22

        raw_clips: list[tuple[Path, float, str]] = []
        for idx, text in enumerate(seg.narrations):
            mp3_path = cfg.AUDIO_DIR / f"{seg.id}_{idx}.mp3"
            asyncio.run(_tts_save(text, mp3_path, voice, rate))
            dur = float(probe_media(mp3_path)["duration"])
            raw_clips.append((mp3_path, dur, text))

        raw_total = sum(d for _, d, _ in raw_clips) + gap * max(0, len(raw_clips) - 1)
        budget = max(0.8, seg.duration - lead_in - tail_guard)
        tempo = min(1.22, raw_total / budget) if raw_total > budget else 1.0

        fitted_clips: list[tuple[Path, float, str]] = []
        for idx, (mp3_path, dur, text) in enumerate(raw_clips):
            wav_line = cfg.AUDIO_DIR / f"{seg.id}_{idx}_fit.wav"
            af = [f"atempo={tempo:.4f}"] if tempo > 1.005 else []
            af.append("aresample=48000")
            run_ffmpeg(["-i", str(mp3_path), "-af", ",".join(af), "-ac", "2", "-ar", "48000", str(wav_line)])
            fitted_dur = float(probe_media(wav_line)["duration"])
            fitted_clips.append((wav_line, fitted_dur, text))

        # Ghép các câu trong phân đoạn thành 1 track đúng thời lượng `seg.duration`
        seg_wav = cfg.AUDIO_DIR / f"{seg.id}_voice.wav"
        inputs: list[str] = ["-f", "lavfi", "-t", f"{seg.duration:.3f}", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000"]
        filter_parts: list[str] = []
        mix_labels: list[str] = ["[0:a]"]
        local_t = lead_in
        for idx, (wav_line, dur, text) in enumerate(fitted_clips, start=1):
            inputs.extend(["-i", str(wav_line)])
            delay_ms = max(0, int(round(local_t * 1000)))
            label = f"[a{idx}]"
            filter_parts.append(f"[{idx}:a]adelay={delay_ms}|{delay_ms}{label}")
            mix_labels.append(label)
            sub_start = global_cursor + local_t
            sub_end = min(global_cursor + seg.duration - 0.08, sub_start + dur + 0.12)
            subtitles.append((sub_start, sub_end, text))
            local_t += dur + gap

        filter_complex = ";".join(
            filter_parts + [f"{''.join(mix_labels)}amix=inputs={len(mix_labels)}:duration=first:normalize=0,atrim=0:{seg.duration:.3f}[aout]"]
        )
        run_ffmpeg([*inputs, "-filter_complex", filter_complex, "-map", "[aout]", "-ac", "2", "-ar", "48000", str(seg_wav)])
        seg_wavs.append(seg_wav)
        global_cursor += seg.duration

    # Xuất file SRT chuẩn UTF-8
    srt_lines: list[str] = []
    for idx, (st, en, text) in enumerate(subtitles, start=1):
        srt_lines.append(f"{idx}\n{fmt_srt_time(st)} --> {fmt_srt_time(en)}\n{wrap_subtitle(text)}\n")
    cfg.SUBTITLES_SRT.write_text("\n".join(srt_lines), encoding="utf-8")

    # Nối toàn bộ track thoại thành voice_full.wav
    concat_txt = cfg.AUDIO_DIR / "voice_concat.txt"
    concat_txt.write_text("\n".join(f"file '{p.as_posix()}'" for p in seg_wavs), encoding="utf-8")
    voice_full = cfg.WORK_DIR / "voice_full.wav"
    run_ffmpeg(["-f", "concat", "-safe", "0", "-i", str(concat_txt), "-c:a", "pcm_s16le", str(voice_full)])
    return voice_full, subtitles


def build_video_clips() -> list[Path]:
    """Cắt 6 phân đoạn live từ raw_screen.webm, khớp thời lượng mục tiêu và gắn OpenDesign Lower-Third badge."""
    if not cfg.MARKS_JSON.exists() or not cfg.RAW_SCREEN_WEBM.exists():
        raise FileNotFoundError("Chưa có dữ liệu quay thô. Hãy chạy record_demo.py trước.")

    marks = json.loads(cfg.MARKS_JSON.read_text(encoding="utf-8"))
    raw_dur = float(probe_media(cfg.RAW_SCREEN_WEBM)["duration"])
    close_time = float(marks["close_time"])

    def webm_ts(mono_ts: float) -> float:
        return max(0.0, min(raw_dur - 0.1, raw_dur - (close_time - mono_ts)))

    live_specs = [seg for seg in cfg.SEGMENTS if seg.kind == "live"]
    boundaries: dict[str, tuple[float, float]] = {}
    for i, seg in enumerate(live_specs):
        t0 = webm_ts(float(marks[f"{seg.id}_start"]))
        if i + 1 < len(live_specs):
            t1 = webm_ts(float(marks[f"{live_specs[i + 1].id}_start"]))
        else:
            t1 = webm_ts(float(marks["s6_admin_end"]))
        boundaries[seg.id] = (t0, max(t0 + 0.5, t1))

    cfg.CLIPS_DIR.mkdir(parents=True, exist_ok=True)
    ordered_clips: list[Path] = []

    for seg in cfg.SEGMENTS:
        if seg.id == "s1_intro":
            ordered_clips.append(cfg.WORK_DIR / "intro_3s.mp4")
            continue
        if seg.id == "s7_outro":
            ordered_clips.append(cfg.WORK_DIR / "outro_8s.mp4")
            continue

        start_t, end_t = boundaries[seg.id]
        actual_dur = max(0.5, end_t - start_t)
        target_dur = seg.duration
        pts_factor = max(0.68, min(1.30, target_dur / actual_dur))
        scaled_dur = actual_dur * pts_factor
        pad_dur = max(0.0, target_dur - scaled_dur)

        v_chain = [
            f"setpts={pts_factor:.6f}*(PTS-STARTPTS)",
            f"scale={cfg.WIDTH}:{cfg.HEIGHT}:force_original_aspect_ratio=decrease",
            f"pad={cfg.WIDTH}:{cfg.HEIGHT}:(ow-iw)/2:(oh-ih)/2:color=#0f172a",
            "setsar=1",
            f"fps={cfg.FPS}",
        ]
        if pad_dur > 0.02:
            v_chain.append(f"tpad=stop_mode=clone:stop_duration={pad_dur:.3f}")
        v_chain.append(f"trim=duration={target_dur:.3f}")

        badge_png = cfg.BADGES_DIR / f"{seg.id}.png"
        clip_out = cfg.CLIPS_DIR / f"{seg.id}.mp4"
        if badge_png.exists():
            fade_out_st = max(0.6, target_dur - 0.55)
            filter_complex = (
                f"[0:v]{','.join(v_chain)}[base];"
                f"[1:v]format=rgba,fade=t=in:st=0.25:d=0.30:alpha=1,fade=t=out:st={fade_out_st:.3f}:d=0.30:alpha=1[badge];"
                f"[base][badge]overlay=0:0:shortest=1,format=yuv420p[vout]"
            )
            run_ffmpeg([
                "-ss", f"{start_t:.3f}", "-to", f"{end_t:.3f}", "-i", str(cfg.RAW_SCREEN_WEBM),
                "-loop", "1", "-t", f"{target_dur:.3f}", "-i", str(badge_png),
                "-filter_complex", filter_complex,
                "-map", "[vout]",
                "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "17", "-pix_fmt", "yuv420p", "-r", str(cfg.FPS), "-video_track_timescale", "30000",
                str(clip_out),
            ])
        else:
            run_ffmpeg([
                "-ss", f"{start_t:.3f}", "-to", f"{end_t:.3f}", "-i", str(cfg.RAW_SCREEN_WEBM),
                "-vf", ",".join(v_chain) + ",format=yuv420p",
                "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "17", "-pix_fmt", "yuv420p", "-r", str(cfg.FPS), "-video_track_timescale", "30000",
                str(clip_out),
            ])
        print(f"  + {seg.id}: thô {actual_dur:.2f}s -> chuẩn {target_dur:.2f}s (speed {1/pts_factor:.2f}x)")
        ordered_clips.append(clip_out)

    return ordered_clips


def find_bgm(explicit_bgm: str | None) -> Path | None:
    if explicit_bgm:
        p = Path(explicit_bgm)
        if not p.is_file():
            raise FileNotFoundError(f"Không tìm thấy file nhạc nền: {p}")
        return p
    for ext in ("*.mp3", "*.wav", "*.m4a", "*.ogg"):
        matches = sorted(p for p in cfg.DEMO_DIR.glob(ext) if p.is_file())
        if matches:
            return matches[0]
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Dựng video demo 100s cho Bản đồ Ký ức")
    parser.add_argument("--voice", default=cfg.DEFAULT_VOICE, help="Giọng edge-tts (vd: vi-VN-NamMinhNeural hoặc vi-VN-HoaiMyNeural)")
    parser.add_argument("--rate", default=cfg.DEFAULT_RATE, help="Tốc độ đọc edge-tts (mặc định: +5%%)")
    parser.add_argument("--bgm", default=None, help="Đường dẫn file nhạc nền tùy chọn (âm lượng -22dB)")
    parser.add_argument("--bgm-start", type=float, default=0.0, help="Bắt đầu phát nhạc nền từ giây thứ mấy (mặc định: 0)")
    args = parser.parse_args()

    print(f"1/4 Tạo giọng đọc tiếng Việt ({args.voice}, rate={args.rate}) và xuất {cfg.SUBTITLES_SRT.name}...")
    voice_full, _ = build_audio_and_subtitles(args.voice, args.rate)

    print("2/4 Cắt, đồng bộ thời lượng và gắn Lower-Third Badge lên từng phân đoạn...")
    clips = build_video_clips()

    print("3/4 Ghép Intro + 6 phân đoạn quay thực tế + Outro...")
    concat_vid_txt = cfg.WORK_DIR / "video_concat.txt"
    concat_vid_txt.write_text("\n".join(f"file '{p.as_posix()}'" for p in clips), encoding="utf-8")
    master_silent = cfg.WORK_DIR / "master_silent.mp4"
    run_ffmpeg(["-f", "concat", "-safe", "0", "-i", str(concat_vid_txt), "-c", "copy", str(master_silent)])

    total_dur = float(probe_media(master_silent)["duration"]) or cfg.TOTAL_DURATION
    if not (98.0 <= total_dur <= 102.0):
        inputs_v: list[str] = []
        filter_v: list[str] = []
        for idx, p in enumerate(clips):
            inputs_v.extend(["-i", str(p)])
            filter_v.append(f"[{idx}:v]fps={cfg.FPS},format=yuv420p,setsar=1[v{idx}]")
        concat_inputs = "".join(f"[v{i}]" for i in range(len(clips)))
        filter_v.append(f"{concat_inputs}concat=n={len(clips)}:v=1:a=0[vout]")
        run_ffmpeg([
            *inputs_v,
            "-filter_complex", ";".join(filter_v),
            "-map", "[vout]",
            "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "16", "-pix_fmt", "yuv420p", "-r", str(cfg.FPS), "-video_track_timescale", "30000",
            str(master_silent),
        ])
        total_dur = float(probe_media(master_silent)["duration"]) or cfg.TOTAL_DURATION
    fade_out_v = max(1.0, total_dur - 0.6)

    bgm_path = find_bgm(args.bgm)
    sub_style = (
        "FontName=Segoe UI,FontSize=20,Bold=0,"
        "PrimaryColour=&H00FFFFFF,OutlineColour=&H000F172A,BackColour=&H990F172A,"
        "BorderStyle=4,Outline=1,Shadow=0,MarginV=24,Alignment=2"
    )
    vf = (
        f"subtitles='subtitles.srt':charenc=UTF-8:force_style='{sub_style}',"
        f"fade=t=in:st=0:d=0.3,fade=t=out:st={fade_out_v:.3f}:d=0.6,format=yuv420p"
    )

    print(f"4/4 Burn phụ đề tiếng Việt & mix âm thanh -> {cfg.OUTPUT_VIDEO} ...")
    if bgm_path:
        bgm_input = bgm_path
        if args.bgm_start > 0:
            bgm_trimmed = cfg.WORK_DIR / "bgm_trimmed.wav"
            run_ffmpeg(["-ss", f"{args.bgm_start:.3f}", "-i", str(bgm_path), "-ac", "2", "-ar", "48000", str(bgm_trimmed)])
            bgm_input = bgm_trimmed
        print(f"    (Phát hiện nhạc nền: {bgm_path.name} từ giây {args.bgm_start:.1f}s — ghép ở mức -22dB)")
        fade_out_bgm = max(1.0, total_dur - 3.0)
        run_ffmpeg(
            [
                "-i", str(master_silent),
                "-i", str(voice_full),
                "-stream_loop", "-1", "-i", str(bgm_input),
                "-filter_complex",
                f"[0:v]{vf}[vout];"
                f"[2:a]atrim=0:{total_dur:.3f},afade=t=in:st=0:d=2.0,afade=t=out:st={fade_out_bgm:.3f}:d=3.0,volume=-22dB[bgm];"
                f"[1:a][bgm]amix=inputs=2:duration=first:normalize=0[aout]",
                "-map", "[vout]",
                "-map", "[aout]",
                "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-r", str(cfg.FPS),
                "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
                "-movflags", "+faststart",
                "-shortest",
                str(cfg.OUTPUT_VIDEO),
            ],
            cwd=cfg.DEMO_DIR,
        )
    else:
        run_ffmpeg(
            [
                "-i", str(master_silent),
                "-i", str(voice_full),
                "-vf", vf,
                "-map", "0:v",
                "-map", "1:a",
                "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-r", str(cfg.FPS),
                "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
                "-movflags", "+faststart",
                "-shortest",
                str(cfg.OUTPUT_VIDEO),
            ],
            cwd=cfg.DEMO_DIR,
        )

    info = probe_media(cfg.OUTPUT_VIDEO)
    size_mb = cfg.OUTPUT_VIDEO.stat().st_size / (1024 * 1024)
    print(f"HOÀN TẤT: {cfg.OUTPUT_VIDEO} ({size_mb:.2f} MB, thời lượng {info['duration']:.2f}s)")


if __name__ == "__main__":
    main()
