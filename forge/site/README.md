# Forge landing page

Dependency-free Russian landing page for `https://razex.shop/forge/`.
HTML download links work without JavaScript. The small script only filters
platform panels using browser-provided platform strings; it does not fetch,
store data, send analytics or start downloads automatically.

`assets/forge-desktop.webp` is a real headless chrome screenshot of the signed
Apple Silicon app, captured with an isolated temporary profile and local pages.
The feature-card graphics are schematic illustrations, not screenshots.

`downloads.json` records exact artifact source commits, hashes and limitations.
`SHA256SUMS` covers the linked packages plus the download manifest. The macOS
downloads are the newly Developer ID signed and notarized ZIPs, not the older
ad-hoc release packages. Never overwrite an existing filename with different
bytes. Intel post-signing runtime validation is explicitly not claimed.

## Preview

```sh
python3 -m http.server 8765 --bind 127.0.0.1 --directory forge/site
```

Download ZIPs are not stored in Git. To test their paths locally, provide a
separate test server or use the deployed range/HEAD checks. Do not add personal
profiles, credentials, `.p8`, IPA/provisioning data or signing logs to this site.

## Deployment layout

The existing Nginx `razex.shop` HTTPS server includes `nginx-location.conf` via
`/etc/nginx/snippets/forge-site.conf`. This only adds `/forge` routes; Matrix
well-known routes and existing sites stay untouched. The previously undefined
domain-level `/robots.txt` gets a valid policy pointing to the Forge sitemap.
No DNS, firewall, TLS
verification, OS trust settings or app services need to be changed.

```
/var/www/forge-site/
  current -> releases/<release>/
  releases/<release>/forge/
    index.html, styles.css, site.js, privacy.html, downloads.json, SHA256SUMS
    robots.txt, sitemap.xml
    assets/
    downloads -> /var/www/forge-site/downloads/
  downloads/<immutable notarized ZIPs>
```

Deploy only the listed static files and assets, not this README or Nginx config.
Verify package hashes before exposing them. Back up the existing Nginx config
before adding the single include, run `nginx -t`, then reload rather than restart.
Activate a fully verified release with an atomic `current` symlink replacement.
After reloading Nginx, wait for a content/hash readiness check before judging the
new route: a successful reload signal can precede worker configuration activation.
Rollback means pointing that symlink to the previous retained release; for an
initial deployment, remove only the newly added include and reload after testing.
Keep backups and pre-existing files; do not delete unrelated server content.

TestFlight status is dated in the manifest and manually updated. No public
TestFlight link exists while the external build awaits review; developer archives
are not offered as installable iPhone IPAs. Do not publish private App Store
Connect links or contact information as download links.
