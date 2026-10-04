"""Pure-Python checks for nearest-view axis mapping."""


def projection_for_axis(axis):
    component = max(range(3), key=lambda index: abs(axis[index]))
    positive = axis[component] >= 0.0
    if component == 0:
        return "lft" if positive else "rgt"
    if component == 1:
        return "bot" if positive else "top"
    return "fnt" if positive else "bck"


def test_all_cardinal_views():
    # The vector points from the object toward the viewer. Modo's fixed-view
    # tokens describe the viewing direction, so X and Y signs are opposite.
    assert projection_for_axis((1.0, 0.0, 0.0)) == "lft"
    assert projection_for_axis((-1.0, 0.0, 0.0)) == "rgt"
    assert projection_for_axis((0.0, 1.0, 0.0)) == "bot"
    assert projection_for_axis((0.0, -1.0, 0.0)) == "top"
    assert projection_for_axis((0.0, 0.0, 1.0)) == "fnt"
    assert projection_for_axis((0.0, 0.0, -1.0)) == "bck"


def test_nearest_cardinal_axis_wins():
    assert projection_for_axis((0.82, 0.12, -0.55)) == "lft"
    assert projection_for_axis((-0.31, 0.91, 0.27)) == "bot"
    assert projection_for_axis((0.14, -0.28, -0.95)) == "bck"


def test_right_side_perspective_stays_on_the_right_side():
    # Camera-back +X means the viewer is positioned on the object's right.
    assert projection_for_axis((0.99, 0.05, -0.02)) == "lft"


def test_top_side_perspective_stays_on_the_top_side():
    # Camera-back +Y means the viewer is positioned above the object.
    assert projection_for_axis((0.03, 0.99, -0.04)) == "bot"
