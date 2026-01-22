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
print(f"   USE_MODEL_EXTRACTION: {os.getenv('USE_MODEL_EXTRACTION', 'NOT SET (defaults to true)')}")
print(f"   MODEL_BACKEND: {os.getenv('MODEL_BACKEND', 'NOT SET (defaults to local)')}")
print(f"   MEDGEMMA_BACKEND: {os.getenv('MEDGEMMA_BACKEND', 'NOT SET')}")
print(f"   MEDGEMMA_MODEL_PATH: {os.getenv('MEDGEMMA_MODEL_PATH', 'NOT SET (defaults to google/medgemma-4b-it)')}")
print(f"   MEDGEMMA_QUANTIZATION: {os.getenv('MEDGEMMA_QUANTIZATION', 'NOT SET (defaults to 4bit)')}")
print(f"   GCP_PROJECT_ID: {os.getenv('GCP_PROJECT_ID', 'NOT SET')}")
print(f"   GCP_REGION: {os.getenv('GCP_REGION', 'NOT SET (defaults to europe-west4)')}")
print(f"   VERTEX_ENDPOINT_ID: {os.getenv('VERTEX_ENDPOINT_ID', 'NOT SET')}")
print()

# Check 2: AgentConfig
print("2. AgentConfig from Environment:")
try:
    from inference import AgentConfig
    
    cfg = AgentConfig.from_env()
    print(f"   Backend: {cfg.backend}")
    print(f"   Model Path: {cfg.model_path}")
    print(f"   Quantization: {cfg.quantization}")
    print(f"   Max Tokens: {cfg.max_new_tokens}")
    if cfg.backend == "vertex":
        print(f"   GCP Project ID: {cfg.gcp_project_id or 'NOT SET'}")
        print(f"   GCP Region: {cfg.gcp_region}")
        print(f"   Vertex Endpoint ID: {cfg.vertex_endpoint_id or 'NOT SET'}")
        if not cfg.gcp_project_id or not cfg.vertex_endpoint_id:
            print("   ⚠ WARNING: Vertex backend requires GCP_PROJECT_ID and VERTEX_ENDPOINT_ID")
except Exception as e:
    print(f"   ✗ Error loading AgentConfig: {e}")
    import traceback
    traceback.print_exc()
print()

# Check 3: Model Loader Creation
print("3. Model Loader Creation:")
try:
    from inference import create_model_loader, AgentConfig
    
    cfg = AgentConfig.from_env()
    print(f"   Attempting to create model loader for backend: {cfg.backend}")
    
    if cfg.backend == "local":
        print("   Checking local model dependencies...")
        try:
            import torch
            print(f"   ✓ PyTorch available: {torch.__version__}")
        except ImportError:
            print("   ✗ PyTorch not installed")
        
        try:
            import transformers
            print(f"   ✓ Transformers available: {transformers.__version__}")
        except ImportError:
            print("   ✗ Transformers not installed")
        
        try:
            import importlib.util
            spec = importlib.util.find_spec("bitsandbytes")
            if spec is not None:
                print("   ✓ bitsandbytes available (for quantization)")
            else:
                print("   ⚠ bitsandbytes not installed (quantization may not work)")
        except Exception:
            print("   ⚠ bitsandbytes not installed (quantization may not work)")
    
    model_loader = create_model_loader(cfg)
    print("   ✓ Model loader created successfully")
    
    # Try to actually load the model (this might take time)
    print("   Attempting to load model (this may take a moment)...")
    try:
        model = model_loader()
        print(f"   ✓ Model loaded successfully: {type(model).__name__}")
    except Exception as e:
        print(f"   ✗ Failed to load model: {e}")
        import traceback
        traceback.print_exc()
        
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
    print(f"   Use Model: {ext_cfg.use_model}")
    print(f"   Model Path Override: {ext_cfg.model_path or 'None'}")
    
    pipeline = ExtractionPipeline(config=ext_cfg)
    print("   ✓ Pipeline created successfully")
    
    # Try to get model loader (this will trigger lazy loading)
    try:
        model_loader, prompts_dir, agent_cfg = pipeline._get_model_loader()
        print(f"   ✓ Model loader retrieved: {type(model_loader).__name__}")
        print(f"   Prompts directory: {prompts_dir}")
        print(f"   Prompts directory exists: {prompts_dir.exists()}")
    except Exception as e:
        print(f"   ✗ Failed to get model loader: {e}")
        import traceback
        traceback.print_exc()
        
except Exception as e:
    print(f"   ✗ Error creating pipeline: {e}")
    import traceback
    traceback.print_exc()
print()

# Check 5: Test Agent Creation
print("5. Test Agent Creation:")
try:
    from extraction_service.pipeline import ExtractionPipeline
    
    pipeline = ExtractionPipeline()
    if pipeline.config.use_model:
        print("   Attempting to create iterative agent...")
        try:
            agent, tool_factory = pipeline._create_iterative_agent()
            print("   ✓ Iterative agent created successfully")
        except Exception as e:
            print(f"   ✗ Failed to create iterative agent: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("   ⚠ Model extraction disabled (use_model=False)")
        
except Exception as e:
    print(f"   ✗ Error: {e}")
    import traceback
    traceback.print_exc()
print()

print("=" * 60)
print("Diagnostic Complete")
print("=" * 60)
print()
print("Next steps:")
print("1. If using Vertex backend, ensure GCP_PROJECT_ID and VERTEX_ENDPOINT_ID are set")
print("2. If using local backend, ensure PyTorch and transformers are installed")
print("3. Check the full error traceback in application logs (with exc_info=True)")
print("4. Try setting LOG_LEVEL=DEBUG to see more detailed error messages")
