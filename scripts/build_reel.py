"""Usage: python3 build_reel.py REEL_DIR [SECONDS]

Assemble a reel from REEL_DIR: frames/*.png + audio/vo*.wav + audio/music.wav -> reel.mp4 (1080x1920, 30 fps, exactly TARGET s)."""
import glob, os, subprocess, sys

HERE = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = float(sys.argv[2]) if len(sys.argv) > 2 else 30.0
_, XF, FPS, LEAD, HOLD = 30.0, 0.4, 30, 0.3, 1.5   # total, crossfade, fps, VO delay after cut, extra hold on last frame
frames = sorted(glob.glob(f"{HERE}/frames/*.png"))
vos = sorted(glob.glob(f"{HERE}/audio/vo*.wav"))
assert len(frames) == len(vos), (len(frames), len(vos))

dur = lambda f: float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f]))
vo_len = [dur(v) for v in vos]
n = len(frames)
pad = (TARGET + XF * (n - 1) - sum(vo_len) - HOLD) / n          # spread the spare time evenly
scene = [v + pad for v in vo_len]; scene[-1] += HOLD
starts = [sum(scene[:i]) - XF * i for i in range(n)]
assert pad > LEAD + 0.1, f"voiceover too long for {TARGET}s (pad {pad:.2f}s)"

cmd = ["ffmpeg", "-y", "-v", "error"]
for f, d in zip(frames, scene):
    cmd += ["-loop", "1", "-framerate", str(FPS), "-t", f"{d:.3f}", "-i", f]
for v in vos:
    cmd += ["-i", v]
cmd += ["-i", f"{HERE}/audio/music.wav"]

g = []
for i, d in enumerate(scene):   # slow push-in anchored to the bottom edge so the footer bar is never cropped
    fr = int(round(d * FPS))
    g.append(f"[{i}:v]scale=1080:1920,setsar=1,zoompan=z='1+0.035*on/{fr}':x='iw/2-(iw/zoom/2)':y='ih-ih/zoom'"
             f":d=1:s=1080x1920:fps={FPS},format=yuv420p[v{i}]")
last = "v0"
for i in range(1, n):
    off = starts[i]
    g.append(f"[{last}][v{i}]xfade=transition={'slideleft' if i % 2 else 'fade'}:duration={XF}:offset={off:.3f}[x{i}]")
    last = f"x{i}"
for i in range(n):              # place each VO line just after its scene starts
    ms = int((starts[i] + LEAD) * 1000)
    g.append(f"[{n + i}:a]aformat=sample_rates=44100:channel_layouts=stereo,adelay={ms}|{ms}[a{i}]")
g.append("".join(f"[a{i}]" for i in range(n)) + f"amix=inputs={n}:normalize=0,volume=1.6[vo]")
g.append(f"[vo]apad=whole_dur={TARGET},asplit=2[vo1][vo2]")
g.append(f"[{2 * n}:a]volume=0.32,afade=t=in:d=0.6[mus]")
g.append("[mus][vo1]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=300[duck]")
g.append(f"[duck][vo2]amix=inputs=2:normalize=0,alimiter=limit=0.95,atrim=0:{TARGET},afade=t=out:st={TARGET - 1.2}:d=1.2[aout]")
cmd += ["-filter_complex", ";".join(g), "-map", f"[{last}]", "-map", "[aout]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-profile:v", "high", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-t", str(TARGET), f"{HERE}/reel.mp4"]
subprocess.run(cmd, check=True)
for i in range(n):
    print(f"scene {i + 1}: {starts[i]:6.2f}s  dur {scene[i]:.2f}s  VO {vo_len[i]:.2f}s  {os.path.basename(frames[i])}")
print("wrote", f"{HERE}/reel.mp4")
