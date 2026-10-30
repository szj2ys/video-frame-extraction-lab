# Video frame timing lab

## Extract a still without confusing duration with frame time

A three-second video can have its final frame at two seconds. That is not a missing frame: a frame has a presentation time and then remains visible for an interval. The end of that interval is a different number.

This small lab gives you two original clips, actual exported PNGs and a reproducible check. It helps answer three practical questions:

- Why did seeking to the displayed duration produce no image?
- How can I save the actual final decoded frame?
- When should I choose an earlier frame for a continuation?

## See the difference

Download [the three-frame clip](fixtures/three-frames.mp4), or clone/download this repository and open the [offline HTML guide](index.html) locally. GitHub displays the HTML source rather than rendering it as a web page.

| Frame index, starting at zero | Picture | Presentation time | Visible interval in this fixture |
| --- | --- | --- | --- |
| 0 | Red | 0 seconds | 0–1 seconds |
| 1 | Green | 1 second | 1–2 seconds |
| 2 | Blue | 2 seconds | 2–3 seconds |

The clip contains three 320×180 frames at one frame per second. Its duration is three seconds. There is no fourth frame beginning at three seconds.

The [second clip](fixtures/longer-audio.mp4) has exactly the same video frames plus a five-second silent audio track. Its reported container duration is five seconds, but the last video frame still starts at two seconds. Subtracting one frame interval from the container duration now gives four seconds: the wrong answer.

For evenly spaced frames beginning at time zero, `last frame start = (number of frames − 1) / frames per second`. Using `duration − 1 / fps` additionally assumes the duration describes those same video frames. Variable frame rate, a timestamp offset, a longer audio track or an edit can break that shortcut. Inspect actual presentation timestamps when accuracy matters.

## Three extraction jobs

Use a new output filename if you want to keep an existing image. The examples below select the first video stream, `0:v:0`; inspect your file if it contains multiple video tracks or cover art.

### Save the final decoded frame

```sh
ffmpeg -i "input.mp4" -map 0:v:0 -an -fps_mode passthrough -update 1 "last.png"
```

This decodes the selected video stream and repeatedly updates one PNG. After the process finishes, the file contains the last frame delivered to that output. It can be slow for long clips, but it avoids estimating a seek time from the container duration. Do not add `-frames:v 1` to this command: that would stop after its first output frame.

### Save a known frame index

```sh
ffmpeg -i "input.mp4" -map 0:v:0 -an -vf "select=eq(n\,1)" -frames:v 1 -fps_mode passthrough -update 1 "frame-1.png"
```

Here `n=1` means the second decoded frame. On our fixture it saves green, not blue. Replace `1` with your desired zero-based frame index. This command does not infer which frame looks best.

### Inspect timestamps

```sh
ffmpeg -i "input.mp4" -map 0:v:0 -an -vf showinfo -f null -
```

Look for the `pts_time` values in the diagnostic output. The fixture reports `0`, `1`, `2`. Timestamp inspection and a visible picture together are more useful than a successful exit code alone. See the official [FFmpeg command reference](https://ffmpeg.org/ffmpeg.html), [image2 output options](https://ffmpeg.org/ffmpeg-formats.html#image2-1), and [select filter reference](https://ffmpeg.org/ffmpeg-filters.html#select_002c-aselect) for the underlying controls.

## Reproduce the result

You need Python 3.10+ and an FFmpeg build with H.264 encoding (`libx264`), AAC encoding and PNG support. No Python packages are required. The recorded run used FFmpeg 7.1 on Windows. No FFmpeg executable is distributed here.

```sh
python frame_timing_lab.py --out lab-output
```

If FFmpeg is not on your command path:

```sh
python frame_timing_lab.py --ffmpeg "/path/to/ffmpeg" --out lab-output
```

Choose a **new** output directory each time. The script refuses an existing directory, generates its own colored source frames, encodes the two fixtures, runs the three extraction/inspection operations and checks the resulting pixels and timestamps. It does not upload anything or modify your own videos.

The [recorded result](fixtures/result.json) from 30 October 2026 contains eight passed checks:

1. Video presentation timestamps are 0, 1 and 2 seconds.
2. The silent video-only clip reports a three-second duration.
3. Full decoding leaves a blue final PNG.
4. Selecting index 1 produces a green PNG.
5. Seeking to the three-second endpoint creates no PNG, **even though FFmpeg exits with code 0**.
6. Both exported PNGs are 320×180.
7. Adding longer audio changes the reported duration to five seconds.
8. The video timestamps remain 0, 1 and 2 seconds.

These are fixture results, not a claim that every build, codec or damaged file behaves identically. The script saves command logs so a failed reproduction can be investigated.

## Pick a free tool by the job

This is a small comparison of different workflows, not a ranking. Product-page limits were checked on 30 October 2026 and can change.

| Tool | Useful job | Processing and limits | What was checked here |
| --- | --- | --- | --- |
| [FFmpeg](https://ffmpeg.org/) | Repeatable frame-index extraction, local files and scripts | Runs locally. Supported formats depend on the installed build; requires command-line use. | The two synthetic fixtures and commands above were actually run with 7.1. |
| [imgmov Last-Frame Extractor](https://imgmov.com/extract-last-frame-from-video) | Inspect ending frames and choose a PNG for a continuation reference | The standalone tool processes selected files in the browser without an account. Its page lists MP4/WebM/MOV, up to 512 MB and two minutes; browser codec support still matters. | The official page and its stated limits were read. This synthetic lab tests FFmpeg, not this browser service. |
| [Ezgif Video to PNG](https://ezgif.com/video-to-png) | Export a sequence of images, with range/frame-rate controls and ZIP output | Upload-based service. Its page lists a 200 MB limit and says uploaded files are deleted after one hour. Use a local tool for footage you cannot upload. | Official instructions and limits were read; no file was uploaded or conversion benchmark run. |

## Choose a useful ending, not merely the last frame

For a thumbnail, save the picture that communicates the subject clearly. For a continuation reference, inspect the final decoded frame first. If it is black, faded, blurred or visibly distorted, inspect earlier frames.

If you choose an earlier reference, make the source clip end at the same chosen picture in your editor. Otherwise the audience sees later pictures before the next clip begins from an older one. A sharpness score cannot establish semantic correctness: check faces, hands, labels, edges and motion direction yourself.

PNG export cannot recreate detail lost in video compression. The fixture tests do not cover HDR, tone mapping, rotation metadata, variable frame rate, multiple tracks or corrupt media. For color-critical footage, use a color-managed workflow and inspect the exported image rather than assuming a file extension guarantees fidelity.

## Scope and attribution

Prepared by contributors working on imgmov, which is one of the tools listed above. This guide covers frame extraction; imgmov's AI generation backend is not required for the standalone extraction workflow and is not advertised as available here. No third-party endorsement or independent benchmark is implied.

All included fixture pixels and audio are generated by the supplied script. No customer footage, third-party video, vendor screenshots, analytics or account data are included. The [MIT license](LICENSE) covers this repository's newly authored guide, page, code and synthetic fixtures. External tools, their documentation and trademarks retain their own terms and licenses.
