import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_text(path):
    return (ROOT / path).read_text()


def test_species_profile_panel_shell_is_present():
    html = read_text("templates/index.html")

    assert 'id="species-profile-panel"' in html
    assert 'id="species-profile-title"' in html
    assert 'id="species-profile-body"' in html
    assert 'aria-live="polite"' in html
    assert 'aria-atomic="false"' in html
    assert 'id="species-profile-close"' in html
    assert 'aria-label="Close species profile"' in html
    assert 'title="Close species profile"' in html


def test_species_profile_panel_uses_lazy_numeric_route():
    html = read_text("templates/index.html")
    script = read_text("static/js/script.js")

    assert "/static/js/species_profile_helpers.js" in html
    assert html.index("/static/js/species_profile_helpers.js") < html.index("/static/js/script.js")
    assert "function usableSpeciesId" in script
    assert "Number.isInteger(numericValue)" in script
    assert "SPECIES_PROFILE_LOCAL_RADIUS_M = 1000" in script
    assert "fetch(`/species/${numericSpeciesId}/profile${queryString}`)" in script
    assert "class=\"species-profile-trigger\"" in script
    assert "lastSpeciesProfileTrigger = trigger" in script
    assert "data-species-id=\"${speciesId}\"" in script
    assert "data-latitude=\"${latitude === null ? '' : latitude}\"" in script
    assert "data-longitude=\"${longitude === null ? '' : longitude}\"" in script
    assert "radius_m=${radiusM}" in script
    assert "} \u2192</button>" in script


def test_species_profile_panel_handles_profile_states_and_attribution_guard():
    script = read_text("static/js/script.js")

    assert "Loading species profile..." in script
    assert "No species profile is available yet." in script
    assert "Unable to load this species profile right now." in script
    assert "summaryText && attribution && (license || licenseUrl)" in script
    assert "Read more on Wikipedia" in script
    assert "Summary from " in script
    assert "species-profile-source-copy" in script


def test_species_profile_panel_manages_focus_and_escape_close():
    script = read_text("static/js/script.js")

    assert "let lastSpeciesProfileTrigger = null" in script
    assert "let activeSpeciesProfileRequestId = 0" in script
    assert "closeButton.focus()" in script
    assert "document.contains(lastSpeciesProfileTrigger)" in script
    assert "lastSpeciesProfileTrigger.focus()" in script
    assert "function isSpeciesProfilePanelOpen()" in script
    assert "event.key === 'Escape' && isSpeciesProfilePanelOpen()" in script
    assert "closeSpeciesProfilePanel();" in script


def test_species_profile_panel_ignores_stale_fetch_results():
    script = read_text("static/js/script.js")

    assert "activeSpeciesProfileRequestId += 1" in script
    assert "const requestId = activeSpeciesProfileRequestId + 1" in script
    assert "activeSpeciesProfileRequestId = requestId" in script
    assert "if (requestId !== activeSpeciesProfileRequestId)" in script
    assert "speciesProfileCache.set(cacheKey, profile);" in script
    assert script.index("speciesProfileCache.set(cacheKey, profile);") < script.index(
        "if (requestId !== activeSpeciesProfileRequestId)"
    )
    assert script.index("if (requestId !== activeSpeciesProfileRequestId)") < script.index(
        "renderSpeciesProfile(profile, commonName, botanicalName);"
    )
    assert script.index("if (requestId !== activeSpeciesProfileRequestId)") < script.index(
        "renderSpeciesProfileError(commonName, botanicalName);"
    )


def test_species_profile_panel_renders_local_stats_when_present():
    script = read_text("static/js/script.js")
    css = read_text("static/css/styles.css")

    assert "const localStats = profile.sections ? profile.sections.local_stats : null" in script
    assert "if (localStats)" in script
    assert "speciesProfileHelpers.formatSpeciesProfileLocalStats(localStats)" in script
    assert "Nearby in TreeSeek" in script
    assert "records within" not in script
    assert "Radius used:" not in script
    assert ".species-profile-local-stats" in css
    assert ".species-profile-source-copy" in css


def test_species_profile_panel_has_mobile_release_polish():
    css = read_text("static/css/styles.css")

    assert "max-height: 100dvh" in css
    assert "height: min(78dvh, 620px)" in css
    assert "env(safe-area-inset-bottom" in css
    assert "env(safe-area-inset-left" in css
    assert "env(safe-area-inset-right" in css
    assert "overscroll-behavior: contain" in css
    assert "-webkit-overflow-scrolling: touch" in css
    assert "min-width: 44px" in css
    assert "min-height: 44px" in css


def run_species_profile_helper(expression):
    helper_path = ROOT / "static/js/species_profile_helpers.js"
    node_script = f"""
        const helpers = require({json.dumps(str(helper_path))});
        const result = {expression};
        process.stdout.write(JSON.stringify(result));
    """
    completed = subprocess.run(
        ["node", "-e", node_script],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def test_species_profile_radius_formats_1000_m_as_1_km():
    assert run_species_profile_helper("helpers.formatSpeciesProfileRadius(1000)") == "1 km"


def test_species_profile_local_stats_copy_includes_count_and_largest_dbh():
    result = run_species_profile_helper(
        "helpers.formatSpeciesProfileLocalStats({"
        "radius_m: 1000, "
        "same_species_count: 12, "
        "largest_dbh: 42.5"
        "})"
    )

    assert result["countLine"] == "12 mapped trees of this species within 1 km"
    assert result["largestLine"] == "Largest nearby: 42.5 cm trunk diameter"


def test_species_profile_local_stats_copy_omits_missing_largest_dbh():
    result = run_species_profile_helper(
        "helpers.formatSpeciesProfileLocalStats({"
        "radius_m: 500, "
        "same_species_count: 3, "
        "largest_dbh: null"
        "})"
    )

    assert result["countLine"] == "3 mapped trees of this species within 500 m"
    assert result["largestLine"] is None


def test_species_profile_summary_attribution_copy_is_concise():
    result = run_species_profile_helper(
        "helpers.formatSpeciesProfileSummaryAttribution("
        "'Wikipedia contributors', "
        "'CC BY-SA 4.0'"
        ")"
    )

    assert result == "Summary from Wikipedia contributors · CC BY-SA 4.0"
