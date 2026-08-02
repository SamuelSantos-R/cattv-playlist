# cattv-playlist

Playlist de canais abertos brasileiros, testada todo dia.

A lista pública do [iptv-org](https://github.com/iptv-org/iptv) não é podada: numa
medição de 02/08/2026, das 302 entradas brasileiras apenas 192 devolviam um
manifesto HLS de verdade. O resto aparece no player e não toca.

`scripts/build_playlist.py` baixa o começo de cada stream, descarta quem não
responde e grava `playlist/br.m3u` com logo, resolução e categoria em português.
Um workflow do Actions repete isso diariamente.

## Uso

```
https://raw.githubusercontent.com/SamuelSantos-R/cattv-playlist/main/playlist/br.m3u
```

Só agrega links públicos já publicados pelo iptv-org. Nenhum conteúdo é
hospedado aqui.
