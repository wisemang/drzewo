from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_text(path):
    return (ROOT / path).read_text()


def test_species_profile_panel_shell_is_present():
    html = read_text("templates/index.html")

    assert 'id="species-profile-panel"' in html
    assert 'id="species-profile-title"' in html
    assert 'id="species-profile-body"' in html
    assert 'id="species-profile-close"' in html


def test_species_profile_panel_uses_lazy_numeric_route():
    script = read_text("static/js/script.js")

    assert "function usableSpeciesId" in script
    assert "Number.isInteger(numericValue)" in script
    assert "fetch(`/species/${numericSpeciesId}/profile`)" in script
    assert "class=\"species-profile-trigger\"" in script
    assert "data-species-id=\"${speciesId}\"" in script


def test_species_profile_panel_handles_profile_states_and_attribution_guard():
    script = read_text("static/js/script.js")

    assert "Loading species profile..." in script
    assert "No species profile is available yet." in script
    assert "Unable to load this species profile right now." in script
    assert "summaryText && attribution && (license || licenseUrl)" in script
    assert "Read more on Wikipedia" in script
