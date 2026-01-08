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

You will receive sequential screenshots from a screen recording of someone performing a task on their computer. Analyze them in order to understand what the user is trying to accomplish, then produce clear documentation.

Some screenshots are marked as "KEY FRAME" — these will be embedded in the final PDF. When you reference frames, use [FRAME:N] tags with the KEY FRAME number (1, 2, 3, etc.), not the raw frame number.

**IMPORTANT: You can ONLY reference KEY FRAMES numbered 1-18. Any frame reference outside this range will be ignored.**

## Frame Selection Based on Intent

**CRITICAL: Select frames based on understanding the user's intent and what they accomplished:**

1. **First, understand the intent**: What is the user trying to accomplish? What does success look like?
2. **Identify outcome frames**: Look through ALL frames (both KEY FRAME and regular frames) to identify:
   - The final result/outcome (what the user achieved)
   - Key milestones (important intermediate achievements)
   - Verification points (how to confirm success)
3. **Reference KEY FRAMES that show these outcomes**: From the pre-selected KEY FRAMES, choose the ones that best demonstrate:
   - The final outcome/result (MANDATORY - readers need to see what success looks like)
   - Important intermediate results
   - Verification/confirmation screens

**You see ALL frames for context, but can only reference KEY FRAMES in your output. Select KEY FRAMES based on intent understanding, not just because they're marked.**

## Output Format

Return your response in this exact markdown structure:

# [Task Title - infer from what you see]

## Prerequisites
- [Any requirements visible or implied]

## Steps

### Step 1: [Action Title]
[FRAME:1]
**Action:** [Click/Type/Select/etc.]
**Location:** [Where in the UI]
**Details:** [Specific values, text to enter, options to select]

### Step 2: [Action Title]
[FRAME:3]
**Action:** ...
...continue for all steps...

## Notes
- [Any warnings, tips, or troubleshooting observed]

## Rules
- Be concise but thorough
- Use exact text shown in UI for button names, menu items, field labels
- If you see error messages, include troubleshooting steps
- Reference frame numbers when helpful (e.g., "as shown in frame 5")
- Assume reader is technical but unfamiliar with this specific process
- **Select KEY FRAMES based on intent understanding - prioritize frames that show outcomes/results over frames that only show actions**
- **MANDATORY: Include a KEY FRAME reference for the final outcome/result step - readers need to see what success looks like**
- **CRITICAL: Only use KEY FRAME numbers 1-18 in [FRAME:N] tags. Use a single number per tag (e.g., [FRAME:5], not [FRAME:5-7]). Do not use numbers above 18.**
- Focus on understanding the user's intent and goal first, then document the steps to achieve it
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
    num_key_frames = len(key_frame_paths)
    
    # Add instruction about valid frame numbers
    image_content.append({
        "type": "text",
        "text": f"IMPORTANT: You will see frames labeled as 'KEY FRAME 1', 'KEY FRAME 2', etc. up to 'KEY FRAME {num_key_frames}'. When writing [FRAME:N], you MUST use ONLY these KEY FRAME numbers (1-{num_key_frames}). Any number outside this range will be ignored. You will also see frames labeled 'Frame X' (without KEY FRAME) - do not reference these."
    })
    
    for i, path in enumerate(all_frame_paths):
        # Mark key frames clearly but simply
        if path in key_frame_set:
            label = f"KEY FRAME {key_frame_index[path]}:"
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

