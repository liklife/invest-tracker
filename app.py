from flask import Flask, render_template, redirect, url_for, flash, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import datetime
from datetime import timedelta
from market.price_cache import get_cached_price  # вместо get_current_price
from database.db import db, User, Portfolio, Stock, Transaction, Dividend  # ДОБАВИЛ Stock
from forms import LoginForm, RegisterForm
from collections import defaultdict
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here-2026'  # ПОМЕНЯЙ ПОТОМ
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tracker.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Инициализация
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Пожалуйста, войдите для доступа к этой странице'

# Старая функция для совместимости
from database.db_manager import get_db as get_old_db


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route('/')
@app.route('/portfolio/<int:portfolio_id>')
@login_required
def index(portfolio_id=None):
    """Главная страница - показывает портфель по умолчанию или выбранный"""

    # Если не передан portfolio_id, берем первый портфель пользователя
    if portfolio_id is None:
        first_portfolio = Portfolio.query.filter_by(user_id=current_user.id).first()
        if not first_portfolio:
            flash('Создайте портфель', 'warning')
            return redirect(url_for('portfolios'))
        portfolio_id = first_portfolio.id

    # Получаем портфель
    portfolio = Portfolio.query.get_or_404(portfolio_id)
    if portfolio.user_id != current_user.id:
        flash('Доступ запрещен', 'error')
        return redirect(url_for('portfolios'))

    # Получаем транзакции ТОЛЬКО ЭТОГО портфеля
    transactions = Transaction.query.filter_by(portfolio_id=portfolio_id).all()

    # Группируем по бумагам
    stocks_data = {}
    for t in transactions:
        stock = Stock.query.get(t.stock_id)
        if stock.ticker not in stocks_data:
            stocks_data[stock.ticker] = {
                'stock': stock,
                'quantity': 0,
                'total_spent': 0,
                'transactions': []
            }
        stocks_data[stock.ticker]['quantity'] += t.quantity
        stocks_data[stock.ticker]['total_spent'] += t.total
        stocks_data[stock.ticker]['transactions'].append(t)

    # Считаем текущую стоимость
    total_current = 0
    total_spent = 0
    portfolio_data = []

    for ticker, data in stocks_data.items():
        stock = data['stock']
        quantity = data['quantity']
        spent = data['total_spent']
        total_spent += spent
        avg_price = spent / quantity if quantity > 0 else 0

        current_price = get_cached_price(ticker)

        if current_price:
            current_value = quantity * current_price
            profit = current_value - spent
            profit_percent = (profit / spent) * 100 if spent > 0 else 0
            price_source = "биржа"
        else:
            current_price = avg_price
            current_value = spent
            profit = 0
            profit_percent = 0
            price_source = "покупка"

        total_current += current_value

        portfolio_data.append({
            'name': stock.name,
            'ticker': ticker,
            'quantity': quantity,
            'avg_price': round(avg_price, 2),
            'current_price': round(current_price, 2),
            'price_source': price_source,
            'spent': round(spent, 2),
            'current_value': round(current_value, 2),
            'profit': round(profit, 2),
            'profit_percent': round(profit_percent, 2)
        })

    current_time = datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")

    # Получаем все портфели для меню
    portfolios = Portfolio.query.filter_by(user_id=current_user.id).all()

    return render_template('index.html',
                           portfolio=portfolio,
                           portfolios=portfolios,
                           portfolio_data=portfolio_data,
                           total_spent=round(total_spent, 2),
                           total_current=round(total_current, 2),
                           profit=round(total_current - total_spent, 2),
                           profit_percent=round(((total_current / total_spent) - 1) * 100, 2) if total_spent > 0 else 0,
                           current_time=current_time)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()

        if user and check_password_hash(user.password_hash, form.password.data):
            login_user(user)
            flash('Вы успешно вошли!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Неверное имя пользователя или пароль', 'error')

    return render_template('login.html', form=form)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    form = RegisterForm()
    if form.validate_on_submit():
        # Проверка существующего пользователя
        if User.query.filter_by(username=form.username.data).first():
            flash('Такое имя пользователя уже существует', 'error')
            return render_template('register.html', form=form)

        if User.query.filter_by(email=form.email.data).first():
            flash('Такой email уже зарегистрирован', 'error')
            return render_template('register.html', form=form)

        # Создаем нового пользователя
        user = User(
            username=form.username.data,
            email=form.email.data,
            password_hash=generate_password_hash(form.password.data)
        )

        db.session.add(user)
        db.session.commit()

        flash('Регистрация успешна! Теперь можно войти', 'success')
        return redirect(url_for('login'))

    return render_template('register.html', form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы вышли из системы', 'success')
    return redirect(url_for('login'))


@app.route('/portfolios')
@login_required
def portfolios():
    """Список портфелей пользователя"""
    user_portfolios = Portfolio.query.filter_by(user_id=current_user.id).all()
    return render_template('portfolios.html', portfolios=user_portfolios)


@app.route('/portfolio/new', methods=['GET', 'POST'])
@login_required
def new_portfolio():
    """Создание нового портфеля"""
    if request.method == 'POST':
        name = request.form.get('name')
        currency = request.form.get('currency', 'RUB')

        portfolio = Portfolio(
            name=name,
            currency=currency,
            user_id=current_user.id
        )
        db.session.add(portfolio)
        db.session.commit()

        flash('Портфель создан', 'success')
        return redirect(url_for('portfolios'))

    return render_template('new_portfolio.html')


@app.route('/portfolio/<int:portfolio_id>')
@login_required
def view_portfolio(portfolio_id):
    """Просмотр конкретного портфеля"""
    portfolio = Portfolio.query.get_or_404(portfolio_id)

    # Проверяем, что портфель принадлежит пользователю
    if portfolio.user_id != current_user.id:
        flash('Доступ запрещен', 'error')
        return redirect(url_for('portfolios'))

    # Получаем все транзакции этого портфеля
    transactions = Transaction.query.filter_by(portfolio_id=portfolio_id).all()

    # Группируем по бумагам
    stocks_data = {}
    for t in transactions:
        stock = Stock.query.get(t.stock_id)
        if stock.ticker not in stocks_data:
            stocks_data[stock.ticker] = {
                'stock': stock,
                'quantity': 0,
                'total_spent': 0,
                'transactions': []
            }
        stocks_data[stock.ticker]['quantity'] += t.quantity
        stocks_data[stock.ticker]['total_spent'] += t.total
        stocks_data[stock.ticker]['transactions'].append(t)

    # Считаем текущую стоимость
    portfolio_data = []
    for ticker, data in stocks_data.items():
        stock = data['stock']
        quantity = data['quantity']
        spent = data['total_spent']
        avg_price = spent / quantity if quantity > 0 else 0

        current_price = get_cached_price(ticker)

        if current_price:
            current_value = quantity * current_price
            profit = current_value - spent
            profit_percent = (profit / spent) * 100 if spent > 0 else 0
            price_source = "биржа"
        else:
            current_price = avg_price
            current_value = spent
            profit = 0
            profit_percent = 0
            price_source = "покупка"

        portfolio_data.append({
            'name': stock.name,
            'ticker': ticker,
            'quantity': quantity,
            'avg_price': round(avg_price, 2),
            'current_price': round(current_price, 2),
            'price_source': price_source,
            'spent': round(spent, 2),
            'current_value': round(current_value, 2),
            'profit': round(profit, 2),
            'profit_percent': round(profit_percent, 2),
            'transaction_id': data['transactions'][0].id  # для удаления
        })

    return render_template('portfolio.html', portfolio=portfolio, portfolio_data=portfolio_data)


@app.route('/add_transaction', methods=['GET', 'POST'])
@login_required
def add_transaction():
    """Добавление сделки вручную"""
    if request.method == 'POST':
        portfolio_id = request.form.get('portfolio_id')

        # Проверяем, что портфель принадлежит пользователю
        portfolio = Portfolio.query.get(portfolio_id)
        if portfolio.user_id != current_user.id:
            flash('Доступ запрещен', 'error')
            return redirect(url_for('portfolios'))

        ticker = request.form.get('ticker').upper()  # Верхний регистр
        quantity = float(request.form.get('quantity'))
        price = float(request.form.get('price'))
        date_str = request.form.get('date')
        commission = float(request.form.get('commission', 0))

        # Находим бумагу по тикеру
        stock = Stock.query.filter_by(ticker=ticker).first()
        if not stock:
            # Если бумаги нет в базе - создаем
            stock = Stock(
                ticker=ticker,
                name=ticker,
                isin=None,  # ВАЖНО: None, а не пустая строка
                currency='RUB'
            )
            db.session.add(stock)
            db.session.flush()

        date = datetime.datetime.strptime(date_str, '%Y-%m-%d')
        total = quantity * price + commission

        transaction = Transaction(
            portfolio_id=portfolio_id,
            stock_id=stock.id,
            date=date,
            quantity=quantity,
            price=price,
            commission=commission,
            total=total
        )
        db.session.add(transaction)
        db.session.commit()

        flash('Сделка добавлена', 'success')
        return redirect(url_for('view_portfolio', portfolio_id=portfolio_id))

    # GET запрос
    portfolios = Portfolio.query.filter_by(user_id=current_user.id).all()
    selected = request.args.get('portfolio_id')
    return render_template('add_transaction.html', portfolios=portfolios, selected=selected)


@app.route('/delete_transaction/<int:transaction_id>')
@login_required
def delete_transaction(transaction_id):
    """Удаление сделки"""
    transaction = Transaction.query.get_or_404(transaction_id)

    # Проверяем, что портфель принадлежит пользователю
    portfolio = Portfolio.query.get(transaction.portfolio_id)
    if portfolio.user_id != current_user.id:
        flash('Доступ запрещен', 'error')
        return redirect(url_for('portfolios'))

    portfolio_id = transaction.portfolio_id
    db.session.delete(transaction)
    db.session.commit()

    flash('Сделка удалена', 'success')
    return redirect(url_for('view_portfolio', portfolio_id=portfolio_id))


@app.route('/transactions/<int:portfolio_id>')
@login_required
def transactions_list(portfolio_id):
    """Список всех сделок портфеля"""
    portfolio = Portfolio.query.get_or_404(portfolio_id)

    if portfolio.user_id != current_user.id:
        flash('Доступ запрещен', 'error')
        return redirect(url_for('portfolios'))

    # Получаем все сделки портфеля с сортировкой по дате
    transactions = Transaction.query.filter_by(portfolio_id=portfolio_id) \
        .order_by(Transaction.date.desc()).all()

    # Обогащаем данными о бумагах
    transactions_data = []
    for t in transactions:
        stock = Stock.query.get(t.stock_id)
        transactions_data.append({
            'id': t.id,
            'date': t.date.strftime('%d.%m.%Y'),
            'stock_name': stock.name,
            'ticker': stock.ticker,
            'quantity': t.quantity,
            'price': t.price,
            'commission': t.commission,
            'total': t.total
        })

    return render_template('transactions.html',
                           portfolio=portfolio,
                           transactions=transactions_data)


@app.route('/refresh/<int:portfolio_id>')
@login_required
def refresh_prices(portfolio_id):
    """Принудительно обновляет кэш цен"""
    portfolio = Portfolio.query.get_or_404(portfolio_id)

    if portfolio.user_id != current_user.id:
        flash('Доступ запрещен', 'error')
        return redirect(url_for('portfolios'))

    # Очищаем кэш для всех бумаг этого портфеля
    from market.price_cache import _cache, _cache_time

    transactions = Transaction.query.filter_by(portfolio_id=portfolio_id).all()
    for t in transactions:
        stock = Stock.query.get(t.stock_id)
        if stock.ticker in _cache:
            del _cache[stock.ticker]
            del _cache_time[stock.ticker]

    flash('Кэш цен очищен', 'success')
    return redirect(url_for('index', portfolio_id=portfolio_id))


@app.route('/api/search_tickers')
def search_tickers():
    """Поиск тикеров через API Мосбиржи"""
    query = request.args.get('q', '').strip().upper()
    if len(query) < 2:
        return jsonify([])

    results = []

    # 1. Сначала ищем через API Мосбиржи
    try:
        import requests
        url = "https://iss.moex.com/iss/securities.json"
        params = {
            'q': query,
            'iss.meta': 'off',
            'iss.only': 'securities',
            'securities.columns': 'secid,shortname,isin,emitent_title'
        }

        response = requests.get(url, params=params, timeout=3)
        data = response.json()

        securities = data.get('securities', {}).get('data', [])

        for sec in securities[:15]:  # берем 15 результатов
            ticker = sec[0]
            name = sec[1]
            emitent = sec[3] if len(sec) > 3 else ''

            # Формируем понятное название
            display_name = name
            if emitent and emitent not in name:
                display_name = f"{name} - {emitent}"

            results.append({
                'ticker': ticker,
                'name': display_name,
                'short_name': name
            })

            # Сохраняем в базу для будущих поисков
            try:
                from database.db import Stock, db
                stock = Stock.query.filter_by(ticker=ticker).first()
                if not stock:
                    stock = Stock(
                        ticker=ticker,
                        name=name,
                        isin=sec[2] if len(sec) > 2 else None,
                        currency='RUB'
                    )
                    db.session.add(stock)
                    db.session.commit()
            except:
                pass

    except Exception as e:
        print(f"Ошибка API: {e}")

    # 2. Если API не дал результатов, ищем в локальной базе
    if len(results) < 3:
        try:
            from database.db import Stock
            stocks = Stock.query.filter(
                (Stock.ticker.contains(query)) |
                (Stock.name.contains(query))
            ).limit(10).all()

            for s in stocks:
                # Проверяем, нет ли уже такого тикера в результатах
                if not any(r['ticker'] == s.ticker for r in results):
                    results.append({
                        'ticker': s.ticker,
                        'name': s.name,
                        'short_name': s.name
                    })
        except:
            pass

    # Убираем дубликаты по тикеру
    seen = set()
    unique_results = []
    for r in results:
        if r['ticker'] not in seen:
            seen.add(r['ticker'])
            unique_results.append(r)

    return jsonify(unique_results[:15])


@app.route('/update_dividends/<int:portfolio_id>')
@login_required
def update_dividends(portfolio_id):
    """Автоматически обновляет дивиденды для портфеля"""
    portfolio = Portfolio.query.get_or_404(portfolio_id)

    if portfolio.user_id != current_user.id:
        flash('Доступ запрещен', 'error')
        return redirect(url_for('portfolios'))

    from market.dividends_client import fetch_dividends_history

    # Получаем все бумаги в портфеле
    stocks = db.session.query(Stock).join(Transaction).filter(
        Transaction.portfolio_id == portfolio_id
    ).distinct().all()

    print(f"\n🔍 Найдено бумаг в портфеле: {len(stocks)}")

    for stock in stocks:
        print(f"\n📊 Проверяем {stock.ticker} - {stock.name}")

        # Получаем историю дивидендов с биржи
        div_history = fetch_dividends_history(stock.ticker)
        print(f"  Получено дивидендов из API: {len(div_history)}")

        for div_data in div_history:
            print(f"\n  --- Дивиденд ---")
            print(f"    Дата отсечки: {div_data['record_date']}")
            print(f"    Сумма на акцию: {div_data['value']}")
            print(f"    Валюта: {div_data['currency']}")

            if not div_data['record_date']:
                print("    ❌ Нет даты - пропускаем")
                continue

            # Проверяем, есть ли уже такой дивиденд
            existing = Dividend.query.filter_by(
                stock_id=stock.id,
                record_date=div_data['record_date']
            ).first()

            if existing:
                print(f"    ⏩ Уже есть в базе ID: {existing.id}")
                continue

            # Считаем количество акций на дату отсечки
            quantity_query = db.session.query(db.func.sum(Transaction.quantity)).filter(
                Transaction.portfolio_id == portfolio_id,
                Transaction.stock_id == stock.id,
                Transaction.date <= div_data['record_date']
            )
            total_quantity = quantity_query.scalar() or 0
            print(f"    Акций на дату отсечки: {total_quantity}")

            if total_quantity == 0:
                # Если нет на дату - берем текущее количество
                current_quantity = db.session.query(db.func.sum(Transaction.quantity)).filter(
                    Transaction.portfolio_id == portfolio_id,
                    Transaction.stock_id == stock.id
                ).scalar() or 0
                print(f"    Текущее количество акций: {current_quantity}")

                if current_quantity == 0:
                    print("    ❌ Нет акций вообще - пропускаем")
                    continue
                total_quantity = current_quantity

            total_amount = total_quantity * div_data['value']
            tax = total_amount * 0.13

            # Дата выплаты (обычно через месяц)
            payment_date = div_data['record_date'] + timedelta(days=30)
            if payment_date.month > 12:
                payment_date = payment_date.replace(year=payment_date.year + 1, month=1)

            print(f"    Всего сумма до налога: {total_amount}")
            print(f"    Налог: {tax}")
            print(f"    После налога: {total_amount - tax}")
            print(f"    Дата выплаты: {payment_date}")

            dividend = Dividend(
                date=payment_date,
                record_date=div_data['record_date'],
                portfolio_id=portfolio_id,
                stock_id=stock.id,
                amount_per_share=div_data['value'],
                total_amount=total_amount - tax,
                tax=tax,
                currency=div_data['currency']
            )

            db.session.add(dividend)
            db.session.commit()
            print(f"    ✅ ДОБАВЛЕНО!")

            # Проверяем сразу что добавилось
            check = Dividend.query.filter_by(
                stock_id=stock.id,
                record_date=div_data['record_date']
            ).first()
            if check:
                print(f"    ✅ Проверка: дивиденд ID {check.id} в базе")

    return redirect(url_for('dividends_list', portfolio_id=portfolio_id))


@app.route('/dividends/<int:portfolio_id>')
@login_required
def dividends_list(portfolio_id):
    """Список дивидендов портфеля"""
    portfolio = Portfolio.query.get_or_404(portfolio_id)

    if portfolio.user_id != current_user.id:
        flash('Доступ запрещен', 'error')
        return redirect(url_for('portfolios'))

    dividends = Dividend.query.filter_by(portfolio_id=portfolio_id) \
        .order_by(Dividend.date.desc()).all()

    return render_template('dividends.html', portfolio=portfolio, dividends=dividends)


@app.route('/dividend_forecast/<int:portfolio_id>')
@login_required
def dividend_forecast(portfolio_id):
    """Прогноз дивидендов по портфелю"""
    portfolio = Portfolio.query.get_or_404(portfolio_id)

    if portfolio.user_id != current_user.id:
        flash('Доступ запрещен', 'error')
        return redirect(url_for('portfolios'))

    from market.dividends_client import fetch_dividends_history, predict_next_dividend

    # Получаем все бумаги в портфеле
    stocks = db.session.query(Stock).join(Transaction).filter(
        Transaction.portfolio_id == portfolio_id
    ).distinct().all()

    forecasts = []
    total_expected = 0

    for stock in stocks:
        if not stock.ticker:
            continue

        # Получаем историю с биржи
        history = fetch_dividends_history(stock.ticker)

        if not history:
            continue

        # Прогнозируем следующий
        next_date, next_amount = predict_next_dividend(stock.ticker, history)

        if next_date and next_amount:
            # Считаем текущее количество акций
            total_quantity = db.session.query(db.func.sum(Transaction.quantity)).filter(
                Transaction.portfolio_id == portfolio_id,
                Transaction.stock_id == stock.id
            ).scalar() or 0

            expected_total = total_quantity * next_amount
            total_expected += expected_total

            forecasts.append({
                'stock': stock,
                'next_date': next_date,
                'amount_per_share': next_amount,
                'total_quantity': total_quantity,
                'expected_total': expected_total,
                'history_count': len(history)
            })

    # Сортируем по дате
    forecasts.sort(key=lambda x: x['next_date'])

    return render_template('forecast.html',
                           portfolio=portfolio,
                           forecasts=forecasts,
                           total_expected=total_expected)


@app.route('/api/portfolio_history/<int:portfolio_id>')
@login_required
def portfolio_history(portfolio_id):
    """История стоимости портфеля с возможностью выбора периода"""
    portfolio = Portfolio.query.get_or_404(portfolio_id)

    if portfolio.user_id != current_user.id:
        return jsonify({'error': 'Доступ запрещен'}), 403

    # Параметры периода
    period = request.args.get('period', 'all')
    from_date = request.args.get('from')
    to_date = request.args.get('to')

    # Базовый запрос
    query = Transaction.query.filter_by(portfolio_id=portfolio_id)

    # Применяем фильтры по дате
    if from_date:
        query = query.filter(Transaction.date >= datetime.datetime.strptime(from_date, '%Y-%m-%d'))
    if to_date:
        query = query.filter(Transaction.date <= datetime.datetime.strptime(to_date, '%Y-%m-%d'))

    transactions = query.order_by(Transaction.date).all()

    # Если нет транзакций за период
    if not transactions:
        return jsonify({'dates': [], 'values': []})

    # Группируем по дням/месяцам
    from collections import defaultdict
    import calendar

    if period == 'month':
        # По дням
        timeline = defaultdict(float)
        for t in transactions:
            day_key = t.date.strftime('%Y-%m-%d')
            timeline[day_key] += t.total
    else:
        # По месяцам
        timeline = defaultdict(float)
        for t in transactions:
            month_key = t.date.strftime('%Y-%m')
            timeline[month_key] += t.total

    dates = []
    values = []
    cumulative = 0

    for key in sorted(timeline.keys()):
        dates.append(key)
        cumulative += timeline[key]
        values.append(round(cumulative, 2))

    return jsonify({'dates': dates, 'values': values})


@app.route('/api/dividends_by_year/<int:portfolio_id>')
@login_required
def dividends_by_year(portfolio_id):
    """Дивиденды по годам с фильтром по дате"""
    portfolio = Portfolio.query.get_or_404(portfolio_id)

    if portfolio.user_id != current_user.id:
        return jsonify({'error': 'Доступ запрещен'}), 403

    # Получаем параметры дат
    from_date = request.args.get('from')
    to_date = request.args.get('to')

    # Базовый запрос
    query = Dividend.query.filter_by(portfolio_id=portfolio_id)

    # Применяем фильтры по дате
    if from_date:
        query = query.filter(Transaction.date >= datetime.datetime.strptime(from_date, '%Y-%m-%d'))
    if to_date:
        query = query.filter(Transaction.date <= datetime.datetime.strptime(to_date, '%Y-%m-%d'))

    dividends = query.all()

    # Группируем по годам
    from collections import defaultdict
    yearly = defaultdict(float)

    for d in dividends:
        year = d.date.year
        yearly[year] += d.total_amount

    years = sorted(yearly.keys())
    values = [round(yearly[y], 2) for y in years]

    return jsonify({'years': years, 'values': values})


@app.route('/api/sectors/<int:portfolio_id>')
@login_required
def sectors_distribution(portfolio_id):
    """Распределение по отраслям"""
    portfolio = Portfolio.query.get_or_404(portfolio_id)

    if portfolio.user_id != current_user.id:
        return jsonify({'error': 'Доступ запрещен'}), 403

    # Сектора по бумагам (можно расширить)
    sector_map = {
        'SBER': 'Банки',
        'VTBR': 'Банки',
        'AFLT': 'Транспорт',
        'MTSS': 'Телеком',
        'RTKMP': 'Телеком',
        'SIBN': 'Нефть',
        'ROSN': 'Нефть',
        'SNGSP': 'Нефть',
        'TRNFP': 'Нефть',
        'CHMF': 'Металлы',
        'MOEX': 'Финансы'
    }

    # Считаем стоимость по секторам
    from market.price_cache import get_cached_price

    stocks = db.session.query(Stock).join(Transaction).filter(
        Transaction.portfolio_id == portfolio_id
    ).distinct().all()

    sectors = defaultdict(float)

    for stock in stocks:
        sector = sector_map.get(stock.ticker, 'Другое')

        quantity = db.session.query(db.func.sum(Transaction.quantity)).filter(
            Transaction.portfolio_id == portfolio_id,
            Transaction.stock_id == stock.id
        ).scalar() or 0

        if quantity > 0:
            price = get_cached_price(stock.ticker) or 0
            sectors[sector] += quantity * price

    labels = list(sectors.keys())
    values = list(sectors.values())

    return jsonify({'labels': labels, 'values': values})


@app.route('/api/profit_by_stock/<int:portfolio_id>')
@login_required
def profit_by_stock(portfolio_id):
    """Прибыль по каждой бумаге"""
    portfolio = Portfolio.query.get_or_404(portfolio_id)

    if portfolio.user_id != current_user.id:
        return jsonify({'error': 'Доступ запрещен'}), 403

    from market.price_cache import get_cached_price

    stocks = db.session.query(Stock).join(Transaction).filter(
        Transaction.portfolio_id == portfolio_id
    ).distinct().all()

    labels = []
    values = []

    for stock in stocks:
        transactions = Transaction.query.filter_by(
            portfolio_id=portfolio_id,
            stock_id=stock.id
        ).all()

        total_spent = sum(t.total for t in transactions)
        total_quantity = sum(t.quantity for t in transactions)

        if total_quantity > 0:
            current_price = get_cached_price(stock.ticker) or 0
            current_value = total_quantity * current_price
            profit = current_value - total_spent

            labels.append(stock.name)
            values.append(profit)

    return jsonify({'labels': labels, 'values': values})


@app.route('/charts/<int:portfolio_id>')
@login_required
def charts(portfolio_id):
    """Страница с графиками"""
    portfolio = Portfolio.query.get_or_404(portfolio_id)

    if portfolio.user_id != current_user.id:
        flash('Доступ запрещен', 'error')
        return redirect(url_for('portfolios'))

    chart_type = request.args.get('type', 'portfolio')

    return render_template('charts.html', portfolio=portfolio, chart_type=chart_type)

# Создаем таблицы в базе
with app.app_context():
    db.create_all()
    print("✅ Таблицы пользователей созданы")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)