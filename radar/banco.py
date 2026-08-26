"""UNICO ponto de acesso ao Supabase. Nao criar client em outro lugar.

Em modo seco (--seco) nada e' gravado: o radar so' imprime o que faria.
Serve para testar sem banco e para conferir uma fonte nova antes de sujar a base.
"""
from __future__ import annotations

from .config import env


class Banco:
    def __init__(self, seco: bool = False):
        self.seco = seco
        self.cliente = None
        self._memoria: set[str] = set()   # dedup em modo seco
        self._cotacoes: list[dict] = []   # serie em memoria no modo seco
        if not seco:
            from supabase import create_client
            self.cliente = create_client(env("SUPABASE_URL", True),
                                         env("SUPABASE_SERVICE_KEY", True))

    # -- itens ---------------------------------------------------------------

    def item_existe(self, site: str, hash_dedup: str) -> bool:
        if self.seco:
            return hash_dedup in self._memoria
        r = (self.cliente.table("itens").select("id")
             .eq("site", site).eq("hash_dedup", hash_dedup).limit(1).execute())
        return bool(r.data)

    def grava_item(self, item: dict) -> int | None:
        if self.seco:
            self._memoria.add(item["hash_dedup"])
            print(f"  [seco] item: {item['titulo'][:90]}")
            return None
        r = self.cliente.table("itens").insert(item).execute()
        return r.data[0]["id"] if r.data else None

    # -- pautas --------------------------------------------------------------

    def grava_pauta(self, pauta: dict) -> None:
        if self.seco:
            print(f"  [seco] pauta [{pauta['angulo']}] {pauta['titulo_sug']}")
            if pauta.get("dado_proprio"):
                print(f"         dado proprio: {pauta['dado_proprio']}")
            return
        self.cliente.table("pautas").insert(pauta).execute()

    # -- bases proprias ------------------------------------------------------

    def conta_eventos_na_cidade(self, site: str, cidade: str) -> int:
        """Quantas vezes o artista ja tocou na cidade. E' o dado que transforma
        'reescrever a noticia' em 'noticia com informacao nova'."""
        if self.seco or not self.cliente:
            return 0
        r = (self.cliente.table("eventos").select("id", count="exact")
             .eq("site", site).ilike("cidade", cidade).execute())
        return r.count or 0

    def ultimo_evento_na_cidade(self, site: str, cidade: str) -> dict | None:
        if self.seco or not self.cliente:
            return None
        r = (self.cliente.table("eventos").select("*")
             .eq("site", site).ilike("cidade", cidade)
             .order("data", desc=True).limit(1).execute())
        return r.data[0] if r.data else None

    def cidades_conhecidas(self, site: str) -> list[str]:
        if self.seco or not self.cliente:
            return []
        r = self.cliente.table("eventos").select("cidade").eq("site", site).execute()
        return sorted({linha["cidade"] for linha in (r.data or [])})

    def grava_cotacao(self, linha: dict) -> None:
        if self.seco:
            print(f"  [seco] cotacao {linha['data']}: venda {linha['ptax_venda']}")
            self._cotacoes.append(linha)
            return
        # upsert: rodar duas vezes no mesmo dia nao pode duplicar
        self.cliente.table("cotacoes").upsert(
            linha, on_conflict="site,data,moeda").execute()

    def serie_cotacoes(self, site: str, dias: int = 30) -> list[dict]:
        """Serie em ordem crescente de data — o gerador espera assim."""
        if self.seco:
            linhas = self._cotacoes[-dias:]
        else:
            r = (self.cliente.table("cotacoes").select("*")
                 .eq("site", site).eq("moeda", "USD")
                 .order("data", desc=True).limit(dias).execute())
            linhas = list(reversed(r.data or []))
        saida = []
        for l in linhas:
            from datetime import date as _date
            d = l["data"]
            saida.append({
                "data": d if isinstance(d, _date) else _date.fromisoformat(str(d)),
                "compra": float(l["ptax_compra"]), "venda": float(l["ptax_venda"]),
            })
        return saida

    def grava_artigo(self, artigo: dict) -> None:
        if self.seco:
            print(f"  [seco] artigo [{artigo['status']}] {artigo['titulo']}")
            return
        self.cliente.table("artigos").upsert(
            artigo, on_conflict="site,tipo,referencia").execute()

    def artigo_existente(self, site: str, tipo: str, referencia: str) -> dict | None:
        if self.seco or not self.cliente:
            return None
        r = (self.cliente.table("artigos").select("*")
             .eq("site", site).eq("tipo", tipo).eq("referencia", referencia)
             .limit(1).execute())
        return r.data[0] if r.data else None

    def marca_publicado(self, site: str, tipo: str, referencia: str,
                        post_id: int, url: str | None) -> None:
        if self.seco:
            print(f"  [seco] publicado no WP: post {post_id} -> {url}")
            return
        (self.cliente.table("artigos")
         .update({"wp_post_id": post_id, "url_publicada": url})
         .eq("site", site).eq("tipo", tipo).eq("referencia", referencia).execute())

    def variacao_cotacao(self, site: str, dias: int = 30) -> dict | None:
        if self.seco or not self.cliente:
            return None
        r = (self.cliente.table("cotacoes").select("*")
             .eq("site", site).order("data", desc=True).limit(dias).execute())
        linhas = r.data or []
        if len(linhas) < 2:
            return None
        atual, antiga = linhas[0], linhas[-1]
        vendas = [float(l["ptax_venda"]) for l in linhas if l.get("ptax_venda")]
        return {
            "atual": float(atual["ptax_venda"]),
            "variacao_pct": (float(atual["ptax_venda"]) / float(antiga["ptax_venda"]) - 1) * 100,
            "maior": max(vendas), "menor": min(vendas), "dias": len(linhas),
        }
