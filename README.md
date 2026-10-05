# MTG News → Discord

Forwards new [official MTG announcements](https://magic.wizards.com/en/news/announcements) to Discord as links with native previews. GitHub Actions checks hourly at :07; runs may be delayed.

Titles containing **Secret Lair** or **Chaos Vault** route to the Secret Lair webhook. All other titles route to the general webhook. Matching is case-insensitive. Channel names are unrestricted; both routes can use the same webhook.

## Setup

1. Create Discord webhooks under **Channel Settings → Integrations → Webhooks**.
2. Add the repository files to a public GitHub repository, including `.github/workflows/mtg-news.yml`, on its default branch.
3. Under **Settings → Secrets and variables → Actions**, add:

   | Secret | Destination |
   | --- | --- |
   | `MTG_WEBHOOK` | General announcements |
   | `SECRET_LAIR_WEBHOOK` | Secret Lair / Chaos Vault |

4. Select **Actions → MTG announcements → Run workflow**.

The first run records existing articles without posting. Subsequent runs forward new articles. Keep `state.json` during updates and allow the workflow to commit changes to it.

## Additional servers

Add an optional `EXTRA_SERVERS_JSON` Actions secret:

```json
[
  {
    "id": "second-server",
    "mtg_webhook": "https://discord.com/api/webhooks/ID/TOKEN",
    "secret_lair_webhook": "https://discord.com/api/webhooks/ID/TOKEN"
  }
]
```

Replace the example URLs. Add one object per extra server; keep each `id` unique and stable. The original server continues using the two separate secrets. Each server maintains independent delivery history and skips existing articles on initialization.

## Testing

After initialization, remove one article URL from `state.json` → `seen`, then run the workflow manually. Extra servers use `servers` → `<id>` → `seen`.

```sh
python mtg_news.py --dry-run
python -m unittest discover -s tests
```

Python 3.10+; standard library only. Dry runs neither post nor save state.

## Limitations

Failed deliveries remain queued. Delivery interruptions can occasionally cause duplicates. Website changes can interrupt collection. GitHub may disable scheduled workflows after 60 days of repository inactivity; check Actions for failures or disabled schedules.
