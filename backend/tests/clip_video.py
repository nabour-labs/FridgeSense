"""Tiny MP4s with solid-colour frames at known times, written with PyAV for clip tests."""

from fractions import Fraction
from pathlib import Path

from PIL import Image

Rgb = tuple[int, int, int]
MS = Fraction(1, 1000)


def write_mp4(
    path: Path, frames: list[tuple[int, Rgb]], size: tuple[int, int] = (320, 180)
) -> Path:
    """`frames` are (start ms, colour); the clip lasts until 40 ms after the last frame starts."""
    import av

    with av.open(str(path), "w") as container:
        stream = container.add_stream("mpeg4", rate=25)
        stream.width, stream.height, stream.pix_fmt = *size, "yuv420p"
        stream.codec_context.time_base = MS
        for pts, colour in frames:
            frame = av.VideoFrame.from_image(Image.new("RGB", size, colour))
            frame.pts, frame.time_base = pts, MS
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
    return path


def door_clip(
    path: Path,
    open_ms: list[tuple[int, int]],
    duration_ms: int = 20_000,
    step_ms: int = 250,
    closed: Rgb = (128, 128, 128),
    lit: Rgb = (40, 90, 200),
    size: tuple[int, int] = (320, 180),
) -> Path:
    """A clip with a frame every `step_ms`, lit (fridge open) inside each [from, to) span."""
    frames = []
    for t in range(0, duration_ms - 40 + 1, step_ms):
        is_open = any(a <= t < b for a, b in open_ms)
        frames.append((t, lit if is_open else closed))
    if frames[-1][0] != duration_ms - 40:  # make the clip last exactly duration_ms
        frames.append((duration_ms - 40, frames[-1][1]))
    return write_mp4(path, frames, size)
