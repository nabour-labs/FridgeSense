"""fridge-area: the owner's box around the fridge, stored per account and device."""

import pytest

from fridgesense import fridge_area as fa
from fridgesense.analysis_config import Invalid
from fridgesense.table import FridgeTable
from tests.conftest import color_jpeg

ACCOUNT = "ava1.ring.account.A1"
D1, D2 = "ava1.ring.device.D1", "ava1.ring.device.D2"
T0 = 1792112400000  # 2026-10-16T01:00:00Z
BOX = {"x": 0.2, "y": 0.05, "width": 0.5, "height": 0.9}


def save(image, box, device=D1, at=T0):
    return fa.save(FridgeTable(), ACCOUNT, device, image, box, now_ms=at)


def test_nothing_saved(aws):
    assert fa.load(FridgeTable(), ACCOUNT, D1) is None


# Fridge area saved
def test_fridge_area_saved(aws):
    image = color_jpeg(size=(960, 540))
    save(image, BOX)
    area = fa.load(FridgeTable(), ACCOUNT, D1)
    assert area.image == image
    assert area.box == (0.2, 0.05, 0.5, 0.9)
    assert area.updated_at == "2026-10-16T01:00:00.000Z"


# Saving again replaces the area
def test_saving_again_replaces_the_area(aws):
    save(color_jpeg((10, 10, 10)), BOX)
    second = color_jpeg((200, 200, 200))
    save(second, {"x": 0.1, "y": 0, "width": 0.6, "height": 1}, at=T0 + 1000)
    area = fa.load(FridgeTable(), ACCOUNT, D1)
    assert area.box == (0.1, 0, 0.6, 1)
    assert area.image == second


# Invalid fridge area rejected
@pytest.mark.parametrize(
    "box",
    [
        {"x": 0.9, "y": 0, "width": 0.2, "height": 1},
        {"x": 0, "y": 0, "width": 0.01, "height": 1},
        {"x": 0, "y": 0, "width": 0.5},
    ],
)
def test_invalid_box_leaves_area_unchanged(aws, box):
    save(color_jpeg(), BOX)
    with pytest.raises(Invalid, match="box must be inside the image"):
        save(color_jpeg(), box, at=T0 + 1000)
    assert fa.load(FridgeTable(), ACCOUNT, D1).box == (0.2, 0.05, 0.5, 0.9)


# Fridge area kept per device
def test_fridge_area_kept_per_device(aws):
    save(color_jpeg(), BOX, device=D1)
    save(color_jpeg(), {"x": 0, "y": 0, "width": 1, "height": 1}, device=D2)
    assert fa.load(FridgeTable(), ACCOUNT, D1).box == (0.2, 0.05, 0.5, 0.9)
    assert fa.load(FridgeTable(), ACCOUNT, D2).box == (0, 0, 1, 1)
