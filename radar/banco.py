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
        # motor discover em modo seco: sinais e topicos ficam so' na memoria
        self._sinais: list[dict] = []
        self._coletas: list[dict] = []
        self._topicos: list[dict] = []
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

    _aviso_descarte_dado = False

    def grava_descarte(self, item: dict) -> None:
        """Item que o classificador julgou IRRELEVANTE. Entra em `itens` com
        relevante=false so' para o hash ficar registrado: no proximo ciclo
        `item_existe` o pula e o modelo nao le a mesma noticia de novo.

        Ate 26/09/2026 o descarte nao era gravado, e a mesma manchete
        irrelevante voltava do feed e passava pelo modelo a cada 30 min,
        enquanto ficasse no Google News — era o maior gasto silencioso do
        radar. Nao gera pauta e nao aparece no painel (que le `itens` so'
        atraves das pautas).

        Sem a coluna (migration sql/itens-relevante-2026-09.sql ainda nao
        aplicada) avisa UMA vez e segue: o radar volta ao comportamento
        antigo, nunca quebra por causa disso."""
        if self.seco:
            self._memoria.add(item["hash_dedup"])
            return
        try:
            self.cliente.table("itens").insert({**item, "relevante": False}).execute()
        except Exception as erro:
            if not Banco._aviso_descarte_dado:
                Banco._aviso_descarte_dado = True
                print(f"  aviso: descarte nao gravado ({str(erro)[:160]}) — "
                      f"aplique sql/itens-relevante-2026-09.sql no Supabase")

    # -- pautas --------------------------------------------------------------

    def grava_pauta(self, pauta: dict) -> int | None:
        """Devolve o id (None em modo seco) — o motor discover liga a ideia
        a pauta por ele."""
        if self.seco:
            print(f"  [seco] pauta [{pauta['angulo']}] {pauta['titulo_sug']}")
            if pauta.get("dado_proprio"):
                print(f"         dado proprio: {pauta['dado_proprio']}")
            return None
        r = self.cliente.table("pautas").insert(pauta).execute()
        return r.data[0]["id"] if r.data else None

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

    def imagens_usadas(self, site: str, limite: int = 200) -> set[str]:
        """URLs de origem das capas que o site ja' usou (artigos.imagem_origem),
        as mais recentes. A busca de imagem pula essas — tres posts seguidos
        com a mesma foto (doll, 25/09/2026) e' o que o Discover le como
        conteudo repetido."""
        if self.seco or not self.cliente:
            return set()
        try:
            r = (self.cliente.table("artigos").select("imagem_origem")
                 .eq("site", site).not_.is_("imagem_origem", "null")
                 .order("criado_em", desc=True).limit(limite).execute())
        except Exception as erro:
            print(f"  aviso: nao li as capas usadas ({str(erro)[:120]}) — "
                  f"aplique sql/imagem-origem-2026-10.sql")
            return set()
        return {l["imagem_origem"] for l in (r.data or []) if l.get("imagem_origem")}

    def marca_publicado(self, site: str, tipo: str, referencia: str,
                        post_id: int, url: str | None,
                        status: str = "publicada",
                        midia_id: int | None = None,
                        imagem_url: str | None = None,
                        imagem_credito: str | None = None,
                        imagem_origem: str | None = None) -> None:
        """So' aqui o artigo vira 'publicada': o status acompanha o que o
        WordPress confirmou. Sem esse passo, uma falha de publicacao deixava
        o artigo 'publicada' no banco sem nunca ter ido ao ar.

        wp_media_id guarda a imagem destacada ja' enviada: a rerodada
        reaproveita em vez de encher a biblioteca do WP de copias."""
        if self.seco:
            print(f"  [seco] publicado no WP: post {post_id} -> {url}")
            return
        campos = {"wp_post_id": post_id, "url_publicada": url, "status": status}
        if midia_id:
            campos["wp_media_id"] = midia_id
        if imagem_url:
            campos["imagem_url"] = imagem_url
        if imagem_credito:
            campos["imagem_credito"] = imagem_credito
        if imagem_origem:
            campos["imagem_origem"] = imagem_origem
        try:
            (self.cliente.table("artigos").update(campos)
             .eq("site", site).eq("tipo", tipo).eq("referencia", referencia).execute())
        except Exception as erro:
            if "imagem_origem" not in campos:
                raise
            # Coluna nova ainda nao aplicada: grava o resto e avisa, em vez
            # de deixar o artigo sem wp_post_id (ele seria republicado).
            print(f"  aviso: imagem_origem nao gravada ({str(erro)[:100]}) — "
                  f"aplique sql/imagem-origem-2026-10.sql")
            campos.pop("imagem_origem")
            (self.cliente.table("artigos").update(campos)
             .eq("site", site).eq("tipo", tipo).eq("referencia", referencia).execute())

    # -- selecao automatica de pautas ---------------------------------------

    def garante_meta(self, site: str, pautas_por_dia: int,
                     wp_url: str | None) -> str:
        """Cria a linha de `metas` do site se ela nao existir.

        SEM essa linha a selecao automatica sai na primeira instrucao
        (meta_do_site devolve None) e o site coleta pautas que nunca viram
        nada. Foi o que segurou os 5 blogs em 18/09/2026.

        NAO sobrescreve meta existente: pautas_por_dia e criterios sao
        ajustados na aba Radar, e o configurador nao pode desfazer isso.
        Preenche wp_url so' quando esta' vazio. Devolve 'criada', 'wp_url' ou
        'ja existia'."""
        if self.seco or not self.cliente:
            print(f"  [seco] metas[{site}] = {pautas_por_dia}/dia, wp {wp_url}")
            return "seco"
        atual = self.meta_do_site(site)
        if atual is None:
            self.cliente.table("metas").insert({
                "site": site, "pautas_por_dia": pautas_por_dia,
                "wp_url": wp_url}).execute()
            return "criada"
        if wp_url and not atual.get("wp_url"):
            (self.cliente.table("metas").update({"wp_url": wp_url})
             .eq("site", site).execute())
            return "wp_url"
        return "ja existia"

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

    @staticmethod
    def _fim_do_dia(inicio_dia_iso: str) -> str:
        """24h depois do inicio do dia — o LIMITE SUPERIOR das consultas de
        'hoje'.

        Sem ele, `selecionada_em >= inicio do dia` tambem pega o FUTURO. Isso
        nao incomodava enquanto o unico jeito de selecionar era o cron (que
        sempre grava o instante atual), mas o calendario da tela Discovery
        grava pauta datada para os proximos dias: sem o teto, um plano de 7
        dias contaria como 7 selecionadas hoje e zeraria as vagas do radar de
        noticias no mesmo instante em que fosse salvo."""
        from datetime import datetime, timedelta
        return (datetime.fromisoformat(inicio_dia_iso) + timedelta(days=1)).isoformat()

    def fatos_selecionados_hoje(self, site: str, inicio_dia_iso: str) -> set:
        """item_ids das pautas ja escolhidas hoje (inclusive as vetadas depois):
        o mesmo fato nao volta por outro angulo na reposicao."""
        if self.seco or not self.cliente:
            return set()
        r = (self.cliente.table("pautas").select("item_id")
             .eq("site", site).gte("selecionada_em", inicio_dia_iso)
             .lt("selecionada_em", self._fim_do_dia(inicio_dia_iso)).execute())
        return {l["item_id"] for l in (r.data or []) if l.get("item_id")}

    def selecionadas_hoje(self, site: str, inicio_dia_iso: str) -> int:
        if self.seco or not self.cliente:
            return 0
        r = (self.cliente.table("pautas").select("id", count="exact")
             .eq("site", site).eq("status", "aprovada")
             .gte("selecionada_em", inicio_dia_iso)
             .lt("selecionada_em", self._fim_do_dia(inicio_dia_iso)).execute())
        return r.count or 0

    def hubs_selecionados_hoje(self, site: str, inicio_dia_iso: str) -> dict:
        """Quantas pautas cada hub ja consumiu hoje (aprovadas E publicadas) —
        a selecao usa para nao encher a meta com hub que ja bateu o teto."""
        if self.seco or not self.cliente:
            return {}
        r = (self.cliente.table("pautas").select("hub,status")
             .eq("site", site).in_("status", ["aprovada", "publicada"])
             .gte("selecionada_em", inicio_dia_iso)
             .lt("selecionada_em", self._fim_do_dia(inicio_dia_iso)).execute())
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
             .lt("selecionada_em", self._fim_do_dia(inicio_dia_iso))
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

    def artigos_recentes(self, site: str, limite: int = 12) -> list[dict]:
        """Ultimos artigos publicados (titulo + url) — viram o bloco
        Leia tambem dos satelites: profundidade por link interno."""
        if self.seco or not self.cliente:
            return []
        r = (self.cliente.table("artigos")
             .select("titulo,url_publicada,tipo")
             .eq("site", site).eq("status", "publicada")
             .not_.is_("url_publicada", "null")
             .order("criado_em", desc=True).limit(limite).execute())
        return list(r.data or [])

    def ancoras_publicadas(self, site: str) -> list[dict]:
        """Os guias evergreen no ar — candidatos permanentes do Leia tambem
        (sao antigos demais para a lista de recentes, mas sao os textos de
        maior valor para linkar)."""
        if self.seco or not self.cliente:
            return []
        r = (self.cliente.table("artigos")
             .select("titulo,url_publicada,tipo")
             .eq("site", site).eq("tipo", "ancora").eq("status", "publicada")
             .not_.is_("url_publicada", "null").execute())
        return list(r.data or [])

    def ancora_do_hub(self, site: str, hub: str) -> str | None:
        """URL do texto ancora publicado deste hub — o destino do satelite."""
        if self.seco or not self.cliente:
            return None
        r = (self.cliente.table("artigos").select("url_publicada")
             .eq("site", site).eq("tipo", "ancora").eq("hub", hub)
             .eq("status", "publicada").not_.is_("url_publicada", "null")
             .limit(1).execute())
        return r.data[0]["url_publicada"] if r.data else None

    def pautas_para_satelite(self, site: str, inicio_dia_iso: str,
                             exige_dado: bool = True) -> tuple[list[dict], dict]:
        """Devolve (candidatas, publicadas_por_hub): as pautas do dia ainda
        aprovadas, por pontuacao, e quantas JA sairam por hub.
        A POLITICA (teto por hub, horario, maduras primeiro) fica no fluxo —
        aqui e' so' leitura. Licao de 31/08: aplicar o teto aqui, antes do
        filtro de horario, deixava pauta futura roubar a vaga da madura.

        exige_dado=False atende os sites SEM base propria (os blogs Tihee):
        la' nenhuma pauta tem dado_proprio e o filtro devolveria sempre vazio.
        Ver radar/publicar.py."""
        if self.seco or not self.cliente:
            return [], {}
        ja = (self.cliente.table("pautas").select("hub")
              .eq("site", site).eq("status", "publicada")
              .gte("selecionada_em", inicio_dia_iso)
              .lt("selecionada_em", self._fim_do_dia(inicio_dia_iso)).execute())
        por: dict[str, int] = {}
        for p in (ja.data or []):
            h = p.get("hub") or "_"
            por[h] = por.get(h, 0) + 1
        consulta = (self.cliente.table("pautas")
                    .select("id,item_id,angulo,hub,titulo_sug,dado_proprio,"
                            "pontuacao,horario_sugerido,tipo,topico_id,brief,evidencias,"
                            "itens(titulo,url,veiculo)")
                    .eq("site", site).eq("status", "aprovada")
                    .gte("selecionada_em", inicio_dia_iso)
                    .lt("selecionada_em", self._fim_do_dia(inicio_dia_iso)))
        if exige_dado:
            consulta = consulta.not_.is_("dado_proprio", "null")
        r = consulta.order("pontuacao", desc=True).execute()
        return list(r.data or []), por

    def pautas_aprovadas_antes(self, site: str, inicio_dia_iso: str) -> list[dict]:
        """Pautas 'aprovada' selecionadas ANTES de hoje: as que a esteira
        (que so' olha o dia corrente) nunca mais vai pegar. Sao as orfas do
        periodo em que o WP recusava (18 a 26/09/2026): guia escrito e salvo
        em `artigos`, nunca enviado. Ver radar/rascunhos.py."""
        if self.seco or not self.cliente:
            return []
        r = (self.cliente.table("pautas")
             .select("id,hub,titulo_sug,pontuacao,selecionada_em")
             .eq("site", site).eq("status", "aprovada")
             .lt("selecionada_em", inicio_dia_iso)
             .order("selecionada_em", desc=False).execute())
        return list(r.data or [])

    def marca_pauta_status(self, pauta_id: int | None, status: str) -> None:
        """Muda o status de uma pauta (ex.: 'descartada' quando o checador
        reprova o artigo — ela nao volta a fila)."""
        if self.seco or not self.cliente or not pauta_id:
            return
        self.cliente.table("pautas").update({"status": status}).eq("id", pauta_id).execute()

    def marca_pauta_publicada(self, pauta_id: int) -> None:
        """A pauta vira 'publicada' — some da fila de satelites e nao se
        repete. A URL do post fica no artigo (tabela artigos), nao aqui."""
        if self.seco:
            print(f"  [seco] pauta {pauta_id} -> publicada")
            return
        (self.cliente.table("pautas").update({"status": "publicada"})
         .eq("id", pauta_id).execute())

    # -- motor discover: sinais, coletas, topicos ----------------------------
    # Tabelas de sql/discover-2026-10.sql. Em modo seco tudo fica na memoria
    # da rodada, entao o ensaio (--seco) agrupa e pontua sem gravar.

    def ultima_coleta(self, site: str, hub: str, fonte: str, consulta: str) -> str | None:
        """Quando esta fonte/consulta foi coletada pela ultima vez (ISO), ou
        None. E' o TTL que segura o custo das fontes pagas."""
        if self.seco or not self.cliente:
            for c in reversed(self._coletas):
                if (c["site"], c["hub"], c["fonte"], c["consulta"]) == (site, hub, fonte, consulta):
                    return c["coletado_em"]
            return None
        r = (self.cliente.table("coletas").select("coletado_em")
             .eq("site", site).eq("hub", hub).eq("fonte", fonte).eq("consulta", consulta)
             .order("coletado_em", desc=True).limit(1).execute())
        return r.data[0]["coletado_em"] if r.data else None

    def registra_coleta(self, coleta: dict) -> None:
        if self.seco or not self.cliente:
            self._coletas.append(coleta)
            return
        try:
            self.cliente.table("coletas").insert(coleta).execute()
        except Exception as erro:
            print(f"  aviso: coleta nao registrada ({str(erro)[:120]}) — "
                  f"aplique sql/discover-2026-10.sql")

    def coletas_hoje(self, fonte: str, inicio_dia_iso: str) -> int:
        """Quantas chamadas desta fonte ja' foram feitas hoje (todos os
        sites) — o teto diario da SerpAPI e' por conta, nao por site."""
        if self.seco or not self.cliente:
            return sum(1 for c in self._coletas if c["fonte"] == fonte)
        r = (self.cliente.table("coletas").select("id", count="exact")
             .eq("fonte", fonte).gte("coletado_em", inicio_dia_iso).execute())
        return r.count or 0

    def grava_sinais(self, sinais: list[dict]) -> None:
        """Upsert ignorando repetidos: o mesmo sinal no mesmo dia nao duplica."""
        if not sinais:
            return
        if self.seco or not self.cliente:
            vistos = {(s["site"], s["hub"], s["fonte"], s["dia"], s["hash_dedup"])
                      for s in self._sinais}
            for s in sinais:
                chave = (s["site"], s["hub"], s["fonte"], s["dia"], s["hash_dedup"])
                if chave not in vistos:
                    vistos.add(chave)
                    self._sinais.append(s)
            return
        try:
            self.cliente.table("sinais").upsert(
                sinais, on_conflict="site,hub,fonte,dia,hash_dedup",
                ignore_duplicates=True).execute()
        except Exception as erro:
            print(f"  aviso: sinais nao gravados ({str(erro)[:120]}) — "
                  f"aplique sql/discover-2026-10.sql")

    def sinais_recentes(self, site: str, hub: str, dias: int = 30,
                        limite: int = 2000) -> list[dict]:
        if self.seco or not self.cliente:
            return [s for s in self._sinais if s["site"] == site and s["hub"] == hub]
        from datetime import date, timedelta
        desde = (date.today() - timedelta(days=dias)).isoformat()
        r = (self.cliente.table("sinais").select("*")
             .eq("site", site).eq("hub", hub).gte("dia", desde)
             .order("dia", desc=True).limit(limite).execute())
        return list(r.data or [])

    def topicos_recentes(self, site: str, hub: str, dias: int = 7) -> list[dict]:
        if self.seco or not self.cliente:
            return [t for t in self._topicos if t["site"] == site and t["hub"] == hub]
        from datetime import date, timedelta
        desde = (date.today() - timedelta(days=dias)).isoformat()
        r = (self.cliente.table("topicos")
             .select("id,chave,rotulo,pontuacao,status,pauta_id,primeiro_visto,dia")
             .eq("site", site).eq("hub", hub).gte("dia", desde)
             .order("dia", desc=True).limit(500).execute())
        return list(r.data or [])

    def grava_topico(self, topico: dict) -> int | None:
        """Upsert por (site, hub, chave, dia): a mesma rodada de 30 min
        atualiza a nota do topico do dia em vez de empilhar linhas."""
        if self.seco or not self.cliente:
            self._topicos.append(topico)
            return None
        try:
            r = (self.cliente.table("topicos")
                 .upsert(topico, on_conflict="site,hub,chave,dia").execute())
            return r.data[0]["id"] if r.data else None
        except Exception as erro:
            print(f"  aviso: topico nao gravado ({str(erro)[:120]}) — "
                  f"aplique sql/discover-2026-10.sql")
            return None

    def marca_topico(self, topico_id: int, status: str, pauta_id: int | None = None) -> None:
        if self.seco or not self.cliente or not topico_id:
            return
        campos = {"status": status}
        if pauta_id:
            campos["pauta_id"] = pauta_id
        self.cliente.table("topicos").update(campos).eq("id", topico_id).execute()

    def artigos_publicados_do_hub(self, site: str, hub: str, limite: int = 50) -> list[dict]:
        """O que o site ja' publicou neste hub — base da autoridade topica e
        da lacuna de informacao."""
        if self.seco or not self.cliente:
            return []
        r = (self.cliente.table("artigos").select("titulo,url_publicada")
             .eq("site", site).eq("hub", hub).eq("status", "publicada")
             .order("criado_em", desc=True).limit(limite).execute())
        return list(r.data or [])

    # -- ideias por categoria (sql/ideias-2026-10.sql) -----------------------

    def grava_ideias(self, linhas: list[dict]) -> None:
        """Upsert por (site, hub, chave): atualiza titulo/nota/detalhes e
        PRESERVA status e marcacao (nao vao na carga)."""
        if not linhas:
            return
        if self.seco or not self.cliente:
            for l in linhas:
                print(f"    [seco] ideia sugerida [{l['pontuacao']}] {l['titulo'][:70]}")
            return
        try:
            self.cliente.table("ideias").upsert(linhas, on_conflict="site,hub,chave").execute()
        except Exception as erro:
            print(f"  aviso: ideias nao gravadas ({str(erro)[:120]}) — "
                  f"aplique sql/ideias-2026-10.sql")

    def ideias_marcadas(self, site: str, limite: int = 20) -> list[dict]:
        """As ideias que a pessoa marcou e ainda nao viraram pauta, na ordem
        em que foram marcadas."""
        if self.seco or not self.cliente:
            return []
        try:
            r = (self.cliente.table("ideias").select("*")
                 .eq("site", site).eq("status", "marcada")
                 .order("marcada_em", desc=False).limit(limite).execute())
        except Exception as erro:
            print(f"  aviso: nao li as ideias ({str(erro)[:120]})")
            return []
        return list(r.data or [])

    def marca_ideia(self, ideia_id: int | None, status: str, pauta_id: int | None = None) -> None:
        if self.seco or not self.cliente or not ideia_id:
            return
        campos: dict = {"status": status}
        if pauta_id:
            campos["pauta_id"] = pauta_id
        from datetime import datetime, timezone
        campos["atualizado_em"] = datetime.now(timezone.utc).isoformat()
        self.cliente.table("ideias").update(campos).eq("id", ideia_id).execute()

    def marca_ideia_da_pauta(self, pauta_id: int | None, status: str) -> None:
        """Depois que a pauta e' publicada ou reprovada, a ideia de origem
        acompanha (a tela mostra o status pela ideia)."""
        if self.seco or not self.cliente or not pauta_id:
            return
        from datetime import datetime, timezone
        (self.cliente.table("ideias")
         .update({"status": status, "atualizado_em": datetime.now(timezone.utc).isoformat()})
         .eq("pauta_id", pauta_id).execute())

    def execucao_hoje(self, fluxo: str, site: str, inicio_dia_iso: str) -> bool:
        """Ja' houve rodada deste fluxo hoje? Serve para avisar UMA vez por
        dia (o cron roda 48x)."""
        if self.seco or not self.cliente:
            return False
        r = (self.cliente.table("execucoes").select("id", count="exact")
             .eq("fluxo", fluxo).eq("site", site).gte("inicio", inicio_dia_iso).execute())
        return bool(r.count)

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
