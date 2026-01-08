# Test Results Summary: V1 vs V2 Intent Capture Comparison

## Test Date
January 7, 2025

## Test Video
`tmp/doctest.mp4` - Screen recording of creating a Mule project in VS Code with Anypoint Code Builder

## Results

### V1 Output
- **Title:** "Implement an API Specification with Anypoint Code Builder"
- **Steps:** 13 steps
- **Frame References:** Text-based (e.g., "frame 2", "frames 6–10")
- **Intent Capture:** ✅ Excellent - Clear understanding of the workflow
- **Detail Level:** High - Includes verification steps (Step 12, 13)
- **Strengths:**
  - More comprehensive (13 steps vs 10)
  - Includes verification/exploration steps
  - Better breakdown of authentication flow
  - Clearer step-by-step progression

### V2 Updated Output (After Prompt Simplification)
- **Title:** "Implementing an API Specification via Anypoint Code Builder (VS Code)"
- **Steps:** 10 steps
- **Frame References:** 7 total (6 valid, 1 invalid)
- **Intent Capture:** ✅ Good - Understands the task well
- **Detail Level:** Medium - Missing some verification steps
- **Issues:**
  - Invalid frame reference formats: `[FRAME:6-8]`, `[FRAME:9-10]`, `[FRAME:12-14]` (ranges not supported)
  - One invalid frame number: `[FRAME:38]` (exceeds max of 18)
  - Fewer steps than V1 (missing verification steps)

## Key Differences

1. **Intent Understanding:** Both versions understand the task well, but V1 captures more detail
2. **Step Count:** V1 has 13 steps vs V2's 10 steps
3. **Verification Steps:** V1 includes Steps 12-13 (verify project creation, explore API flow) which V2 lacks
4. **Frame References:** V2 has frame reference issues that need fixing

## Improvements Made

1. ✅ Simplified V2 prompt from ~140 lines to ~40 lines
2. ✅ Removed excessive "CRITICAL"/"MANDATORY" language
3. ✅ Added explicit instruction about frame number range (1-18)
4. ✅ Focused on intent understanding first

## Remaining Issues

1. ❌ Frame reference format: GPT-4o is using ranges (`[FRAME:6-8]`) instead of single numbers
2. ❌ Some invalid frame numbers still appearing (>18)
3. ⚠️ V2 still has fewer steps than V1 - may need to encourage more detail

## Recommendations

1. **Fix Frame Reference Format:**
   - Add explicit example: "Use single numbers only: [FRAME:5], NOT [FRAME:5-7]"
   - Consider post-processing to validate and fix frame references

2. **Improve Detail Level:**
   - Add instruction to include verification steps
   - Encourage more comprehensive step breakdown

3. **Maintain Intent Focus:**
   - Keep the simplified prompt structure
   - Continue emphasizing understanding user intent first

## Next Steps

1. Update prompt to explicitly forbid frame ranges
2. Add validation/post-processing for frame references
3. Consider adding instruction to match V1's detail level
4. Run additional tests to verify consistency

