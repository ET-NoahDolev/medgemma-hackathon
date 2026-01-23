#!/usr/bin/env python3
"""Diagnostic script to check extraction model configuration."""

import os
import sys
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

# Add repo root to path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root))

# Load environment variables from .env file
load_dotenv(find_dotenv())

print("=" * 60)
print("Extraction Model Configuration Diagnostic")
print("=" * 60)
print()

# Check 1: Environment variables
print("1. Environment Variables:")
print(f"   GEMINI_MODEL_NAME: {os.getenv('GEMINI_MODEL_NAME', 'NOT SET (defaults to gemini-2.5-pro)')}")
print(f"   GCP_PROJECT_ID: {os.getenv('GCP_PROJECT_ID', 'NOT SET')}")
print(f"   GCP_REGION: {os.getenv('GCP_REGION', 'NOT SET (defaults to europe-west4)')}")
print()

# Check 2: ExtractionConfig
print("2. ExtractionConfig from Environment:")
try:
    from extraction_service.pipeline import ExtractionConfig

    cfg = ExtractionConfig.from_env()
    print(f"   Gemini model: {cfg.gemini_model_name or 'default'}")
    print(f"   GCP Project ID: {cfg.gcp_project_id or 'NOT SET'}")
    print(f"   GCP Region: {cfg.gcp_region}")
    print(f"   Max page chars: {cfg.max_page_chars}")
    print(f"   Pages per batch: {cfg.max_pages_per_batch}")
    print(f"   Paragraphs per batch: {cfg.max_paragraphs_per_batch}")
except Exception as e:
    print(f"   ✗ Error loading ExtractionConfig: {e}")
    import traceback
    traceback.print_exc()
print()

# Check 3: Gemini Model Loader Creation
print("3. Gemini Model Loader Creation:")
try:
    from extraction_service.pipeline import ExtractionConfig
    from inference.model_factory import create_gemini_model_loader

    cfg = ExtractionConfig.from_env()
    model_loader = create_gemini_model_loader(
        model_name=cfg.gemini_model_name,
        project=cfg.gcp_project_id,
        region=cfg.gcp_region,
    )
    print("   ✓ Gemini loader created successfully")

    # Try to actually load the model (this might take time)
    print("   Attempting to load Gemini model (this may take a moment)...")
    model = model_loader()
    print(f"   ✓ Model loaded successfully: {type(model).__name__}")
except Exception as e:
    print(f"   ✗ Error creating model loader: {e}")
    import traceback
    traceback.print_exc()
print()

# Check 4: Extraction Pipeline
print("4. Extraction Pipeline:")
try:
    from extraction_service.pipeline import ExtractionPipeline, ExtractionConfig

    ext_cfg = ExtractionConfig.from_env()
    pipeline = ExtractionPipeline(config=ext_cfg)
    print("   ✓ Pipeline created successfully")
    prompts_dir = (Path(__file__).parent.parent / "components/extraction-service/src/extraction_service/prompts")
    print(f"   Prompts directory: {prompts_dir}")
    print(f"   Prompts directory exists: {prompts_dir.exists()}")
except Exception as e:
    print(f"   ✗ Error creating pipeline: {e}")
    import traceback
    traceback.print_exc()
print()

print("=" * 60)
print("Diagnostic Complete")
print("=" * 60)
print()
print("Next steps:")
print("1. Ensure GCP_PROJECT_ID is set for Vertex Gemini usage")
print("2. Check the full error traceback in application logs (with exc_info=True)")
print("3. Try setting LOG_LEVEL=DEBUG to see more detailed error messages")
