import os
import sys
import asyncio
from pydantic import BaseModel, Field
from inference import AgentConfig, create_model_loader
from langchain_core.messages import HumanMessage, SystemMessage

class ExtractedCriterion(BaseModel):
    text: str = Field(..., description="The criterion text")
    criterion_type: str = Field(..., description="inclusion or exclusion")
    confidence: float = Field(..., description="0.0-1.0")

class ExtractionResult(BaseModel):
    criteria: list[ExtractedCriterion] = Field(default_factory=list)

async def test_structured_output():
    cfg = AgentConfig.from_env()
    # Ensure high tokens
    os.environ["MEDGEMMA_MAX_TOKENS"] = "1024"
    cfg = AgentConfig.from_env()
    
    print(f"Testing with_structured_output for Model Garden with Robust Parsing...")
    
    loader = create_model_loader(cfg)
    model = loader()
    
    structured_model = model.with_structured_output(ExtractionResult)
    
    # Forceful prompt
    messages = [
        SystemMessage(content="You are a JSON extractor. Output ONLY JSON. No thought process. No markdown. Match the schema exactly."),
        HumanMessage(content="Protocol: Children under 18 years old are excluded. Inclusion: Adults over 18.")
    ]
    
    try:
        response = await structured_model.ainvoke(messages)
        print(f"Response Type: {type(response)}")
        print(f"Structured Response: {response}")
        # If it's a dict, handle it gracefully for the test
        if isinstance(response, dict):
            print("Received dict instead of Pydantic model. Trying to convert...")
            response = ExtractionResult(**response)
            
        assert isinstance(response, ExtractionResult)
        if response.criteria:
            print(f"First criterion: {response.criteria[0]}")
        print("Success!")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Failed: {e}")

if __name__ == '__main__':
    asyncio.run(test_structured_output())
