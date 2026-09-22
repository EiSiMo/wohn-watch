"""Central translation lookup.

Plain per-language dicts, no gettext — matches the project's dependency-free
style. `tests/test_i18n.py` enforces that every locale has exactly the same
keys with matching .format() placeholders, and a pre-commit hook
(.githooks/pre-commit) runs that test before every commit.
"""
import string
from importlib import import_module

SUPPORTED_LANGUAGES = ("de", "en")
DEFAULT_LANGUAGE = "en"  # fallback for a Telegram language_code we don't support

# Native names, shown on the /language picker — never translated.
LANGUAGE_NAMES = {"de": "Deutsch", "en": "English"}

_LOCALES = {lang: import_module(f"app.i18n.{lang}").STRINGS for lang in SUPPORTED_LANGUAGES}
_FORMATTER = string.Formatter()


def resolve_language(telegram_code: str | None) -> str:
    """Telegram's language_code ('de', 'de-DE', 'de_AT', ...) -> 'de';
    anything else (including None/'') -> the English fallback."""
    if telegram_code and telegram_code.lower().startswith("de"):
        return "de"
    return DEFAULT_LANGUAGE


def t(key: str, lang: str, **kwargs) -> str:
    strings = _LOCALES.get(lang, _LOCALES[DEFAULT_LANGUAGE])
    value = strings[key]
    return value.format(**kwargs) if kwargs else value


def format_fields(s: str) -> set[str]:
    """The .format() field names used by a string, for the completeness test."""
    return {name for _, name, _, _ in _FORMATTER.parse(s) if name}
