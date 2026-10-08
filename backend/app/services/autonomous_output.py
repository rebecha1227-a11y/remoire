"""Separate authored role monologue/messages from provider reasoning.

Never reinterpret hidden thought tags as outgoing messages. This parser does
not reconstruct role prose from reasoning or mutate historical stored logs.
"""
import re


def parse_autonomous_reply(message: dict) -> tuple[str, str]:
    text = message.get('content') or ''
    if not isinstance(text, str):
        return '', ''
    text = re.sub(r'<(think|thinking)\b[^>]*>.*?</\1\s*>', '', text, flags=re.S | re.I)
    # Truncated thought/tool blocks are not user-facing output either.
    text = re.sub(r'<(?:think|thinking)\b[^>]*>.*$', '', text, flags=re.S | re.I)
    text = re.sub(r'<[｜|]+DSML[｜|]+[^>]*>.*?</[｜|]+DSML[｜|]+[^>]*>', '', text, flags=re.S)
    text = re.sub(r'<[｜|]+DSML[｜|]+[^>]*>.*$', '', text, flags=re.S)
    messages = re.findall(r'<message>(.*?)</message>', text, flags=re.S | re.I)
    monologue = re.sub(r'<message>.*?</message>', '', text, flags=re.S | re.I)
    monologue = re.sub(r'<message>.*$', '', monologue, flags=re.S | re.I)
    # The UI expects plain Chinese prose, not English analysis section labels.
    monologue = re.sub(r'\*\*[A-Za-z][A-Za-z \t]{5,80}\*\*', '', monologue)
    monologue = re.sub(r'(?m)^\s*#{1,6}\s+[A-Za-z][A-Za-z \t]{5,80}\s*$', '', monologue)
    monologue = re.sub(r'\n{3,}', '\n\n', monologue).strip()
    return '\n\n'.join(m.strip() for m in messages if m.strip()), monologue
