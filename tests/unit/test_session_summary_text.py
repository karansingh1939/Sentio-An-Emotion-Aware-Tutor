from sentio.ai.tutor_llm import summary_bullets


def test_json_summary_becomes_plain_bullets():
    reply = '```json\n{"covered_content": "Registers", "struggles": ["Flags", "Stack"]}\n```'
    assert summary_bullets(reply) == "- Registers\n- Flags\n- Stack"


def test_plain_text_summary_is_unchanged():
    reply = "- Covered registers\n- Struggled with flags"
    assert summary_bullets(reply) == reply


def test_empty_json_keeps_the_original_reply():
    assert summary_bullets("{}") == "{}"
