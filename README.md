# Free MTG announcements for Discord

Checks Wizards' announcements page every 30 minutes and posts each new title
with its official link. Titles containing "Secret Lair" or "Chaos Vault" (case-insensitive) go
into a separate channel. All other announcements go to `#mtg`.
Posts use a plain URL so Discord can generate the article's native preview
(description and image, when available). Preview rendering is controlled by
Discord and the website's metadata.
No Python packages, paid services, or AI needed.

## Setup

1. Create Discord channels `#mtg` and `#secret-lair`.
2. For each channel, open **Edit Channel → Integrations → Webhooks → New Webhook**.
   Select that channel and copy its webhook URL.
3. Create a **public** GitHub repository. Standard hosted Actions runners are
   free in public repositories. Upload `mtg_news.py` and this README at its root.
   GitHub's web uploader may omit hidden folders: use **Add file → Create new
   file**, name it `.github/workflows/mtg-news.yml`, and paste the included
   workflow's contents. Commit to the default branch.
4. Open **Settings → Secrets and variables → Actions → New repository secret**:
   - `MTG_WEBHOOK`: `#mtg` channel's webhook URL.
   - `SECRET_LAIR_WEBHOOK`: Secret Lair channel's webhook URL.
   Keep URLs in secrets, never in the public code.
5. Open **Actions → MTG announcements → Run workflow** once.
   This initializes `state.json`, marking existing headlines as seen so it
   doesn't flood your channels with old posts. Check that the run succeeds
   and reports a nonzero number of existing announcements.

Future announcements post on the next check. GitHub scheduling can delay runs;
this is near-real-time polling, not instant delivery.

## Upgrade an existing installation

Replace `mtg_news.py` and `.github/workflows/mtg-news.yml`, then commit and push.
Keep your existing `state.json`, `MTG_WEBHOOK`, and `SECRET_LAIR_WEBHOOK` secrets.
The original server continues working without any configuration changes or
history reset. The plain-URL previews and Chaos Vault routing are included.

## Add more servers (optional)

Create the two channels and webhooks in each additional Discord server. In
your existing GitHub repository, add one Actions secret named
`EXTRA_SERVERS_JSON` containing an array like this:

```json
[
  {
    "id": "friends",
    "mtg_webhook": "https://discord.com/api/webhooks/REPLACE_WITH_MTG_WEBHOOK",
    "secret_lair_webhook": "https://discord.com/api/webhooks/REPLACE_WITH_SECRET_LAIR_WEBHOOK"
  },
  {
    "id": "game-club",
    "mtg_webhook": "https://discord.com/api/webhooks/REPLACE_WITH_MTG_WEBHOOK",
    "secret_lair_webhook": "https://discord.com/api/webhooks/REPLACE_WITH_SECRET_LAIR_WEBHOOK"
  }
]
```

Use the full copied webhook URLs in place of those examples. Delete the second
object if adding only one server. Don't include the original server here;
it still uses the two existing secrets. Each extra server needs its own pair
of webhooks. Never paste the real JSON into a public repository file.

The `id` is a nickname you choose, not a Discord server ID. Keep it stable;
it connects that server to its delivery history. Updating a webhook URL under
the same ID preserves that history. Reusing an ID for a different server also
reuses its history, so use a new ID for a genuinely new server.

Run the workflow once after adding a server. Its first run marks currently
visible headlines as seen, then future posts arrive automatically. To test an
extra server, remove one URL from `servers.<id>.seen` inside `state.json` and
run the workflow again. The original server still uses the top-level `seen`.

Each server has its own queue. Successful deliveries are removed only from
that server's queue; failures elsewhere do not cause repeats there. Removing
a server from the secret stops its posts but retains its saved history. Re-adding
the same ID resumes any queued messages and discovers currently visible new
articles; articles that left the source page while disabled may be missed.

Leaving `EXTRA_SERVERS_JSON` absent, blank, or `[]` uses just the original server.
Malformed extra-server JSON fails visibly before sending or changing history.

## Test a current article

After initialization, edit `state.json` and remove one article URL from `seen`.
Run the workflow manually; that article should post to its matching channel.
Repeat with one Secret Lair and one general article if desired.

## Limits and maintenance

- Routing examines only titles. Articles about Secret Lair without either phrase
  in the title stay in `#mtg`.
- Existing URLs aren't posted again when their contents change.
- Failed deliveries stay queued. Rate limits stop that channel's batch until
  the next run. Other channel deliveries can proceed.
- No role/everyone mentions; mute either channel independently.
- Discord sends and GitHub commits cannot be one transaction. A crash, timeout,
  or failed push after sending can cause a repeat. Check the channel before
  manually retrying ambiguous delivery failures.
- Reads headlines in the page's HTML. Layout changes or articles disappearing
  between checks can cause misses. Zero headlines produce a visible failure
  instead of resetting history. Verify the first live run against the page;
  live access wasn't available during creation.
- Use a dedicated repository without branch protection preventing bot commits.
- GitHub may disable schedules after 60 days of repository inactivity. New
  announcement commits normally provide activity. If it stops, open Actions
  and re-enable the workflow. Enable GitHub Actions failure notifications.

## Local preview / tests

Requires Python 3.10+; uses only the standard library.

```sh
python mtg_news.py --dry-run
python -m unittest discover -s tests
```

Dry run fetches the page but neither writes state nor posts.

References:
- https://magic.wizards.com/en/news/announcements
- https://docs.github.com/en/actions/concepts/billing-and-usage
- https://support.discord.com/hc/en-us/articles/228383668-Intro-to-Webhooks
