"""door-event-detection: Faces blurred before storage."""

import io
import json
import logging

import boto3
import pytest
from botocore.exceptions import ReadTimeoutError
from botocore.stub import Stubber
from PIL import Image, ImageChops, ImageStat

from fridgesense.faces import FaceBlurrer, blur_regions, enlarge_box
from tests.conftest import checkerboard_jpeg, load_fixture

CONTEXT = {"account_id": "ava1.ring.account.A1", "device_id": "ava1.ring.device.D1", "still": 3}

ONE_FACE = (0.40, 0.20, 0.20, 0.30)
TWO_FACES = [(0.05, 0.10, 0.15, 0.25), (0.70, 0.30, 0.15, 0.25)]


def gray(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data)).convert("L")


def pixels(img: Image.Image, box) -> tuple[int, int, int, int]:
    W, H = img.size
    x, y, w, h = box
    return round(x * W), round(y * H), round((x + w) * W), round((y + h) * H)


def stddev_inside(data: bytes, box) -> float:
    img = gray(data)
    return ImageStat.Stat(img.crop(pixels(img, box))).stddev[0]


def mean_diff_outside(before: bytes, after: bytes, boxes) -> float:
    diff = ImageChops.difference(gray(before), gray(after))
    mask = Image.new("L", diff.size, 255)
    for box in boxes:
        mask.paste(0, pixels(diff, box))
    return ImageStat.Stat(diff, mask).mean[0]


def test_one_face_found_box_is_enlarged_by_30_percent():
    box = enlarge_box((0.40, 0.20, 0.20, 0.30))
    assert box == pytest.approx((0.37, 0.155, 0.26, 0.39))


def test_face_at_the_image_edge_box_is_clipped():
    x, y, w, h = enlarge_box((0.90, -0.05, 0.15, 0.25))
    assert (x, y) == pytest.approx((0.8775, 0.0))
    assert x + w == pytest.approx(1.0)
    assert h == pytest.approx(0.2375)


def test_one_face_found_box_is_blurred_and_rest_unchanged():
    original = checkerboard_jpeg()
    blurred = blur_regions(original, [ONE_FACE])
    enlarged = enlarge_box(ONE_FACE)
    assert stddev_inside(original, enlarged) > 100
    assert stddev_inside(blurred, enlarged) < 10
    assert mean_diff_outside(original, blurred, [enlarged]) <= 3


def test_two_faces_found_both_boxes_are_blurred():
    blurred = blur_regions(checkerboard_jpeg(), TWO_FACES)
    for face in TWO_FACES:
        assert stddev_inside(blurred, enlarge_box(face)) < 10


def test_face_at_the_image_edge_visible_part_is_blurred():
    edge = (0.90, -0.05, 0.15, 0.25)
    blurred = blur_regions(checkerboard_jpeg(), [edge])
    assert stddev_inside(blurred, enlarge_box(edge)) < 10


def test_blurred_still_is_a_jpeg_of_the_same_size():
    img = Image.open(io.BytesIO(blur_regions(checkerboard_jpeg(), [ONE_FACE])))
    assert img.format == "JPEG" and img.size == (320, 180)


@pytest.fixture
def rekognition():
    client = boto3.client(
        "rekognition",
        region_name="us-east-1",
        aws_access_key_id="testing",
        aws_secret_access_key="testing",
    )
    with Stubber(client) as stub:
        yield client, stub
        stub.assert_no_pending_responses()


def detect(stub, data: bytes, response: dict) -> None:
    stub.add_response(
        "detect_faces", response, {"Image": {"Bytes": data}, "Attributes": ["DEFAULT"]}
    )


def test_no_face_found_bytes_are_returned_unchanged(rekognition):
    client, stub = rekognition
    original = checkerboard_jpeg()
    detect(stub, original, {"FaceDetails": []})
    assert FaceBlurrer(client).blur(original, CONTEXT) == original


def test_one_face_found_detector_blurs_it(rekognition):
    client, stub = rekognition
    original = checkerboard_jpeg()
    detect(stub, original, load_fixture("rekognition/detect_faces_one.json"))
    blurred = FaceBlurrer(client).blur(original, CONTEXT)
    assert blurred != original
    assert stddev_inside(blurred, enlarge_box(ONE_FACE)) < 10


