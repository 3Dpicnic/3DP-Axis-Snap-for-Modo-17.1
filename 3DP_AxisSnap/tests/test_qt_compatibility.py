"""Import checks for the Qt bindings bundled with different Modo versions."""

import importlib.util
import pathlib
import sys
import types


SOURCE = pathlib.Path(__file__).parents[1] / "lxserv" / "three_dp_axis_snap.py"


def _old_qt_core():
    class QPoint:
        def __init__(self, x, y):
            self._x = x
            self._y = y

        def x(self):
            return self._x

        def y(self):
            return self._y

    class Qt:
        LeftButton = 1
        AltModifier = 2
        ShiftModifier = 4
        ControlModifier = 8
        MetaModifier = 16
        Key_Alt = 32

    class QEvent:
        MouseButtonPress = 40
        MouseButtonRelease = 41
        MouseMove = 42
        KeyPress = 43
        KeyRelease = 44

    class QObject:
        def __init__(self, _parent=None):
            pass

    class QTimer:
        @staticmethod
        def singleShot(_delay, _callback):
            pass

    return types.SimpleNamespace(
        Qt=Qt, QEvent=QEvent, QObject=QObject, QTimer=QTimer, QPoint=QPoint
    )


def _qt6_core():
    class QPoint:
        def __init__(self, x, y):
            self._x = x
            self._y = y

        def x(self):
            return self._x

        def y(self):
            return self._y

    class Qt:
        class MouseButton:
            LeftButton = 1

        class KeyboardModifier:
            AltModifier = 2
            ShiftModifier = 4
            ControlModifier = 8
            MetaModifier = 16

        class Key:
            Key_Alt = 32

    class QEvent:
        class Type:
            MouseButtonPress = 40
            MouseButtonRelease = 41
            MouseMove = 42
            KeyPress = 43
            KeyRelease = 44

    class QObject:
        def __init__(self, _parent=None):
            pass

    class QTimer:
        @staticmethod
        def singleShot(_delay, _callback):
            pass

    return types.SimpleNamespace(
        Qt=Qt, QEvent=QEvent, QObject=QObject, QTimer=QTimer, QPoint=QPoint
    )


