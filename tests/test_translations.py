"""Guard translation strings against ICU message-format pitfalls.

The HA frontend renders translation strings through an ICU message formatter,
so any `{...}` is treated as a placeholder. A group like `{latitude, longitude}`
(a comma inside the braces) is parsed as an argument with an invalid type and
raises `INVALID_ARGUMENT_TYPE` in the UI. Every placeholder we use must be a
bare identifier.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml

from custom_components.naver_map.const import DIRECTIONS_MODES

PLACEHOLDER = re.compile(r"\{([^{}]*)\}")
COMPONENT = Path(__file__).parent.parent / "custom_components" / "naver_map"
TRANSLATIONS = COMPONENT / "translations"


def _iter_strings(obj: object) -> list[str]:
    if isinstance(obj, dict):
        return [s for value in obj.values() for s in _iter_strings(value)]
    if isinstance(obj, list):
        return [s for value in obj for s in _iter_strings(value)]
    if isinstance(obj, str):
        return [obj]
    return []


@pytest.mark.parametrize("name", ["en", "ko"])
def test_translation_placeholders_are_bare_identifiers(name: str) -> None:
    """Every {placeholder} in a translation string is a bare identifier."""
    data = json.loads((TRANSLATIONS / f"{name}.json").read_text(encoding="utf-8"))
    for text in _iter_strings(data):
        for placeholder in PLACEHOLDER.findall(text):
            assert placeholder.isidentifier(), (
                f"{name}.json: '{{{placeholder}}}' is not a bare placeholder; "
                "the frontend ICU formatter raises INVALID_ARGUMENT_TYPE"
            )


@pytest.mark.parametrize("name", ["en", "ko"])
def test_mode_selector_options_cover_all_modes(name: str) -> None:
    """The mode selector labels one entry for every travel mode token."""
    data = json.loads((TRANSLATIONS / f"{name}.json").read_text(encoding="utf-8"))
    options = data["selector"]["mode"]["options"]
    assert set(options) == set(DIRECTIONS_MODES)
    assert all(label for label in options.values())


@pytest.mark.parametrize("name", ["en", "ko"])
def test_every_service_field_is_translated(name: str) -> None:
    """Each services.yaml field has a name and description in the translation file."""
    services = yaml.safe_load((COMPONENT / "services.yaml").read_text(encoding="utf-8"))
    data = json.loads((TRANSLATIONS / f"{name}.json").read_text(encoding="utf-8"))
    for service, spec in services.items():
        fields = data["services"][service]["fields"]
        for field in spec.get("fields", {}):
            label = f"{name}.json: {service}.{field}"
            assert fields[field]["name"], f"{label} has no name"
            assert fields[field]["description"], f"{label} has no description"
