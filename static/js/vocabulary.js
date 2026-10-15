// Vocabulary page: pinyin and meaning lists (via dynamic_list.js) and the edit overlay.

function escapeAttr(text) {
    return text.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
}

function rowHTML(name, placeholder, removeLabel) {
    return () =>
        `<input type="text" name="${name}" placeholder="${escapeAttr(placeholder)}" autocomplete="off">` +
        `<button type="button" class="link-row-remove" aria-label="${removeLabel}">×</button>`;
}

// Fill a container with one row per value, then let dynamic_list wire them
// up and add the trailing empty row.
function fillRows(containerId, values, makeRowHTML) {
    const list = document.getElementById(containerId);
    list.replaceChildren();
    for (const value of values) {
        const row = document.createElement('div');
        row.className = 'link-row';
        row.innerHTML = makeRowHTML();
        row.querySelector('input').value = value;  // set as a value, never as HTML
        list.appendChild(row);
    }
    initDynamicRows(containerId, makeRowHTML);
}

const meaningRow = rowHTML('meaning', 'Add a meaning', 'Remove meaning');
const pinyinRow = placeholder => rowHTML('pinyin', placeholder, 'Remove pinyin');

fillRows('add-pinyin', [], pinyinRow('e.g. péngyou'));
fillRows('add-meanings', [], meaningRow);

const dialog = document.getElementById('edit-dialog');

document.querySelectorAll('.vocab-item .edit-button').forEach(button => {
    button.addEventListener('click', () => {
        const item = button.closest('.vocab-item');
        const pinyin = JSON.parse(item.dataset.pinyin);
        document.getElementById('edit-title').textContent = item.dataset.text;
        document.getElementById('edit-text').value = item.dataset.text;
        // With no pinyin yet, suggest one; otherwise invite another reading.
        const placeholder = pinyin.length ? 'Add another reading' : item.dataset.suggestedPinyin;
        fillRows('edit-pinyin', pinyin, pinyinRow(placeholder));
        fillRows('edit-meanings', JSON.parse(item.dataset.meanings), meaningRow);
        dialog.showModal();
        document.querySelector('#edit-pinyin input').focus();
    });
});

document.getElementById('edit-cancel').addEventListener('click', () => dialog.close());

// Clicking the dimmed backdrop (outside the form) closes the overlay.
dialog.addEventListener('click', event => {
    if (event.target === dialog) dialog.close();
});

// Search filter: matches characters, pinyin (tone marks and spaces optional,
// so "hao" finds hǎo and "pengyou" finds péngyou) and meanings.
function normalize(text) {
    return text.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
}

const items = [...document.querySelectorAll('.vocab-item')].map(item => {
    const pinyin = JSON.parse(item.dataset.pinyin).map(normalize);
    return {
        item,
        haystack: [
            item.dataset.text,
            ...pinyin,
            ...pinyin.map(p => p.replace(/\s+/g, '')),
            ...JSON.parse(item.dataset.meanings).map(normalize),
        ].join('\n'),
    };
});

const search = document.getElementById('vocab-search');
const count = document.getElementById('vocab-count');

search.addEventListener('input', () => {
    const query = normalize(search.value.trim());
    let shown = 0;
    for (const { item, haystack } of items) {
        const match = haystack.includes(query);
        item.hidden = !match;
        if (match) shown++;
    }
    count.textContent = query ? `${shown} of ${items.length}` : items.length;
    document.getElementById('vocab-empty').hidden = shown > 0;
});
