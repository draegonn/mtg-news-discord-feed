import copy
import json
import unittest
from unittest.mock import patch
import mtg_news as news


def item(title, slug):
    return {'title': title, 'url': news.SOURCE + '/' + slug}


class NewsTests(unittest.TestCase):
    def setUp(self):
        self.env_patch = patch.dict(news.os.environ, {}, clear=True)
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)

    def test_parser(self):
        p = news.Announcements()
        p.feed('<a href="/en/news/announcements">Announcements</a>'
               '<a href="/en/news/announcements/one"><img src="x"></a>'
               '<a href="/en/news/announcements/one"><h3>Secret Lair &amp; More</h3></a>'
               '<a href="https://evil.example/en/news/announcements/two">No</a>')
        self.assertEqual(list(p.items.values()), [item('Secret Lair & More', 'one')])

    def test_chaos_vault_routing(self):
        self.assertEqual(news.route('Chaos Vault: New Drop'), 'secret_lair')
        self.assertEqual(news.route('Introducing CHAOS VAULT'), 'secret_lair')
        self.assertEqual(news.route('New booster announcement'), 'general')

    def test_initialization(self):
        state = {}
        with patch.object(news, 'save'), patch.object(news, 'post') as post:
            news.run([item('Old', 'old')], state)
        post.assert_not_called()
        self.assertEqual(state['pending'], [])

    def test_routing_and_deduplication(self):
        state = {'seen': [], 'pending': []}
        items = [item('SECRET LAIR drop', 'lair'), item('God packs', 'packs')]
        with patch.object(news, 'save'), patch.object(news, 'post') as post, patch.dict(
            news.os.environ, {'MTG_WEBHOOK': 'general', 'SECRET_LAIR_WEBHOOK': 'lair'}):
            news.run(items, state)
            self.assertEqual(post.call_count, 2)
            self.assertEqual(post.call_args_list[0].args[0], 'general')
            self.assertEqual(post.call_args_list[1].args[0], 'lair')
            news.run(items, state)
            self.assertEqual(post.call_count, 2)

    def test_partial_failure(self):
        state = {'seen': [], 'pending': []}
        items = [item('Secret Lair', 'lair'), item('New set', 'set')]
        with patch.object(news, 'save'), patch.object(news, 'post', side_effect=[None, RuntimeError('failure')]), patch.dict(
            news.os.environ, {'MTG_WEBHOOK': 'general', 'SECRET_LAIR_WEBHOOK': 'lair'}):
            self.assertEqual(news.run(items, state), 1)
        self.assertEqual(state['pending'], [items[0]])

    def extra_config(self):
        return {'id': 'friends',
                'mtg_webhook': 'https://discord.com/api/webhooks/extra/general',
                'secret_lair_webhook': 'https://discord.com/api/webhooks/extra/lair'}

    def test_upgrade_preserves_seen_and_pending_without_replay(self):
        old, queued = item('Old', 'old'), item('Chaos Vault', 'queued')
        state = {'seen': [old['url'], queued['url']], 'pending': [queued]}
        with patch.object(news, 'save'), patch.object(news, 'post') as post, patch.dict(
                news.os.environ, {'MTG_WEBHOOK': 'general', 'SECRET_LAIR_WEBHOOK': 'lair'}):
            news.run([old, queued], state)
        self.assertEqual(post.call_count, 1)
        self.assertEqual(post.call_args.args[1], queued)
        self.assertEqual(state, {'seen': [old['url'], queued['url']], 'pending': []})

    def test_new_server_baseline_then_both_receive_new_articles(self):
        old, new = item('Old', 'old'), item('CHAOS VAULT', 'new')
        state = {'seen': [old['url']], 'pending': []}
        extra = self.extra_config()
        env = {'MTG_WEBHOOK': 'general', 'SECRET_LAIR_WEBHOOK': 'lair',
               'EXTRA_SERVERS_JSON': json.dumps([extra])}
        with patch.object(news, 'save'), patch.object(news, 'post') as post, patch.dict(news.os.environ, env):
            news.run([old], state)
            post.assert_not_called()
            news.run([new, old], state)
            self.assertEqual([c.args[0] for c in post.call_args_list], ['lair', extra['secret_lair_webhook']])
            news.run([new, old], state)
            self.assertEqual(post.call_count, 2)

    def test_one_server_failure_does_not_repost_successful_server(self):
        article = item('New set', 'new')
        state = {'seen': [], 'pending': [], 'servers': {'friends': {'seen': [], 'pending': []}}}
        extra = self.extra_config()
        env = {'MTG_WEBHOOK': 'general', 'SECRET_LAIR_WEBHOOK': 'lair',
               'EXTRA_SERVERS_JSON': json.dumps([extra])}
        def deliver(url, article, label):
            if url == 'general':
                raise RuntimeError('temporary failure')
        with patch.object(news, 'save'), patch.object(news, 'post', side_effect=deliver) as post, patch.dict(news.os.environ, env):
            self.assertEqual(news.run([article], state), 1)
            self.assertEqual(post.call_count, 2)
            self.assertEqual(state['pending'], [article])
            self.assertEqual(state['servers']['friends']['pending'], [])
            post.reset_mock(side_effect=True)
            self.assertEqual(news.run([article], state), 0)
            self.assertEqual(post.call_count, 1)
            self.assertEqual(post.call_args.args[0], 'general')

    def test_invalid_extra_config_does_not_modify_history_or_send(self):
        state = {'seen': [], 'pending': []}
        original = copy.deepcopy(state)
        with patch.object(news, 'save') as save, patch.object(news, 'post') as post, patch.dict(
                news.os.environ, {'EXTRA_SERVERS_JSON': '[invalid'}):
            with self.assertRaises(RuntimeError):
                news.run([item('New', 'new')], state)
        self.assertEqual(state, original)
        post.assert_not_called()
        save.assert_not_called()

    def test_plain_url_preview_payload(self):
        article = item('Example', 'example')
        with patch.object(news, 'urlopen') as send:
            news.post('https://discord.com/api/webhooks/test/test', article, 'MTG')
        self.assertEqual(json.loads(send.call_args.args[0].data), {
            'content': article['url'], 'allowed_mentions': {'parse': []}})


if __name__ == '__main__':
    unittest.main()
