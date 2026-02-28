import requests
import sqlite3
import os

DB_PATH = os.path.join('instance', 'tracker.db')


def get_current_price(ticker):
    """Получает цену с Мосбиржи, выбирая правильный режим торгов"""
    url = f"https://iss.moex.com/iss/engines/stock/markets/shares/securities/{ticker}.json"
    params = {
        'iss.meta': 'off',
        'marketdata.columns': 'LAST,BOARDID'
    }

    try:
        #print(f"🔍 Запрашиваю {ticker}...")
        response = requests.get(url, params=params, timeout=5)
        data = response.json()

        market_data = data.get('marketdata', {}).get('data', [])
        market_cols = data.get('marketdata', {}).get('columns', [])

        #print(f"📊 Получено записей: {len(market_data)}")

        # Находим индексы колонок
        last_idx = market_cols.index('LAST') if 'LAST' in market_cols else 0
        board_idx = market_cols.index('BOARDID') if 'BOARDID' in market_cols else 1

        # Смотрим все записи
        for i, row in enumerate(market_data):
            board = row[board_idx] if len(row) > board_idx else 'unknown'
            last = row[last_idx] if len(row) > last_idx else None
            #print(f"  Запись {i}: BOARD={board}, LAST={last}")

            # Нам нужен TQBR (основной режим)
            if board == 'TQBR':
                if last and isinstance(last, (int, float)):
                    #print(f"✅ НАШЕЛ TQBR: {last}")
                    return float(last)

        # Если нет TQBR, ищем любой с ценой
        for row in market_data:
            board = row[board_idx] if len(row) > board_idx else 'unknown'
            last = row[last_idx] if len(row) > last_idx else None
            if last and isinstance(last, (int, float)):
                #print(f"⚠️ Использую {board}: {last}")
                return float(last)

        # Если ничего нет - берем PREVPRICE из securities
        securities_data = data.get('securities', {}).get('data', [])
        securities_cols = data.get('securities', {}).get('columns', [])

        if 'PREVPRICE' in securities_cols:
            prev_idx = securities_cols.index('PREVPRICE')
            for row in securities_data:
                if len(row) > prev_idx and row[prev_idx] and isinstance(row[prev_idx], (int, float)):
                    #print(f"📅 Использую PREVPRICE: {row[prev_idx]}")
                    return float(row[prev_idx])

    except Exception as e:
        print(f"❌ Ошибка для {ticker}: {e}")

    #print(f"❌ НЕ НАШЕЛ цену для {ticker}")
    return None


def get_stock_by_isin(isin):
    """Найти бумагу по ISIN в БД"""
    if not isin:
        return None
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute('SELECT * FROM stocks WHERE isin = ?', (isin,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_stock_by_ticker(ticker):
    """Найти бумагу по тикеру в БД"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute('SELECT * FROM stocks WHERE ticker = ?', (ticker,))
        row = cursor.fetchone()
        return dict(row) if row else None


def add_stock_from_report(ticker, name, isin, emitent=''):
    """Добавить бумагу из отчета"""
    with sqlite3.connect(DB_PATH) as conn:
        if isin:
            cursor = conn.execute('SELECT id FROM stocks WHERE isin = ?', (isin,))
            existing = cursor.fetchone()
            if existing:
                return existing[0]

        if ticker:
            cursor = conn.execute('SELECT id FROM stocks WHERE ticker = ?', (ticker,))
            existing = cursor.fetchone()
            if existing:
                return existing[0]

        cursor = conn.execute('''
            INSERT INTO stocks (ticker, name, isin, emitent, source)
            VALUES (?, ?, ?, ?, 'report')
        ''', (ticker, name, isin, emitent))
        conn.commit()
        return cursor.lastrowid


def search_and_save(query):
    """Поиск бумаг на Мосбирже"""
    url = "https://iss.moex.com/iss/securities.json"
    params = {
        'q': query,
        'iss.meta': 'off',
        'iss.only': 'securities',
        'securities.columns': 'secid,shortname,isin,emitent_title'
    }

    try:
        response = requests.get(url, params=params)
        data = response.json()
        securities = data.get('securities', {}).get('data', [])

        results = []
        with sqlite3.connect(DB_PATH) as conn:
            for sec in securities[:10]:
                ticker = sec[0]
                name = sec[1]
                isin = sec[2] if len(sec) > 2 else ''
                emitent = sec[3] if len(sec) > 3 else ''

                conn.execute('''
                    INSERT OR IGNORE INTO stocks (ticker, name, isin, emitent, source)
                    VALUES (?, ?, ?, ?, 'search')
                ''', (ticker, name, isin, emitent))
                conn.commit()

                results.append({
                    'ticker': ticker,
                    'name': name,
                    'isin': isin,
                    'emitent': emitent
                })
        return results
    except:
        return []