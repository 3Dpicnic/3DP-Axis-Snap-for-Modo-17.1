"""Regression checks against measured Modo views and rotation distance."""
import importlib.util
import json
import math
import pathlib
import random


DIRECTORY = pathlib.Path(__file__).parent
spec = importlib.util.spec_from_file_location(
    'qt_test_helpers', DIRECTORY / 'test_qt_compatibility.py'
)
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)


def _cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2],
            a[0]*b[1]-a[1]*b[0])


def _measured_views():
    with (DIRECTORY / 'modo_17_1_axis_views.json').open() as handle:
        return [
            ((r['projection'], r['orientation']),
             (tuple(r['right']), tuple(r['up']), _cross(r['right'], r['up'])))
            for r in json.load(handle)
        ]


def _quaternion_axes(q):
    w, x, y, z = q
    return (
        (1-2*(y*y+z*z), 2*(x*y+w*z), 2*(x*z-w*y)),
        (2*(x*y-w*z), 1-2*(x*x+z*z), 2*(y*z+w*x)),
        (2*(x*z+w*y), 2*(y*z-w*x), 1-2*(x*x+y*y)),
    )


def test_all_24_measured_views_snap_to_themselves():
    measured = _measured_views()
    assert len(measured) == 24
    for major in (14, 16, 17):
        module = helpers._load_for_modo(major)
        for expected, axes in measured:
            assert module._nearest_axis_view(axes) == expected


def test_near_each_view_keeps_face_heading_and_roll():
    module = helpers._load_for_modo(17)
    # Apply a 15-degree world rotation around a non-cardinal axis.
    half = math.radians(15) * 0.5
    rotation = _quaternion_axes(
        (math.cos(half), math.sin(half)/math.sqrt(3),
         math.sin(half)/math.sqrt(3), math.sin(half)/math.sqrt(3))
    )
    for expected, axes in _measured_views():
        perturbed = tuple(
            tuple(sum(rotation[j][i]*v[j] for j in range(3)) for i in range(3))
            for v in axes
        )
        assert module._nearest_axis_view(perturbed) == expected


def test_random_rotations_choose_minimum_full_rotation_angle():
    module = helpers._load_for_modo(17)
    measured = _measured_views()
    generator = random.Random(1707)
    selected = set()
    for _ in range(2000):
        q = [generator.gauss(0, 1) for _ in range(4)]
        length = math.sqrt(sum(v*v for v in q))
        axes = _quaternion_axes([v/length for v in q])

        # Independent angle calculation against native measured destinations.
        angles = {}
        for key, target in measured:
            trace = sum(sum(a*b for a, b in zip(v, t))
                        for v, t in zip(axes, target))
            angles[key] = math.acos(max(-1, min(1, (trace-1)*0.5)))
        result = module._nearest_axis_view(axes)
        assert angles[result] <= min(angles.values()) + 1e-10
        selected.add(result)
    assert len(selected) == 24
