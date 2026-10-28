# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. https://mozilla.org/MPL/2.0/
"""Read-only public-site smoke checks. No sign-ins, submissions, or user profiles."""
import json
import time
from marionette_driver import Wait, errors

SITES=(
    ('MDN','https://developer.mozilla.org/en-US/docs/Web/JavaScript','JavaScript'),
    ('GitHub','https://github.com/mozilla/gecko-dev','gecko-dev'),
    ('Wikipedia','https://en.wikipedia.org/wiki/Rust_(programming_language)','Rust'),
)


def run_public_site_checks(client, results, passed):
    client.set_context('content')
    client.timeout.page_load=60
    samples=[]
    failures=[]
    for name,url,expected in SITES:
        started=time.monotonic()
        sample={'site':name,'url':url,'status':'failed'}
        try:
            client.navigate(url)
            Wait(client,timeout=30,ignored_exceptions=(errors.JavascriptException,)).until(
                lambda c:c.execute_script("return location.protocol==='https:' && document.readyState==='complete' && document.querySelectorAll('h1,h2').length>0;"))
            state=client.execute_script("""
                return {url:location.href,title:document.title,headings:document.querySelectorAll('h1,h2').length,
                    links:document.querySelectorAll('a[href]').length,
                    forgeThemeLeaked:!!getComputedStyle(document.documentElement).getPropertyValue('--forge-accent').trim(),
                    width:document.documentElement.clientWidth};
            """)
            if expected.lower() not in state['title'].lower() or state['links']<10 or state['forgeThemeLeaked'] or state['width']<=0:
                raise AssertionError(f'Unexpected public document state: {state}')
            client.execute_script("window.scrollTo(0,Math.min(800,document.documentElement.scrollHeight));")
            sample.update(status='passed',document=state,loadAndCheckMs=round((time.monotonic()-started)*1000,2))
            label=f'{name} public HTTPS page loads, lays out and remains outside Forge theme scope'
            passed.append(label);print(f'PASS {label}',flush=True)
        except Exception as error:
            sample['error']=str(error)
            try: sample['failureDocument']=client.execute_script("return {url:location.href,title:document.title,ready:document.readyState};")
            except errors.MarionetteException: pass
            failures.append(f'{name}: {error}')
        samples.append(sample)
    (results/'public-sites-details.json').write_text(json.dumps({'samples':samples,
        'limitations':['Read-only page-load/layout checks, not long-duration compatibility or authenticated workflows',
                       'No certificate bypass, consent clicks, or account activity',
                       'Network availability and public-site changes can affect results']},indent=2)+'\n')
    client.set_context('chrome')
    return failures
