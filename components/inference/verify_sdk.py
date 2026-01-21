import os
from google.cloud import aiplatform
from inference import AgentConfig

def test_sdk():
    cfg = AgentConfig.from_env()
    print(f"Testing Vertex SDK with endpoint: {cfg.vertex_endpoint_id}")
    
    aiplatform.init(project=cfg.gcp_project_id, location=cfg.gcp_region)
    # Use full resource name
    endpoint_name = f"projects/{cfg.gcp_project_id}/locations/{cfg.gcp_region}/endpoints/{cfg.vertex_endpoint_id}"
    endpoint = aiplatform.Endpoint(endpoint_name)
    
    # Check if dedicated endpoint is enabled
    print(f"Dedicated DNS from SDK: {getattr(endpoint, 'dedicated_endpoint_dns', 'Not found')}")
    
    instances = [{"prompt": "Reply with 'ok' only."}]
    try:
        # Standard predict
        print("Trying endpoint.predict()...")
        response = endpoint.predict(instances=instances)
        print(f"Predict Response: {response.predictions}")
    except Exception as e:
        print(f"Predict Failed: {e}")
        
    try:
        # Raw predict (some Model Garden models need this)
        print("Trying endpoint.raw_predict()...")
        import json
        payload = {"instances": instances}
        response = endpoint.raw_predict(
            body=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        print(f"Raw Predict Response: {response.text}")
    except Exception as e:
        print(f"Raw Predict Failed: {e}")

if __name__ == '__main__':
    test_sdk()
