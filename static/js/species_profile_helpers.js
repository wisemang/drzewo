(function speciesProfileHelpersModule(root) {
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

    function formatSpeciesProfileBenefits(benefits) {
        if (!benefits || benefits.available === false || !Array.isArray(benefits.items)) {
            return [];
        }

        return benefits.items
            .filter((item) => {
                if (!item || typeof item !== 'object' || item.scope !== 'species') {
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
                label: typeof item.label === 'string' && item.label.trim() ? item.label.trim() : null,
                text: item.text.trim()
            }));
    }

    const helpers = {
        formatSpeciesProfileBenefits,
        formatSpeciesProfileLocalStats,
        formatSpeciesProfileNumber,
        formatSpeciesProfileRadius,
        formatSpeciesProfileSummaryAttribution
    };

    if (typeof module !== 'undefined' && module.exports) {
        module.exports = helpers;
    }
    root.speciesProfileHelpers = helpers;
}(typeof globalThis !== 'undefined' ? globalThis : window));
