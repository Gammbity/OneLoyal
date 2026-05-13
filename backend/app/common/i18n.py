from typing import Any


def get_localized_value(i18n_map: dict | None, locale: str, default_locale: str = "en") -> str | None:
    if not i18n_map:
        return None
    # exact match
    if locale in i18n_map and i18n_map[locale]:
        return i18n_map[locale]
    # default locale
    if default_locale in i18n_map and i18n_map[default_locale]:
        return i18n_map[default_locale]
    # any available
    for v in i18n_map.values():
        if v:
            return v
    return None


def ensure_i18n_defaults(value: str | None, default_locale: str = "en") -> dict[str, str] | None:
    if value is None:
        return None
    return {default_locale: value}
