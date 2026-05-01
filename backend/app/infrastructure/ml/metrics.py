"""Метрики качества классификатора по ISO/IEC 18305:2016.

**Detection Probability (DP)** — основная метрика для зонной
классификации: доля правильно классифицированных observations.
Считаем overall (по всему test set'у) и per-zone (отдельно для
каждой зоны — для confusion-анализа).

**Confusion matrix** — обязательная визуализация в дипломе.
Хранится как `dict[(predicted, true), count]` — компактнее, чем
квадратная матрица, особенно при разреженных ошибках.

В отличие от RMSE, который применим к координатной локализации,
DP — естественная метрика для классификации в дискретный набор зон.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from app.core.logging import get_logger
from app.domain.positioning.classifiers import PositionClassifier
from app.domain.radiomap.value_objects import RSSIVector

log = get_logger(__name__)


@dataclass(frozen=True)
class ClassificationMetrics:
    """Результат прогона классификатора на тест-сете.

    Поля:
    - `total_samples`: общее количество observation'ов в тесте
    - `correct`: число правильно классифицированных
    - `detection_probability`: `correct / total_samples`, в [0.0, 1.0]
    - `per_zone_detection_probability`: `{zone_id: dp}` —
      DP считается отдельно для каждой зоны как
      `correct_in_zone / total_in_zone`
    - `confusion_matrix`: `{(predicted_zone_id, true_zone_id): count}` —
      позволяет построить визуализацию ошибок в дипломе
    """

    total_samples: int
    correct: int
    detection_probability: float
    per_zone_detection_probability: dict[int, float] = field(default_factory=dict)
    confusion_matrix: dict[tuple[int, int], int] = field(default_factory=dict)


def evaluate_classifier(
    classifier: PositionClassifier,
    test_set: list[tuple[RSSIVector, int]],
) -> ClassificationMetrics:
    """Прогоняет classifier по test_set и вычисляет метрики.

    `test_set` — список пар `(observation, true_zone_id)`.
    Classifier обязан быть обучен (`is_trained() == True`).

    Возвращает `ClassificationMetrics` с overall DP, per-zone DP
    и confusion matrix.
    """
    log.info(
        "[ml.metrics.evaluate_classifier] start", test_size=len(test_set)
    )

    if not test_set:
        return ClassificationMetrics(
            total_samples=0,
            correct=0,
            detection_probability=0.0,
        )

    correct = 0
    confusion: dict[tuple[int, int], int] = defaultdict(int)
    per_zone_total: dict[int, int] = defaultdict(int)
    per_zone_correct: dict[int, int] = defaultdict(int)

    for observation, true_zone_id in test_set:
        result = classifier.classify(observation)
        predicted = result.zone_id

        per_zone_total[true_zone_id] += 1
        confusion[(predicted, true_zone_id)] += 1

        if predicted == true_zone_id:
            correct += 1
            per_zone_correct[true_zone_id] += 1

    total = len(test_set)
    overall_dp = correct / total
    per_zone_dp: dict[int, float] = {}
    for zid, total_in_zone in per_zone_total.items():
        per_zone_dp[zid] = (
            per_zone_correct.get(zid, 0) / total_in_zone if total_in_zone > 0 else 0.0
        )

    log.info(
        "[ml.metrics.evaluate_classifier] done",
        total_samples=total,
        correct=correct,
        detection_probability=round(overall_dp, 4),
    )
    return ClassificationMetrics(
        total_samples=total,
        correct=correct,
        detection_probability=overall_dp,
        per_zone_detection_probability=dict(per_zone_dp),
        confusion_matrix=dict(confusion),
    )


def format_confusion_matrix(
    metrics: ClassificationMetrics,
    zone_names: dict[int, str] | None = None,
) -> str:
    """Форматирует confusion matrix как читаемую таблицу.

    `zone_names` — опциональный маппинг `zone_id → отображаемое имя`
    (например, имя зоны или ZoneType.value). Без него выводятся id.

    Используется в логах метрологических тестов и в выводе для
    диссертации.
    """
    if not metrics.confusion_matrix:
        return "Confusion matrix is empty (no classifications performed)."

    # Все уникальные zone_id из confusion (предсказанные + истинные).
    all_zones: set[int] = set()
    for predicted, true_id in metrics.confusion_matrix:
        all_zones.add(predicted)
        all_zones.add(true_id)
    sorted_zones = sorted(all_zones)
    names = zone_names or {zid: str(zid) for zid in sorted_zones}

    # Заголовок: "predicted → true" по строкам / столбцам.
    col_width = max(8, max(len(names.get(zid, str(zid))) for zid in sorted_zones) + 2)
    header_cells = [f"{'pred\\true':<{col_width}}"]
    header_cells.extend(f"{names.get(zid, str(zid)):>{col_width}}" for zid in sorted_zones)
    lines = [" ".join(header_cells)]

    for predicted in sorted_zones:
        row_cells = [f"{names.get(predicted, str(predicted)):<{col_width}}"]
        for true_id in sorted_zones:
            count = metrics.confusion_matrix.get((predicted, true_id), 0)
            row_cells.append(f"{count:>{col_width}}")
        lines.append(" ".join(row_cells))

    summary = (
        f"\nOverall DP: {metrics.detection_probability:.4f} "
        f"({metrics.correct}/{metrics.total_samples})"
    )
    if metrics.per_zone_detection_probability:
        per_zone = ", ".join(
            f"{names.get(zid, str(zid))}={dp:.3f}"
            for zid, dp in sorted(metrics.per_zone_detection_probability.items())
        )
        summary += f"\nPer-zone DP: {per_zone}"

    return "\n".join(lines) + summary
