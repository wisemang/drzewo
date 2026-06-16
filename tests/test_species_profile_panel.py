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
    assert "if (localStatsCopy)" in script
    assert "Nearby in TreeSeek" in script
    assert "records within" not in script
    assert "Radius used:" not in script
    assert ".species-profile-local-stats" in css
    assert ".species-profile-source-copy" in css


def test_species_profile_panel_renders_benefits_when_present():
    script = read_text("static/js/script.js")
    css = read_text("static/css/styles.css")

    assert "const benefits = profile.sections ? profile.sections.benefits : null" in script
    assert "speciesProfileHelpers.formatSpeciesProfileBenefits(benefits)" in script
    assert "<section class=\"species-profile-benefits\">" in script
    assert "<h3>Benefits</h3>" in script
    assert (
        "Species-level notes from cited sources. Actual benefits depend on tree size, "
        "health, and site conditions."
    ) in script
    assert "species-profile-benefits-caveat" in script
    assert "species-profile-benefit-item" in script
    assert "species-profile-benefit-source" in script
    assert "species-profile-benefit-license" in script
    assert ".species-profile-benefits" in css
    assert ".species-profile-benefits-caveat" in css
    assert ".species-profile-benefit-item" in css
    assert ".species-profile-benefit-source" in css
    assert ".species-profile-benefit-license" in css


def test_species_profile_panel_renders_regional_status_and_cautions():
    script = read_text("static/js/script.js")
    css = read_text("static/css/styles.css")

    assert "const risk = profile.sections ? profile.sections.risk : null" in script
    assert "speciesProfileHelpers.formatSpeciesProfileRisks(risk)" in script
    assert "<section class=\"species-profile-risk\">" in script
    assert "<h3>Regional status and cautions</h3>" in script
    assert (
        "Signals are from cited regional sources. Missing risk data does not mean "
        "the species is safe or free of concerns."
    ) in script
    assert (
        "Regional status is not a planting recommendation. Native does not mean "
        "risk-free, and introduced does not necessarily mean invasive."
    ) in script
    assert (
        "Pest-host notes are species- or genus-level signals and do not indicate "
        "that this individual tree is affected."
    ) in script
    assert "species-profile-risk-item" in script
    assert "species-profile-risk-region" in script
    assert "species-profile-risk-source" in script
    assert "species-profile-risk-license" in script
    assert ".species-profile-risk" in css
    assert ".species-profile-risk-caveat" in css
    assert ".species-profile-risk-item" in css
    assert ".species-profile-risk-region" in css
    assert ".species-profile-risk-source" in css
    assert ".species-profile-risk-license" in css


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


def test_species_profile_panel_keeps_media_section_hidden():
    script = read_text("static/js/script.js")
    css = read_text("static/css/styles.css")

    assert "species-profile-media" not in script
    assert "species-profile-media" not in css


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


def test_species_profile_local_stats_copy_omits_malformed_stats():
    assert run_species_profile_helper("helpers.formatSpeciesProfileLocalStats(null)") is None
    assert (
        run_species_profile_helper(
            "helpers.formatSpeciesProfileLocalStats({"
            "radius_m: null, "
            "same_species_count: 3, "
            "largest_dbh: null"
            "})"
        )
        is None
    )
    assert (
        run_species_profile_helper(
            "helpers.formatSpeciesProfileLocalStats({"
            "radius_m: 1000, "
            "same_species_count: undefined, "
            "largest_dbh: null"
            "})"
        )
        is None
    )


def test_species_profile_summary_attribution_copy_is_concise():
    result = run_species_profile_helper(
        "helpers.formatSpeciesProfileSummaryAttribution("
        "'Wikipedia contributors', "
        "'CC BY-SA 4.0'"
        ")"
    )

    assert result == "Summary from Wikipedia contributors · CC BY-SA 4.0"


def test_species_profile_benefits_copy_formats_text_notes():
    result = run_species_profile_helper(
        "helpers.formatSpeciesProfileBenefits({"
        "available: true, "
        "items: [{"
        "metric_type: 'shade_or_amenity', "
        "scope: 'species', "
        "label: 'Ignored API label', "
        "text: ' Large-canopied trees can provide shade and cooling in urban settings. ', "
        "source_system: 'usda-plants', "
        "source_url: 'https://plants.usda.gov/example', "
        "attribution: 'USDA NRCS', "
        "license: 'Public domain'"
        "}]"
        "})"
    )

    assert result == [
        {
            "label": "Shade and amenity",
            "text": "Large-canopied trees can provide shade and cooling in urban settings.",
            "sourceSystem": "usda-plants",
            "sourceUrl": "https://plants.usda.gov/example",
            "attribution": "USDA NRCS",
            "license": "Public domain",
            "licenseUrl": None,
        }
    ]


