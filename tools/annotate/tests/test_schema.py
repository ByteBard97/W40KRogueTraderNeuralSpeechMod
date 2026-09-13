from schema import EMOTIONS, JSON_SCHEMA, build_json_schema


def test_module_level_schema_uses_default_emotions():
    assert JSON_SCHEMA["properties"]["lines"]["items"]["properties"]["emotion"]["enum"] == EMOTIONS


def test_build_json_schema_swaps_emotion_enum():
    custom = ["resigned", "hopeful", "defiant"]
    schema = build_json_schema(custom)
    assert schema["properties"]["lines"]["items"]["properties"]["emotion"]["enum"] == custom
    # everything else about the shape is unchanged
    assert schema["properties"]["lines"]["items"]["required"] == JSON_SCHEMA["properties"]["lines"]["items"]["required"]
