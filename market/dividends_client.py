import requests
from datetime import datetime, timedelta


def fetch_dividends_history(ticker):
    """
    Получает историю дивидендов с Мосбиржи
    Возвращает список словарей с ключами:
    - record_date (datetime)
    - value (float)
    - currency (str)
    """
    url = f"https://iss.moex.com/iss/securities/{ticker}/dividends.json"
    params = {'iss.meta': 'off'}

    try:
        #print(f"📡 Запрос к {url}")
        response = requests.get(url, params=params, timeout=5)

        if response.status_code != 200:
            #print(f"❌ Ошибка HTTP: {response.status_code}")
            return []

        data = response.json()

        # Проверяем наличие данных
        if 'dividends' not in data:
            #print("❌ Нет раздела 'dividends' в ответе")
            return []

        dividends_data = data['dividends']
        columns = dividends_data.get('columns', [])
        rows = dividends_data.get('data', [])

        #print(f"📊 Найдено строк: {len(rows)}")
        #print(f"📋 Колонки: {columns}")

        if not rows:
            return []

        # Определяем индексы колонок
        try:
            date_idx = columns.index('registryclosedate')
            value_idx = columns.index('value')
            currency_idx = columns.index('currencyid') if 'currencyid' in columns else None
        except ValueError as e:
            #print(f"❌ Ошибка в названиях колонок: {e}")
            return []

        result = []
        for row in rows:
            try:
                # Дата отсечки
                date_str = row[date_idx]
                if not date_str:
                    continue

                record_date = datetime.strptime(date_str, '%Y-%m-%d')

                # Сумма дивиденда
                value = row[value_idx]
                if value is None:
                    continue

                # Валюта
                currency = row[currency_idx] if currency_idx is not None and len(row) > currency_idx else 'RUB'

                result.append({
                    'record_date': record_date,
                    'value': float(value),
                    'currency': currency
                })

            except Exception as e:
                #print(f"⚠️ Ошибка обработки строки {row}: {e}")
                continue

        #print(f"✅ Успешно обработано: {len(result)} записей")

        # Для Транснефти сразу делим старые данные
        if ticker == 'TRNFP':
            for r in result:
                if r['record_date'].year <= 2023:
                    r['value'] = r['value'] / 100
                    #print(f"  🔧 TRNFP: исправлены данные за {r['record_date'].year} -> {r['value']} ₽")

        return result

    except requests.exceptions.Timeout:
        #print(f"⏰ Таймаут для {ticker}")
        return []
    except requests.exceptions.RequestException as e:
       #print(f"🌐 Ошибка сети для {ticker}: {e}")
        return []
    except Exception as e:
        #print(f"💥 Неизвестная ошибка для {ticker}: {e}")
        return []


def predict_next_dividend(ticker, history):
    """
    Предсказывает следующий дивиденд на основе истории
    Использует только последние 3 года для реалистичного прогноза
    """
    if len(history) < 2:
        return None, None

    # Сортируем по дате
    valid_history = [h for h in history if h['record_date'] is not None]
    if len(valid_history) < 2:
        return None, None

    valid_history.sort(key=lambda x: x['record_date'])

    # Берем только последние 3 года для расчета суммы
    # (чтобы избежать проблем со старыми данными в копейках)
    now = datetime.now()
    three_years_ago = now.replace(year=now.year - 3)

    recent_history = [h for h in valid_history if h['record_date'] >= three_years_ago]

    # Если за последние 3 года нет данных, берем все
    if len(recent_history) < 2:
        recent_history = valid_history

    # Для Транснефти особая обработка - там данные в копейках до 2023
    if ticker == 'TRNFP':
        # Исправляем старые данные (делим на 100)
        fixed_history = []
        for h in recent_history:
            if h['record_date'].year <= 2023:
                # Делим на 100, потому что это копейки
                fixed_value = h['value'] / 100
                fixed_history.append({
                    'record_date': h['record_date'],
                    'value': fixed_value,
                    'currency': h['currency']
                })
            else:
                fixed_history.append(h)
        recent_history = fixed_history

    # Считаем средний интервал по всей истории (для даты)
    dates = [h['record_date'] for h in valid_history]
    intervals = []
    for i in range(1, len(dates)):
        delta = (dates[i] - dates[i - 1]).days
        intervals.append(delta)

    avg_interval = sum(intervals) / len(intervals)
    next_date = dates[-1] + timedelta(days=avg_interval)

    # Считаем среднюю сумму ПОСЛЕДНИХ 3 лет
    amounts = [h['value'] for h in recent_history]
    avg_amount = sum(amounts) / len(amounts)

    #print(f"  📊 {ticker}: используем {len(recent_history)} записей, средняя сумма: {avg_amount:.2f}")

    return next_date, avg_amount