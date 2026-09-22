"""Translation completeness. This is the file the pre-commit hook
(.githooks/pre-commit) runs before every commit — it must stay fast and
must fail whenever a locale is missing a key or a key's .format()
placeholders drift apart between locales."""
import pytest

from app.i18n import SUPPORTED_LANGUAGES, _LOCALES, format_fields, resolve_language


def test_every_locale_has_exactly_the_same_keys():
    reference = set(_LOCALES["de"])
    for lang, strings in _LOCALES.items():
        missing = reference - set(strings)
        extra = set(strings) - reference
        assert not missing and not extra, f"{lang}: missing={missing} extra={extra}"


def test_format_placeholders_match_across_locales():
    for key, de_value in _LOCALES["de"].items():
        want = format_fields(de_value)
        for lang, strings in _LOCALES.items():
            got = format_fields(strings[key])
            assert got == want, f"{key}/{lang}: placeholders {got} != {want}"


def test_no_blank_strings():
    for lang, strings in _LOCALES.items():
        for key, value in strings.items():
            assert value.strip(), f"{lang}.{key} is blank"


@pytest.mark.parametrize("code,expected", [
    ("de", "de"), ("de-DE", "de"), ("de_AT", "de"), ("DE", "de"),
    ("en", "en"), ("en-US", "en"), ("fr", "en"), (None, "en"), ("", "en"),
])
def test_resolve_language(code, expected):
    assert resolve_language(code) == expected


def test_command_descriptions_exist_for_every_registered_command():
    from app.handlers.commands import COMMAND_NAMES

    for name in COMMAND_NAMES:
        for lang in SUPPORTED_LANGUAGES:
            assert f"CMD_DESC_{name.upper()}" in _LOCALES[lang]
