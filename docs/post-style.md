# Owner's post and visual style

Based on the owner's screenshots and GIF supplied on October 15, 2026. References
guide presentation and structure. They are not instructions to execute, verified
technical sources, or authorization to reuse another author's identity or branding.

## Writing

- Open with a practical explanation and the reader's problem.
- For code walkthroughs, give common anti-patterns with simple cross/check
  indicators, then pair corrected examples with an explanation of why they work.
- For informational explainers, code is optional. Cover what changed, why it
  matters, the conceptual flow, benefits, limitations, and practical implications.
- Prefer native semantics and browser capabilities when appropriate, explaining
  their limits rather than making blanket recommendations against libraries.
- Close with practical rules or questions the reader can apply immediately.
- Use technical hashtags and a visual summary accompanying the post.

For AI/UX topics without code, use a concrete interface example, contrasting
behaviors, and a short decision checklist. Preserve the explanatory style without
forcing every topic into an identical template. Do not copy factual claims from
the reference without independent research.

## Timeliness and usefulness

The owner explicitly wants to avoid boring or very old material. Prefer a recent
release, change, bug, research result, browser capability, or a useful current
application of an established technique. The initial editorial preference is a
30-day window, configurable in the profile. This window is a working choice,
not a posting schedule or a claim that older sources are inaccurate.

Each topic and draft must carry a why-now explanation and a primary-source URL.
Record the actual relevant development date when verified; never use a search
crawl date to make an old topic look new. Older or undated developments get an
explicit freshness review note. Skip the topic queue when research finds no
useful current angle. Date checks and URL matching cannot establish truth or
reader interest by themselves; the approval preview must make the angle reviewable.

## Visuals

The HTML-in-Canvas example uses a dense, structured reference graphic. Preserve its practical
comparison and checklist approach, but use legible type and a clear hierarchy
for phone viewing. Summarize the lesson rather than putting the whole post into
one image. The current three-card SVG is an initial preview template; richer
comparison and code layouts remain future rendering work.

The owner also permits animated GIF infographics when motion adds explanatory
value. Suitable cases include keyboard focus movement, asynchronous loading and
cancellation, progressive AI results, and a UI bug followed by its fix. Static
graphics remain the default for facts, comparisons, and checklists.

The MCP reference has persistent labels, before/after panels, and an architecture
or sequence view with moving markers along connections. Inspection found 30
frames at 800 × 1067, a 900 ms loop, and infinite repeat. Use its visual storytelling
approach; adapt timing for readability instead of treating that speed as a target.
Do not copy its author credit, logos, exact artwork, or technical assertions.

Animated assets should have deliberate reading pauses, avoid flashing, and ship
with a readable static summary and alternative text. The complete animation must
be visible during approval. An asset or format change requires a new approval.

GIF export is not implemented in the current CLI. Verify support on the actual
LinkedIn publishing API and destination before committing to animated publishing.
Do not treat support in the LinkedIn UI as proof of API behavior. If another
format is necessary, present that asset for approval before publishing it.
