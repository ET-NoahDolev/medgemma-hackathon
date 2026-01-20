"""Evaluation metrics stubs."""

import re
from typing import Iterable, List


def _normalize_criterion_text(text: str) -> str:
    """Normalize criterion text for comparison.

    Normalizes by:
    - Converting to lowercase
    - Removing trailing punctuation
    - Normalizing whitespace

    Args:
        text: Criterion text to normalize.

    Returns:
        Normalized text string.

    Examples:
        >>> _normalize_criterion_text("Age >= 18.")
        'age >= 18'
        >>> _normalize_criterion_text("Age  >=  18")
        'age >= 18'
    """
    # Convert to lowercase
    normalized = text.lower()
    # Remove trailing punctuation (periods, commas, etc.)
    normalized = normalized.rstrip(".,;:!?")
    # Normalize whitespace (multiple spaces to single space)
    normalized = re.sub(r"\s+", " ", normalized)
    # Strip leading/trailing whitespace
    return normalized.strip()


def extraction_f1(predicted: List[str], gold: List[str]) -> float:
    """Compute extraction F1 score for criteria lists.

    Normalizes strings before comparison to handle minor variations
    like trailing punctuation or case differences.

    Args:
        predicted: Extracted criterion strings.
        gold: Gold-standard criterion strings.

    Returns:
        F1 score in the range [0.0, 1.0].

    Raises:
        ValueError: If the inputs are empty or not comparable.

    Examples:
        >>> extraction_f1(["Age >= 18"], ["Age >= 18."])
        1.0
        >>> extraction_f1(["age >= 18"], ["Age >= 18"])
        1.0
    """
    if not predicted or not gold:
        raise ValueError("predicted and gold must be non-empty")

    # Normalize both predicted and gold before comparison
    predicted_normalized = {_normalize_criterion_text(p) for p in predicted}
    gold_normalized = {_normalize_criterion_text(g) for g in gold}

    true_positives = len(predicted_normalized & gold_normalized)
    if true_positives == 0:
        return 0.0

    precision = true_positives / len(predicted_normalized)
    recall = true_positives / len(gold_normalized)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def snomed_top1_accuracy(predicted: List[str], gold: List[str]) -> float:
    """Compute Top-1 accuracy for SNOMED grounding.

    Args:
        predicted: Predicted SNOMED codes.
        gold: Gold-standard SNOMED codes.

    Returns:
        Top-1 accuracy in the range [0.0, 1.0].

    Raises:
        ValueError: If the inputs are empty or not comparable.

    Examples:
        >>> snomed_top1_accuracy(["372244006"], ["372244006"])
        0.0

    Notes:
        This stub will be replaced by a metric implementation aligned with
        UMLS candidate ranking outputs.
    """
    if not predicted or not gold:
        raise ValueError("predicted and gold must be non-empty")

    comparisons = zip(predicted, gold)
    matches = sum(
        1
        for predicted_code, gold_code in comparisons
        if predicted_code == gold_code
    )
    return matches / len(gold)


def field_mapping_accuracy(predicted: List[str], gold: List[str]) -> float:
    """Compute accuracy for field/relation/value mappings.

    Args:
        predicted: Predicted normalized mapping strings (field|relation|value).
        gold: Gold-standard normalized mapping strings.

    Returns:
        Accuracy in the range [0.0, 1.0].

    Raises:
        ValueError: If the inputs are empty or not comparable.

    Examples:
        >>> field_mapping_accuracy(["demographics.age|>|75"], ["demographics.age|>|75"])
        0.0

    Notes:
        This stub will be replaced by a metric implementation aligned with
        normalized field/value parsing in the grounding service.
    """
    if not predicted or not gold:
        raise ValueError("predicted and gold must be non-empty")

    comparisons = zip(predicted, gold)
    matches = sum(
        1
        for predicted_value, gold_value in comparisons
        if predicted_value == gold_value
    )
    return matches / len(gold)


def hitl_acceptance_rate(actions: Iterable[str]) -> float:
    """Compute acceptance rate from HITL action labels.

    Args:
        actions: Iterable of action labels (e.g., "accept", "reject").

    Returns:
        Acceptance rate as a float in the range [0.0, 1.0].

    Raises:
        ValueError: If no actions are provided.

    Examples:
        >>> hitl_acceptance_rate(["accept", "reject", "accept"])
        0.0

    Notes:
        This stub represents the acceptance metric tracked in the hackathon.
    """
    action_list = list(actions)
    if not action_list:
        raise ValueError("actions must be non-empty")

    accepted = sum(1 for action in action_list if action == "accept")
    return accepted / len(action_list)
