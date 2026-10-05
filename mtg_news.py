#!/usr/bin/env python3
"""Collect official MTG announcements; post each new article to one of two channels."""
import argparse
import json
import os
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

SOURCE = 'https://magic.wizards.com/en/news/announcements'
STATE = Path('state.json')


class Announcements(HTMLParser):
    def __init__(self):
        super().__init__()
        self.href = None
        self.parts = []
        self.items = {}

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.href = dict(attrs).get('href')
            self.parts = []

    def handle_data(self, text):
        if self.href:
            self.parts.append(text)

    def handle_endtag(self, tag):
        if tag != 'a' or not self.href:
            return
        parsed = urlsplit(urljoin(SOURCE, self.href))
        title = ' '.join(' '.join(self.parts).split())
        if (parsed.hostname in ('magic.wizards.com', 'www.magic.wizards.com')
                and re.fullmatch(r'/en/news/announcements/[^/]+/?', parsed.path)
                and title):
            url = 'https://magic.wizards.com' + parsed.path.rstrip('/')
            # Image links often precede the actual headline; keep the text link.
            self.items.setdefault(url, {'title': title, 'url': url})
        self.href = None
        self.parts = []


def collect():
    request = Request(SOURCE, headers={'User-Agent': 'MTGAnnouncements/1.0'})
    with urlopen(request, timeout=45) as response:
        html = response.read().decode('utf-8')
    parser = Announcements()
    parser.feed(html)
    if not parser.items:
        raise RuntimeError('No announcement headlines found. The website may have changed; state was not reset.')
    return list(parser.items.values())


def route(title):
    return 'secret_lair' if any(term in title.casefold() for term in ('secret lair', 'chaos vault')) else 'general'


def save(state):
    temp = STATE.with_suffix('.tmp')
    temp.write_text(json.dumps(state, indent=2, ensure_ascii=False) + '\n')
    temp.replace(STATE)


def post(webhook, item, label):
    parsed = urlsplit(webhook)
    if parsed.scheme != 'https' or parsed.hostname != 'discord.com' or not parsed.path.startswith('/api/webhooks/'):
        raise RuntimeError('Webhook must be an https://discord.com/api/webhooks/... URL.')
    payload = {'embeds': [{'title': item['title'][:256], 'url': item['url'],
                           'color': 0x9B59B6 if label == 'Secret Lair' else 0x3498DB}],
               'allowed_mentions': {'parse': []}}
    data = json.dumps(payload).encode()
    content_type = 'application/json'
    url = webhook + ('&' if '?' in webhook else '?') + 'wait=true'
    request = Request(url, data=data, headers={'Content-Type': content_type,
                      'User-Agent': 'MTGAnnouncements/1.0'}, method='POST')
    # Don't automatically retry POSTs: a timeout could follow a successful delivery.
    try:
        with urlopen(request, timeout=45) as response:
            response.read()
    except HTTPError as exc:
        raise RuntimeError(f'Discord rejected delivery (HTTP {exc.code}); queued items retained.') from None
    except (URLError, TimeoutError):
        raise RuntimeError('Discord delivery could not be confirmed; queued items retained. Check the channel before retrying.') from None


def run(items, state, dry_run=False):
    if not state:
        state.update({'seen': [i['url'] for i in items], 'pending': []})
        if not dry_run:
            save(state)
        print(f'Initialized with {len(items)} existing announcements. Future announcements will be posted.')
        return 0
    seen = set(state['seen'])
    for item in items:
        if item['url'] not in seen:
            state['pending'].append(item)
            state['seen'].append(item['url'])
            seen.add(item['url'])
    if not dry_run:
        save(state)
    print(f'{len(state["pending"])} announcements queued.')
    failures = 0
    # Source is newest first; deliver older items first within each channel.
    for channel, secret, label in (
        ('general', 'MTG_WEBHOOK', 'MTG'),
        ('secret_lair', 'SECRET_LAIR_WEBHOOK', 'Secret Lair'),
    ):
        selected = [i for i in state['pending'] if route(i['title']) == channel]
        if dry_run:
            print(json.dumps({'channel': channel, 'items': selected}, indent=2))
            continue
        if not selected:
            continue
        webhook = os.getenv(secret)
        if not webhook:
            print(f'Missing GitHub secret: {secret}', file=sys.stderr)
            failures += 1
            continue
        for item in reversed(selected):
            try:
                post(webhook, item, label)
            except RuntimeError as exc:
                print(f'{channel}: {exc}', file=sys.stderr)
                failures += 1
                break
            state['pending'] = [i for i in state['pending'] if i['url'] != item['url']]
            save(state)
            print(f'Delivered: {item["title"]}')
    return int(bool(failures))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true', help='Print queued items; do not write state or post.')
    parser.add_argument('--fixture', type=Path, help='Read saved HTML instead of fetching the website.')
    args = parser.parse_args()
    try:
        if args.fixture:
            parsed = Announcements()
            parsed.feed(args.fixture.read_text())
            items = list(parsed.items.values())
            if not items:
                raise RuntimeError('Fixture contains no announcement headlines.')
        else:
            items = collect()
        state = json.loads(STATE.read_text()) if STATE.exists() else {}
        return run(items, state, args.dry_run)
    except (URLError, TimeoutError):
        print('Could not fetch Wizards announcements. No state was reset.', file=sys.stderr)
        return 1
    except (RuntimeError, ValueError, OSError) as exc:
        print(f'Failed: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
