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
    assert "SPECIES_PROFILE_LOCAL_RADIUS_M = 1000" in script
    assert "fetch(`/species/${numericSpeciesId}/profile${queryString}`)" in script
    assert "class=\"species-profile-trigger\"" in script
    assert "data-species-id=\"${speciesId}\"" in script
    assert "data-latitude=\"${latitude === null ? '' : latitude}\"" in script
    assert "data-longitude=\"${longitude === null ? '' : longitude}\"" in script
    assert "radius_m=${radiusM}" in script


def test_species_profile_panel_handles_profile_states_and_attribution_guard():
    script = read_text("static/js/script.js")

    assert "Loading species profile..." in script
    assert "No species profile is available yet." in script
    assert "Unable to load this species profile right now." in script
    assert "summaryText && attribution && (license || licenseUrl)" in script
    assert "Read more on Wikipedia" in script


def test_species_profile_panel_renders_local_stats_when_present():
    script = read_text("static/js/script.js")
    css = read_text("static/css/styles.css")

    assert "const localStats = profile.sections ? profile.sections.local_stats : null" in script
    assert "if (localStats)" in script
    assert "Nearby in TreeSeek" in script
    assert "localStats.same_species_count" in script
    assert "localStats.largest_dbh" in script
    assert "Radius used:" in script
    assert ".species-profile-local-stats" in css
