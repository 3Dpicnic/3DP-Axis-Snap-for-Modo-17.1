# 3DP Axis Snap for Modo

Blender-style orthographic view snapping during viewport orbiting for Modo.

## Gesture

1. Start Modo's normal **Option + left-mouse drag** to orbit the viewport.
2. Keep the left mouse button held, release Option, then press Option again.
3. The current orientation snaps to the nearest Front, Back, Top, Bottom,
   Left, or Right orthographic view.

After snapping, release the left mouse button before starting another orbit.
From an orthographic view, beginning an **Option + left-mouse drag** switches
the viewport back to perspective and continues orbiting.

## Install on macOS

1. Quit Modo.
2. Copy the entire `3DP_AxisSnap` folder into:
   `~/Library/Application Support/Luxology/Kits/`
3. Start Modo.

The feature enables itself at startup.

## Session controls

Enter any of these in Modo's Command History:

- `threeDP.axisSnap.toggle`
- `threeDP.axisSnap.enable`
- `threeDP.axisSnap.disable`

These commands affect the current Modo session only. The kit enables itself
again the next time Modo starts.

## Remove

Quit Modo, delete the `3DP_AxisSnap` folder from the Kits directory, and
restart Modo.

## Compatibility

Version 1.2.0 selects the Qt binding bundled with the running Modo version:

- Modo 14 and earlier: PySide
- Modo 15 and 16: PySide2
- Modo 17 and later: PySide6

It also normalizes the Qt 4/5 and Qt 6 enum layouts used by the gesture event
filter.

Tested on macOS with:

- Modo 16.1v8
- Modo 17.1v1

The implementation is expected to work on Windows because it uses Modo and
Qt input APIs rather than macOS-specific APIs, but Windows has not yet been
tested. The kit does not modify Modo's saved keyboard or mouse mappings.
