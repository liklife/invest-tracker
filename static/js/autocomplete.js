let searchTimeout;

function setupTickerAutocomplete() {
    const tickerInput = document.getElementById('ticker');
    const suggestionsDiv = document.getElementById('ticker-suggestions');

    if (!tickerInput || !suggestionsDiv) return;

    tickerInput.addEventListener('input', function() {
        const query = this.value.trim();

        clearTimeout(searchTimeout);

        if (query.length < 2) {
            suggestionsDiv.innerHTML = '';
            suggestionsDiv.style.display = 'none';
            return;
        }

        // Показываем загрузку
        suggestionsDiv.innerHTML = '<div class="suggestion-item disabled">🔍 Поиск...</div>';
        suggestionsDiv.style.display = 'block';

        searchTimeout = setTimeout(() => {
            fetch(`/api/search_tickers?q=${encodeURIComponent(query)}`)
                .then(response => response.json())
                .then(data => {
                    if (data.length === 0) {
                        suggestionsDiv.innerHTML = '<div class="suggestion-item disabled">❌ Ничего не найдено</div>';
                        return;
                    }

                    let html = '';
                    data.forEach(item => {
                        html += `<div class="suggestion-item" onclick="selectTicker('${item.ticker}', '${item.short_name.replace(/'/g, "\\'")}')">`;
                        html += `<strong>${item.ticker}</strong> - ${item.name}`;
                        html += `</div>`;
                    });

                    suggestionsDiv.innerHTML = html;
                })
                .catch(error => {
                    suggestionsDiv.innerHTML = '<div class="suggestion-item disabled">❌ Ошибка поиска</div>';
                });
        }, 300);
    });

    document.addEventListener('click', function(e) {
        if (!tickerInput.contains(e.target) && !suggestionsDiv.contains(e.target)) {
            suggestionsDiv.style.display = 'none';
        }
    });
}

function selectTicker(ticker, name) {
    document.getElementById('ticker').value = ticker;
    document.getElementById('ticker-suggestions').style.display = 'none';
}

document.addEventListener('DOMContentLoaded', setupTickerAutocomplete);