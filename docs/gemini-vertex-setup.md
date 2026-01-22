# Gemini 2.5 Pro Vertex AI Setup Guide

## Overview

**Important**: Gemini models (including Gemini 2.5 Pro) do **NOT** require deployment like MedGemma. They are accessed directly via Vertex AI's API using the model name. No endpoint creation is needed.

## Prerequisites

1. GCP Project with billing enabled
2. Vertex AI API enabled
3. Application Default Credentials (ADC) configured
4. Required Python packages installed

## Step-by-Step Setup

### Step 1: Enable Required APIs

The `setup_gcp.sh` script already enables these, but you can verify manually:

```bash
# Enable Vertex AI API
gcloud services enable aiplatform.googleapis.com

# Enable Generative Language API (for Gemini models)
gcloud services enable generativelanguage.googleapis.com
```

### Step 2: Authenticate with GCP

```bash
# Authenticate with your Google account
gcloud auth login

# Set up Application Default Credentials (required for Vertex AI)
gcloud auth application-default login

# Set your project
gcloud config set project YOUR_PROJECT_ID
```

### Step 3: Run the Setup Script

The `setup_gcp.sh` script will:
- Enable required APIs
- Create GCS bucket
- Deploy MedGemma (if needed)
- **Configure Gemini 2.5 Pro** (no deployment needed)

```bash
cd /Users/noahdolevelixir/Code/gemma-hackathon
./scripts/setup_gcp.sh
```

Or with custom project/region:

```bash
GCP_PROJECT_ID=your-project-id GCP_REGION=us-central1 ./scripts/setup_gcp.sh
```

### Step 4: Verify Environment Variables

After running the script, check your `.env` file:

```bash
cat .env | grep GEMINI
```

You should see:
```
GEMINI_MODEL_NAME=gemini-2.5-pro
```

**Note**: If `gemini-2.5-pro` is not available in your region, try:
- `gemini-1.5-pro` (stable, widely available)
- `gemini-1.5-flash` (faster, lower cost)
- `gemini-2.0-flash-exp` (experimental)

### Step 5: Verify Model Availability

Check available Gemini models in your region:

```bash
# List available models (requires Vertex AI API)
gcloud ai models list --region=YOUR_REGION --filter="displayName:gemini*"
```

Or test programmatically:

```python
from langchain_google_genai import ChatGoogleGenerativeAI
import os

model = ChatGoogleGenerativeAI(
    model=os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-pro"),
    project=os.getenv("GCP_PROJECT_ID"),
    location=os.getenv("GCP_REGION", "europe-west4"),
    vertexai=True,
)

# Test the model
response = model.invoke("Say 'Hello'")
print(response.content)
```

### Step 6: Test the Grounding Agent

```bash
# Set environment variables
export $(grep -v '^#' .env | xargs)

# Run a test
uv run python -c "
from grounding_service.agent import get_grounding_agent
import asyncio

async def test():
    agent = get_grounding_agent()
    result = await agent.ground('Age >= 18 years', 'inclusion')
    print(f'SNOMED codes: {result.snomed_codes}')
    print(f'Field mappings: {len(result.field_mappings)}')

asyncio.run(test())
"
```

## Troubleshooting

### Error: "Model not found" or "Permission denied"

1. **Verify model name**: Check available models in Vertex AI Console:
   ```
   https://console.cloud.google.com/vertex-ai/models?project=YOUR_PROJECT_ID
   ```

2. **Check region**: Gemini models may not be available in all regions. Try:
   - `us-central1`
   - `us-east1`
   - `europe-west4`

3. **Verify API access**: Ensure you have the `Vertex AI User` role:
   ```bash
   gcloud projects get-iam-policy YOUR_PROJECT_ID --flatten="bindings[].members" --filter="bindings.members:user:YOUR_EMAIL"
   ```

### Error: "Application Default Credentials not found"

```bash
gcloud auth application-default login
```

### Model Name Alternatives

If `gemini-2.5-pro` is not available, update `.env`:

```bash
# Edit .env file
GEMINI_MODEL_NAME=gemini-1.5-pro  # or gemini-1.5-flash
```

## Key Differences: MedGemma vs Gemini

| Aspect | MedGemma | Gemini 2.5 Pro |
|--------|----------|----------------|
| **Deployment** | ✅ Requires endpoint deployment (10-15 min) | ❌ No deployment needed |
| **Access** | Via `VERTEX_ENDPOINT_ID` | Via `GEMINI_MODEL_NAME` |
| **Setup** | Model Garden deployment | Just set env var |
| **Cost** | Pay for endpoint compute | Pay per API call |
| **Tool Support** | ❌ No native tool calling | ✅ Native tool calling |

## Next Steps

Once configured, the grounding service will automatically use Gemini 2.5 Pro as the orchestrator. The agent will:
1. Use Gemini to decide when to call tools
2. Call MedGemma tool for medical interpretation
3. Call UMLS MCP tools for code lookups
4. Return structured GroundingResult

No additional deployment steps needed!
