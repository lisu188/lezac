"""Authenticate the retained natural RAM origin without decoding its CPU corpus."""
import hashlib
import json

MANIFEST_SHA = 'dc3c9625e33cf53c8a18504a3ee465f37b525191af94cd952e9034967fbf2794'
RECIPE_SHA = '6a36df22f8fd1e20ff6e5c65f74366d04bd8f5b562b9a34857ec7221a0ef3029'
sha = lambda raw: hashlib.sha256(raw).hexdigest()


def authenticate(root):
    fixture = root / 'tests/fixtures/foreground_live'
    raw = (fixture / 'manifest.json').read_bytes()
    if sha(raw) != MANIFEST_SHA:
        raise ValueError('Frozen render-origin manifest differs')
    manifest = json.loads(raw)
    for name, digest in manifest['sources'].items():
        if sha((root / name).read_bytes()) != digest:
            raise ValueError('Frozen render-origin source differs: ' + name)
    for item in manifest['files']:
        raw = (fixture / item['name']).read_bytes()
        if len(raw) != item['bytes'] or sha(raw) != item['sha256']:
            raise ValueError('Frozen render-origin file differs: ' + item['name'])
    raw = (fixture / 'natural-recipe.json').read_bytes()
    if sha(raw) != RECIPE_SHA:
        raise ValueError('Frozen render-origin recipe differs')
    recipe = json.loads(raw)
    from original_capture_contract import read_canonical_assets
    read_canonical_assets(root)
    return recipe
