"""Вспомогательные функции: работа с JSON-хранилищем и путями."""

from __future__ import annotations

import json
from pathlib import Path

# Корень проекта: .../final_project
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = PROJECT_ROOT / "data"

USERS_FILE = DATA_DIR / "users.json"
PORTFOLIOS_FILE = DATA_DIR / "portfolios.json"
RATES_FILE = DATA_DIR / "rates.json"


def ensure_data_dir() -> None:
    """Создаёт папку data/, если её ещё нет."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_json(path: Path, default):
    """Загружает JSON из файла. Если файла нет — возвращает default."""
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


def save_json(path: Path, data) -> None:
    """Сохраняет данные в JSON-файл (с отступами и без ASCII-эскейпов)."""
    ensure_data_dir()
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# --- users ---

def load_users() -> list[dict]:
    return load_json(USERS_FILE, [])


def save_users(users: list[dict]) -> None:
    save_json(USERS_FILE, users)


# --- portfolios ---

def load_portfolios() -> list[dict]:
    return load_json(PORTFOLIOS_FILE, [])


def save_portfolios(portfolios: list[dict]) -> None:
    save_json(PORTFOLIOS_FILE, portfolios)


# --- rates ---

def load_rates() -> dict:
    """Курсы валют. По умолчанию — фиксированные значения-заглушки."""
    default = {
        "EUR_USD": {"rate": 1.0786, "updated_at": "2025-10-09T10:30:00"},
        "BTC_USD": {"rate": 59337.21, "updated_at": "2025-10-09T10:29:42"},
        "RUB_USD": {"rate": 0.01016, "updated_at": "2025-10-09T10:31:12"},
        "ETH_USD": {"rate": 3720.00, "updated_at": "2025-10-09T10:35:00"},
        "source": "stub",
        "last_refresh": "2025-10-09T10:35:00",
    }
    return load_json(RATES_FILE, default)


def save_rates(rates: dict) -> None:
    save_json(RATES_FILE, rates)