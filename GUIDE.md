# Migrate a documentation route inventory

Supply lists of old and new paths with their page titles. New pages can list previously published addresses in aliases. Paths must be literal site-root paths. The importer normalizes a trailing slash and rejects external addresses, query strings and relative traversal. Split large sites into documentation sections before comparing them.

An old path that still exists requires no redirect. A declared alias takes precedence over fuzzy title and path comparison. When two new pages claim the same address, both appear for review. For remaining legacy pages the tool proposes at most three destinations based on weighted title and path similarity. A similar title may cover a materially different feature, so compare the underlying pages before accepting.

Approve one destination per old address. The _redirects file is compatible with static hosts that accept three-column path, target and status rules. The accompanying CSV retains every retired route without an approved replacement. Multiple old paths may legitimately point to the same active article.
