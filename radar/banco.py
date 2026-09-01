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
                        post_id: int, url: str | None,
                        status: str = "publicada") -> None:
        """So' aqui o artigo vira 'publicada': o status acompanha o que o
        WordPress confirmou. Sem esse passo, uma falha de publicacao deixava
        o artigo 'publicada' no banco sem nunca ter ido ao ar."""
        if self.seco:
            print(f"  [seco] publicado no WP: post {post_id} -> {url}")
            return
        (self.cliente.table("artigos")
         .update({"wp_post_id": post_id, "url_publicada": url, "status": status})
         .eq("site", site).eq("tipo", tipo).eq("referencia", referencia).execute())

    # -- selecao automatica de pautas ---------------------------------------

    def meta_do_site(self, site: str) -> dict | None:
        if self.seco or not self.cliente:
            return None
        r = self.cliente.table("metas").select("*").eq("site", site).limit(1).execute()
        return r.data[0] if r.data else None

    def pautas_novas(self, site: str, limite: int = 200) -> list[dict]:
        if self.seco or not self.cliente:
            return []
        r = (self.cliente.table("pautas")
             .select("id,item_id,angulo,hub,titulo_sug,dado_proprio,criado_em,"
                     "itens(publicado_em)")
             .eq("site", site).eq("status", "nova")
             .order("criado_em", desc=True).limit(limite).execute())
        return r.data or []

    def fatos_selecionados_hoje(self, site: str, inicio_dia_iso: str) -> set:
        """item_ids das pautas ja escolhidas hoje (inclusive as vetadas depois):
        o mesmo fato nao volta por outro angulo na reposicao."""
        if self.seco or not self.cliente:
            return set()
        r = (self.cliente.table("pautas").select("item_id")
             .eq("site", site).gte("selecionada_em", inicio_dia_iso).execute())
        return {l["item_id"] for l in (r.data or []) if l.get("item_id")}

    def selecionadas_hoje(self, site: str, inicio_dia_iso: str) -> int:
        if self.seco or not self.cliente:
            return 0
        r = (self.cliente.table("pautas").select("id", count="exact")
             .eq("site", site).eq("status", "aprovada")
             .gte("selecionada_em", inicio_dia_iso).execute())
        return r.count or 0

    def hubs_selecionados_hoje(self, site: str, inicio_dia_iso: str) -> dict:
        """Quantas pautas cada hub ja consumiu hoje (aprovadas E publicadas) —
        a selecao usa para nao encher a meta com hub que ja bateu o teto."""
        if self.seco or not self.cliente:
            return {}
        r = (self.cliente.table("pautas").select("hub,status")
             .eq("site", site).in_("status", ["aprovada", "publicada"])
             .gte("selecionada_em", inicio_dia_iso).execute())
        por: dict = {}
        for p in (r.data or []):
            h = p.get("hub") or "_"
            por[h] = por.get(h, 0) + 1
        return por

    def ultimo_horario_sugerido(self, site: str, inicio_dia_iso: str) -> str | None:
        """O slot mais tarde ja marcado hoje — base do espacamento da pista fixa."""
        if self.seco or not self.cliente:
            return None
        r = (self.cliente.table("pautas").select("horario_sugerido")
             .eq("site", site).gte("selecionada_em", inicio_dia_iso)
             .not_.is_("horario_sugerido", "null")
             .order("horario_sugerido", desc=True).limit(1).execute())
        return r.data[0]["horario_sugerido"] if r.data else None

    def marca_selecionada(self, pauta_id: int, pontuacao: int, motivo: str,
                          quando_iso: str, horario_iso: str) -> None:
        if self.seco:
            print(f"  [seco] selecionada pauta {pauta_id} ({pontuacao} pts)")
            return
        (self.cliente.table("pautas")
         .update({"status": "aprovada", "pontuacao": pontuacao,
                  "motivo_selecao": motivo, "selecionada_em": quando_iso,
                  "horario_sugerido": horario_iso})
         .eq("id", pauta_id).execute())

    # -- satelites (artigos de pauta que linkam para os ancora) --------------

    def ancora_do_hub(self, site: str, hub: str) -> str | None:
        """URL do texto ancora publicado deste hub — o destino do satelite."""
        if self.seco or not self.cliente:
            return None
        r = (self.cliente.table("artigos").select("url_publicada")
             .eq("site", site).eq("tipo", "ancora").eq("hub", hub)
             .eq("status", "publicada").not_.is_("url_publicada", "null")
             .limit(1).execute())
        return r.data[0]["url_publicada"] if r.data else None

    def pautas_para_satelite(self, site: str,
                             inicio_dia_iso: str) -> tuple[list[dict], dict]:
        """Devolve (candidatas, publicadas_por_hub): as pautas do dia com dado
        proprio ainda aprovadas, por pontuacao, e quantas JA sairam por hub.
        A POLITICA (teto por hub, horario, maduras primeiro) fica no fluxo —
        aqui e' so' leitura. Licao de 31/08: aplicar o teto aqui, antes do
        filtro de horario, deixava pauta futura roubar a vaga da madura."""
        if self.seco or not self.cliente:
            return [], {}
        ja = (self.cliente.table("pautas").select("hub")
              .eq("site", site).eq("status", "publicada")
              .gte("selecionada_em", inicio_dia_iso).execute())
        por: dict[str, int] = {}
        for p in (ja.data or []):
            h = p.get("hub") or "_"
            por[h] = por.get(h, 0) + 1
        r = (self.cliente.table("pautas")
             .select("id,item_id,angulo,hub,titulo_sug,dado_proprio,pontuacao,"
                     "horario_sugerido,itens(titulo,url,veiculo)")
             .eq("site", site).eq("status", "aprovada")
             .not_.is_("dado_proprio", "null")
             .gte("selecionada_em", inicio_dia_iso)
             .order("pontuacao", desc=True).execute())
        return list(r.data or []), por

    def marca_pauta_publicada(self, pauta_id: int) -> None:
        """A pauta vira 'publicada' — some da fila de satelites e nao se
        repete. A URL do post fica no artigo (tabela artigos), nao aqui."""
        if self.seco:
            print(f"  [seco] pauta {pauta_id} -> publicada")
            return
        (self.cliente.table("pautas").update({"status": "publicada"})
         .eq("id", pauta_id).execute())

    # -- execucoes -----------------------------------------------------------

    def registra_execucao(self, registro: dict) -> None:
        """Uma linha por rodada de cron. E' o que o painel le para responder
        'rodou? quando? deu certo?' sem abrir o GitHub Actions."""
        if self.seco:
            print(f"  [seco] execucao {registro['fluxo']}/{registro.get('site')}: "
                  f"{registro['status']} — {registro.get('resumo')}")
            return
        try:
            self.cliente.table("execucoes").insert(registro).execute()
        except Exception as erro:
            # Telemetria nunca derruba a rodada: sem a tabela (schema.sql
            # desatualizado no Supabase), avisa e segue.
            print(f"  aviso: execucao nao registrada ({erro})")

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
