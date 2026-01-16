#!/usr/bin/env python3
"""Generate a clean, grouped components overview page for the monorepo.

This script automatically discovers components in the components/ directory,
extracts information from their pyproject.toml and README.md files, and generates
a comprehensive overview page grouped by category.
"""

import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional

try:
    import tomllib
except ImportError:
    # Python < 3.11 compatibility
    try:
        import tomli as tomllib
    except ImportError:
        print("Error: tomllib (Python 3.11+) or tomli is required.")
        print("Install with: uv add tomli")
        sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

COMPONENTS_DIR = "components"
OUTPUT_MD = "docs/components-overview.md"


def extract_description(readme_path: Path) -> str:
    """Extract a short description from the README file.

    Args:
        readme_path: Path to the README.md file.

    Returns:
        A short description extracted from the README, or a default message
        if the file cannot be read or doesn't contain a description.

    Example:
        >>> extract_description(Path("components/my-component/README.md"))
        "A component for data processing"
    """
    if not readme_path.exists():
        logger.warning(f"README file not found: {readme_path}")
        return "No description available"

    try:
        content = readme_path.read_text(encoding="utf-8")
        lines = content.split("\n")

        # Look for the first non-empty line after the title
        for line in lines:
            line = line.strip()
            if line and not line.startswith("#") and not line.startswith("["):
                # Truncate if too long
                if len(line) > 200:
                    return line[:200] + "..."
                return line

        logger.warning(f"No description found in README: {readme_path}")
        return "No description available"
    except Exception as e:
        logger.error(f"Error reading README file {readme_path}: {e}")
        return "No description available"


def read_pyproject_data(component_path: Path) -> Optional[Dict]:
    """Read component data from pyproject.toml.

    Args:
        component_path: Path to the component directory.

    Returns:
        Dictionary containing the parsed pyproject.toml data, or None if
        the file cannot be read or parsed.

    Example:
        >>> data = read_pyproject_data(Path("components/my-component"))
        >>> print(data.get('project', {}).get('description'))
        "My component description"
    """
    pyproject_path = component_path / "pyproject.toml"

    if not pyproject_path.exists():
        logger.warning(f"pyproject.toml not found: {pyproject_path}")
        return None

    try:
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
        return data
    except Exception as e:
        logger.error(f"Could not read pyproject.toml for {component_path.name}: {e}")
        return None


def infer_category(
    component_name: str, dependencies: Optional[List[str]] = None
) -> str:
    """Infer component category from name and dependencies.

    Args:
        component_name: Name of the component.
        dependencies: List of dependencies from pyproject.toml.

    Returns:
        Inferred category: 'mcp', 'utils', 'agents', or 'others'.

    Example:
        >>> infer_category("my-mcp-server", ["mcp-server"])
        "mcp"
        >>> infer_category("data-utils")
        "utils"
    """
    name_lower = component_name.lower()

    # Check for MCP components
    if name_lower.endswith("-mcp") or (
        dependencies and any("mcp" in dep.lower() for dep in dependencies)
    ):
        return "mcp"

    # Check for utility components
    if name_lower.endswith("-utils") or name_lower.endswith("-utils"):
        return "utils"

    # Check for agent components
    if "agent" in name_lower:
        return "agents"

    # Default to others
    return "others"


def get_component_info(component_name: str) -> Dict:
    """Get comprehensive information about a component.

    Args:
        component_name: Name of the component directory.

    Returns:
        Dictionary containing component information including name, description,
        category, status, owner, and file availability.

    Example:
        >>> info = get_component_info("my-component")
        >>> print(info["description"])
        "A component for data processing"
    """
    component_path = Path(COMPONENTS_DIR) / component_name
    readme_path = component_path / "README.md"
    mkdocs_path = component_path / "mkdocs.yml"

    # Try to read pyproject.toml data
    pyproject_data = read_pyproject_data(component_path)

    if pyproject_data:
        try:
            project_data = pyproject_data.get("project", {})
            dependencies = project_data.get("dependencies", [])

            # Get description from pyproject.toml
            description = project_data.get("description", "No description available")

            # Get authors from pyproject.toml - handle different formats
            authors = project_data.get("authors", [])
            owner = "Unknown"
            if authors:
                first_author = authors[0]
                if isinstance(first_author, dict):
                    owner = first_author.get("name", "Unknown")
                elif isinstance(first_author, str):
                    owner = first_author
                else:
                    owner = str(first_author)

            # Infer category
            category = infer_category(component_name, dependencies)

            return {
                "name": component_name,
                "display_name": component_name.replace("-", " ").title(),
                "description": description,
                "category": category,
                "status": "active",  # Default status
                "owner": owner,
                "has_required_files": readme_path.exists() and mkdocs_path.exists(),
                "pyproject_data": pyproject_data,
            }
        except Exception as e:
            logger.error(f"Error processing pyproject.toml for {component_name}: {e}")
            # Fall through to basic info
    else:
        # Fallback to basic info
        has_required_files = readme_path.exists() and mkdocs_path.exists()
        return {
            "name": component_name,
            "display_name": component_name.replace("-", " ").title(),
            "description": extract_description(readme_path)
            if has_required_files
            else "Missing documentation",
            "category": infer_category(component_name),
            "status": "active",
            "owner": "Unknown",
            "has_required_files": has_required_files,
            "pyproject_data": None,
        }


