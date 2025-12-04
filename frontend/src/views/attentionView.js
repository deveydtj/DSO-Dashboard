// Attention strip view module - "Things That Need Attention" rendering
// Pure JavaScript - no external dependencies

/**
 * Placeholder function to build attention items.
 * Currently returns an empty array - selection logic to be implemented in a later PR.
 * @param {Object} params - Data to analyze for attention items
 * @param {Object|null} params.summary - Summary data from API
 * @param {Array} params.repos - Repository list
 * @param {Array} params.services - Service list
 * @param {Array} params.pipelines - Pipeline list
 * @returns {Array} - Array of attention items (currently empty)
 */
export function buildAttentionItems({ summary, repos, services, pipelines }) {
    // Selection logic to be implemented in a later PR
    return [];
}

/**
 * Render the attention strip based on current data.
 * Shows an "all clear" message when no items need attention.
 * Shows a horizontal list of chips/pills when items exist.
 * @param {Object} params - Data to analyze for attention items
 * @param {Object|null} params.summary - Summary data from API
 * @param {Array} params.repos - Repository list
 * @param {Array} params.services - Service list
 * @param {Array} params.pipelines - Pipeline list
 */
export function renderAttentionStrip({ summary, repos, services, pipelines }) {
    const strip = document.getElementById('attentionStrip');
    if (!strip) {
        return;
    }

    // Ensure arrays are never null/undefined
    const safeRepos = repos || [];
    const safeServices = services || [];
    const safePipelines = pipelines || [];

    // Build attention items (currently returns empty array)
    const items = buildAttentionItems({
        summary,
        repos: safeRepos,
        services: safeServices,
        pipelines: safePipelines
    });

    // Clear previous content
    strip.innerHTML = '';

    if (items.length === 0) {
        // Show "all clear" message
        strip.classList.add('attention-strip--empty');
        const clearMessage = document.createElement('span');
        clearMessage.className = 'attention-clear-message';
        clearMessage.textContent = '✓ All clear – nothing needs attention right now';
        strip.appendChild(clearMessage);
    } else {
        // Show attention items as pills/chips
        strip.classList.remove('attention-strip--empty');
        items.forEach(item => {
            const chip = document.createElement('div');
            chip.className = 'attention-item';
            chip.textContent = item.label || 'Unknown';
            strip.appendChild(chip);
        });
    }
}
