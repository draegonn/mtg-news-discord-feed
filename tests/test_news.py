import unittest
from unittest.mock import patch
import mtg_news as news


def item(title, slug):
    return {'title': title, 'url': news.SOURCE + '/' + slug}


class NewsTests(unittest.TestCase):
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


if __name__ == '__main__':
    unittest.main()
