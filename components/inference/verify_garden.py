import os
import sys
os.environ["GRPC_DNS_RESOLVER"] = "native"
from langchain_google_vertexai import VertexAIModelGarden
from inference import AgentConfig

def test_model_garden():
    cfg = AgentConfig.from_env()
    if not cfg.vertex_endpoint_id:
        print("Missing VERTEX_ENDPOINT_ID")
        return

    print(f"Testing VertexAIModelGarden with endpoint: {cfg.vertex_endpoint_id}")
    
    dedicated_dns = "mg-endpoint-d2d17a3d-7ccf-43f3-9f9b-798ff0bed7f9.europe-west4-461821350308.prediction.vertexai.goog"
    
    llm = VertexAIModelGarden(
        project=cfg.gcp_project_id,
        location=cfg.gcp_region,
        endpoint_id=cfg.vertex_endpoint_id,
    )
    
    # Manually override the client to use the dedicated DNS
    from google.api_core.client_options import ClientOptions
    from google.cloud.aiplatform.gapic import PredictionServiceClient
    
    client_options = ClientOptions(api_endpoint=dedicated_dns)
    llm.client = PredictionServiceClient(client_options=client_options)
    
    prompt = "Reply with 'ok' only."
    try:
        # VertexAIModelGarden.invoke calls _generate which calls self.client.predict
        response = llm.invoke(prompt)
        print(f"Response: {response}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Failed: {e}")

if __name__ == '__main__':
    test_model_garden()