def test_two_faces_found_detector_blurs_both(rekognition):
    client, stub = rekognition
    original = checkerboard_jpeg()
    detect(stub, original, load_fixture("rekognition/detect_faces_two.json"))
    blurred = FaceBlurrer(client).blur(original, CONTEXT)
    for face in TWO_FACES:
        assert stddev_inside(blurred, enlarge_box(face)) < 10


def test_low_confidence_face_still_blurred(rekognition):
    client, stub = rekognition
    original = checkerboard_jpeg()
    low = load_fixture("rekognition/detect_faces_one.json")
    low["FaceDetails"][0]["Confidence"] = 50.2
    detect(stub, original, low)
    blurred = FaceBlurrer(client).blur(original, CONTEXT)
    assert blurred == blur_regions(original, [ONE_FACE])


def test_detection_sees_the_downloaded_bytes(rekognition):
    # The Stubber's expected params fail the call unless the request carries
    # exactly the downloaded bytes inline, with no S3Object reference.
    client, stub = rekognition
    original = checkerboard_jpeg()
    detect(stub, original, {"FaceDetails": []})
    FaceBlurrer(client).blur(original, CONTEXT)


def logged(caplog, event: str) -> list[dict]:
    return [json.loads(r.getMessage()) for r in caplog.records if f'"{event}"' in r.getMessage()]


@pytest.mark.parametrize(
    "code",
    [
        "ThrottlingException",
        "InternalServerError",
        "InvalidImageFormatException",
        "ImageTooLargeException",
    ],
)
def test_detection_fails_still_is_dropped(rekognition, caplog, code):
    caplog.set_level(logging.INFO)
    client, stub = rekognition
    stub.add_client_error("detect_faces", service_error_code=code, http_status_code=400)
    assert FaceBlurrer(client).blur(checkerboard_jpeg(), {**CONTEXT, "still": 2}) is None
    [line] = logged(caplog, "face_detect_failed")
    assert line["still"] == 2 and line["error"] == code
    assert line["device_id"] == "ava1.ring.device.D1"


def test_detection_times_out_still_is_dropped(caplog):
    caplog.set_level(logging.INFO)

    class TimingOut:
        def detect_faces(self, **kwargs):
            raise ReadTimeoutError(endpoint_url="https://rekognition.us-east-1.amazonaws.com")

    assert FaceBlurrer(TimingOut()).blur(checkerboard_jpeg(), CONTEXT) is None
    [line] = logged(caplog, "face_detect_failed")
    assert line["error"] == "ReadTimeoutError"


def test_failed_call_is_not_costed(rekognition, caplog):
    caplog.set_level(logging.INFO)
    client, stub = rekognition
    stub.add_client_error("detect_faces", service_error_code="ThrottlingException")
    FaceBlurrer(client).blur(checkerboard_jpeg(), CONTEXT)
    assert logged(caplog, "face_detect_cost") == []


def test_default_price(rekognition, caplog):
    caplog.set_level(logging.INFO)
    client, stub = rekognition
    original = checkerboard_jpeg()
    detect(stub, original, load_fixture("rekognition/detect_faces_one.json"))
    FaceBlurrer(client).blur(original, CONTEXT)
    assert logged(caplog, "face_detect_cost") == [
        {
            "event": "face_detect_cost",
            "account_id": "ava1.ring.account.A1",
            "device_id": "ava1.ring.device.D1",
            "still": 3,
            "faces": 1,
            "usd": 0.001,
        }
    ]


def test_configured_price(rekognition, caplog):
    caplog.set_level(logging.INFO)
    client, stub = rekognition
    original = checkerboard_jpeg()
    detect(stub, original, {"FaceDetails": []})
    FaceBlurrer(client, price_usd=0.0008).blur(original, CONTEXT)
    [line] = logged(caplog, "face_detect_cost")
    assert line["faces"] == 0 and line["usd"] == 0.0008
