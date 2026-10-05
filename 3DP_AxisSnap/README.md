# 3DP Axis Snap for Modo

Blender-style orthographic view snapping during viewport orbiting for Foundry
Modo. A Python kit designed for multiple Modo versions on macOS and Windows,
not exclusively Modo 17.1 or macOS. The kit automatically selects the Qt
binding provided by Modo; tested configurations are listed under Compatibility.

The repository's historical `Modo-17.1` URL does not limit kit compatibility.

## Download

Get `3DP_Axis_Snap_for_Modo_1.3.0.zip` from the
[v1.3.0 release](https://github.com/3Dpicnic/3DP-Axis-Snap-for-Modo-17.1/releases/tag/v1.3.0).
The same archive contains the kit for both macOS and Windows.

## Gesture

1. Start Modo's normal **Option/Alt + left-mouse drag** to orbit the viewport.
2. Keep the left mouse button held, release Option/Alt, then press it again.
3. The current orientation snaps to the nearest Front, Back, Top, Bottom,
   Left, or Right orthographic view.

After snapping, release the left mouse button before starting another orbit.
From an orthographic view, beginning an **Option/Alt + left-mouse drag** switches
the viewport back to perspective and continues orbiting.
The complete snapped orientation is preserved when returning to perspective.

When more than one Modo view window is open, the gesture is locked to the
top-level window under the mouse pointer. Other view windows are left
unchanged.

Version 1.3.0 rebuilds snapping around the complete screen orientation.
It compares all 24 fixed-view rotations: six viewing sides, each with four
90-degree spins. The closest rotation is selected using the screen-right,
screen-up, and outward axes together. This preserves the perspective heading
and bank as closely as an axis-aligned 2D view allows, including Top/Bottom,
rolled views, and orbiting over a pole.

The kit samples Modo's actual screen-to-world transformation with `To3D()`.
Modo's fixed-view `Matrix()` omits the orthographic spin, so that matrix alone
cannot reproduce what is on screen. Every snap explicitly sets both the view
type and its orientation, including the zero-degree rotation on Front.

## Version log

- **1.3.0:** Rebuilt full-orientation matching across all 24 axis views; restored
  correct Front snapping and prevented previously used spins from carrying
  into subsequent snaps. Added native Modo orientation fixtures and randomized
  rotation checks. Preserved orthographic spin when returning to perspective.
- **1.2.6:** Attempted direct Top/Bottom heading matching; superseded by 1.3.0.
- **1.2.5:** Attempted runtime orientation cycling; superseded by 1.3.0.
- **1.2.4:** Corrected perspective matrix axis extraction for pitched views.

Made using OpenAI Codex.

## Install on macOS

1. Quit Modo.
2. Copy the entire `3DP_AxisSnap` folder into:
   `~/Library/Application Support/Luxology/Kits/`
3. Start Modo.

The feature enables itself at startup.

When upgrading, replace the existing `3DP_AxisSnap` folder while Modo is closed.
Do not keep multiple versions of the kit in the Kits directory.

## Install on Windows

1. Quit Modo.
2. Press **Windows + R**, enter `%APPDATA%\Luxology\Kits`, and press Enter.
   Create the `Kits` folder if it does not already exist.
3. Copy the entire `3DP_AxisSnap` folder into the `Kits` folder.
4. Start Modo.

`%APPDATA%` normally expands to
`C:\Users\<username>\AppData\Roaming`. The feature enables itself at startup.

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

This kit is not tied to a single Modo version or operating system. Version
1.3.0 selects the Qt binding bundled with the running Modo version:

- Modo 14 and earlier: PySide
- Modo 15 and 16: PySide2
- Modo 17 and later: PySide6

It also normalizes the Qt 4/5 and Qt 6 enum layouts used by the gesture event
filter. These binding branches are covered by automated import tests; they do
not imply that every Modo release has been tested in the application.

Earlier gesture versions were tested on macOS with:

- Modo 16.1v8
- Modo 17.1v1

The 1.3.0 destination orientations were measured directly in Modo 17.1v1.
Automated checks cover the 24 native orientations, nearby views, and 2,000
arbitrary rotations. All 13 automated test groups passed.

In Modo 17.1v1 on macOS, 120 native viewport round trips passed: all 24 exact
axis orientations, 24 nearby oblique orientations, and 72 arbitrary rotations.
These checks exercised the event handler with simulated input events while
using real Modo projection/orientation commands and screen transforms. Every
snap selected the expected destination; every return to perspective preserved
the snapped basis and left the initial mouse press unconsumed for normal
orbiting. Physical held-button dragging still requires manual confirmation.

The implementation is expected to work on Windows because it uses Modo and
Qt input APIs rather than macOS-specific APIs, but Windows has not yet been
tested. The kit does not modify Modo's saved keyboard or mouse mappings.
