"""Evaluation metrics stubs."""

from typing import Iterable, List


def extraction_f1(predicted: List[str], gold: List[str]) -> float:
    """Compute extraction F1 score for criteria lists.

    Args:
        predicted: Extracted criterion strings.
        gold: Gold-standard criterion strings.

    Returns:
        F1 score in the range [0.0, 1.0].

    Raises:
        ValueError: If the inputs are empty or not comparable.

    Examples:
        >>> extraction_f1(["age >= 18"], ["age >= 18"])
        0.0

    Notes:
        This is a wireframe stub. The production implementation will
        normalize text and compute precision/recall on span matches.
    """
    if not predicted or not gold:
        raise ValueError("predicted and gold must be non-empty")

    predicted_set = set(predicted)
    gold_set = set(gold)
    true_positives = len(predicted_set & gold_set)
    precision = true_positives / len(predicted_set)
    recall = true_positives / len(gold_set)
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
        UBKG candidate ranking outputs.
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