def discover_components_by_category() -> Dict[str, List[Dict]]:
    """Auto-discover components and group them by category.

    Returns:
        Dictionary mapping category names to lists of component information.

    Example:
        >>> categories = discover_components_by_category()
        >>> print(categories["mcp"])
        [{"name": "athena-mcp", "category": "mcp", ...}]
    """
    categories = {}

    try:
        components_path = Path(COMPONENTS_DIR)
        if not components_path.exists():
            logger.error(f"Components directory not found: {COMPONENTS_DIR}")
            return categories

        for component_path in components_path.iterdir():
            if not component_path.is_dir() or component_path.name.startswith("."):
                continue

            try:
                info = get_component_info(component_path.name)
                if info["has_required_files"]:
                    category = info["category"]
                    if category not in categories:
                        categories[category] = []
                    categories[category].append(info)
                else:
                    logger.warning(
                        f"Component {component_path.name} missing required files (README.md or mkdocs.yml)"
                    )
            except Exception as e:
                logger.error(f"Error processing component {component_path.name}: {e}")

    except Exception as e:
        logger.error(f"Error discovering components: {e}")

    return categories


def generate_category_section(category_name: str, components: List[Dict]) -> str:
    """Generate a markdown section for a category of components.

    Args:
        category_name: Name of the category.
        components: List of component information dictionaries.

    Returns:
        Markdown formatted string for the category section.

    Example:
        >>> section = generate_category_section("mcp", [{"name": "test", "display_name": "Test"}])
        >>> print(section)
        "## Mcp Components\n\n| Name | Description | Owner |..."
    """
    if not components:
        return ""

    # Sort by display name
    components.sort(key=lambda x: x["display_name"])

    # Generate the section
    section = f"\n## {category_name.title()} Components\n\n"
    section += "| Name | Description | Owner |\n"
    section += "|------|-------------|-------|\n"

    for info in components:
        # Link directly to the component's README within the built docs tree
        link = f"{info['name']}/README.md"
        section += f"| [{info['display_name']}]({link}) | {info['description']} | {info['owner']} |\n"

    return section


def generate_overview() -> str:
    """Generate the complete components overview markdown.

    Returns:
        Complete markdown content for the components overview page.

    Example:
        >>> content = generate_overview()
        >>> print(content[:100])
        "# Components Overview\n\nThis page lists all available components..."
    """
    # Discover components by category
    categories = discover_components_by_category()

    content = """# Components Overview

This page lists all available components in the monorepo, grouped by category. Click a component name to view its documentation.

"""

    # Generate sections for each category
    for category_name, components in categories.items():
        section = generate_category_section(category_name, components)
        if section:
            content += section

    # Add summary
    total_components = sum(len(comps) for comps in categories.values())
    content += f"\n---\n\n**Total Components:** {total_components}\n\n"
    content += "*This overview is automatically generated from component pyproject.toml files and README files.*\n"

    return content


def main() -> None:
    """Generate the components overview markdown file.

    This function orchestrates the entire process of discovering components,
    extracting their information, and generating the overview markdown file.

    Raises:
        SystemExit: If the script encounters a critical error that prevents
                   successful completion.

    Example:
        >>> main()
        # Generates docs/components-overview.md
    """
    logger.info("Generating components overview...")

    try:
        # Ensure output directory exists
        output_path = Path(OUTPUT_MD)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Generate the overview content
        content = generate_overview()

        # Write the file
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info(f"✅ Components overview generated successfully: {output_path}")

    except Exception as e:
        logger.error(f"❌ Failed to generate components overview: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
