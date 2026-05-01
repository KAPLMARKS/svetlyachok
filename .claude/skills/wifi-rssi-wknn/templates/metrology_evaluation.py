"""
Шаблон метрологической оценки классификаторов по ISO/IEC 18305:2016.

Используется для генерации таблиц и графиков для дипломной работы.
Вычисляет: Detection Probability per zone, confusion matrix, RMSE, computational time.

Принципы:
- Все эксперименты сохраняются в JSON для воспроизводимости
- Каждая метрика помечена timestamp + git commit
- Классификаторы сравниваются на ОДНОМ И ТОМ ЖЕ test-сете
"""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.metrics import confusion_matrix


@dataclass
class ExperimentResult:
    """Результат одного эксперимента — для сохранения в JSON."""

    experiment_id: str
    classifier: str  # "wknn" | "random_forest"
    hyperparameters: dict[str, Any]
    calibration_set_size: int
    test_set_size: int
    n_features: int
    classes: list[str]
    detection_probability_per_zone: dict[str, float]
    confusion_matrix: list[list[int]]
    rmse_meters: float | None = None
    training_time_s: float = 0.0
    inference_time_ms_mean: float = 0.0
    inference_time_ms_p95: float = 0.0
    inference_time_ms_p99: float = 0.0
    git_commit: str = ""
    sklearn_version: str = ""
    python_version: str = ""
    random_seed: int = 42
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def detection_probability_per_zone(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    classes: list[str],
) -> dict[str, float]:
    """
    Вычисляет Detection Probability для каждой зоны.

    DetectionProbability(zone) = TP_zone / (TP_zone + FN_zone)
                              = (правильно_предсказали_зону) / (всего_было_зоны_в_test)
    """
    result: dict[str, float] = {}
    for zone in classes:
        true_positive = int(np.sum((y_true == zone) & (y_pred == zone)))
        actual_total = int(np.sum(y_true == zone))
        if actual_total == 0:
            result[zone] = float("nan")  # не было примеров этой зоны в test-сете
        else:
            result[zone] = round(true_positive / actual_total, 4)
    return result


def measure_inference_time(
    classifier: Any,
    test_observations: list,
    n_warmup: int = 5,
) -> tuple[float, float, float]:
    """
    Измеряет среднее, p95, p99 время инференса в миллисекундах.

    Args:
        classifier: объект с методом `.classify(observation)`.
        test_observations: список наблюдений для замеров.
        n_warmup: число первых вызовов, исключаемых из статистики (JIT/warmup).

    Returns:
        (mean_ms, p95_ms, p99_ms)
    """
    if len(test_observations) <= n_warmup:
        raise ValueError("test set is too small for reliable timing")

    timings: list[float] = []
    for i, obs in enumerate(test_observations):
        t0 = time.perf_counter()
        classifier.classify(obs)
        t1 = time.perf_counter()
        if i >= n_warmup:  # exclude warmup
            timings.append((t1 - t0) * 1000.0)

    arr = np.array(timings)
    return (
        round(float(arr.mean()), 3),
        round(float(np.percentile(arr, 95)), 3),
        round(float(np.percentile(arr, 99)), 3),
    )


