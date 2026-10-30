# LinkedIn publishing agent

Work in progress. The Telegram-only approval core and local topic/draft generation
pipeline are implemented. Live model calls have not been verified. Telegram intake,
GitHub Actions orchestration, persistent hosting storage, and LinkedIn publishing are
not connected yet. Nothing is sent or published.

## Agreed workflow

1. Suggest topics based on the owner's audience and interests in `config/editorial.json`.
2. Research and draft a personal LinkedIn post plus a concise supporting infographic.
3. Send the same version, image preview, sources, and destination list to Telegram
   with Approve, Request changes, and Reject actions.
4. Accept the first valid Telegram decision for that version. Later clicks return an
   already-closed response. Telegram buttons can be removed after a decision.
5. A change request closes that version. Incorporate the feedback in both text and
   graphic where relevant, and issue fresh approval requests for the new version.
6. Approval queues the exact approved payload for publishing to the personal profile
   and selected groups, where access is verified. Track each destination separately.

Approval covers the post, infographic, and destination list together. Changing any
of them requires a new version. Expired requests cannot approve publication.

## Implemented foundation

`agent/approvals.py` stores immutable version payloads and a hashed Telegram
single-use token in SQLite. A transaction serializes competing decisions and
creates one publishing job on approval. Correction feedback must be nonempty.

`config/editorial.json` records the owner's scope: UI frameworks (React, Solid,
Qwik, Next.js, Gatsby, Remix), native and new browser APIs, AI, UX design evolving
with AI, AI interface UX, and UI bugs/fixes. Telegram is the only approval channel.
Audience is a working assumption. All ten owner-supplied group names and normalized
URLs are recorded with publishing access explicitly unverified. The owner selected
three approval requests per week. Monday, Wednesday, and Friday at 9:00 a.m.
America/New_York are working defaults; no scheduler is active yet. Publishing
remains conditional on approval, so three requests do not guarantee three posts.

The owner's screenshot style is recorded in `docs/post-style.md` and the editorial
profile: both code walkthroughs and informational explainers, with takeaways,
restrained markers, and relevant hashtags. Optional animated GIFs are permitted
when they clarify interactions or state changes. Static visuals remain the default.
The current CLI still exports only SVG previews; animation recommendations appear
in review notes, and GIF rendering/approval previews remain to be implemented.

Freshness metadata includes a why-now angle, development date (or null when
unverified), and a source URL present in research. The initial preference is the
last 30 days. Older or undated developments get a review note; future release
dates cannot be represented as completed developments. Topic discovery can return
no proposals with a skip reason instead of manufacturing novelty. These checks
assist editorial review; they cannot prove the accuracy or appeal of a story.

`agent/content.py` uses OpenAI Responses with web search for research, then
Structured Outputs for topic proposals and drafts. It checks that generated source
URLs appeared in research output and enforces copy limits. These checks do not
prove that a source supports every claim: factual review remains necessary.

Set `OPENAI_API_KEY` and `OPENAI_MODEL` in your shell (see `.env.example`). Choose
an available model supporting web search and Structured Outputs. No model is
silently selected. Live calls incur your provider's API charges.

```sh
python3 -m agent.content suggest --output output/topics.json
python3 -m agent.content draft --topic "Native browser APIs for UI cancellation" --output output/draft-001
python3 -m agent.content draft --topic "Native browser APIs for UI cancellation" --previous output/draft-001/draft.json --feedback "Clarify browser support" --output output/draft-002
python3 -m agent.content custom --topic "My idea for a post" --notes "Focus on the UX tradeoff" --post-kind informational --output output/custom-001
```

Custom-topic requests can include repeated `--source-url` options and an optional
`--post-kind` (`auto`, `code_walkthrough`, or `informational`). They follow the
same research and preview pipeline; the request details are retained in the draft
bundle and during revisions in custom mode. Owner-supplied topics can extend
beyond the usual scope but still require factual and freshness review. Custom
requests are additional to the three weekly requests and never bypass approval.

After Telegram integration, `/topic <idea>` will submit a custom request during an
active workflow session. While Actions is idle, use **Actions → Editorial agent
session → Run workflow** and choose `custom`, then enter the topic. Actions cannot
receive a Telegram message or button click while no workflow is running. Telegram
retains uncollected updates for up to 24 hours, so don't rely on a Monday session to
receive messages sent between sessions. The CLI is currently the only implemented
custom-topic option; it does not send an approval request or publish.

