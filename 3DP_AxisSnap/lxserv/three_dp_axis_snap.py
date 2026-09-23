# python
"""Blender-style axis-view snapping during Modo viewport orbiting.

Start Modo's normal Option/Alt + left-mouse orbit, then release and press
Option/Alt again while keeping the mouse button held.  The current view snaps
to the nearest world-axis view.  Starting an Option/Alt orbit drag from an
orthographic view returns the viewport to perspective.
"""

import math
import traceback

import lx
import lxu
import lxu.command


try:
    HEADLESS = bool(lx.eval("query platformservice isheadless ?"))
except Exception:
    HEADLESS = False

if not HEADLESS:
    from PySide6 import QtCore, QtWidgets
    _EventFilterBase = QtCore.QObject
else:
    QtCore = None
    QtWidgets = None
    _EventFilterBase = object


KIT_NAME = "3DP Axis Snap"
ORBIT_THRESHOLD = 4.0

_filter = None


def _log(message):
    lx.out("%s: %s" % (KIT_NAME, message))


def _normalize(vector):
    values = tuple(float(value) for value in vector[:3])
    length = math.sqrt(sum(value * value for value in values))
    if length < 1.0e-8:
        raise ValueError("Cannot normalize a zero-length vector")
    return tuple(value / length for value in values)


def _cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _decode_space(value):
    space = lxu.decodeID4(value)
    if isinstance(space, bytes):
        space = space.decode("utf-8")
    return space


def _matrix_rows(matrix):
    """Return the rotation rows from Modo's matrix return value."""
    if len(matrix) >= 3 and hasattr(matrix[0], "__len__"):
        return [tuple(float(value) for value in row[:3]) for row in matrix[:3]]

    flat = [float(value) for value in matrix]
    if len(flat) == 9:
        return [tuple(flat[index:index + 3]) for index in range(0, 9, 3)]
    if len(flat) == 16:
        return [tuple(flat[index:index + 3]) for index in (0, 4, 8)]
    raise ValueError("Unexpected View3D matrix shape")


def _view_axes(view):
    """Return screen-right, screen-up, and camera-back vectors in world space."""
    try:
        # inverse=1 returns the view-to-world transform.  Modo matrices use
        # row-vector convention, so its rows are the local X/Y/Z axes.
        rows = _matrix_rows(view.Matrix(1))
        return (
            _normalize(rows[0]),
            _normalize(rows[1]),
            _normalize(rows[2]),
        )
    except Exception:
        # Conservative fallback for builds where Matrix() is unavailable.
        _distance, _position, direction = view.EyeVector()
        forward = _normalize(direction)
        backward = tuple(-value for value in forward)
        reference_up = (0.0, 1.0, 0.0)
        if abs(sum(a * b for a, b in zip(forward, reference_up))) > 0.95:
            reference_up = (0.0, 0.0, -1.0)
        right = _normalize(_cross(forward, reference_up))
        up = _normalize(_cross(right, forward))
        return right, up, backward


def _view_under_mouse():
    service = lx.service.View3Dport()
    index, x, y = service.Mouse()
    if index < 0 or x < 0 or y < 0:
        return None

    try:
        view = lx.object.View3D(service.View(index))
    except (IndexError, LookupError, RuntimeError):
        return None

    if _decode_space(view.Space()) != "MO3D":
        return None
    return view


def _projection_for_axis(axis):
    """Map a camera-position direction to Modo's projection token."""
    component = max(range(3), key=lambda index: abs(axis[index]))
    positive = axis[component] >= 0.0
    if component == 0:
        return "rgt" if positive else "lft"
    if component == 1:
        return "top" if positive else "bot"
    return "fnt" if positive else "bck"


def _nearest_projection(view):
    """Return the orthographic projection nearest the current view angle."""
    _right, _up, camera_back = _view_axes(view)
    return _projection_for_axis(camera_back)


def _is_orthographic(view):
    """True for Modo's six fixed axis views, false for perspective/camera."""
    axis_kind, camera, _axis = view.Axis()
    return (
        axis_kind != lx.symbol.i_VP_AXIS_PERSP
        and camera != lx.symbol.i_VP_CAM_PERSP
        and camera in {
            lx.symbol.i_VP_CAM_LEFT,
            lx.symbol.i_VP_CAM_RIGHT,
            lx.symbol.i_VP_CAM_TOP,
            lx.symbol.i_VP_CAM_BOTTOM,
            lx.symbol.i_VP_CAM_FRONT,
            lx.symbol.i_VP_CAM_BACK,
        }
    )


def _apply_projection(projection):
    # Make the viewport beneath the pointer current before changing its view.
    lx.eval("viewport.goto")
    lx.eval("view3d.projection %s" % projection)


def _event_global_position(event):
    try:
        point = event.globalPosition()
    except AttributeError:
        point = event.globalPos()
    return float(point.x()), float(point.y())


