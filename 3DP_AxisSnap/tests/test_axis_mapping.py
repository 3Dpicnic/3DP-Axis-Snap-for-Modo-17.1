"""Pure-Python checks for nearest-view axis mapping."""


def projection_for_axis(axis):
    component = max(range(3), key=lambda index: abs(axis[index]))
    positive = axis[component] >= 0.0
    if component == 0:
        return "rgt" if positive else "lft"
    if component == 1:
        return "top" if positive else "bot"
    return "fnt" if positive else "bck"


def test_all_cardinal_views():
    assert projection_for_axis((1.0, 0.0, 0.0)) == "rgt"
    assert projection_for_axis((-1.0, 0.0, 0.0)) == "lft"
    assert projection_for_axis((0.0, 1.0, 0.0)) == "top"
    assert projection_for_axis((0.0, -1.0, 0.0)) == "bot"
    assert projection_for_axis((0.0, 0.0, 1.0)) == "fnt"
    assert projection_for_axis((0.0, 0.0, -1.0)) == "bck"


def test_nearest_cardinal_axis_wins():
    assert projection_for_axis((0.82, 0.12, -0.55)) == "rgt"
    assert projection_for_axis((-0.31, 0.91, 0.27)) == "top"
    assert projection_for_axis((0.14, -0.28, -0.95)) == "bck"