Draft output includes `post.txt`, `draft.json`, `infographic.svg`, and `preview.html`.
The SVG is a vector preview; raster export and final branding still need integration
before it can be uploaded to LinkedIn. The preview is marked as a draft. Generated
bundles have a graphic hash and cannot overwrite an existing output directory.
Generation does not yet submit bundles to the approval ledger or send messages.

Run the tests with Python 3.11 or newer:

```sh
python3 -m unittest discover -s tests -v
```

The publishing job is only an outbox entry. A future worker must claim jobs
transactionally and reconcile uncertain external outcomes before retrying; a
database uniqueness constraint alone cannot guarantee one remote LinkedIn post.

## Integration requirements

- Confirm audience/voice, default weekdays/time, and branding.
- Telegram owner identity and bot token still need secure onboarding. Verify the
  owner's numeric user ID and private chat ID; a username alone is not an
  authenticated identity.
- LinkedIn application and member OAuth authorization for personal posting.
- Verify group publishing access independently. Documentation mentions group
  containers, but this does not establish access for a new application. If access
  is unavailable, agree on a manual group-posting handoff before enabling that path.
- Telegram Bot API polling during active Actions sessions, owner allowlisting,
  durable update offsets, and callback identity checks. Never approve based on a
  callback token alone.
- Shared PostgreSQL and private media storage for draft versions, Telegram update
  cursors, approvals, and publishing jobs. Actions runner files disappear after
  each run; artifacts are not the approval database.
- GitHub Actions schedule and `workflow_dispatch` modes for `scheduled`, `custom`,
  and `resume`, with a shared concurrency group and a database lease.
- HTTPS hosting, protected secrets, durable database, monitoring, and backups.
- Live generation verification, factual review, raster image export, delivery
  outboxes and retries, and connection of generated bundles to approval requests.

Tokens are bearer secrets: send only to the owner, keep them out of logs, and
authenticate the owner at the transport boundary. This module is an internal
primitive, not a public approval endpoint. Production adapters must fail closed
unless identity and request authenticity checks succeed.

## GitHub Actions deployment plan

Python 3.11 or newer is required. The current code uses only the standard library,
so no package installation is needed for the current code. No Vercel service is
needed. A GitHub-hosted runner is temporary, so use managed PostgreSQL and private
file storage (for example, Supabase) to resume approvals across runs.

Add `.github/workflows/editorial-agent.yml` on the repository's default branch with:

- A `schedule` for Monday, Wednesday, and Friday at 9:00 a.m. in
  `America/New_York`.
- `workflow_dispatch` inputs: `mode` (`scheduled`, `custom`, `resume`), `topic`,
  and `draft_id`.
- A single concurrency group with `cancel-in-progress: false`, a reviewed
  `timeout-minutes`, and only the repository permissions the job needs.
- A Python environment, then `python -m agent.session`. That coordinator does not
  exist yet; the current CLI alone cannot poll Telegram, restore drafts, or publish.

Set required values in **GitHub → repository → Settings → Secrets and variables →
Actions** after implementing the coordinator: `OPENAI_API_KEY`, `OPENAI_MODEL`,
`TELEGRAM_BOT_TOKEN`, `TELEGRAM_OWNER_ID`, `TELEGRAM_CHAT_ID`, the database URL and
service credential, private storage credentials, and LinkedIn OAuth credentials.
Never put their values in workflow YAML or commit them. Use dry-run mode first,
then verify one Telegram approval and personal-profile post before enabling the
weekly schedule. Group posting remains gated on LinkedIn access verification.

GitHub Actions can send Telegram messages and poll button clicks only while a run
is active. `/topic` works during that session; when Actions is idle, start a
custom run from the Actions tab. Telegram cannot wake an idle workflow without a
separate always-on receiver. Set a session timeout so an unanswered approval saves
as pending and exits. Resume it manually to reopen a short review session.

GitHub supports an IANA timezone on scheduled workflows, but runs can still be
delayed under load. Configure the local time as a target rather than a guarantee.
Custom topic and resume requests are additional to the three weekly sessions.
Actions and hosting limits apply, and model API usage may cost money.

Local contacts, `.env` files, databases, generated output, and Python caches are
excluded from Git. Keep credentials in repository Actions secrets.

## References

- [LinkedIn personal sharing](https://learn.microsoft.com/linkedin/consumer/integrations/self-serve/share-on-linkedin)
- [LinkedIn Posts API](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api)
- [LinkedIn post schema](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/post-api-schema)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [OpenAI web search](https://developers.openai.com/api/docs/guides/tools-web-search)
