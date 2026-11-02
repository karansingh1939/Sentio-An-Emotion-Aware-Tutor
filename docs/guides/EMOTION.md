# Emotion-aware side feature

Sentio began as an emotion-aware tutor. That first prototype is kept as an optional
side feature: the main product, cited study from your own notes, never depends on it.

## What it does

| Part                                                                       | Where it runs                               | Output                                                      |
| -------------------------------------------------------------------------- | ------------------------------------------- | ----------------------------------------------------------- |
| Facial emotion CNN (7 classes, FER2013, 48×48 grayscale)                   | Server, `src/sentio/emotion/detector.py`    | emotion → learning state (for example `sad` → `struggling`) |
| Attention estimate from MediaPipe face landmarks (eye openness, head pose) | Browser, `static/js/core/emotion_camera.js` | attention score and focus state sent as telemetry           |

The learning state changes only the tutor's **tone and pacing** instructions (simpler
wording, shorter answers when distracted). It never changes the session's difficulty
(see `sentio/tutor/difficulty.py`), which notes are cited, or whether the evidence check
refuses an answer.

## Turning it on

1. Install the optional TensorFlow extra: `uv sync --locked --extra camera`, and start
   Sentio with `uv run --extra camera sentio` (a plain `uv sync` removes the extra).
2. Provide the trained model at `models/emotion_model.h5` (train it with
   `python scripts/emotion/train.py`, see the script for dataset layout).
3. For browser attention tracking, supply the MediaPipe assets locally:
   `src/sentio/static/vendor/mediapipe/vision_bundle.mjs`, its `wasm/` folder and
   `face_landmarker.task`. Nothing is downloaded automatically. Tested with
   `@mediapipe/tasks-vision` 0.10.35 from npm and the float16 face landmarker model from
   Google's MediaPipe model storage; the folder is git-ignored.
4. Start Sentio with `ENABLE_EMOTION=true`.
5. Each learner must turn on camera consent in **Settings**.

## Studying slides with the camera

On **Study slides** the camera feeds two signals, both turned into a mood by
`src/sentio/emotion/policy.py` (`study_mood`):

- every 3 seconds the browser sends one frame, scaled to at most 320×240 JPEG, over the
  authenticated live-frame connection to the CNN; only the resulting emotion reading is
  kept on the session, never the frame;
- every 10 seconds MediaPipe attention arrives as telemetry; clearly looking away (low
  attention, not focused) counts as a "disengaged" reading.

The mood uses only confident readings from the last 30 seconds, needs a state to last
5 seconds before it counts, and offers a simpler explanation after 20 seconds of
struggling, frustration or anxiety, or a break after 60 seconds of disengagement. A
fresh mood sets the tutor's tone; an explicit request in the student's message wins.
The connection reopens once each time the login token is renewed.

## Privacy and safety

- Off by default. With the flag off, the camera controls are hidden and the telemetry
  and live-frame endpoints return 404.
- The server checks the learner's latest saved consent before accepting any camera
  data (telemetry, live frames, or a frame attached to a chat message) and closes
  live connections when consent is withdrawn.
- Frames are limited to 512 KB and 1280×720 pixels; dimensions are read before the
  image is decoded.
- Navigation, logout, session changes and consent revocation stop the camera.
- Settings can delete stored attention and emotion telemetry.

## Limits

The emotion model and attention heuristics have **no validated accuracy**. Facial
expressions are a weak and culturally variable signal of how someone feels, and the
feature does not measure learning. Treat it as a prototype that shows how the project
grew, not as a measured capability.
