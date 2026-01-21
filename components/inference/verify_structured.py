import os
import sys
from pydantic import BaseModel, Field
from inference import AgentConfig, create_model_loader

class SimpleSchema(BaseModel):
    answer: str = Field(..., description="The answer")

async def test_structured_output():
    cfg = AgentConfig.from_env()
    print(f"Testing with_structured_output for Model Garden...")
    
    loader = create_model_loader(cfg)
    model = loader()
    
    structured_model = model.with_structured_output(SimpleSchema)
    
    prompt = "Reply in JSON format: {'answer': 'hello'}"
    try:
        response = await structured_model.ainvoke(prompt)
        print(f"Structured Response: {response}")
        assert isinstance(response, SimpleSchema)
        assert response.answer == 'hello'
        print("Success!")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Failed: {e}")

if __name__ == '__main__':
    import asyncio
    asyncio.run(test_structured_output())
