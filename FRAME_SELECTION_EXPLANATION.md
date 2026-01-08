# Frame Selection: Intent vs Algorithm

## Current Flow

1. **Algorithmic Pre-Selection** (`frame_selector.py`):
   - Uses image difference detection
   - Selects frames with visual changes
   - Pre-selects ~18 "KEY FRAME" candidates
   - **NOT intent-based** - purely visual/algorithmic

2. **GPT-4o Analysis** (`analyzer.py`):
   - GPT-4o sees **ALL frames** (for context)
   - Some frames are marked "KEY FRAME 1", "KEY FRAME 2", etc.
   - Other frames are marked "Frame X" (not a key frame)
   - GPT-4o can **ONLY reference KEY FRAME numbers** in [FRAME:N] tags

3. **The Constraint**:
   - GPT-4o understands intent and sees all frames
   - But it can only reference frames that were algorithmically pre-selected
   - If an important outcome frame wasn't pre-selected, GPT-4o can't reference it

## The Problem

- **Algorithmic selection** might miss intent-relevant frames
- **GPT-4o** understands intent but is constrained to pre-selected frames
- We're not fully leveraging GPT-4o's intent understanding for frame selection

## Current Prompt

The prompt tells GPT-4o:
- "Focus on understanding the user's intent and goal first"
- "Include [FRAME:N] references for key frames that show important steps or outcomes"
- But GPT-4o can only reference frames that were already marked as KEY FRAME

## What We're NOT Doing

We're **NOT** prompting GPT-4o to:
- Identify which frames show the final outcome based on intent
- Choose frames based on understanding what the user accomplished
- Select frames that demonstrate success/completion

We're relying on algorithmic pre-selection, then asking GPT-4o to work within those constraints.

