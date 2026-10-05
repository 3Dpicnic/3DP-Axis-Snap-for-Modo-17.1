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

platform_svc = lx.service.Platform()
MODO_MAJOR_VERSION = platform_svc.AppVersionMajor()

if not HEADLESS:
    if MODO_MAJOR_VERSION < 15:
        from PySide import QtCore, QtGui

        # Qt 4 keeps widgets in QtGui; use one name throughout the kit.
        QtWidgets = QtGui
        QT_BINDING = "PySide"
    elif MODO_MAJOR_VERSION < 17:
        from PySide2 import QtCore, QtGui, QtWidgets

        QT_BINDING = "PySide2"
    else:
        from PySide6 import QtCore, QtGui, QtWidgets

        QT_BINDING = "PySide6"

    _EventFilterBase = QtCore.QObject
else:
    QtCore = None
    QtGui = None
    QtWidgets = None
    QT_BINDING = None
    _EventFilterBase = object


def _qt_enum_value(owner, group_name, member_name):
    """Return an enum value from either Qt 4/5 or Qt 6 enum layouts."""
    group = getattr(owner, group_name, owner)
    return getattr(group, member_name)


if not HEADLESS:
    _QT_LEFT_BUTTON = _qt_enum_value(QtCore.Qt, "MouseButton", "LeftButton")
    _QT_ALT_MODIFIER = _qt_enum_value(
        QtCore.Qt, "KeyboardModifier", "AltModifier"
    )
    _QT_SHIFT_MODIFIER = _qt_enum_value(
        QtCore.Qt, "KeyboardModifier", "ShiftModifier"
    )
    _QT_CONTROL_MODIFIER = _qt_enum_value(
        QtCore.Qt, "KeyboardModifier", "ControlModifier"
    )
    _QT_META_MODIFIER = _qt_enum_value(
        QtCore.Qt, "KeyboardModifier", "MetaModifier"
    )
    _QT_KEY_ALT = _qt_enum_value(QtCore.Qt, "Key", "Key_Alt")
    _QT_MOUSE_BUTTON_PRESS = _qt_enum_value(
        QtCore.QEvent, "Type", "MouseButtonPress"
    )
    _QT_MOUSE_BUTTON_RELEASE = _qt_enum_value(
        QtCore.QEvent, "Type", "MouseButtonRelease"
    )
    _QT_MOUSE_MOVE = _qt_enum_value(QtCore.QEvent, "Type", "MouseMove")
    _QT_KEY_PRESS = _qt_enum_value(QtCore.QEvent, "Type", "KeyPress")
    _QT_KEY_RELEASE = _qt_enum_value(QtCore.QEvent, "Type", "KeyRelease")


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


def _dot(a, b):
    return sum(first * second for first, second in zip(a, b))


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
        # Flags=0 projects onto the view plane without work-plane mapping or
        # grid snapping. Unlike Matrix(), To3D() includes fixed-view spin.
        _x, _y, width, height = view.Bounds()
        x, y = width * 0.5, height * 0.5
        origin = view.To3D(x, y, 0)
        along_right = view.To3D(x + 16.0, y, 0)
        along_up = view.To3D(x, y - 16.0, 0)
        right = _normalize(tuple(b - a for a, b in zip(origin, along_right)))
        up = tuple(b - a for a, b in zip(origin, along_up))
        # Remove numerical drift before comparing complete rotations.
        parallel = _dot(right, up)
        up = _normalize(tuple(u - parallel * r for u, r in zip(up, right)))
        return right, up, _normalize(_cross(right, up))
    except Exception:
        # Perspective Matrix(1) stores the view-to-world axes in columns.
        # Keep this fallback for older builds that lack To3D(). Do not use
        # EyeVector(): it gazes toward the world origin rather than the view
        # center when the viewport has been panned.
        rows = _matrix_rows(view.Matrix(1))
        columns = [
            tuple(rows[row][column] for row in range(3))
            for column in range(3)
        ]
        return (
            _normalize(columns[0]),
            _normalize(columns[1]),
            _normalize(columns[2]),
        )


def _top_level_window(widget):
    """Return the top-level Qt window containing *widget*."""
    if widget is None:
        return None

    try:
        window = widget.window()
        if window is not None and window.isWindow():
            return window
    except (AttributeError, RuntimeError):
        pass

    # Some Modo/Qt combinations do not expose QWidget.window() consistently
    # for native viewport children. Walk the widget hierarchy as a fallback.
    try:
        window = widget
        while window.parentWidget() is not None:
            window = window.parentWidget()
        if window.isWindow():
            return window
    except (AttributeError, RuntimeError):
        pass
    return None