def evaluate_classifier(
    classifier: Any,
    calibration_fingerprints: list,
    test_fingerprints: list,
    test_observations: list,
    test_y_true: np.ndarray,
    *,
    classifier_name: str,
    hyperparameters: dict[str, Any],
    output_dir: str | Path = "ml-artifacts",
) -> ExperimentResult:
    """
    Полный цикл оценки одного классификатора.

    1. Тренировка с замером времени.
    2. Batch-инференс на test-сете.
    3. Расчёт Detection Probability per zone.
    4. Confusion matrix.
    5. Замер inference time.
    6. Сохранение результата в JSON.

    Args:
        classifier: объект с методами `.fit(calibration)` и `.predict_batch(observations)`.
        calibration_fingerprints: тренировочный набор Fingerprint.
        test_fingerprints: тестовый набор Fingerprint (для контекста).
        test_observations: тестовые RSSIVector (для inference timing).
        test_y_true: numpy-массив истинных меток зон.
        classifier_name: "wknn" или "random_forest".
        hyperparameters: дикт гиперпараметров для журнала.
        output_dir: директория для сохранения JSON.

    Returns:
        ExperimentResult с полным набором метрик.
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # 1. Тренировка
    t0 = time.perf_counter()
    classifier.fit(calibration_fingerprints)
    training_time_s = round(time.perf_counter() - t0, 3)

    # 2. Batch-инференс
    predictions = classifier.predict_batch(test_observations)
    y_pred = np.array([p["zone"] for p in predictions])

    # 3. Detection Probability per zone
    classes = sorted(set(test_y_true.tolist()))
    dp_per_zone = detection_probability_per_zone(test_y_true, y_pred, classes)

    # 4. Confusion matrix
    cm = confusion_matrix(test_y_true, y_pred, labels=classes)

    # 5. Inference time per single classify
    mean_ms, p95_ms, p99_ms = measure_inference_time(classifier, test_observations[:200])

    # 6. Сборка результата
    timestamp_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    experiment_id = f"{classifier_name}_{timestamp_str}"

    result = ExperimentResult(
        experiment_id=experiment_id,
        classifier=classifier_name,
        hyperparameters=hyperparameters,
        calibration_set_size=len(calibration_fingerprints),
        test_set_size=len(test_fingerprints),
        n_features=len(getattr(classifier, "_bssid_index", []) or []),
        classes=classes,
        detection_probability_per_zone=dp_per_zone,
        confusion_matrix=cm.tolist(),
        training_time_s=training_time_s,
        inference_time_ms_mean=mean_ms,
        inference_time_ms_p95=p95_ms,
        inference_time_ms_p99=p99_ms,
        git_commit=_get_git_commit(),
        sklearn_version=_get_sklearn_version(),
        python_version=_get_python_version(),
    )

    # 7. Сохранение
    output_file = output_path / f"experiment_{experiment_id}.json"
    output_file.write_text(
        json.dumps(asdict(result), indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    return result


def compare_classifiers(
    results: list[ExperimentResult],
    output_dir: str | Path = "ml-artifacts",
) -> Path:
    """
    Сводный отчёт по нескольким экспериментам — для раздела сравнения в дипломе.

    Возвращает путь к Markdown-таблице.
    """
    if not results:
        raise ValueError("results is empty")

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Заголовок: классификаторы → столбцы
    classes = sorted(set(c for r in results for c in r.classes))
    lines = [
        "# Сравнение классификаторов",
        "",
        "## Detection Probability per zone",
        "",
        "| Зона | " + " | ".join(r.classifier for r in results) + " |",
        "|------|" + "|".join(["---"] * len(results)) + "|",
    ]
    for zone in classes:
        row = [zone]
        for r in results:
            v = r.detection_probability_per_zone.get(zone, float("nan"))
            row.append(f"{v:.2%}" if not np.isnan(v) else "—")
        lines.append("| " + " | ".join(row) + " |")

    lines.extend([
        "",
        "## Производительность",
        "",
        "| Классификатор | Training (s) | Inference mean (ms) | p95 (ms) | p99 (ms) |",
        "|---------------|--------------|---------------------|----------|----------|",
    ])
    for r in results:
        lines.append(
            f"| {r.classifier} | {r.training_time_s} | "
            f"{r.inference_time_ms_mean} | {r.inference_time_ms_p95} | "
            f"{r.inference_time_ms_p99} |"
        )

    output_file = output_path / "comparison.md"
    output_file.write_text("\n".join(lines), encoding="utf-8")
    return output_file


def _get_git_commit() -> str:
    """Текущий git commit hash для journal."""
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def _get_sklearn_version() -> str:
    try:
        import sklearn

        return sklearn.__version__
    except ImportError:
        return "unknown"


def _get_python_version() -> str:
    import sys

    return sys.version.split()[0]
