"""Import checks for the Qt bindings bundled with different Modo versions."""

import importlib.util
import pathlib
import sys
import types


SOURCE = pathlib.Path(__file__).parents[1] / "lxserv" / "three_dp_axis_snap.py"


def _old_qt_core():
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
        pass

    class QTimer:
        @staticmethod
        def singleShot(_delay, _callback):
            pass

    return types.SimpleNamespace(Qt=Qt, QEvent=QEvent, QObject=QObject, QTimer=QTimer)


def _qt6_core():
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
        pass

    class QTimer:
        @staticmethod
        def singleShot(_delay, _callback):
            pass

    return types.SimpleNamespace(Qt=Qt, QEvent=QEvent, QObject=QObject, QTimer=QTimer)


def _load_for_modo(major):
    missing = object()
    previous_modules = {}

    def install_module(name, module):
        previous_modules[name] = sys.modules.get(name, missing)
        sys.modules[name] = module

    qt_core = _qt6_core() if major >= 17 else _old_qt_core()
    qt_gui = types.SimpleNamespace()

    class QApplication:
        @staticmethod
        def instance():
            return None

        @staticmethod
        def mouseButtons():
            return 0

    qt_widgets = types.SimpleNamespace(QApplication=QApplication)
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