def _same_window(first, second):
    """Compare Qt windows, including bindings that create new wrappers."""
    if first is None or second is None:
        return False
    if first is second:
        return True
    try:
        return int(first.winId()) == int(second.winId())
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return False


def _cursor_global_position():
    point = QtGui.QCursor.pos()
    return float(point.x()), float(point.y())


def _window_at_global_position(position):
    """Return the top-level Qt window at a global screen position."""
    x, y = int(position[0]), int(position[1])

    # widgetAt accounts for overlapping floating windows and their stacking
    # order, so prefer it to scanning window rectangles.
    try:
        widget = QtWidgets.QApplication.widgetAt(x, y)
    except TypeError:
        widget = QtWidgets.QApplication.widgetAt(QtCore.QPoint(x, y))
    except (AttributeError, RuntimeError):
        widget = None

    window = _top_level_window(widget)
    if window is not None:
        return window

    # Native viewport widgets can occasionally be absent from widgetAt().
    # Fall back to the top-level-widget approach used by Modo scripts.
    try:
        windows = QtWidgets.QApplication.topLevelWidgets()
    except (AttributeError, RuntimeError):
        return None

    for candidate in reversed(windows):
        try:
            if (
                candidate.isWindow()
                and candidate.isVisible()
                and candidate.frameGeometry().contains(x, y)
            ):
                return candidate
        except (AttributeError, RuntimeError, TypeError):
            continue
    return None


def _pointer_is_in_window(window, position=None):
    if window is None:
        return False
    if position is None:
        position = _cursor_global_position()
    return _same_window(_window_at_global_position(position), window)


def _window_for_mouse_event(watched, event):
    """Resolve the one top-level window that owns a mouse event."""
    position = _event_global_position(event)
    pointer_window = _window_at_global_position(position)
    watched_window = _top_level_window(watched)
    if pointer_window is None:
        return None
    if watched_window is not None and not _same_window(
        pointer_window, watched_window
    ):
        return None
    return pointer_window


def _activate_window(window):
    """Make the pointer's window current before issuing viewport commands."""
    if window is None:
        return False
    try:
        application = QtWidgets.QApplication.instance()
        if application is not None:
            application.setActiveWindow(window)
        else:
            window.activateWindow()
        return True
    except (AttributeError, RuntimeError):
        try:
            window.activateWindow()
            return True
        except (AttributeError, RuntimeError):
            return False


def _view_under_mouse(target_window=None, position=None):
    if target_window is not None and not _pointer_is_in_window(
        target_window, position
    ):
        return None

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


