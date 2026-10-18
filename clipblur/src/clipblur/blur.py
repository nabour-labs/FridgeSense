"""Blur every face in a clip with deface, leaving the rest of each frame as recorded."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import av
import numpy as np
from deface.deface import anonymize_frame

# A detector takes an RGB frame and returns rows of (x1, y1, x2, y2, score) in frame pixels.
Detector = Callable[[np.ndarray], np.ndarray]

THRESHOLD = 0.2  # deface's default score threshold
# deface grows each side of a box by (mask_scale - 1) of its size: 1.15 makes it 30% bigger
# about its centre, as the stills' face boxes are.
MASK_SCALE = 1.15
MAX_DETECT_WIDTH = 960  # detection runs on a copy at most this wide; boxes come back full size
CRF = "18"  # visually lossless: outside the faces only re-encoding noise remains


class ClipUnreadable(Exception):
    """The raw clip can't be opened or decoded."""


@dataclass
class BlurStats:
    frames: int = 0
    frames_with_faces: int = 0


def centerface(width: int, height: int) -> Detector:
    """deface's CenterFace model, run at most MAX_DETECT_WIDTH px wide."""
    from deface.centerface import CenterFace

    scale = min(1.0, MAX_DETECT_WIDTH / width)
    model = CenterFace(
        in_shape=(round(width * scale), round(height * scale)),
        override_execution_provider="CPUExecutionProvider",  # all Lambda has; CoreML is slower
    )

    def detect(frame: np.ndarray) -> np.ndarray:
        dets, _landmarks = model(frame, threshold=THRESHOLD)
        return dets

    return detect


def blur_frame(frame: np.ndarray, dets: np.ndarray) -> int:
    """Blur an ellipse over each face scoring at least THRESHOLD, in place. Returns how many."""
    faces = dets[dets[:, 4] >= THRESHOLD] if len(dets) else dets
    if len(faces):
        anonymize_frame(
            faces,
            frame,
            mask_scale=MASK_SCALE,
            replacewith="blur",
            ellipse=True,
            draw_scores=False,
            replaceimg=None,
            mosaicsize=20,
        )
    return len(faces)


def blur_clip(src: Path, dst: Path, detector: Detector | None = None) -> BlurStats:
    """Write `src` to `dst` as H.264 MP4 with every face blurred: same size, frames and rate,
    no audio. On any error `dst` is removed and the error raised."""
    stats = BlurStats()
    try:
        try:
            source = av.open(str(src))
            video = source.streams.video[0]
        except (av.error.FFmpegError, IndexError) as e:
            raise ClipUnreadable(str(e)) from e
        with source, av.open(str(dst), "w", options={"movflags": "+faststart"}) as out:
            ctx = video.codec_context
            stream = out.add_stream("libx264", rate=video.average_rate or 15)
            stream.width, stream.height, stream.pix_fmt = ctx.width, ctx.height, "yuv420p"
            stream.options = {"crf": CRF, "preset": "veryfast"}
            detect = detector or centerface(ctx.width, ctx.height)
            try:
                frames = source.decode(video)
                for frame in frames:
                    rgb = frame.to_ndarray(format="rgb24")
                    if blur_frame(rgb, np.asarray(detect(rgb), float).reshape(-1, 5)):
                        stats.frames_with_faces += 1
                    stats.frames += 1
                    for packet in stream.encode(av.VideoFrame.from_ndarray(rgb, format="rgb24")):
                        out.mux(packet)
            except av.error.FFmpegError as e:
                raise ClipUnreadable(str(e)) from e
            for packet in stream.encode():
                out.mux(packet)
        if stats.frames == 0:
            raise ClipUnreadable("no frames")
    except BaseException:
        dst.unlink(missing_ok=True)
        raise
    return stats
