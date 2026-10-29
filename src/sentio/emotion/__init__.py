"""Optional emotion-aware side feature.

An earlier prototype that adapts the tutor's tone to how the learner seems to feel:
a FER2013 CNN classifies facial emotion on the server, and MediaPipe face landmarks in
the browser estimate attention. It is off unless ENABLE_EMOTION=true and the learner has
turned on camera consent; studying never depends on it, and its accuracy has not been
validated.
"""