class AxisSnapEventFilter(_EventFilterBase):
    def __init__(self, parent=None):
        super(AxisSnapEventFilter, self).__init__(parent)
        self._orbiting = False
        self._started_orthographic = False
        self._alt_released = False
        self._moved = False
        self._snapped = False
        self._start = (0.0, 0.0)

    def _reset(self):
        self._orbiting = False
        self._started_orthographic = False
        self._alt_released = False
        self._moved = False
        self._snapped = False

    def _is_orbit_press(self, event):
        if event.button() != QtCore.Qt.MouseButton.LeftButton:
            return False

        modifiers = event.modifiers()
        if not (modifiers & QtCore.Qt.KeyboardModifier.AltModifier):
            return False

        incompatible = (
            QtCore.Qt.KeyboardModifier.ShiftModifier
            | QtCore.Qt.KeyboardModifier.ControlModifier
            | QtCore.Qt.KeyboardModifier.MetaModifier
        )
        return not bool(modifiers & incompatible)

    def eventFilter(self, watched, event):
        event_type = event.type()

        try:
            if event_type == QtCore.QEvent.Type.MouseButtonPress:
                if not self._is_orbit_press(event):
                    return False

                view = _view_under_mouse()
                if view is None:
                    return False

                self._start = _event_global_position(event)
                self._orbiting = True
                self._started_orthographic = _is_orthographic(view)
                self._alt_released = False
                self._moved = False
                self._snapped = False

                if self._started_orthographic:
                    # Switch before Modo receives the press. It can then begin
                    # its normal perspective-orbit haul with this same drag,
                    # rather than having to wait for a second gesture.
                    _apply_projection("psp")

                # Modo must receive the original press so its normal orbit
                # hauling action begins unchanged.
                return False

            if event_type == QtCore.QEvent.Type.KeyRelease:
                if (
                    self._orbiting
                    and event.key() == QtCore.Qt.Key.Key_Alt
                    and QtWidgets.QApplication.mouseButtons()
                    & QtCore.Qt.MouseButton.LeftButton
                ):
                    self._alt_released = True
                return False

            if event_type == QtCore.QEvent.Type.KeyPress:
                if (
                    self._orbiting
                    and not self._started_orthographic
                    and self._alt_released
                    and self._moved
                    and not self._snapped
                    and event.key() == QtCore.Qt.Key.Key_Alt
                    and not event.isAutoRepeat()
                    and QtWidgets.QApplication.mouseButtons()
                    & QtCore.Qt.MouseButton.LeftButton
                ):
                    view = _view_under_mouse()
                    if view is not None:
                        _apply_projection(_nearest_projection(view))
                        self._snapped = True
                        return True
                return False

            if not self._orbiting:
                return False

            if event_type == QtCore.QEvent.Type.MouseMove:
                if not (event.buttons() & QtCore.Qt.MouseButton.LeftButton):
                    self._reset()
                    return False

                current_x, current_y = _event_global_position(event)
                delta_x = current_x - self._start[0]
                delta_y = current_y - self._start[1]
                if math.hypot(delta_x, delta_y) >= ORBIT_THRESHOLD:
                    self._moved = True

                # Once snapped, hold the fixed axis view until the user ends
                # the drag. Otherwise Modo keeps handling its normal orbit.
                return self._snapped

            if event_type == QtCore.QEvent.Type.MouseButtonRelease:
                if event.button() == QtCore.Qt.MouseButton.LeftButton:
                    self._reset()
                    return False

            return False
        except Exception:
            self._reset()
            _log("gesture failed\n%s" % traceback.format_exc())
            return False


def install_filter():
    global _filter
    if HEADLESS:
        return False
    if _filter is not None:
        return True

    application = QtWidgets.QApplication.instance()
    if application is None:
        return False

    _filter = AxisSnapEventFilter(application)
    application.installEventFilter(_filter)
    _log("enabled (Option/Alt re-press during left-mouse orbit)")
    return True


def remove_filter():
    global _filter
    if _filter is None:
        return False

    application = QtWidgets.QApplication.instance()
    if application is not None:
        application.removeEventFilter(_filter)
    _filter.deleteLater()
    _filter = None
    _log("disabled")
    return True


class ToggleCommand(lxu.command.BasicCommand):
    def basic_Execute(self, message, flags):
        if _filter is None:
            install_filter()
        else:
            remove_filter()


class EnableCommand(lxu.command.BasicCommand):
    def basic_Execute(self, message, flags):
        install_filter()


class DisableCommand(lxu.command.BasicCommand):
    def basic_Execute(self, message, flags):
        remove_filter()


lx.bless(ToggleCommand, "threeDP.axisSnap.toggle")
lx.bless(EnableCommand, "threeDP.axisSnap.enable")
lx.bless(DisableCommand, "threeDP.axisSnap.disable")


# lxserv modules load during startup. Defer installation until Qt's event loop
# exists and the main interface has finished constructing.
if not HEADLESS:
    QtCore.QTimer.singleShot(0, install_filter)
