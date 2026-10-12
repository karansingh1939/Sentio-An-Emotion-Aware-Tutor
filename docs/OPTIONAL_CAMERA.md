# Optional camera assets

Camera controls are excluded from the supported study interface at this checkpoint.
For development only, TensorFlow can be installed with `uv sync --locked --extra camera`.
This does not install browser assets or certify the consent/privacy lifecycle.

Normal studying requires no camera or attention model. Camera consent starts off;
navigation, logout, session changes and consent revocation stop capture, including
late permission grants. Missing dependencies stop acquired tracks and report that
camera setup is unavailable.

The browser now loads optional assets only from the local application:

```text
src/sentio/static/vendor/mediapipe/vision_bundle.mjs
src/sentio/static/vendor/mediapipe/wasm/
src/sentio/static/vendor/mediapipe/face_landmarker.task
```

These assets are not bundled or automatically downloaded. A separately reviewed
installation must supply a compatible MediaPipe module exporting FilesetResolver
and FaceLandmarker, its matching WASM files and an appropriately licensed face
landmarker model. Do not mix versions or rename a third-party bundle without
checking its internal asset paths. Preserve upstream licences and attribution.
No camera setup or model-recognition accuracy has been verified for this release.
The normal study workflow and diagnostics remain available without these files.

Attention heuristics are experimental and do not measure learning or diagnose
emotion. Backend consent enforcement and a complete physical-camera test remain
open work in the implementation ledger.
