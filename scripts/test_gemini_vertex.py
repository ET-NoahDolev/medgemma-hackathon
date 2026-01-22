#!/usr/bin/env python3
"""Smoke test to verify Gemini model access via Vertex AI API.

This script tests that:
1. Environment variables are properly configured
2. Vertex AI can be initialized
3. Gemini 2.5 Pro model can be accessed
4. A simple API call succeeds

Usage:
    uv run python scripts/test_gemini_vertex.py
    GEMINI_MODEL_NAME=gemini-1.5-pro uv run python scripts/test_gemini_vertex.py
"""

import os
import sys
from pathlib import Path


def load_env_file(env_path: Path) -> None:
    """Load environment variables from .env file."""
    if not env_path.exists():
        return

    with env_path.open() as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith("#"):
                continue
            # Parse KEY=VALUE
            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()
                # Only set if not already in environment
                if key and value and key not in os.environ:
                    os.environ[key] = value


def main() -> int:
    """Run smoke test for Gemini Vertex AI access."""
    # Load .env file if it exists
    repo_root = Path(__file__).parent.parent
    env_path = repo_root / ".env"
    load_env_file(env_path)

    # Get required environment variables
    project_id = os.getenv("GCP_PROJECT_ID")
    region = os.getenv("GCP_REGION", "europe-west4")
    model_name = os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-pro")

    print("🔍 Gemini Vertex AI Smoke Test")
    print("=" * 50)
    print(f"Project ID: {project_id or '❌ NOT SET'}")
    print(f"Region: {region}")
    print(f"Model: {model_name}")
    print()

    if not project_id:
        print("❌ ERROR: GCP_PROJECT_ID is not set")
        print("   Set it in .env or as an environment variable")
        return 1

    # Check for required dependencies
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
    except ImportError as e:
        print(f"❌ ERROR: Missing dependency: {e}")
        print("   Install with: uv add langchain-google-genai")
        return 1

    try:
        import vertexai
    except ImportError as e:
        print(f"❌ ERROR: Missing dependency: {e}")
        print("   Install with: uv add google-cloud-aiplatform")
        return 1

    # Initialize Vertex AI
    print("📡 Initializing Vertex AI...")
    try:
        vertexai.init(project=project_id, location=region)
        print("   ✅ Vertex AI initialized")
    except Exception as e:
        print(f"   ❌ Failed to initialize Vertex AI: {e}")
        return 1

    # Create model instance
    print(f"🤖 Creating {model_name} model instance...")
    try:
        model = ChatGoogleGenerativeAI(
            model=model_name,
            project=project_id,
            location=region,
            vertexai=True,
            max_output_tokens=32,  # Keep it small for smoke test
        )
        print("   ✅ Model instance created")
    except Exception as e:
        print(f"   ❌ Failed to create model: {e}")
        print(f"   💡 Check that {model_name} is available in your region")
        print("   💡 Available models: https://console.cloud.google.com/vertex-ai/models")
        return 1

    # Make a simple API call
    print("💬 Testing API call...")
    try:
        from langchain_core.messages import HumanMessage

        response = model.invoke([HumanMessage(content="Say 'ok' only.")])
        content = getattr(response, "content", None)

        if not content:
            print("   ❌ No content in response")
            return 1

        print("   ✅ API call succeeded")
        print(f"   📝 Response: {content[:100]}{'...' if len(str(content)) > 100 else ''}")
    except Exception as e:
        print(f"   ❌ API call failed: {e}")
        print("   💡 Check your authentication: gcloud auth application-default login")
        print(f"   💡 Check model availability in region {region}")
        return 1

    print()
    print("✅ All tests passed! Gemini model is accessible via Vertex AI.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