def _load_for_modo(major):
    missing = object()
    previous_modules = {}

    def install_module(name, module):
        previous_modules[name] = sys.modules.get(name, missing)
        sys.modules[name] = module

    qt_core = _qt6_core() if major >= 17 else _old_qt_core()
    class CursorPoint:
        def __init__(self, x=0, y=0):
            self._x = x
            self._y = y

        def x(self):
            return self._x

        def y(self):
            return self._y

    class QCursor:
        position = CursorPoint()

        @staticmethod
        def pos():
            return QCursor.position

    qt_gui = types.SimpleNamespace(QCursor=QCursor)

    class QApplication:
        widget_at = None
        top_level_widgets = []
        active_window = None

        @staticmethod
        def instance():
            return None

        @staticmethod
        def mouseButtons():
            return 0

        @staticmethod
        def widgetAt(*_position):
            return QApplication.widget_at

        @staticmethod
        def topLevelWidgets():
            return list(QApplication.top_level_widgets)

        @staticmethod
        def setActiveWindow(window):
            QApplication.active_window = window

    qt_widgets = types.SimpleNamespace(QApplication=QApplication, QCursor=QCursor)
    package_name = "PySide" if major < 15 else "PySide2" if major < 17 else "PySide6"
    package = types.ModuleType(package_name)
    package.QtCore = qt_core
    package.QtGui = qt_gui if major >= 15 else qt_widgets
    if major >= 15:
        package.QtWidgets = qt_widgets
    install_module(package_name, package)

    class Platform:
        def AppVersionMajor(self):
            return major

    lx = types.ModuleType("lx")
    lx.eval = lambda _command: False
    lx.bless = lambda _command, _name: None
    lx.service = types.SimpleNamespace(Platform=Platform)
    install_module("lx", lx)

    class BasicCommand:
        pass

    lxu = types.ModuleType("lxu")
    lxu.command = types.SimpleNamespace(BasicCommand=BasicCommand)
    lxu.decodeID4 = lambda value: value
    install_module("lxu", lxu)
    install_module("lxu.command", lxu.command)

    try:
        module_name = "three_dp_axis_snap_modo_%s" % major
        spec = importlib.util.spec_from_file_location(module_name, SOURCE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        for name, previous in previous_modules.items():
            if previous is missing:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous


def test_modo_14_uses_pyside_and_qt4_enums():
    module = _load_for_modo(14)
    assert module.QT_BINDING == "PySide"
    assert module.QtWidgets is module.QtGui
    assert module._QT_LEFT_BUTTON == 1
    assert module._QT_MOUSE_BUTTON_PRESS == 40


def test_modo_16_uses_pyside2_and_qt5_enums():
    module = _load_for_modo(16)
    assert module.QT_BINDING == "PySide2"
    assert module._QT_ALT_MODIFIER == 2
    assert module._QT_KEY_RELEASE == 44


def test_modo_17_uses_pyside6_and_scoped_enums():
    module = _load_for_modo(17)
    assert module.QT_BINDING == "PySide6"
    assert module._QT_META_MODIFIER == 16
    assert module._QT_KEY_PRESS == 43


def test_modo_side_tokens_match_measured_screen_bases():
    module = _load_for_modo(17)
    assert module._nearest_axis_view(
        ((1, 0, 0), (0, 1, 0), (0, 0, 1))
    ) == ("fnt", "zero")
    assert module._nearest_axis_view(
        ((0, 0, -1), (0, 1, 0), (1, 0, 0))
    ) == ("rgt", "zero")


class _MatrixView:
    def __init__(self, matrix):
        self.matrix = matrix

    def Matrix(self, inverse):
        assert inverse == 1
        return self.matrix


def test_nearest_projection_reads_camera_back_from_matrix_column():
    module = _load_for_modo(17)

    # These view-to-world matrices look almost straight down/up with a 45
    # degree heading. Their third rows are horizontal, while their third
    # columns correctly contain the camera-back vectors +Y and -Y.
    top_side_view = _MatrixView(
        (
            (0.70710678, -0.70710678, 0.0),
            (0.0, 0.0, 1.0),
            (-0.70710678, -0.70710678, 0.0),
        )
    )
    bottom_side_view = _MatrixView(
        (
            (0.70710678, 0.70710678, 0.0),
            (0.0, 0.0, -1.0),
            (-0.70710678, 0.70710678, 0.0),
        )
    )

    assert module._nearest_projection(top_side_view) == "top"
    assert module._nearest_projection(bottom_side_view) == "bot"


def test_screen_sampling_includes_spin_that_matrix_omits():
    module = _load_for_modo(17)

    class ScreenView(_MatrixView):
        def Bounds(self):
            return 4, 4, 640, 480

        def To3D(self, x, y, flags):
            assert flags == 0
            # Top ninety: screen-right=-Z, screen-up=-X. Panned center.
            return (3.0 + y * 0.1, 2.0, 4.0 - x * 0.1)

    # Its matrix deliberately reports Top zero, just as Modo does.
    view = ScreenView(((1, 0, 0), (0, 0, 1), (0, -1, 0)))
    assert module._nearest_axis_view(module._view_axes(view)) == (
        "top", "ninety"
    )


class _Rectangle:
    def __init__(self, left, top, width, height):
        self.left = left
        self.top = top
        self.right = left + width
        self.bottom = top + height

    def contains(self, x, y):
        return self.left <= x < self.right and self.top <= y < self.bottom


class _Window:
    def __init__(self, identifier, rectangle):
        self.identifier = identifier
        self.rectangle = rectangle
        self.activated = False

    def window(self):
        return self

    def isWindow(self):
        return True

    def isVisible(self):
        return True

    def frameGeometry(self):
        return self.rectangle

    def winId(self):
        return self.identifier

    def activateWindow(self):
        self.activated = True


class _ChildWidget:
    def __init__(self, window):
        self._window = window

    def window(self):
        return self._window


def test_window_under_pointer_uses_the_widget_top_level_window():
    module = _load_for_modo(17)
    first = _Window(1, _Rectangle(0, 0, 100, 100))
    second = _Window(2, _Rectangle(100, 0, 100, 100))
    module.QtWidgets.QApplication.top_level_widgets = [first, second]
    module.QtWidgets.QApplication.widget_at = _ChildWidget(second)

    assert module._window_at_global_position((150, 50)) is second


def test_window_under_pointer_falls_back_to_top_level_widgets():
    module = _load_for_modo(16)
    first = _Window(1, _Rectangle(0, 0, 100, 100))
    second = _Window(2, _Rectangle(100, 0, 100, 100))
    module.QtWidgets.QApplication.widget_at = None
    module.QtWidgets.QApplication.top_level_widgets = [first, second]

    assert module._window_at_global_position((50, 50)) is first
    assert module._window_at_global_position((150, 50)) is second


def test_projection_commands_only_run_for_the_window_under_the_pointer():
    module = _load_for_modo(17)
    first = _Window(1, _Rectangle(0, 0, 100, 100))
    second = _Window(2, _Rectangle(100, 0, 100, 100))
    application = module.QtWidgets.QApplication
    application.widget_at = _ChildWidget(second)
    application.top_level_widgets = [first, second]
    module.QtGui.QCursor.position = module.QtCore.QPoint(150, 50)

    commands = []
    module.lx.eval = commands.append

    assert module._apply_projection("top", first) is False
    assert commands == []

    assert module._apply_projection("top", second) is True
    assert commands == ["viewport.goto", "view3d.projection top"]

    commands[:] = []
    assert module._apply_projection(
        "top", second, orientation="twoseventy"
    ) is True
    assert commands == [
        "viewport.goto",
        "view3d.projection top",
        "view3d.orientation twoseventy",
    ]

    commands[:] = []
    assert module._apply_projection("fnt", second, "zero") is True
    assert commands[-1] == "view3d.orientation zero"


def test_return_to_perspective_preserves_visible_spin_and_window_guard():
    for major in (14, 16, 17):
        module = _load_for_modo(major)
        axes = ((0, 0, -1), (-1, 0, 0), (0, 1, 0))
        changes = []
        window = object()
        view = types.SimpleNamespace(SetMatrix=lambda basis: changes.append(basis))
        module._view_axes = lambda candidate: axes

        def apply(projection, target):
            assert projection == "psp" and target is window
            changes.append(projection)
            return True

        module._apply_projection = apply
        assert module._start_perspective_orbit(view, window) is True
        assert changes == ["psp", axes]

        changes[:] = []
        module._apply_projection = lambda projection, target: False
        assert module._start_perspective_orbit(view, window) is False
        assert changes == []
