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
    return 0.0


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
    return 0.0


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
    return 0.0
