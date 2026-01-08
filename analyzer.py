import base64
import os
import time
import logging
from openai import AzureOpenAI
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

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

## Analysis Process (Follow This Order)

**Step 1: Understand Intent**
- Scan through ALL frames to understand: What is the user trying to accomplish?
- Identify the goal/outcome: What does success look like in this video?
- Understand the workflow: What steps lead to that outcome?

**Step 2: Identify Key Frames Based on Intent**
- Based on your understanding of the intent, identify which frames are most important:
  - Frames that show the final outcome/result (what the user achieved)
  - Frames that show key milestones (important intermediate results)
  - Frames that show verification points (how to confirm progress/success)
- These are the frames you should reference with [FRAME:N] tags

**Step 3: Write Documentation**
- Create clear, detailed documentation that guides readers to achieve the same outcome
- **CRITICAL: You MUST include [FRAME:N] references** - screenshots are essential for understanding outcomes
- Reference the intent-relevant frames you identified in Step 2, especially outcome frames

## Output Format

**CRITICAL: You MUST include [FRAME:N] references in your output. Screenshots are essential for documentation.**

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

**IMPORTANT EXAMPLE**: If the final step shows a completed project structure (like a file explorer with created files), you MUST include it like this:
### Step 12: Verify Project Creation
[FRAME:18]
**Action:** Check the Explorer panel
**Location:** Left sidebar
**Details:** You should see the scaffolded project structure with folders and files

## Notes
- [Any warnings, tips, or troubleshooting observed]

## Rules for Frame References (MANDATORY - Intent-Based Selection)
- **YOU MUST INCLUDE [FRAME:N] REFERENCES** - This is not optional. Screenshots are critical for documentation.
- Use [FRAME:N] tags to indicate which key frame should appear with each step
- Place the frame reference on its own line right after the step heading
- **Frame selection must be based on your understanding of intent**:
  - After understanding what the user is trying to accomplish, select frames that best demonstrate:
    * **The final outcome/result (what was achieved) - THIS IS MANDATORY**
    * Key milestones (important intermediate achievements)
    * Verification points (how to confirm success)
- **CRITICAL: You MUST include a frame reference for the final outcome/result step** - readers need to see what success looks like
- **Select frames that show outcomes, not just actions**: Prioritize frames that show results over frames that only show actions being performed
- Include frame references for at least 50% of your steps - more is better
- A frame can be referenced in multiple steps if relevant
- Reference frames by their KEY FRAME number (1, 2, 3...), not the raw frame number
- **If you see a completed project structure, final result, or outcome state, you MUST include a [FRAME:N] reference for it**

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
    # Add instruction at the start about key frames
    image_content.append({
        "type": "text",
        "text": f"IMPORTANT: You will see {len(key_frame_paths)} KEY FRAMES marked as 'KEY FRAME 1', 'KEY FRAME 2', etc. Use these KEY FRAME numbers (1-{len(key_frame_paths)}) in your [FRAME:N] references, NOT the raw frame numbers."
    })
    
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
            markdown_content = response.choices[0].message.content
            
            # Debug: Log the response to see what GPT-4o is actually returning
            import re
            frame_refs = re.findall(r'\[FRAME:\d+\]', markdown_content)
            logger.info(f"GPT-4o returned {len(frame_refs)} frame references in markdown")
            if frame_refs:
                logger.info(f"Frame references found: {frame_refs[:10]}")  # First 10
            else:
                logger.warning("No frame references found in GPT-4o response!")
                # Log first 500 chars to see what we got
                logger.debug(f"First 500 chars of response: {markdown_content[:500]}")
            
            return markdown_content
        
        except Exception as e:
            if attempt < max_attempts - 1:
                # Exponential backoff: wait 2^attempt seconds
                wait_time = 2 ** attempt
                time.sleep(wait_time)
                continue
            else:
                # Final attempt failed, raise exception
                raise RuntimeError(f"Azure OpenAI API call failed after {max_attempts} attempts: {str(e)}")

