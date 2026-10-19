"""Бизнес-логика платформы: регистрация, логин, портфель, покупка/продажа, курсы."""

from __future__ import annotations

from datetime import datetime, timedelta

from valutatrade_hub.core import utils
from valutatrade_hub.core.models import Portfolio, User

# Текущий залогиненный пользователь (сессия в рамках процесса CLI)
_current_user: User | None = None

# Курс считается свежим, если обновлён не позже этого интервала
RATE_TTL = timedelta(minutes=5)


# --- сессия ---

def get_current_user() -> User | None:
    """Возвращает текущего залогиненного пользователя или None."""
    return _current_user


def _require_login() -> User:
    """Проверяет, что пользователь залогинен; иначе кидает ValueError."""
    if _current_user is None:
        raise ValueError("Сначала выполните login")
    return _current_user


def logout() -> None:
    """Завершает сессию."""
    global _current_user
    _current_user = None


# --- вспомогательное ---

def _next_user_id(users: list[dict]) -> int:
    """Возвращает следующий свободный user_id (автоинкремент)."""
    if not users:
        return 1
    return max(int(u["user_id"]) for u in users) + 1


def _find_user_record(users: list[dict], username: str) -> dict | None:
    for u in users:
        if u["username"] == username:
            return u
    return None


def _load_portfolio_for(user_id: int) -> Portfolio:
    """Загружает портфель пользователя из portfolios.json (или пустой)."""
    records = utils.load_portfolios()
    for rec in records:
        if int(rec["user_id"]) == user_id:
            return Portfolio.from_dict(rec)
    return Portfolio(user_id=user_id)


def _save_portfolio(portfolio: Portfolio) -> None:
    """Сохраняет портфель, заменяя запись с тем же user_id."""
    records = utils.load_portfolios()
    new_rec = portfolio.to_dict()
    for i, rec in enumerate(records):
        if int(rec["user_id"]) == portfolio.user_id:
            records[i] = new_rec
            break
    else:
        records.append(new_rec)
    utils.save_portfolios(records)


def _normalize_currency(code: str) -> str:
    if not isinstance(code, str) or not code.strip():
        raise ValueError("Код валюты не может быть пустым")
    return code.strip().upper()


def _validate_amount(amount: float) -> float:
    if not isinstance(amount, (int, float)) or isinstance(amount, bool):
        raise TypeError("'amount' должен быть числом")
    if amount <= 0:
        raise ValueError("'amount' должен быть положительным числом")
    return float(amount)


def _ensure_wallet(portfolio: Portfolio, code: str):
    """Возвращает кошелёк, создавая его при необходимости."""
    wallet = portfolio.get_wallet(code)
    if wallet is None:
        wallet = portfolio.add_currency(code)
    return wallet


# --- регистрация и логин ---

def register(username: str, password: str) -> dict:
    """Создаёт нового пользователя и пустой портфель."""
    users = utils.load_users()
    if not isinstance(username, str) or not username.strip():
        raise ValueError("Имя пользователя не может быть пустым")
    username = username.strip()
    if _find_user_record(users, username) is not None:
        raise ValueError(f"Имя пользователя '{username}' уже занято")

    user_id = _next_user_id(users)
    user = User.create(user_id=user_id, username=username, password=password)
    users.append(user.to_dict())
    utils.save_users(users)

    _save_portfolio(Portfolio(user_id=user_id))
    return {"user_id": user_id, "username": username}


def login(username: str, password: str) -> dict:
    """Логинит пользователя, сохраняя его в сессии."""
    global _current_user
    users = utils.load_users()
    name = username.strip() if isinstance(username, str) else ""
    record = _find_user_record(users, name)
    if record is None:
        raise ValueError(f"Пользователь '{username}' не найден")
    user = User.from_dict(record)
    if not user.verify_password(password):
        raise ValueError("Неверный пароль")
    _current_user = user
    return user.get_user_info()


# --- портфель ---

def show_portfolio(base: str = "USD") -> dict:
    """Возвращает данные о портфеле: список кошельков и итог в base."""
    user = _require_login()
    portfolio = _load_portfolio_for(user.user_id)
    portfolio.attach_user(user)
    base = _normalize_currency(base)

    rows = []
    for code, wallet in portfolio.wallets.items():
        if code == base:
            value = wallet.balance
        else:
            rate = get_rate(code, base)["rate"]
            value = wallet.balance * rate
        rows.append(
            {
                "currency": code,
                "balance": wallet.balance,
                "value_in_base": value,
            }
        )
    total = portfolio.get_total_value(base)
    return {
        "username": user.username,
        "base": base,
        "wallets": rows,
        "total": total,
    }


