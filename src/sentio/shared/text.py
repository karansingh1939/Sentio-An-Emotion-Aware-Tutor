"""Text clean-up for learner input before it reaches the model."""


def sanitise_input(text, max_length=2000):
    """
    Clean student input before sending to the LLM:
      - Strip leading/trailing whitespace
      - Remove null bytes
      - Truncate to max_length

    Args:
        text       : Raw input string
        max_length : Hard cap on input length

    Returns:
        Cleaned string
    """
    if not isinstance(text, str):
        text = str(text)
    text = text.strip().replace("\x00", "")
    return text[:max_length]
