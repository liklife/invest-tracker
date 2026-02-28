from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    portfolios = db.relationship('Portfolio', backref='owner', lazy=True)


class Portfolio(db.Model):
    __tablename__ = 'portfolios'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    currency = db.Column(db.String(10), default='RUB')
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    transactions = db.relationship('Transaction', backref='portfolio', lazy=True)


class Stock(db.Model):
    __tablename__ = 'stocks'

    id = db.Column(db.Integer, primary_key=True)
    ticker = db.Column(db.String(20))
    name = db.Column(db.String(200))
    isin = db.Column(db.String(50), unique=True)
    emitent = db.Column(db.String(200))
    sector = db.Column(db.String(100))
    currency = db.Column(db.String(10), default='RUB')

    transactions = db.relationship('Transaction', backref='stock', lazy=True)


class Transaction(db.Model):
    __tablename__ = 'transactions'

    id = db.Column(db.Integer, primary_key=True)
    portfolio_id = db.Column(db.Integer, db.ForeignKey('portfolios.id'), nullable=False)
    stock_id = db.Column(db.Integer, db.ForeignKey('stocks.id'), nullable=False)
    date = db.Column(db.DateTime, nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    price = db.Column(db.Float, nullable=False)
    commission = db.Column(db.Float, default=0)
    total = db.Column(db.Float, nullable=False)


class Dividend(db.Model):
    __tablename__ = 'dividends'

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, nullable=False)  # дата выплаты
    record_date = db.Column(db.DateTime)  # дата отсечки
    portfolio_id = db.Column(db.Integer, db.ForeignKey('portfolios.id'), nullable=False)
    stock_id = db.Column(db.Integer, db.ForeignKey('stocks.id'), nullable=False)
    amount_per_share = db.Column(db.Float, nullable=False)  # на одну акцию
    total_amount = db.Column(db.Float, nullable=False)  # всего денег
    tax = db.Column(db.Float, default=0)  # налог
    currency = db.Column(db.String(10), default='RUB')

    portfolio = db.relationship('Portfolio', backref='dividends')
    stock = db.relationship('Stock', backref='dividends')