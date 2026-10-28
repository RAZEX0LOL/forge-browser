from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import re
import unittest
from urllib.parse import urlparse

SITE = Path(__file__).resolve().parents[1] / 'site'


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.tags = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


class SiteTests(unittest.TestCase):
    def test_downloads_match_unique_manifest_entries_and_checksums(self):
        manifest = json.loads((SITE / 'downloads.json').read_text())
        builds = manifest['builds']
        targets = {b['target']: b for b in builds}
        self.assertEqual(len(targets), 11)
        self.assertEqual(len({b['file'] for b in builds}), 11)
        links = [attrs for tag, attrs in Page((SITE / 'index.html').read_text()).tags
                 if tag == 'a' and 'data-target' in attrs]
        self.assertEqual({a['data-target'] for a in links}, set(targets))
        for link in links:
            build = targets[link['data-target']]
            self.assertEqual(link['href'], build['url'])
            self.assertRegex(build['sha256'], r'^[a-f0-9]{64}$')
            self.assertRegex(build['sourceCommit'], r'^[a-f0-9]{40}$')
            self.assertGreater(build['bytes'], 0)
            self.assertEqual(Path(urlparse(build['url']).path).name, build['file'])
        checksums = dict(line.split('  ', 1)[::-1] for line in (SITE / 'SHA256SUMS').read_text().splitlines())
        for build in builds:
            self.assertEqual(checksums[build['file']], build['sha256'])
        self.assertEqual(checksums['downloads.json'], hashlib.sha256((SITE / 'downloads.json').read_bytes()).hexdigest())

    def test_site_has_no_remote_passive_resources_inline_scripts_or_forms(self):
        for name in ('index.html', 'privacy.html'):
            page = Page((SITE / name).read_text())
            self.assertEqual(next(a['lang'] for t, a in page.tags if t == 'html'), 'ru')
            ids = [a['id'] for _, a in page.tags if 'id' in a]
            self.assertEqual(len(ids), len(set(ids)))
            self.assertFalse(any(t == 'form' for t, _ in page.tags))
            for tag, attrs in page.tags:
                self.assertFalse(any(k.startswith('on') or k == 'style' for k in attrs))
                if tag == 'script':
                    self.assertTrue(attrs.get('src'))
                if tag in ('script', 'img', 'iframe', 'video', 'audio', 'source') or (tag == 'link' and attrs.get('rel') != 'canonical'):
                    resource = attrs.get('src') or attrs.get('href')
                    if resource:
                        self.assertFalse(urlparse(resource).scheme)
                        self.assertTrue((SITE / resource).is_file(), resource)
        script = (SITE / 'site.js').read_text()
        self.assertNotRegex(script, r'\b(fetch|XMLHttpRequest|sendBeacon|localStorage|sessionStorage|cookie)\b')

    def test_platform_controls_are_accessible_and_limitations_remain_visible(self):
        text = (SITE / 'index.html').read_text()
        tags = Page(text).tags
        controls = [a for t, a in tags if t == 'button' and 'data-platform' in a]
        panels = [a for _, a in tags if 'data-panel' in a]
        self.assertEqual({a['data-platform'] for a in controls}, {'macos', 'windows', 'linux', 'mobile'})
        self.assertTrue(all('aria-pressed' in a for a in controls))
        self.assertTrue(all('hidden' not in a for a in panels))
        self.assertIn('Автоматического сервиса обновлений безопасности пока нет', text)
        self.assertIn('После подписи требуется повторный тест на Intel Mac', text)
        self.assertIn('Открытой ссылки на TestFlight пока нет', text)
        self.assertFalse(any('testflight.apple.com/join/' in a.get('href', '') for _, a in tags))
        self.assertIn('prefers-reduced-motion', (SITE / 'styles.css').read_text())

    def test_nginx_only_adds_scoped_static_routes_and_security_headers(self):
        config = (SITE / 'nginx-location.conf').read_text()
        self.assertEqual(len(re.findall(r'^location ', config, re.M)), 4)
        self.assertIn('location = /robots.txt', config)
        self.assertIn('Sitemap: https://razex.shop/forge/sitemap.xml', (SITE / 'robots.txt').read_text())
        self.assertIn("script-src 'self'", config)
        self.assertIn("connect-src 'none'", config)
        self.assertIn('X-Content-Type-Options "nosniff"', config)
        self.assertNotIn('ssl_verify', config)
        self.assertNotIn('proxy_pass', config)
