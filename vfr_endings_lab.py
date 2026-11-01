"""Reproduce unequal frame spacing and an intentionally black video ending."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess

WIDTH, HEIGHT = 320, 180
COLORS = [(240, 20, 20), (20, 220, 20), (20, 20, 240), (0, 0, 0), (0, 0, 0)]
EXPECTED_TIMES = [0.0, 0.08, 0.48, 0.60, 0.80]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ffmpeg', default=shutil.which('ffmpeg'))
    parser.add_argument('--out', type=Path, required=True, help='A new directory; existing directories are refused')
    args = parser.parse_args()
    if not args.ffmpeg:
        parser.error('FFmpeg is required; supply --ffmpeg with its executable path')
    executable = str(Path(args.ffmpeg).resolve())
    if not Path(executable).is_file():
        parser.error('The supplied FFmpeg executable does not exist')
    args.out.mkdir(parents=True, exist_ok=False)
    commands = []

    def run(label, arguments):
        completed = subprocess.run([executable, '-hide_banner', '-n', *arguments], cwd=args.out, capture_output=True)
        (args.out / (label + '.log')).write_bytes(completed.stderr)
        commands.append({'label': label, 'arguments': arguments, 'returncode': completed.returncode})
        if completed.returncode:
            raise RuntimeError(f'{label} failed; inspect {label}.log')
        return completed

    for index, color in enumerate(COLORS):
        (args.out / f'frame-{index}.ppm').write_bytes(f'P6\n{WIDTH} {HEIGHT}\n255\n'.encode() + bytes(color) * (WIDTH * HEIGHT))
    durations = [0.08, 0.40, 0.12, 0.20, 0.04]
    manifest = 'ffconcat version 1.0\n' + ''.join(f"file frame-{i}.ppm\nduration {duration:.2f}\n" for i, duration in enumerate(durations))
    (args.out / 'frames.ffconcat').write_text(manifest, encoding='ascii')
    run('encode', ['-f', 'concat', '-safe', '1', '-i', 'frames.ffconcat', '-fps_mode', 'vfr', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18', 'vfr-black-ending.mp4'])
    inspected = run('timestamps', ['-i', 'vfr-black-ending.mp4', '-map', '0:v:0', '-an', '-vf', 'showinfo', '-f', 'null', '-'])
    times = [float(x) for x in re.findall(r'\bn:\s*\d+.*?\bpts_time:([\d.-]+)', inspected.stderr.decode(errors='replace'))]
    run('last', ['-i', 'vfr-black-ending.mp4', '-map', '0:v:0', '-an', '-fps_mode', 'passthrough', '-update', '1', 'last.png'])
    run('selected', ['-i', 'vfr-black-ending.mp4', '-map', '0:v:0', '-an', '-vf', 'select=eq(n\,2)', '-frames:v', '1', '-fps_mode', 'passthrough', '-update', '1', 'selected.png'])
    run('contact-sheet', ['-i', 'vfr-black-ending.mp4', '-map', '0:v:0', '-an', '-vf', 'tile=5x1:padding=4:margin=4:color=white', '-frames:v', '1', '-update', '1', 'contact-sheet.png'])

    def decode_rgb(filename):
        png = (args.out / filename).read_bytes()
        if png[:8] != b'\x89PNG\r\n\x1a\n' or struct.unpack('>II', png[16:24]) != (WIDTH, HEIGHT):
            raise RuntimeError(f'{filename}: unexpected PNG dimensions')
        decoded = run(filename + '-pixels', ['-i', filename, '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'])
        if len(decoded.stdout) != WIDTH * HEIGHT * 3:
            raise RuntimeError(f'{filename}: unexpected decoded dimensions')
        offset = ((HEIGHT // 2) * WIDTH + WIDTH // 2) * 3
        return list(decoded.stdout[offset:offset + 3])

    last = decode_rgb('last.png')
    selected = decode_rgb('selected.png')
    intervals = [round(b - a, 6) for a, b in zip(times, times[1:])]
    checks = {
        'five_decoded_frames': len(times) == 5,
        'expected_presentation_timestamps': len(times) == 5 and all(abs(a - b) < 0.00001 for a, b in zip(times, EXPECTED_TIMES)),
        'unequal_frame_intervals': len(set(intervals)) > 1,
        'last_png_is_black': max(last) < 8,
        'selected_png_is_blue': selected[2] > 220 and max(selected[:2]) < 35,
        'exported_dimensions': True,
    }
    version = subprocess.run([executable, '-version'], capture_output=True, text=True, check=True).stdout.splitlines()[0]
    files = {name: {'bytes': (args.out / name).stat().st_size, 'sha256': hashlib.sha256((args.out / name).read_bytes()).hexdigest()} for name in ['vfr-black-ending.mp4', 'last.png', 'selected.png', 'contact-sheet.png']}
    result = {'ffmpeg_version': version, 'presentation_times_seconds': times, 'intervals_seconds': intervals, 'selected_frame_index': 2, 'selected_time_seconds': times[2] if len(times) > 2 else None, 'last_center_rgb': last, 'selected_center_rgb': selected, 'image_dimensions': [WIDTH, HEIGHT], 'checks': checks, 'commands': commands, 'artifacts': files, 'passed': all(checks.values())}
    (args.out / 'result.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'passed': result['passed'], 'checks': checks, 'presentation_times_seconds': times}))
    if not result['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
