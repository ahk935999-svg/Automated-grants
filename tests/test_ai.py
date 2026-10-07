from core.ai import _parse_json

def test_parse_json_plain_object():
    assert _parse_json('{"decision":"REVIEW"}')['decision']=='REVIEW'

def test_parse_json_fenced_object():
    text='Here is the result: ```json\n{"decision":"PRIORITY"}\n```'
    assert _parse_json(text)['decision']=='PRIORITY'

def test_parse_json_embedded_object():
    text='preface {"decision":"LOW"} suffix'
    assert _parse_json(text)['decision']=='LOW'