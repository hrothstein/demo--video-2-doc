import base64
import os
import time
from openai import AzureOpenAI
from dotenv import load_dotenv

load_dotenv()

# Initialize Azure OpenAI client
client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)

DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")

SYSTEM_PROMPT = """You are a technical documentation writer creating a step-by-step how-to guide.

You will receive sequential screenshots from a screen recording of someone performing a task on their computer. Analyze them in order and produce clear documentation.

## Output Format

Return your response in this exact markdown structure:

# [Task Title - infer from what you see]

## Prerequisites
- [Any requirements visible or implied]

## Steps

### Step 1: [Action Title]
**Action:** [Click/Type/Select/etc.]
**Location:** [Where in the UI]
**Details:** [Specific values, text to enter, options to select]

### Step 2: [Action Title]
...continue for all steps...

## Notes
- [Any warnings, tips, or troubleshooting observed]

## Rules
- Be concise but thorough
- Use exact text shown in UI for button names, menu items, field labels
- If you see error messages, include troubleshooting steps
- Reference frame numbers when helpful (e.g., "as shown in frame 5")
- Assume reader is technical but unfamiliar with this specific process
"""

def encode_image(image_path: str) -> str:
    """Convert image to base64"""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode()

def analyze_frames(frame_paths: list[str]) -> str:
    """Send frames to Azure OpenAI GPT-4o and get documentation with retry logic"""
    
    # Build image content
    image_content = []
    for i, path in enumerate(frame_paths):
        image_content.append({
            "type": "text",
            "text": f"Frame {i + 1}:"
        })
        image_content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{encode_image(path)}",
                "detail": "high"
            }
        })
    
    # Retry logic: one automatic retry with exponential backoff
    max_attempts = 2
    for attempt in range(max_attempts):
        try:
            response = client.chat.completions.create(
                model=DEPLOYMENT_NAME,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": image_content}
                ],
                max_tokens=4096
            )
            return response.choices[0].message.content
        
        except Exception as e:
            if attempt < max_attempts - 1:
                # Exponential backoff: wait 2^attempt seconds
                wait_time = 2 ** attempt
                time.sleep(wait_time)
                continue
            else:
                # Final attempt failed, raise exception
                raise RuntimeError(f"Azure OpenAI API call failed after {max_attempts} attempts: {str(e)}")

