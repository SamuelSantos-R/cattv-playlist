#!/usr/bin/env python3
"""Gera playlist/br.m3u só com canais que estão realmente no ar.

A lista pública do iptv-org não é podada: mais da metade das entradas aponta
pra servidor morto, e o app não tem como saber sem tentar tocar. Aqui cada
stream é baixado de verdade e só passa quem devolve um manifesto HLS.
"""

import concurrent.futures as futures
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

API = "https://iptv-org.github.io/api"
COUNTRY = "br"
# O que a AVFoundation manda no Apple TV. Alguns CDNs recusam curl/python.
DEFAULT_UA = "AppleCoreMedia/1.0.0 (Apple TV; U; CPU OS 16_0 like Mac OS X)"
TIMEOUT = 10
WORKERS = 32
OUT = Path(__file__).resolve().parent.parent / "playlist" / "br.m3u"

GROUPS = {
    "animation": "Animação", "business": "Negócios", "classic": "Clássicos",
    "comedy": "Comédia", "cooking": "Culinária", "culture": "Cultura",
    "documentary": "Documentários", "education": "Educação",
    "entertainment": "Entretenimento", "family": "Família", "general": "Geral",
    "kids": "Infantil", "legislative": "Legislativo", "lifestyle": "Estilo de Vida",
    "movies": "Filmes", "music": "Música", "news": "Notícias", "outdoor": "Aventura",
    "public": "Público", "relax": "Relax", "religious": "Religioso",
    "science": "Ciência", "series": "Séries", "shop": "Compras", "sports": "Esportes",
    "travel": "Viagem", "weather": "Clima",
}


def fetch_json(name):
    # curl e não urllib: o python do Homebrew não vem com CA bundle.
    r = subprocess.run(["curl", "-sfL", "-m", "60", f"{API}/{name}.json"],
                       capture_output=True, text=True, timeout=90)
    r.check_returncode()
    return json.loads(r.stdout)


def quality_rank(stream):
    raw = (stream.get("quality") or "").rstrip("pi")
    try:
        return int(raw)
    except ValueError:
        return 0


def is_alive(stream):
    """Baixa o começo do manifesto. 200 não basta: portal caído responde 200 em HTML."""
    cmd = ["curl", "-sL", "-m", str(TIMEOUT), "--max-filesize", "400000",
           "-A", stream.get("user_agent") or DEFAULT_UA]
    if stream.get("referrer"):
        cmd += ["-e", stream["referrer"]]
    cmd += ["-w", "\n@@%{http_code}", stream["url"]]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=TIMEOUT + 15, errors="replace")
    except subprocess.SubprocessError:
        return False
    body, _, code = r.stdout.rpartition("\n@@")
    return code.strip() == "200" and "#EXTM3U" in body[:200]


def escape(value):
    return str(value).replace('"', "'").replace("\n", " ")


def main():
    streams = fetch_json("streams")
    channels = {c["id"]: c for c in fetch_json("channels")}

    # Logos vêm noutro endpoint. Fica o maior, que na TV é o que não serrilha.
    logos = {}
    for logo in fetch_json("logos"):
        cid = logo.get("channel")
        if not cid or not logo.get("url"):
            continue
        area = (logo.get("width") or 0) * (logo.get("height") or 0)
        if area > logos.get(cid, (0, None))[0]:
            logos[cid] = (area, logo["url"])

    # Vários links por canal. Testa todos, porque o de maior resolução costuma ser
    # o mais abandonado — a Globo e a GloboNews só sobrevivem no link secundário.
    by_channel = {}
    for s in sorted(streams, key=quality_rank, reverse=True):
        cid = s.get("channel") or ""
        if cid.endswith(f".{COUNTRY}") and s.get("url"):
            by_channel.setdefault(cid, []).append(s)
    print(f"{len(by_channel)} canais {COUNTRY.upper()}, "
          f"{sum(len(v) for v in by_channel.values())} links", flush=True)

    def first_alive(candidates):
        for s in candidates:
            if is_alive(s):
                return s
        return None

    with futures.ThreadPoolExecutor(WORKERS) as pool:
        approved = [s for s in pool.map(first_alive, by_channel.values()) if s]
    print(f"{len(approved)} no ar", flush=True)

    if len(approved) < 50:
        print("poucos canais aprovados, provável falha de rede — abortando", file=sys.stderr)
        return 1

    def group_of(meta):
        raw = (meta.get("categories") or ["general"])[0].lower()
        return GROUPS.get(raw, raw.title())

    def sort_key(s):
        meta = channels.get(s["channel"], {})
        return (group_of(meta), meta.get("name") or s["channel"])

    lines = ["#EXTM3U"]
    groups = Counter()
    for s in sorted(approved, key=sort_key):
        meta = channels.get(s["channel"], {})
        name = meta.get("name") or s.get("title") or s["channel"]
        group = group_of(meta)
        groups[group] += 1
        attrs = [f'tvg-id="{escape(s["channel"])}"', f'group-title="{escape(group)}"']
        if logo := logos.get(s["channel"]):
            attrs.append(f'tvg-logo="{escape(logo[1])}"')
        if s.get("quality"):
            attrs.append(f'tvg-quality="{escape(s["quality"])}"')
        if s.get("user_agent"):
            attrs.append(f'http-user-agent="{escape(s["user_agent"])}"')
        if s.get("referrer"):
            attrs.append(f'http-referrer="{escape(s["referrer"])}"')
        lines.append(f'#EXTINF:-1 {" ".join(attrs)},{escape(name)}')
        lines.append(s["url"])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"gravado {OUT} — {dict(groups.most_common())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
