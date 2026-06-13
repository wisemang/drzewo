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

    function formatSpeciesProfileLocalStats(localStats) {
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

    const helpers = {
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
