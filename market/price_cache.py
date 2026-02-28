import time
from market.moex_client import get_current_price

_cache = {}
_cache_time = {}


def get_cached_price(ticker):
    """Возвращает цену из кэша или запрашивает новую (кэш на 5 минут)"""
    now = time.time()

    # Если в кэше есть и прошло меньше 5 минут
    if ticker in _cache and now - _cache_time.get(ticker, 0) < 300:
        #print(f"🔵 {ticker} из кэша")
        return _cache[ticker]

    # Иначе запрашиваем новую
    #print(f"🟢 {ticker} запрос к API")
    price = get_current_price(ticker)
    _cache[ticker] = price
    _cache_time[ticker] = now
    return price