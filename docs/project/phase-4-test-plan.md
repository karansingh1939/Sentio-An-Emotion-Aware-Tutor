# Phase 4 manual test plan: study with slides, camera optional

For the student to run once with the real camera and the real model. Automated tests cover
the same behaviour with fakes (`tests/integration/test_slide_study_flow.py`,
`tests/browser/test_slide_study_browser.py`); this list covers what fakes cannot: your camera,
your model and your own lecture.

Setup: a lecture deck (.pptx or .pdf) of 5 or more slides in a course, the local model
running, and a browser that has not yet been given camera permission for Sentio. Run it once
with the camera feature off (default) and once with `ENABLE_EMOTION=true` in `.env`.

Mark each line Pass or Fail, and write what you saw for any Fail.

## A. Slides, camera feature off (default)

- [ ] Library: the lecture row shows **Study slides**. Clicking it opens `#/slides`.
- [ ] The list shows one entry per slide that has text, in order; slide titles look right.
- [ ] Next and Previous move one slide at a time; the first slide has no working Previous and
      the last has no working Next.
- [ ] **Explain this slide** streams an explanation of the slide you are on, not another one.
- [ ] The explanation cites the slide (for example `slide 3`), and the citation matches the slide.
- [ ] Ask a follow-up ("Why does that matter?"). The answer stays about this slide.
- [ ] Move to another slide and ask a question the slide does not answer. The tutor says the
      notes do not cover it instead of inventing an answer.
- [ ] There is no Camera switch and no mood chip anywhere on the page.
- [ ] Reload the page, then reopen the slides. The lecture still opens and works.
- [ ] A different account cannot open your lecture's slides (the page shows an error, not slides).

## B. Camera on (`ENABLE_EMOTION=true`)

- [ ] The Camera switch is now visible on the slides page, and off by default.
- [ ] Settings: camera consent is off. Turning the Camera switch on asks you to give consent
      first; declining leaves the camera off and no camera light turns on.
- [ ] After consent, turning the switch on starts the camera (the camera light comes on).
- [ ] A small mood chip appears and says it is the camera's guess.
- [ ] Look at the slide normally for a minute. The chip reads "focused" or "calm".
- [ ] Look puzzled (frown, lean in) for about 20 to 30 seconds. The chip changes to "unsure"
      and offers "Want a simpler explanation?".
- [ ] Accept. The tutor asks "Explain this slide more simply." and the answer is simpler.
- [ ] The difficulty shown in the tutor bar does not change, and the citations and the
      evidence check behave as before. Mood only changes the tone.
- [ ] Look away from the screen for 30 seconds or more. The chip shows "distracted" and
      offers "Take a short break?".
- [ ] Accept the break. It pauses for 2 minutes with a countdown, then returns to the slide.
- [ ] Cover the camera or leave the frame. The chip stops claiming a mood after about 30 seconds.
- [ ] Turn the Camera switch off. The camera light goes out within a second or two and the
      chip disappears.

## C. Privacy checks (do all of these)

- [ ] **Leaving the page stops the camera.** With the camera on, click another tab inside
      Sentio (for example Dashboard), then check the camera light is off. Come back: the
      switch is off or asks again; it does not resume silently.
- [ ] Close the browser tab with the camera on. The camera light goes out.
- [ ] Reload the page with the camera on. The camera is off after the reload.
- [ ] **Consent off blocks camera data.** Turn camera consent off in Settings while the
      camera is on. The camera stops, the chip disappears, and turning it on again asks for
      consent. With the browser developer tools open (Network), no camera, mood or
      telemetry request succeeds after consent is off (they return 403, not 200).
- [ ] With the feature off (no `ENABLE_EMOTION`), the same requests return 404 and the page
      shows no camera control.
- [ ] No video frames or images are stored: after a camera session, look in the `data/`
      folder for image files and find none.
- [ ] **Settings can delete telemetry.** Settings, Privacy: delete telemetry. Afterwards the
      mood chip starts from nothing (no old "unsure" reading), and a fresh page load shows
      no earlier camera mood.
- [ ] The mood never appears in anything another person can see, and nothing on screen claims
      the tutor can see your face. Any wording about the camera calls it a guess.

## D. Real-model quality (judgement)

- [ ] Explain five different slides. In each, the explanation is correct against the slide
      text and does not add facts the lecture never says.
- [ ] A "simpler" explanation uses plainer words but keeps the same facts.
- [ ] An answer in a different mood has a different tone, not different facts.

## Notes for the tester

Write down anything surprising: slow streaming, a camera light that stays on, a chip that
flickers between moods, or wording that sounds certain about your feelings.
