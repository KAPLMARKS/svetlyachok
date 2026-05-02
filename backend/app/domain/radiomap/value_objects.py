"""Доменные value objects модуля radiomap.

`BSSID` нормализует MAC-адрес и валидирует формат. `RSSIVector` —
неизменяемое отображение `BSSID → dBm` с физически реалистичным
диапазоном. Оба value object'а — frozen, hashable, value-based equality.

Domain не импортирует Pydantic/SQLAlchemy/FastAPI — pure-python+stdlib.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field

from app.domain.shared.exceptions import ValidationError

# Канонический формат: 6 пар hex-цифр через двоеточие, верхний регистр.
# Принимаем на вход любой регистр и оба разделителя `:` и `-` —
# нормализуем в конструкторе.
_BSSID_NORMALIZED_RE = re.compile(r"^[0-9A-F]{2}(:[0-9A-F]{2}){5}$")
_BSSID_INPUT_RE = re.compile(r"^[0-9A-Fa-f]{2}([:-][0-9A-Fa-f]{2}){5}$")

# Wi-Fi RSSI в реальном мире никогда не бывает положительным
# (приёмник не может получить больше, чем передатчик отдал) и редко
# опускается ниже -100 dBm (ниже — тепловой шум, сигнала нет).
# За пределами диапазона данные точно битые → отбрасываем.
_RSSI_MIN_DBM = -100
_RSSI_MAX_DBM = 0

# Реалистично в офисе видимо до нескольких десятков AP. 200 — щедрый
# верхний предел для защиты от DoS через гигантский JSON-payload.
_MAX_ACCESS_POINTS_PER_VECTOR = 200


@dataclass(frozen=True)
class BSSID:
    """MAC-адрес точки доступа в нормализованном виде `AA:BB:CC:DD:EE:FF`.

    Неизменяем после создания, hashable, безопасен как ключ в `dict`.
    """

    value: str

    def __init__(self, raw: str) -> None:
        if not isinstance(raw, str):
            raise ValidationError(
                code="invalid_bssid",
                message=f"BSSID должен быть строкой, получено {type(raw).__name__}",
            )
        if not _BSSID_INPUT_RE.match(raw):
            raise ValidationError(
                code="invalid_bssid",
                message=f"Неверный формат MAC-адреса: {raw!r}",
            )
        normalized = raw.upper().replace("-", ":")
        # Двойная проверка после нормализации (paranoid).
        if not _BSSID_NORMALIZED_RE.match(normalized):
            raise ValidationError(
                code="invalid_bssid",
                message=f"Неверный формат MAC-адреса после нормализации: {normalized!r}",
            )
        # frozen=True не позволяет обычное присваивание; используем
        # object.__setattr__ для инициализации.
        object.__setattr__(self, "value", normalized)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class RSSIVector:
    """Неизменяемое отображение `BSSID → dBm`.

    Используется как input для классификатора и как payload в `Fingerprint`.
    Сравнение и hash — по содержимому (через frozenset of items).
    """

    samples: Mapping[BSSID, int] = field(default_factory=dict)

    def __init__(self, samples: Mapping[str, int] | Mapping[BSSID, int]) -> None:
        if not isinstance(samples, Mapping):
            raise ValidationError(
                code="invalid_rssi_vector",
                message="rssi_vector должен быть отображением BSSID → dBm",
            )
        if len(samples) == 0:
            raise ValidationError(
                code="empty_rssi_vector",
                message="rssi_vector не может быть пустым (минимум 1 точка доступа)",
            )
        if len(samples) > _MAX_ACCESS_POINTS_PER_VECTOR:
            raise ValidationError(
                code="too_many_access_points",
                message=(
                    f"rssi_vector содержит {len(samples)} точек доступа, "
                    f"максимум разрешено {_MAX_ACCESS_POINTS_PER_VECTOR}"
                ),
            )

        normalized: dict[BSSID, int] = {}
        for raw_key, raw_value in samples.items():
            key = raw_key if isinstance(raw_key, BSSID) else BSSID(str(raw_key))
            if isinstance(raw_value, bool) or not isinstance(raw_value, int):
                # bool — подкласс int, но логически не RSSI.
                raise ValidationError(
                    code="invalid_rssi_value",
                    message=(
                        f"RSSI для {key} должен быть int, "
                        f"получено {type(raw_value).__name__}"
                    ),
                )
            if raw_value < _RSSI_MIN_DBM or raw_value > _RSSI_MAX_DBM:
                raise ValidationError(
                    code="rssi_out_of_range",
                    message=(
                        f"RSSI {raw_value} dBm для {key} вне допустимого диапазона "
                        f"[{_RSSI_MIN_DBM}, {_RSSI_MAX_DBM}]"
                    ),
                )
            normalized[key] = raw_value

        # Сохраняем как обычный dict (frozen-dataclass сам не даст
        # мутировать поле; от мутаций самого dict защищаемся API'ом).
        object.__setattr__(self, "samples", normalized)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, RSSIVector):
            return NotImplemented
        return dict(self.samples) == dict(other.samples)

    def __hash__(self) -> int:
        # frozenset of items даёт стабильный hash независимо от порядка
        # вставки в dict.
        return hash(frozenset(self.samples.items()))

    def bssids(self) -> set[BSSID]:
        """Множество BSSID отпечатка — для пересечений с другими векторами."""
        return set(self.samples.keys())

    def to_dict(self) -> dict[str, int]:
        """Сериализация в JSON-совместимый dict (BSSID → строка).

        Используется для записи в JSONB и в API-ответы.
        """
        return {bssid.value: dbm for bssid, dbm in self.samples.items()}

    def __len__(self) -> int:
        return len(self.samples)