def test_species_profile_benefits_copy_omits_missing_or_estimate_items():
    result = run_species_profile_helper(
        "helpers.formatSpeciesProfileBenefits({"
        "available: true, "
        "items: ["
        "{metric_type: 'wildlife_habitat', scope: 'species', text: '  '}, "
        "{metric_type: 'wildlife_habitat', scope: 'tree_instance', label: 'Stormwater', "
        "text: 'Estimated annual stormwater interception'}, "
        "{metric_type: 'wildlife_habitat', scope: 'species', label: 'Stormwater', "
        "text: 'Estimated annual stormwater interception', "
        "value: 1200, unit: 'litres_per_year'}, "
        "{metric_type: 'unknown_metric', scope: 'species', label: 'Unknown', "
        "text: 'Source-backed note.'}, "
        "{metric_type: 'wildlife_habitat', scope: 'species', label: 'Habitat', "
        "text: 'Supports urban wildlife habitat.'}"
        "]"
        "})"
    )

    assert result == [
        {
            "label": "Wildlife habitat",
            "text": "Supports urban wildlife habitat.",
            "sourceSystem": None,
            "sourceUrl": None,
            "attribution": None,
            "license": None,
            "licenseUrl": None,
        }
    ]


def test_species_profile_benefit_labels_cover_approved_first_slice_metric_types():
    result = run_species_profile_helper(
        "["
        "helpers.formatSpeciesProfileBenefitLabel('pollinator_support'), "
        "helpers.formatSpeciesProfileBenefitLabel('shade_or_amenity'), "
        "helpers.formatSpeciesProfileBenefitLabel('wildlife_food'), "
        "helpers.formatSpeciesProfileBenefitLabel('wildlife_habitat'), "
        "helpers.formatSpeciesProfileBenefitLabel('site_rehabilitation'), "
        "helpers.formatSpeciesProfileBenefitLabel('cultural_or_human_use')"
        "]"
    )

    assert result == [
        "Pollinator support",
        "Shade and amenity",
        "Wildlife food",
        "Wildlife habitat",
        "Site rehabilitation",
        "Cultural or human use",
    ]


def test_species_profile_risks_copy_formats_native_status_with_region_and_provenance():
    result = run_species_profile_helper(
        "helpers.formatSpeciesProfileRisks({"
        "available: true, "
        "items: [{"
        "risk_type: 'native_status', "
        "status: 'native', "
        "region: 'CA-ON', "
        "notes: 'Native in Ontario according to the cited regional checklist.', "
        "source_system: 'vascan', "
        "source_url: 'https://example.test/risk/acer-rubrum/ca-on', "
        "attribution: 'VASCAN', "
        "license: 'CC BY 4.0'"
        "}]"
        "})"
    )

    assert result == {
        "items": [
            {
                "riskType": "native_status",
                "label": "Native status",
                "region": "CA-ON",
                "text": "Native in Ontario according to the cited regional checklist.",
                "sourceSystem": "vascan",
                "sourceUrl": "https://example.test/risk/acer-rubrum/ca-on",
                "attribution": "VASCAN",
                "license": "CC BY 4.0",
                "licenseUrl": None,
            }
        ],
        "hasRegionalStatusCaveat": True,
        "hasPestHostCaveat": False,
    }


def test_species_profile_risks_copy_supports_introduced_and_pest_host_caveats():
    result = run_species_profile_helper(
        "helpers.formatSpeciesProfileRisks({"
        "available: true, "
        "items: ["
        "{risk_type: 'introduced_status', status: 'introduced', region: 'CA', "
        "notes: 'Introduced status note from a cited regional source.'}, "
        "{risk_type: 'pest_host', status: 'present', region: 'CA-ON', "
        "notes: 'Ash species are documented hosts in the cited pest advisory.'}"
        "]"
        "})"
    )

    assert result["items"] == [
        {
            "riskType": "introduced_status",
            "label": "Introduced status",
            "region": "CA",
            "text": "Introduced status note from a cited regional source.",
            "sourceSystem": None,
            "sourceUrl": None,
            "attribution": None,
            "license": None,
            "licenseUrl": None,
        },
        {
            "riskType": "pest_host",
            "label": "Pest host",
            "region": "CA-ON",
            "text": "Ash species are documented hosts in the cited pest advisory.",
            "sourceSystem": None,
            "sourceUrl": None,
            "attribution": None,
            "license": None,
            "licenseUrl": None,
        },
    ]
    assert result["hasRegionalStatusCaveat"] is True
    assert result["hasPestHostCaveat"] is True


def test_species_profile_risks_copy_omits_unknown_or_malformed_items():
    result = run_species_profile_helper(
        "helpers.formatSpeciesProfileRisks({"
        "available: true, "
        "items: ["
        "{risk_type: 'unknown_type', status: 'present', region: 'CA', notes: 'x'}, "
        "{risk_type: 'native_status', status: 'unknown', region: 'CA-ON', notes: 'x'}, "
        "{risk_type: 'management_concern', status: 'present', region: '  ', notes: 'x'}, "
        "{risk_type: 'management_concern', status: 'present', region: 'CA-ON', notes: '  '}"
        "]"
        "})"
    )

    assert result == {
        "items": [],
        "hasRegionalStatusCaveat": False,
        "hasPestHostCaveat": False,
    }
