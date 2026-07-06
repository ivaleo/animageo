# Temporary Plan: Pro Generation Iteration

1. Pick one target case at a time for `deepseek-v4-pro`.
2. Before each new generation and after each promotion, check the latest lab
   feedback/status exports for changed ratings, comments, or unresolved common
   issues; fold reusable findings into
   `../ai_construction_generation_context.md` before continuing.
3. Generate only the AI response/DSL first.
4. Review the DSL before accepting it:
   - check that requested geometry is actually constructed and visible;
   - check AnimaGeo DSL semantics, not just Python syntax;
   - check named objects, tuple-unpacks, helper visibility, style calls, and
     requested markings.
5. If the DSL is wrong, update `../ai_construction_generation_context.md` with
   a general reusable rule, then regenerate the same case.
6. Once the DSL is acceptable, render it into the `pro` variant, run lab
   validation, and only then move to the next case.
7. Continue until all lab cases have an acceptable `pro` variant. Work in
   small batches when useful, but still inspect generated DSL and rendered
   diagnostics before accepting each record.
