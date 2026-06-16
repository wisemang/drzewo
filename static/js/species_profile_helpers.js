(function speciesProfileHelpersModule(root) {
    const SPECIES_BENEFIT_LABELS = {
        pollinator_support: 'Pollinator support',
        shade_or_amenity: 'Shade and amenity',
        wildlife_food: 'Wildlife food',
        wildlife_habitat: 'Wildlife habitat',
        site_rehabilitation: 'Site rehabilitation',
        cultural_or_human_use: 'Cultural or human use'
    };
    const SPECIES_RISK_LABELS = {
        native_status: 'Native status',
        introduced_status: 'Introduced status',
        pest_host: 'Pest host',
        management_concern: 'Management concern'
    };

    function formatSpeciesProfileNumber(value) {
        const numericValue = Number(value);
        if (!Number.isFinite(numericValue)) {
            return 'N/A';
        }
        return Number.isInteger(numericValue) ? String(numericValue) : numericValue.toFixed(1);
    }

    function formatSpeciesProfileRadius(value) {
        const numericValue = Number(value);
        if (numericValue === 1000) {
            return '1 km';
        }
        return `${formatSpeciesProfileNumber(value)} m`;
    }

    function hasFiniteSpeciesProfileNumber(value) {
        return value !== null && value !== undefined && value !== '' && Number.isFinite(Number(value));
    }

    function formatSpeciesProfileLocalStats(localStats) {
        if (!localStats || typeof localStats !== 'object') {
            return null;
        }
        if (!hasFiniteSpeciesProfileNumber(localStats.radius_m) ||
                !hasFiniteSpeciesProfileNumber(localStats.same_species_count)) {
            return null;
        }
        const radiusDisplay = formatSpeciesProfileRadius(localStats.radius_m);
        const countDisplay = formatSpeciesProfileNumber(localStats.same_species_count);
        const largestDbh = localStats.largest_dbh;
        return {
            countLine: `${countDisplay} mapped trees of this species within ${radiusDisplay}`,
            largestLine: largestDbh === null || largestDbh === undefined
                ? null
                : `Largest nearby: ${formatSpeciesProfileNumber(largestDbh)} cm trunk diameter`
        };
    }

    function formatSpeciesProfileSummaryAttribution(attribution, license) {
        return `Summary from ${attribution} · ${license}`;
    }

    function formatSpeciesProfileBenefitLabel(metricType) {
        return SPECIES_BENEFIT_LABELS[metricType] || null;
    }

    function formatSpeciesProfileRiskLabel(riskType) {
        return SPECIES_RISK_LABELS[riskType] || null;
    }

    function formatSpeciesProfileSourceFields(item) {
        return {
            sourceSystem: typeof item.source_system === 'string' && item.source_system.trim()
                ? item.source_system.trim()
                : null,
            sourceUrl: typeof item.source_url === 'string' && item.source_url.trim()
                ? item.source_url.trim()
                : null,
            attribution: typeof item.attribution === 'string' && item.attribution.trim()
                ? item.attribution.trim()
                : null,
            license: typeof item.license === 'string' && item.license.trim()
                ? item.license.trim()
                : null,
            licenseUrl: typeof item.license_url === 'string' && item.license_url.trim()
                ? item.license_url.trim()
                : null
        };
    }

    function formatSpeciesProfileBenefits(benefits) {
        if (!benefits || benefits.available === false || !Array.isArray(benefits.items)) {
            return [];
        }

        return benefits.items
            .filter((item) => {
                if (!item || typeof item !== 'object' || item.scope !== 'species') {
                    return false;
                }
                if (!formatSpeciesProfileBenefitLabel(item.metric_type)) {
                    return false;
                }
                if (typeof item.text !== 'string' || !item.text.trim()) {
                    return false;
                }
                if (hasFiniteSpeciesProfileNumber(item.value) ||
                        hasFiniteSpeciesProfileNumber(item.min_value) ||
                        hasFiniteSpeciesProfileNumber(item.max_value)) {
                    return false;
                }
                return true;
            })
            .map((item) => ({
                label: formatSpeciesProfileBenefitLabel(item.metric_type),
                text: item.text.trim(),
                ...formatSpeciesProfileSourceFields(item)
            }));
    }

    function formatSpeciesProfileRisks(risk) {
        const emptyResult = {
            items: [],
            hasRegionalStatusCaveat: false,
            hasPestHostCaveat: false
        };
        if (!risk || risk.available === false || !Array.isArray(risk.items)) {
            return emptyResult;
        }

        const items = risk.items
            .filter((item) => {
                if (!item || typeof item !== 'object') {
                    return false;
                }
                if (!formatSpeciesProfileRiskLabel(item.risk_type)) {
                    return false;
                }
                if (typeof item.region !== 'string' || !item.region.trim()) {
                    return false;
                }
                if (typeof item.notes !== 'string' || !item.notes.trim()) {
                    return false;
                }
                if (typeof item.status !== 'string' || !item.status.trim() || item.status === 'unknown') {
                    return false;
                }
                return true;
            })
            .map((item) => ({
                riskType: item.risk_type,
                label: formatSpeciesProfileRiskLabel(item.risk_type),
                region: item.region.trim(),
                text: item.notes.trim(),
                ...formatSpeciesProfileSourceFields(item)
            }));

        return {
            items,
            hasRegionalStatusCaveat: items.some(
                (item) => item.riskType === 'native_status' || item.riskType === 'introduced_status'
            ),
            hasPestHostCaveat: items.some((item) => item.riskType === 'pest_host')
        };
    }

    const helpers = {
        formatSpeciesProfileBenefitLabel,
        formatSpeciesProfileBenefits,
        formatSpeciesProfileLocalStats,
        formatSpeciesProfileNumber,
        formatSpeciesProfileRadius,
        formatSpeciesProfileRiskLabel,
        formatSpeciesProfileRisks,
        formatSpeciesProfileSummaryAttribution
    };

    if (typeof module !== 'undefined' && module.exports) {
        module.exports = helpers;
    }
    root.speciesProfileHelpers = helpers;
}(typeof globalThis !== 'undefined' ? globalThis : window));
