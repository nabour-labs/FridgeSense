"""Synthetic clips for the blur tests: a checkerboard video, and helpers to read frames back."""

from pathlib import Path

import av
import numpy as np
import skimage.draw


def checkerboard(width: int, height: int, square: int = 8) -> np.ndarray:
    """An RGB black-and-white checkerboard of `square` px squares."""
    y, x = np.indices((height, width))
    on = ((x // square) + (y // square)) % 2 == 0
    return np.repeat(np.where(on, 255, 0).astype(np.uint8)[:, :, None], 3, axis=2)


def make_clip(path: Path, width=640, height=360, frames=30, fps=15) -> Path:
    """An H.264 MP4 of `frames` checkerboard frames at `fps`, with no audio."""
    image = checkerboard(width, height)
    with av.open(str(path), "w") as out:
        stream = out.add_stream("libx264", rate=fps)
        stream.width, stream.height, stream.pix_fmt = width, height, "yuv420p"
        stream.options = {"crf": "12"}
        for _ in range(frames):
            for packet in stream.encode(av.VideoFrame.from_ndarray(image, format="rgb24")):
                out.mux(packet)
        for packet in stream.encode():
            out.mux(packet)
    return path


def luma_frames(path: Path) -> list[np.ndarray]:
    """Every decoded frame as 8-bit luminance."""
    with av.open(str(path)) as c:
        return [f.to_ndarray(format="gray").astype(float) for f in c.decode(video=0)]


def ellipse_mask(shape, box) -> np.ndarray:
    """True inside the ellipse inscribed in `box` = (x1, y1, x2, y2)."""
    x1, y1, x2, y2 = box
    mask = np.zeros(shape, bool)
    ey, ex = skimage.draw.ellipse(
        (y1 + y2) / 2, (x1 + x2) / 2, (y2 - y1) / 2 - 1, (x2 - x1) / 2 - 1, shape=shape
    )
    mask[ey, ex] = True
    return mask


def box_mask(shape, box) -> np.ndarray:
    x1, y1, x2, y2 = box
    mask = np.zeros(shape, bool)
    mask[max(0, y1) : y2, max(0, x1) : x2] = True
    return mask


class FakeDetector:
    """Returns `dets` (rows of x1, y1, x2, y2, score) for frames in `frames` (all if None)."""

    def __init__(self, dets, frames=None, fail_on=None):
        self.dets = np.array(dets, float).reshape(-1, 5)
        self.frames = frames
        self.fail_on = fail_on
        self.calls = 0

    def __call__(self, frame: np.ndarray) -> np.ndarray:
        n = self.calls
        self.calls += 1
        if self.fail_on is not None and n == self.fail_on:
            raise RuntimeError("detector failed")
        if self.frames is not None and n not in self.frames:
            return np.zeros((0, 5))
        return self.dets
