---
name: viral
description: "Route /viral or $viral followed by a prompt to the right viral-content skills. Select and sequence research, ideation, scripting, visual direction, and learning for organic videos, YouTube, and paid ads, then complete the requested work."
---

# Viral

Treat everything after `/viral` or `$viral` as the task, using relevant conversation context. Choose the smallest useful set of skills and execute it. The user should not have to choose the internal workflow.

## Select the work

Identify the requested outcome, organic or paid objective, platform, creative format, scope, and already supplied material. Read the project's `.viral/brand-context.md` or explicitly supplied profile when present, loading only the selected brand. Preserve prior approvals, rejected topics, exact claims and locked script sections.

| What the prompt needs | Read and apply |
|---|---|
| Find sources, study creators or competitor ads, compare creative, inspect hooks/story/editing | [viral-research](../viral-research/SKILL.md) |
| Develop topics, angles, concepts or a test slate | [viral-ideate](../viral-ideate/SKILL.md) |
| Write, rewrite or critique scripts, hooks, ad bodies or speaking cards | [viral-script](../viral-script/SKILL.md) |
| Design visual hooks, shots, performance, blocking, graphics, sound or an editing handoff | [viral-direct](../viral-direct/SKILL.md) |
| Interpret actual performance or taste feedback, retain corrections, recommend the next tests | [viral-learn](../viral-learn/SKILL.md) |

Use [viral-content](../viral-content/SKILL.md) for shared doctrine or a broad brief whose creative decisions need its guidance. Read only the chosen stages and the references they need. A body-only rewrite should go directly to the scripting skill's short body procedure, without loading the whole research library.

## Combine stages when useful

- “Research these creators, develop ideas, then script the strongest” → research → ideate → script. Add direction when the requested result includes visual execution.
- “These ads got clicks but poor qualified leads; use what we learn to write new ones” → learn → ideate or script, using research only for a demonstrated evidence gap.
- “Improve this script and tell me how to film it” → script → direct. Preserve the selected premise unless changing it is requested or necessary to resolve an identified problem.
- “Remember this correction and revise the body” → learn → script. Apply the correction to its actual brand/speaker/format scope.

Carry one coherent brief through the stages: audience, objective, awareness, selected concept, hook promise, payoff, approved facts, CTA, format, assets, source IDs, and relevant feedback. Each stage consumes the previous stage's useful output. Reconcile contradictions before handing off; do not restart the brief or present disconnected answers from each skill.

Use the user's selected idea when one exists. When asked to choose the strongest and continue, make the choice and finish the downstream work. Stop for a choice only when the user requested that checkpoint or essential information is missing. Ask one focused question when needed, while continuing independent work.

For requested interviews, rendering or measured style studies, use the installed `grill-me`, `video-edit` or `video-style-study` skill respectively, following the [handoff contract](../viral-content/references/handoffs.md). Otherwise deliver the requested ideas, words or production plan. Skill routing does not authorize publication, outreach, account changes or unbounded collection.

## Deliver

Give the requested result, not merely the selected skill names or a plan to run them. Briefly explain a consequential routing choice only when useful. Preserve body-only, hook-only and other explicit boundaries. Use existing evidence before acquiring more, and keep owner preference, creator observation and actual performance distinct.
