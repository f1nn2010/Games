#!/usr/bin/env python3
"""Import an authorized CSV metadata export, not game content.

Accepted columns: title,embed_url,game_id,catalog_url,icon_url,rank.
`rank` means an independently established official rank, NOT CSV row number.
"""
import argparse
import csv
import json
import re
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / 'games.json'
GAME_ID = re.compile(r'(?i)(?:https://html5\.gamedistribution\.com/)?([a-f0-9]{32})(?:/|\?|$)')

def slugify(text):
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')

def https_url(value, allowed_hosts=None):
    if not value:
        return None
    parsed = urlparse(value.strip())
    if parsed.scheme != 'https' or not parsed.hostname:
        raise ValueError(f'Only HTTPS URLs are supported: {value!r}')
    if allowed_hosts is not None and parsed.hostname not in allowed_hosts:
        raise ValueError(f'Unexpected domain: {parsed.hostname}')
    return value.strip()

def import_rows(input_path, max_games=1000):
    existing = json.loads(TARGET.read_text(encoding='utf-8')) if TARGET.exists() else []
    by_slug = {slugify(item['title']): item for item in existing}
    counters = dict(added=0, updated=0, skipped=0)
    with open(input_path, encoding='utf-8-sig', newline='') as source:
        for row in csv.DictReader(source):
            title = (row.get('title') or row.get('name') or '').strip()
            if not title:
                counters['skipped'] += 1
                continue
            key = slugify(title)
            if not key:
                counters['skipped'] += 1
                continue
            data = by_slug.get(key)
            if data is None:
                if len(by_slug) >= max_games:
                    counters['skipped'] += 1
                    continue
                data = dict(id=len(by_slug)+1, title=title, slug=key, selection='additional-selection', top50_position=None,
                            game_id=None, embed_url=None, icon_url=None,
                            catalog_url='https://gamedistribution.com/games/', catalog_url_verified=False,
                            width=800, height=600)
                by_slug[key] = data
                counters['added'] += 1
            else:
                counters['updated'] += 1
            url = (row.get('embed_url') or row.get('game_url') or '').strip()
            game_id = (row.get('game_id') or '').strip()
            if url:
                url = https_url(url, {'html5.gamedistribution.com'})
                m = GAME_ID.search(url)
                if not m:
                    raise ValueError(f'Invalid GD embed for {title}: {url}')
                data['embed_url'] = url
                data['game_id'] = m.group(1).lower()
            elif game_id:
                if not re.fullmatch('[a-fA-F0-9]{32}',game_id):
                    raise ValueError(f'Invalid GD game_id for {title}')
                data['game_id'] = game_id.lower()
            if row.get('catalog_url'):
                data['catalog_url'] = https_url(row['catalog_url'], {'gamedistribution.com','www.gamedistribution.com'})
                data['catalog_url_verified'] = True
            if row.get('icon_url'):
                data['icon_url'] = https_url(row['icon_url'])
            if row.get('width'):
                data['width'] = max(200,int(row['width']))
            if row.get('height'):
                data['height'] = max(200,int(row['height']))
            # Rank is used ONLY for independently verified official Top 50 positions.
            if row.get('rank'):
                rank = int(row['rank'])
                if 1 <= rank <= 50 and data.get('selection') == 'official-top-50':
                    data['top50_position'] = rank
    ordered = list(by_slug.values())[:max_games]
    for i, game in enumerate(ordered, 1):
        game['id']=i
    TARGET.write_text(json.dumps(ordered,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f"Import complete. {len(ordered)} catalogue entries. Added {counters['added']}; updated {counters['updated']}; skipped {counters['skipped']}.")
    print(f"Embeds available: {sum(bool(g.get('game_id')) for g in ordered)}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Import authorized GameDistribution game metadata; never downloads game files.')
    parser.add_argument('csv_file',type=Path)
    parser.add_argument('--max-games',type=int,default=1000)
    args=parser.parse_args()
    if not 1 <= args.max_games <= 10000:parser.error('--max-games must be 1 to 10000')
    import_rows(args.csv_file,args.max_games)