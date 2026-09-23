# 3DP Axis Snap for Modo 17.1

Blender-style orthographic view snapping during viewport orbiting for Modo
17.1 on macOS.

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
3. Start Modo 17.1.

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

Built specifically for Modo 17.1's Python 3.10 and PySide6 runtime. The kit
does not modify Modo's saved keyboard or mouse mappings.
