"""Import a DOCX catalogue; no model calls, downloads, or messages are sent."""
import argparse
import asyncio
import json
from pathlib import Path
from app.database import init_db
from app.services.sticker_service import parse_docx, import_catalogue

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('document', type=Path)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    rows = parse_docx(args.document)
    report = {'entries': len(rows), 'categories': sorted({r['category'] for r in rows})}
    if args.apply:
        await init_db()
        report['imported'] = await import_catalogue(rows)
    print(json.dumps(report, ensure_ascii=False))

if __name__ == '__main__':
    asyncio.run(main())
