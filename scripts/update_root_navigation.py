#!/usr/bin/env python3
"""Update the root mkdocs.yml navigation to include all components.

This script automatically discovers components in the components/ directory that
have mkdocs.yml files and updates the root mkdocs.yml navigation section to
include all of them with proper formatting and display names.
"""

import logging
import sys
from pathlib import Path
from typing import List, Optional, Tuple

# Check Python version
if sys.version_info < (3, 8):
    print("Error: Python 3.8+ is required.")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

COMPONENTS_DIR = "components"
ROOT_MKDOCS = "mkdocs.yml"


def get_component_display_name(component_name: str) -> str:
    """Convert component name to display name.

    Args:
        component_name: The component directory name (e.g., "my-component").

    Returns:
        Formatted display name (e.g., "My Component").

    Example:
        >>> get_component_display_name("athena-mcp")
        "Athena Mcp"
        >>> get_component_display_name("cell-ops")
        "Cell Ops"
    """
    return component_name.replace("-", " ").title()


def discover_components() -> List[str]:
    """Discover all components that have mkdocs.yml files.

    Returns:
        List of component names that have valid mkdocs.yml files.

    Example:
        >>> components = discover_components()
        >>> print(components)
        ["athena-mcp", "cell-ops", "omics-embark"]
    """
    components: List[str] = []

    try:
        components_path = Path(COMPONENTS_DIR)
        if not components_path.exists():
            logger.error(f"Components directory not found: {COMPONENTS_DIR}")
            return components

        for component_path in components_path.iterdir():
            if not component_path.is_dir() or component_path.name.startswith("."):
                continue

            mkdocs_path = component_path / "mkdocs.yml"
            if mkdocs_path.exists():
                components.append(component_path.name)
                logger.debug(f"Found component: {component_path.name}")
            else:
                logger.debug(
                    f"Skipping component without mkdocs.yml: {component_path.name}"
                )

    except Exception as e:
        logger.error(f"Error discovering components: {e}")

    return sorted(components)


def find_components_section(lines: List[str]) -> Tuple[Optional[int], Optional[int]]:
    """Find the start and end indices of the Components section in mkdocs.yml.

    Args:
        lines: List of lines from the mkdocs.yml file.

    Returns:
        Tuple of (start_index, end_index) for the Components section.
        Returns (None, None) if the section is not found.

    Example:
        >>> lines = ["- Components:", "  - Overview: components-overview.md"]
        >>> start, end = find_components_section(lines)
        >>> print(start, end)
        0 2
    """
    components_start_idx = None
    components_end_idx = None

    # Find the Components section start
    for i, line in enumerate(lines):
        if line.strip() == "- Components:":
            components_start_idx = i
            break

    if components_start_idx is None:
        logger.error("Could not find Components section in mkdocs.yml")
        return None, None

    # Find where the Components section ends (look for next top-level section)
    for i in range(components_start_idx + 1, len(lines)):
        line = lines[i].strip()
        # Look for a line that starts with "- " and ends with ":" (top-level nav item)
        # but not indented (not a component)
        if (
            line.startswith("- ")
            and line.endswith(":")
            and not line.startswith("  - ")
            and not line.startswith("    - ")
        ):
            components_end_idx = i
            break

    if components_end_idx is None:
        components_end_idx = len(lines)

    return components_start_idx, components_end_idx


def generate_components_navigation(components: List[str]) -> List[str]:
    """Generate the new components navigation lines.

    Args:
        components: List of component names to include in navigation.

    Returns:
        List of formatted navigation lines for the Components section.

    Example:
        >>> lines = generate_components_navigation(["athena-mcp", "cell-ops"])
        >>> print(lines)
        ["  - Components:\n", "    - Overview: components-overview.md\n", ...]
    """
    new_components_lines = []
    new_components_lines.append("  - Components:\n")
    new_components_lines.append("    - Overview: components-overview.md\n")

    for component in components:
        display_name = get_component_display_name(component)
        new_components_lines.append(
            f"    - {display_name}: '!include ./components/{component}/mkdocs.yml'\n"
        )

    return new_components_lines


def update_mkdocs_navigation() -> None:
    """Update the root mkdocs.yml navigation section.

    This function reads the current mkdocs.yml file, finds the Components section,
    and replaces it with an updated version that includes all discovered components.

    Raises:
        SystemExit: If the script encounters a critical error that prevents
                   successful completion.

    Example:
        >>> update_mkdocs_navigation()
        # Updates mkdocs.yml with all discovered components
    """
    logger.info("Updating root mkdocs.yml navigation...")

    try:
        # Check if mkdocs.yml exists
        if not Path(ROOT_MKDOCS).exists():
            logger.error(f"Root mkdocs.yml file not found: {ROOT_MKDOCS}")
            sys.exit(1)

        # Read current mkdocs.yml
        with open(ROOT_MKDOCS, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # Find the Components section
        components_start_idx, components_end_idx = find_components_section(lines)
        if components_start_idx is None:
            logger.error("❌ Could not find Components section in mkdocs.yml")
            sys.exit(1)

        # Discover components
        components = discover_components()
        if not components:
            logger.warning("No components found with mkdocs.yml files")
            return

        # Generate new components navigation
        new_components_lines = generate_components_navigation(components)

        # Replace the Components section
        new_lines = (
            lines[:components_start_idx]
            + new_components_lines
            + lines[components_end_idx:]
        )

        # Write back to file
        with open(ROOT_MKDOCS, "w", encoding="utf-8") as f:
            f.writelines(new_lines)

        logger.info(f"✅ Updated navigation with {len(components)} components")

    except FileNotFoundError as e:
        logger.error(f"❌ File not found: {e}")
        sys.exit(1)
    except PermissionError as e:
        logger.error(f"❌ Permission denied: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Unexpected error updating navigation: {e}")
        sys.exit(1)


if __name__ == "__main__":
    update_mkdocs_navigation()
