from bs4 import BeautifulSoup
from market.moex_client import add_stock_from_report


def parse_deals(html_path, db_conn):
    """Парсит сделки из отчета и сохраняет в БД"""
    with open(html_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')

    tables = soup.find_all('table')
    if len(tables) < 6:
        return []

    deals_table = tables[5]
    rows = deals_table.find_all('tr')

    deals = []
    for row in rows:
        cells = row.find_all('td')
        if len(cells) < 10:
            continue

        date = cells[0].text.strip()
        name = cells[3].text.strip()
        ticker = cells[4].text.strip()
        quantity = cells[7].text.strip()
        price = cells[8].text.strip()
        total = cells[9].text.strip()

        if name in ['', 'Наименование ЦБ', 'Площадка:', 'Итого']:
            continue

        try:
            quantity = float(quantity.replace(' ', ''))
            price = float(price.replace(' ', ''))
            total = float(total.replace(' ', ''))

            isin = None
            # Попробуем найти ISIN из другой таблицы
            isin_table = tables[6]
            isin_rows = isin_table.find_all('tr')
            for isin_row in isin_rows:
                isin_cells = isin_row.find_all('td')
                if len(isin_cells) >= 3 and isin_cells[1].text.strip() == ticker:
                    isin = isin_cells[2].text.strip()
                    break

            stock_id = add_stock_from_report(ticker, name, isin, '')

            deals.append({
                'date': date,
                'stock_id': stock_id,
                'quantity': quantity,
                'price': price,
                'total': total
            })
        except:
            continue

    # Сохраняем в БД
    for deal in deals:
        db_conn.execute('''
            INSERT INTO transactions (date, stock_id, quantity, price, commission, total)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (deal['date'], deal['stock_id'], deal['quantity'], deal['price'], 0, deal['total']))

    return deals