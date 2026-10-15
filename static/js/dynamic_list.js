function initDynamicRows(containerId, makeRowHTML, onChange) {
    const list = document.getElementById(containerId);
    if (!list) return;

    function isRowEmpty(row) {
        return [...row.querySelectorAll('input')].every(input => input.value.trim() === '');
    }

    function updateRemoveVisibility(row) {
        row.querySelector('.link-row-remove').classList.toggle('link-row-remove-invisible', isRowEmpty(row));
    }

    function wireRow(row) {
        row.querySelector('.link-row-remove').addEventListener('click', () => {
            row.remove();
            ensureTrailingEmptyRow();
            if (onChange) onChange();
        });
        row.querySelectorAll('input').forEach(input => {
            input.addEventListener('input', () => {
                row.classList.remove('invalid');
                updateRemoveVisibility(row);
                ensureTrailingEmptyRow();
                if (onChange) onChange();
            });
        });
        row.addEventListener('focusout', () => {
            setTimeout(() => {
                if (
                    row.isConnected &&
                    !row.contains(document.activeElement) &&
                    row !== list.lastElementChild &&
                    isRowEmpty(row)
                ) {
                    row.remove();
                    if (onChange) onChange();
                }
            }, 0);
        });
        updateRemoveVisibility(row);
    }

    function addRow() {
        const row = document.createElement('div');
        row.className = 'link-row';
        row.innerHTML = makeRowHTML();
        wireRow(row);
        list.appendChild(row);
    }

    function ensureTrailingEmptyRow() {
        const rows = list.querySelectorAll('.link-row');
        const last = rows[rows.length - 1];
        if (!last || !isRowEmpty(last)) {
            addRow();
        }
    }

    list.querySelectorAll('.link-row').forEach(wireRow);
    ensureTrailingEmptyRow();
    if (onChange) onChange();
}