# --- покупка/продажа (через USD-кошелёк) ---

def _estimate_usd_amount(currency: str, amount: float) -> tuple[float, dict | None]:
    """Возвращает (сумма в USD, информация о курсе или None для USD)."""
    if currency == "USD":
        return amount, None
    rate_info = get_rate(currency, "USD")
    return amount * rate_info["rate"], rate_info


def buy(currency: str, amount: float) -> dict:
    """Покупает валюту: списывает USD и увеличивает баланс кошелька."""
    user = _require_login()
    code = _normalize_currency(currency)
    amount = _validate_amount(amount)

    portfolio = _load_portfolio_for(user.user_id)

    usd_cost, rate_info = _estimate_usd_amount(code, amount)
    if code != "USD":
        # Списываем USD со счёта
        usd_wallet = _ensure_wallet(portfolio, "USD")
        usd_before = usd_wallet.balance
        if usd_cost > usd_before:
            raise ValueError(
                f"Недостаточно средств: доступно {usd_before:.2f} USD, "
                f"требуется {usd_cost:.2f} USD"
            )
        usd_wallet.withdraw(usd_cost)
    else:
        usd_wallet = portfolio.get_wallet("USD")
        usd_before = usd_wallet.balance if usd_wallet else 0.0

    target_wallet = _ensure_wallet(portfolio, code)
    before = target_wallet.balance
    target_wallet.deposit(amount)
    _save_portfolio(portfolio)

    return {
        "currency": code,
        "amount": amount,
        "before": before,
        "after": target_wallet.balance,
        "rate": rate_info["rate"] if rate_info else None,
        "estimated_usd": usd_cost,
        "usd_before": usd_before,
        "usd_after": (
            portfolio.get_wallet("USD").balance
            if portfolio.get_wallet("USD")
            else 0.0
        ),
    }


def sell(currency: str, amount: float) -> dict:
    """Продаёт валюту: уменьшает баланс кошелька и начисляет USD."""
    user = _require_login()
    code = _normalize_currency(currency)
    amount = _validate_amount(amount)

    portfolio = _load_portfolio_for(user.user_id)
    wallet = portfolio.get_wallet(code)
    if wallet is None:
        raise ValueError(
            f"У вас нет кошелька '{code}'. "
            "Добавьте валюту: она создаётся автоматически при первой покупке."
        )

    proceeds_usd, rate_info = _estimate_usd_amount(code, amount)

    before = wallet.balance
    wallet.withdraw(amount)

    usd_before = 0.0
    if code != "USD":
        usd_wallet = _ensure_wallet(portfolio, "USD")
        usd_before = usd_wallet.balance
        usd_wallet.deposit(proceeds_usd)

    _save_portfolio(portfolio)

    return {
        "currency": code,
        "amount": amount,
        "before": before,
        "after": wallet.balance,
        "rate": rate_info["rate"] if rate_info else None,
        "estimated_usd": proceeds_usd,
        "usd_before": usd_before,
        "usd_after": (
            portfolio.get_wallet("USD").balance
            if portfolio.get_wallet("USD")
            else 0.0
        ),
    }


# --- курсы ---

def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def get_rate(from_currency: str, to_currency: str) -> dict:
    """Возвращает курс from→to из кеша rates.json и признак свежести."""
    src = _normalize_currency(from_currency)
    dst = _normalize_currency(to_currency)
    if src == dst:
        return {
            "rate": 1.0,
            "updated_at": None,
            "source": "identity",
            "fresh": True,
            "stale": False,
        }

    rates = utils.load_rates()
    direct_key = f"{src}_{dst}"
    inverse_key = f"{dst}_{src}"

    record = None
    rate = None
    if direct_key in rates and isinstance(rates[direct_key], dict):
        record = rates[direct_key]
        rate = float(record["rate"])
    elif inverse_key in rates and isinstance(rates[inverse_key], dict):
        record = rates[inverse_key]
        inverse = float(record["rate"])
        rate = 1.0 / inverse if inverse else 0.0

    if record is None or rate is None:
        raise ValueError(
            f"Курс {src}→{dst} недоступен. Повторите попытку позже."
        )

    updated_at = record.get("updated_at")
    updated_dt = _parse_iso(updated_at)
    fresh = True
    if updated_dt is not None:
        fresh = (datetime.now() - updated_dt) <= RATE_TTL

    return {
        "rate": rate,
        "updated_at": updated_at,
        "source": rates.get("source", "cache"),
        "fresh": fresh,
        "stale": not fresh,
    }