# These are actual screen-right/up vectors measured with To3D() in Modo.
# The outward axis is right cross up. Enumerating all four spins for each
# face gives the 24 proper axis-aligned rotations (no reflected views).
_ZERO_VIEW_AXES = (
    ("fnt", (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
    ("bck", (-1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
    ("lft", (0.0, 0.0, 1.0), (0.0, 1.0, 0.0)),
    ("rgt", (0.0, 0.0, -1.0), (0.0, 1.0, 0.0)),
    ("top", (1.0, 0.0, 0.0), (0.0, 0.0, -1.0)),
    ("bot", (-1.0, 0.0, 0.0), (0.0, 0.0, -1.0)),
)


def _axis_view_candidates():
    for projection, right, up in _ZERO_VIEW_AXES:
        back = _cross(right, up)
        for orientation in ("zero", "ninety", "oneeighty", "twoseventy"):
            yield projection, orientation, (right, up, back)
            right, up = up, tuple(-value for value in right)


def _nearest_axis_view(axes):
    """Choose the least angular change among all 24 orthographic rotations.

    Maximizing the trace of the relative rotation is equivalent to minimizing
    quaternion rotation distance. Matching right, up AND back keeps heading
    and bank consistent, including near poles and when crossing over them.
    """
    best = max(
        _axis_view_candidates(),
        key=lambda candidate: sum(
            _dot(current, target)
            for current, target in zip(axes, candidate[2])
        ),
    )
    return best[0], best[1]


def _nearest_projection(view):
    """Return the orthographic projection nearest the current view angle."""
    return _nearest_axis_view(_view_axes(view))[0]


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


def _apply_projection(projection, target_window, orientation=None):
    # The global filter can see a press before Qt activates the clicked
    # floating window. Lock the command context to the window at the pointer
    # so another Modo view window cannot be changed accidentally.
    if not _pointer_is_in_window(target_window):
        return False
    if not _activate_window(target_window):
        return False

    lx.eval("viewport.goto")
    if not _pointer_is_in_window(target_window):
        return False
    lx.eval("view3d.projection %s" % projection)

    if orientation is not None:
        if not _pointer_is_in_window(target_window):
            return False
        # Always set the spin, including zero on Front/Back/Left/Right.
        # Otherwise a previous orthographic spin leaks into the new snap.
        lx.eval("view3d.orientation %s" % orientation)
    return True


def _start_perspective_orbit(view, target_window):
    # Modo's projection command alone drops fixed-view spin. Carry the full
    # visible basis into perspective before forwarding the initial press.
    axes = _view_axes(view)
    if not _apply_projection("psp", target_window):
        return False
    view.SetMatrix(axes)
    return True


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
        self._target_window = None

    def _reset(self):
        self._orbiting = False
        self._started_orthographic = False
        self._alt_released = False
        self._moved = False
        self._snapped = False
        self._target_window = None

    def _is_orbit_press(self, event):
        if event.button() != _QT_LEFT_BUTTON:
            return False

        modifiers = event.modifiers()
        if not (modifiers & _QT_ALT_MODIFIER):
            return False

        incompatible = (
            _QT_SHIFT_MODIFIER | _QT_CONTROL_MODIFIER | _QT_META_MODIFIER
        )
        return not bool(modifiers & incompatible)

    def eventFilter(self, watched, event):
        event_type = event.type()

        try:
            if event_type == _QT_MOUSE_BUTTON_PRESS:
                if not self._is_orbit_press(event):
                    return False

                position = _event_global_position(event)
                target_window = _window_for_mouse_event(watched, event)
                if target_window is None:
                    return False

                view = _view_under_mouse(target_window, position)
                if view is None:
                    return False

                self._start = position
                self._orbiting = True
                self._target_window = target_window
                self._started_orthographic = _is_orthographic(view)
                self._alt_released = False
                self._moved = False
                self._snapped = False

                if self._started_orthographic:
                    # Switch before Modo receives the press. It can then begin
                    # its normal perspective-orbit haul with this same drag,
                    # rather than having to wait for a second gesture.
                    _start_perspective_orbit(view, self._target_window)

                # Modo must receive the original press so its normal orbit
                # hauling action begins unchanged.
                return False

            if event_type == _QT_KEY_RELEASE:
                if (
                    self._orbiting
                    and event.key() == _QT_KEY_ALT
                    and QtWidgets.QApplication.mouseButtons()
                    & _QT_LEFT_BUTTON
                ):
                    if _pointer_is_in_window(self._target_window):
                        self._alt_released = True
                    else:
                        self._reset()
                return False

            if event_type == _QT_KEY_PRESS:
                if (
                    self._orbiting
                    and not self._started_orthographic
                    and self._alt_released
                    and self._moved
                    and not self._snapped
                    and event.key() == _QT_KEY_ALT
                    and not event.isAutoRepeat()
                    and QtWidgets.QApplication.mouseButtons()
                    & _QT_LEFT_BUTTON
                ):
                    if not _pointer_is_in_window(self._target_window):
                        self._reset()
                        return False

                    view = _view_under_mouse(self._target_window)
                    if view is not None:
                        projection, orientation = _nearest_axis_view(
                            _view_axes(view)
                        )
                        if _apply_projection(
                            projection,
                            self._target_window,
                            orientation,
                        ):
                            self._snapped = True
                            return True
                return False

            if not self._orbiting:
                return False

            if event_type == _QT_MOUSE_MOVE:
                if not (event.buttons() & _QT_LEFT_BUTTON):
                    self._reset()
                    return False

                current_x, current_y = _event_global_position(event)
                if not _pointer_is_in_window(
                    self._target_window, (current_x, current_y)
                ):
                    self._reset()
                    return False

                delta_x = current_x - self._start[0]
                delta_y = current_y - self._start[1]
                if math.hypot(delta_x, delta_y) >= ORBIT_THRESHOLD:
                    self._moved = True

                # Once snapped, hold the fixed axis view until the user ends
                # the drag. Otherwise Modo keeps handling its normal orbit.
                return self._snapped

            if event_type == _QT_MOUSE_BUTTON_RELEASE:
                if event.button() == _QT_LEFT_BUTTON:
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
    _log(
        "enabled (Modo %s, %s; Option/Alt re-press during left-mouse orbit)"
        % (MODO_MAJOR_VERSION, QT_BINDING)
    )
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
