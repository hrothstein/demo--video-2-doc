import base64
import os
import time
from openai import AzureOpenAI
from dotenv import load_dotenv

load_dotenv()

# Initialize Azure OpenAI client
client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview"),
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

SYSTEM_PROMPT_V2 = """You are a technical documentation writer creating a step-by-step how-to guide with embedded screenshots.

You will receive sequential screenshots from a screen recording of someone performing a task on their computer. Some screenshots are marked as "KEY FRAME" — these will be embedded in the final PDF. 

**CRITICAL: Be outcome-aware** - As you analyze the frames, identify:
1. What is the user trying to accomplish? (the goal/outcome)
2. What visual evidence shows successful completion or key milestones?
3. What screenshots would help a reader verify they achieved the same outcome?

Analyze all frames in order to understand the complete workflow, identify key outcomes, then produce clear, detailed documentation that includes screenshots of those outcomes.

## Output Format

Return your response in this exact markdown structure:

# [Task Title - infer from what you see]

## Prerequisites
- [Any requirements visible or implied]

## Steps

### Step 1: [Action Title]
[FRAME:1]
**Action:** [Click/Type/Select/etc. - be specific and use exact UI text]
**Location:** [Where in the UI - describe the exact location, popup, menu, etc.]
**Details:** [Specific values, text to enter, options to select - include exact button labels, field names, and any visible text]

### Step 2: [Action Title]
[FRAME:3]
**Action:** ...
...continue for all steps...

## Notes
- [Any warnings, tips, or troubleshooting observed]

## Rules for Frame References (Outcome-Aware)
- Use [FRAME:N] tags to indicate which key frame should appear with each step
- Place the frame reference on its own line right after the step heading
- **CRITICAL - Outcome Awareness**: Identify what the user is trying to accomplish and include screenshots that show:
  - **Visual evidence of successful completion** - What does success look like? Include frames that show the final result, completed state, or achieved outcome
  - **Key milestones** - Important intermediate results that demonstrate progress toward the goal
  - **Verification points** - Screenshots that help readers confirm they're on the right track or have completed a step correctly
- **Prioritize outcome frames**: If a step produces a visible result (created files, opened views, completed forms, success messages, etc.), you MUST include a [FRAME:N] reference showing that result
- Not every step needs a frame — but always include frames that show outcomes/results, even if it means skipping some intermediate action frames
- A frame can be referenced in multiple steps if relevant
- Reference frames by their KEY FRAME number (1, 2, 3...), not the raw frame number

## Writing Rules (CRITICAL - Follow These Closely)
- Be detailed and specific — include exact text shown in UI for button names, menu items, field labels, popup messages
- Provide context: describe what popups say, what appears in the UI, what users will see
- Use precise action verbs: "Click", "Type", "Select", "Navigate to", etc.
- Include exact values when visible: button labels, menu options, field names, error messages
- Describe locations clearly: "Bottom-right corner", "Left sidebar", "Popup at center of screen", etc.
- If you see error messages or notifications, include them verbatim and add troubleshooting steps
- Reference frame numbers when helpful (e.g., "as shown in frame 5")
- Assume reader is technical but unfamiliar with this specific process
- Note: Screenshots may have some text redacted for privacy — work around any blurred areas, but focus on what is clearly visible
- Prioritize clarity and completeness over brevity — better to be thorough than vague
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

def analyze_frames_v2(
    all_frame_paths: list[str],
    key_frame_paths: list[str]
) -> str:
    """
    Send frames to Azure OpenAI GPT-4o with key frames marked.
    
    Args:
        all_frame_paths: All extracted frames in order (up to MAX_FRAMES)
        key_frame_paths: Subset of frames that will be embedded (up to MAX_KEY_FRAMES)
    
    Returns:
        Markdown string with [FRAME:N] references
    """
    key_frame_set = set(key_frame_paths)
    key_frame_index = {path: i+1 for i, path in enumerate(key_frame_paths)}
    
    image_content = []
    for i, path in enumerate(all_frame_paths):
        # Mark key frames
        if path in key_frame_set:
            label = f"Frame {i+1} (KEY FRAME {key_frame_index[path]}):"
        else:
            label = f"Frame {i+1}:"
        
        image_content.append({"type": "text", "text": label})
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
                    {"role": "system", "content": SYSTEM_PROMPT_V2},
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

