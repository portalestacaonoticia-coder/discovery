"""Teste offline do motor Discover (Etapa 1): agrupamento de sinais em
topicos, velocidades, DiscoverScore e plano de producao. Nao acessa rede
nem banco.

    python testar_discover.py
"""
from datetime import date, datetime, timedelta, timezone

from radar.oportunidade import (PADRAO_DISCOVER, avisos_de_producao, componentes,
                                criterios_discover, em_producao, pontua_topico,
                                seleciona_topicos)
from radar.sinais import _manchete_limpa, _sinal, consultas_do_hub
from radar.tendencias import (agrupa_topicos, frescor, funde_com_historico,
                              velocidade_noticias, velocidade_tendencia)

AGORA = datetime(2026, 10, 5, 15, 0, tzinfo=timezone.utc)
HUB = {"id": "receitas-rapidas", "titulo": "Receitas rápidas e práticas",
       "termos": ["receita", "rapida", "airfryer", "poucos ingredientes"],
       "perfil_leitor": "quem cozinha em casa nos dias de semana com pouco tempo",
       "imagem": "quick home cooking"}
SITE = {"entidade": "Broune", "estilo_visual": "fotografia editorial"}


def sinal(tipo, texto, fonte="google_news_rss", horas=1, veiculo="g1", valor=None, extra=None):
    quando = AGORA - timedelta(hours=horas) if tipo == "noticia" else None
    s = _sinal("broune", "receitas-rapidas", fonte, tipo, texto, veiculo=veiculo,
               valor=valor, extra=extra, publicado_em=quando, agora=AGORA)
    s["coletado_em"] = (AGORA - timedelta(hours=horas)).isoformat()
    return s


# -- formato do sinal ----------------------------------------------------------
assert _manchete_limpa("Receita de bolo de airfryer em 20 minutos - G1") == \
    ("Receita de bolo de airfryer em 20 minutos", "G1")
assert _manchete_limpa("Sem veiculo") == ("Sem veiculo", "")
s = sinal("noticia", "Bolo de airfryer   em 20 minutos")
assert s["texto"] == "Bolo de airfryer em 20 minutos" and s["dia"] == "2026-10-05"
assert len(s["hash_dedup"]) == 40

# padroes de consulta do hub
c = consultas_do_hub(HUB)
assert c["serp"] == ["Receitas rápidas e práticas"], c["serp"]
assert c["trends"] == ["receita", "rapida"], c["trends"]
assert c["noticias"] == ["receita OR rapida OR airfryer OR poucos ingredientes"], c["noticias"]
assert c["reddit"] == [] and c["youtube"] == []
c2 = consultas_do_hub({**HUB, "sinais": {"serp": "bolo airfryer", "reddit": ["receitas"]}})
assert c2["serp"] == ["bolo airfryer"] and c2["reddit"] == ["receitas"]

# -- agrupamento ---------------------------------------------------------------
sinais = [
    sinal("noticia", "Bolo de airfryer em 20 minutos vira febre nas redes", horas=2, veiculo="g1"),
    sinal("noticia", "Febre nas redes: bolo de airfryer pronto em 20 minutos", horas=5, veiculo="uol"),
    sinal("noticia", "Como fazer bolo na airfryer em 20 minutos", horas=30, veiculo="terra"),
    sinal("trend_rising", "bolo airfryer", fonte="trends", valor=1000),
    sinal("paa", "Quanto tempo leva um bolo na airfryer?", fonte="serp"),
    sinal("relacionada", "bolo de cenoura airfryer", fonte="serp"),
    sinal("noticia", "Preco do tomate sobe 12% em setembro", horas=3, veiculo="folha"),
    sinal("relacionada", "risoto de cogumelos", fonte="serp"),   # sozinha: ruido, some
]
topicos = agrupa_topicos(sinais, HUB, AGORA)
rotulos = [t["rotulo"] for t in topicos]
assert len(topicos) == 2, rotulos
bolo = next(t for t in topicos if "airfryer" in t["rotulo"])
tomate = next(t for t in topicos if "tomate" in t["rotulo"])
assert bolo["total_sinais"] == 6, bolo["por_tipo"]
assert bolo["veiculos_24h"] == ["g1", "uol"] and bolo["veiculos_7d"] == ["g1", "terra", "uol"]
assert bolo["trend_rising"] == 1000 and bolo["perguntas"] == ["Quanto tempo leva um bolo na airfryer?"]
assert bolo["rotulo"] == "Como fazer bolo na airfryer em 20 minutos"   # manchete mais curta
assert tomate["total_sinais"] == 1 and tomate["trend_rising"] == 0

# -- velocidades ---------------------------------------------------------------
assert velocidade_tendencia(bolo) == 1.0            # Breakout
assert velocidade_tendencia({"trend_top": 50}) == 0.25
assert velocidade_tendencia({"relacionadas": ["x"]}) == 0.2
assert velocidade_tendencia({}) == 0.0
assert velocidade_noticias(bolo) > velocidade_noticias(tomate) > 0
assert velocidade_noticias({"veiculos_24h": [], "veiculos_7d": ["a"]}) == 0.0
assert frescor(bolo, AGORA) == 1.0                 # ultima manchete ha' 2h
assert frescor({"ultimo_visto": (AGORA - timedelta(hours=30)).isoformat()}, AGORA) == 0.4
assert frescor({"ultimo_visto": (AGORA - timedelta(hours=100)).isoformat()}, AGORA) == 0.0

# historico: topico ja' pautado ontem nao volta a ser candidato
funde_com_historico([bolo], [{"chave": bolo["chave"], "status": "pautado", "pauta_id": 7,
                              "primeiro_visto": (AGORA - timedelta(days=3)).isoformat()}])
assert bolo.get("ja_pautado") and bolo["pauta_id"] == 7
assert bolo["primeiro_visto"] == (AGORA - timedelta(days=3)).isoformat()
bolo.pop("ja_pautado"); bolo.pop("pauta_id")

# -- DiscoverScore -------------------------------------------------------------
assert sum(PADRAO_DISCOVER["pesos"].values()) == 100
crit = criterios_discover(None)
comp_bolo = componentes(bolo, HUB, SITE, [], AGORA)
comp_tomate = componentes(tomate, HUB, SITE, [], AGORA)
for nome, v in {**comp_bolo, **comp_tomate}.items():
    assert 0.0 <= v <= 1.0, (nome, v)
assert comp_bolo["afinidade_publico"] > comp_tomate["afinidade_publico"]
assert comp_bolo["potencial_visual"] == 0.8      # imagem + estilo_visual, sem miniatura
assert comp_bolo["conversa_social"] == 0.0
nota_bolo, motivo = pontua_topico(bolo, comp_bolo, crit)
nota_tomate, _ = pontua_topico(tomate, comp_tomate, crit)
assert nota_bolo > nota_tomate, (nota_bolo, nota_tomate)
assert 0 <= nota_bolo <= 100 and "tendencia 1.0" in motivo, motivo

# site que ja' publicou sobre o assunto: mais autoridade, menos lacuna
comp_com_hist = componentes(bolo, HUB, SITE, [{"titulo": "Bolo na airfryer: tempo e temperatura"}], AGORA)
assert comp_com_hist["autoridade_topica"] > comp_bolo["autoridade_topica"]
assert comp_com_hist["lacuna_informacao"] < comp_bolo["lacuna_informacao"]

# hub sem imagem: visual zero, so' sobe com miniatura
assert componentes(bolo, {**HUB, "imagem": False}, {}, [], AGORA)["potencial_visual"] == 0.0

# criterios do editor sobrescrevem um peso e o piso
radical = criterios_discover({"discover": {"pesos": {"frescor": 60, "inexistente": 5}, "minimo": 10}})
assert radical["pesos"]["frescor"] == 60 and "inexistente" not in radical["pesos"]
assert radical["minimo"] == 10 and radical["pesos"]["conversa_social"] == 5
nota_radical, _ = pontua_topico(bolo, comp_bolo, radical)
assert nota_radical != nota_bolo
assert criterios_discover({"satelites_por_hub": 4})["satelites_por_hub"] == 4

# selecao: piso, teto por hub, ja' pautado, um por chave
bolo["pontuacao"], tomate["pontuacao"] = nota_bolo, nota_tomate
assert seleciona_topicos([bolo, tomate], {**crit, "minimo": 0}) == [bolo, tomate]
assert seleciona_topicos([bolo, tomate], {**crit, "minimo": 101}) == []
assert seleciona_topicos([bolo, tomate], {**crit, "minimo": 0, "satelites_por_hub": 1}) == [bolo]
assert seleciona_topicos([bolo, tomate], {**crit, "minimo": 0, "topicos_por_ciclo": 1}) == [bolo]
assert seleciona_topicos([bolo, tomate], {**crit, "minimo": 0}, hubs_usados={"receitas-rapidas": 2}) == []
assert seleciona_topicos([{**bolo, "ja_pautado": True}, tomate], {**crit, "minimo": 0}) == [tomate]

# -- plano de producao ---------------------------------------------------------
hoje = date(2026, 10, 5)
assert em_producao(None, hoje) == (False, "sem periodo de producao configurado (metas.producao_inicio/fim)")
assert em_producao({"producao_inicio": "2026-10-01"}, hoje)[0] is False
meta = {"pautas_por_dia": 5, "producao_inicio": "2026-10-01", "producao_fim": "2026-10-31"}
ok, motivo = em_producao(meta, hoje)
assert ok and motivo == "em producao ate 31/10", motivo
assert em_producao(meta, date(2026, 9, 30)) == (False, "producao comeca em 01/10")
assert em_producao(meta, date(2026, 11, 1)) == (False, "fora do periodo (terminou em 31/10)")
assert em_producao(meta, date(2026, 10, 29))[1] == "em producao ate 31/10 (2 dia(s) restantes)"
assert em_producao({**meta, "producao_inicio": date(2026, 10, 1)}, hoje)[0]   # date tambem serve
assert avisos_de_producao(meta, date(2026, 10, 1)) == ["producao COMECOU hoje: 5 pautas/dia ate 31/10"]
assert avisos_de_producao(meta, date(2026, 10, 28)) == ["producao termina em 3 dias (31/10), 5 pautas/dia"]
assert avisos_de_producao(meta, date(2026, 11, 1)) == ["producao TERMINOU ontem (31/10); o site parou de produzir"]
assert avisos_de_producao(meta, date(2026, 10, 15)) == []

# -- etapa 2/3: angulo, brief, checagem, otimizador -----------------------------
from radar.angulos_ia import escolhe_angulo
from radar.brief import manchete_ok, valida_brief
from radar.checagem import checa_estrutura
from radar.discover import escolhe_manchete
from radar.ideias import chave_manual

# angulo: canibaliza sai; risco alto so' com fontes no hub; melhor nota vence
angs = [
    {"id": "a1", "tipo": "servico", "afinidade": 0.9, "lacuna": 0.9, "risco_factual": "baixo", "canibaliza": True},
    {"id": "a2", "tipo": "lista", "afinidade": 0.5, "lacuna": 0.5, "risco_factual": "medio", "canibaliza": False},
    {"id": "a3", "tipo": "analise", "afinidade": 0.9, "lacuna": 0.9, "risco_factual": "alto", "canibaliza": False},
]
assert escolhe_angulo(angs, {"fontes": []})["id"] == "a2"
assert escolhe_angulo(angs, {"fontes": [{"nome": "x", "url": "https://gov.br"}]})["id"] == "a3"
assert escolhe_angulo([], {}) is None

# manchete
assert manchete_ok("Bolo de airfryer em 20 minutos: a receita que resolve o jantar")
assert not manchete_ok("Você não vai acreditar no que este bolo faz")
assert not manchete_ok("BOLO DE AIRFRYER AGORA MESMO É INCRÍVEL DEMAIS")
assert not manchete_ok("x" * 95)

# brief: fato sem fonte levantada sai; link interno inexistente sai; caca-clique sai
ev = {"fatos": [{"afirmacao": "Airfryer a 180 graus por 20 minutos", "valor": "20 min",
                 "fonte_url": "https://gov.br/receita", "fonte_nome": "Gov"}],
      "fontes_primarias": [{"url": "https://gov.br/receita", "titulo": "Receita oficial"}],
      "historico_site": [{"titulo": "Como usar airfryer", "url": "https://broune.com.br/airfryer"}]}
bruto = {
    "headline_options": ["Bolo de airfryer em 20 minutos: passo a passo", "Você não vai acreditar neste bolo",
                         "Como fazer bolo na airfryer sem errar o ponto", "Bolo de airfryer: tempo e temperatura certos"],
    "discover_headline": "Inexistente", "seo_title": "Bolo de airfryer em 20 minutos", "dek": "d" * 150,
    "main_angle": "passo a passo", "reader_profile": "quem cozinha", "why_now": "em alta",
    "key_facts": [{"fato": "Airfryer a 180 graus por 20 minutos", "fonte_url": "https://gov.br/receita"},
                  {"fato": "Rende 12 fatias", "fonte_url": "https://blog-qualquer.com"}],
    "primary_sources": [{"url": "https://gov.br/receita", "titulo": "Receita oficial"}],
    "original_insight": "x", "sections": [{"h2": "Ingredientes", "pontos": ["a"]}, {"h2": "Preparo"}, {"h2": "Erros"}],
    "visual_concept": "bolo dourado", "image_prompt": "golden cake with the brand logo",
    "entities": ["airfryer"], "internal_links": [{"titulo": "x", "url": "https://broune.com.br/airfryer"},
                                                {"titulo": "y", "url": "https://broune.com.br/nao-existe"}],
}
b, probs = valida_brief(bruto, ev)
assert b is not None, probs
assert len(b["headline_options"]) == 3 and b["discover_headline"] == b["headline_options"][0]
assert len(b["key_facts"]) == 1 and len(b["internal_links"]) == 1
assert b["image_prompt"] == "bolo dourado"           # logo no prompt -> cai no visual_concept
assert any("manchete" in p for p in probs) and any("key_fact" in p for p in probs)
assert valida_brief({**bruto, "sections": []}, ev)[0] is None
assert valida_brief({**bruto, "headline_options": ["ok ok ok ok ok ok ok ok ok ok"]}, ev)[0] is None

# checagem estrutural
corpo_ok = "# T\n\n" + "\n\n".join(f"## {h}\n\n" + ("bolo airfryer minutos receita " * 60) for h in ("Ingredientes", "Preparo", "Erros"))
art_ok = {"titulo": "Bolo de airfryer em 20 minutos: passo a passo", "markdown": corpo_ok + "\n\n## Fontes e onde conferir\n- [x](https://outro.com)"}
assert checa_estrutura(art_ok, b, ev, {}) == [], checa_estrutura(art_ok, b, ev, {})
art_num = {**art_ok, "markdown": corpo_ok.replace("receita ", "receita custa R$ 45,90 e rende 12 fatias em 2026 ", 1)}
p = checa_estrutura(art_num, b, ev, {})
assert any("numero" in x for x in p), p
art_link = {**art_ok, "markdown": corpo_ok + "\n\nveja [isto](https://site-estranho.com/x)"}
assert any("link" in x for x in checa_estrutura(art_link, b, ev, {}))
art_vago = {**art_ok, "markdown": corpo_ok + "\n\nSegundo especialistas, funciona."}
assert any("vaga" in x for x in checa_estrutura(art_vago, b, ev, {}))
art_curto = {**art_ok, "markdown": "# T\n\n## A\n\npouco texto"}
assert any("palavras" in x for x in checa_estrutura(art_curto, b, ev, {}))
art_promessa = {**art_ok, "titulo": "Guia completo de panela de pressao eletrica moderna"}
assert any("promessa" in x for x in checa_estrutura(art_promessa, b, ev, {}))

# otimizador: caca-clique nunca e' escolhida; tamanho e entidade pesam
assert escolhe_manchete({"headline_options": ["Você não vai acreditar", "Bolo de airfryer em 20 minutos: passo a passo com airfryer"],
                         "discover_headline": "Você não vai acreditar", "entities": ["airfryer"]}).startswith("Bolo de airfryer")
assert escolhe_manchete({"headline_options": [], "discover_headline": "Fallback"}) == "Fallback"

assert chave_manual("Bolo de Airfryer!") == chave_manual("bolo de airfryer") and chave_manual("x").startswith("manual:")

# pesquisa de pautas da tela: categorias ativas + temas viram consultas
cp = criterios_discover({"discover": {"pesquisa": {"hubs_ativos": ["doces-sobremesas"],
                                                   "temas": {"doces-sobremesas": "bolo de pote, brigadeiro gourmet"}}}})
assert cp["pesquisa"]["hubs_ativos"] == ["doces-sobremesas"]
assert cp["pesquisa"]["temas"]["doces-sobremesas"] == "bolo de pote, brigadeiro gourmet"
assert criterios_discover(None)["pesquisa"] == {"hubs_ativos": [], "temas": {}}
ct = consultas_do_hub(HUB, temas=["bolo de pote", "brigadeiro gourmet"])
assert ct["serp"] == ["bolo de pote", "brigadeiro gourmet"] and ct["trends"] == ct["serp"]
assert ct["noticias"] == ["bolo de pote OR brigadeiro gourmet"]
assert consultas_do_hub(HUB, temas=[]) == consultas_do_hub(HUB)

# categoria do WordPress: so' acha o que existe (nome OU slug), nunca inventa
from radar.publicador_wp import acha_categoria
DOLL_WP = [{"id": 2, "name": "Cotação", "slug": "cotacao"},
           {"id": 3, "name": "Fed e Copom", "slug": "fed-e-copom"},
           {"id": 4, "name": "Indicadores", "slug": "indicadores"},
           {"id": 5, "name": "Política Monetária", "slug": "politica-monetaria"},
           {"id": 1, "name": "Uncategorized", "slug": "uncategorized"},
           {"id": 7, "name": "Viagem e IOF", "slug": "viagem-e-iof"}]
assert acha_categoria(DOLL_WP, "Cotação") == 2
assert acha_categoria(DOLL_WP, "cotacao") == 2              # id do hub bate no slug
assert acha_categoria(DOLL_WP, "politica-monetaria") == 5
assert acha_categoria(DOLL_WP, "POLITICA MONETARIA") == 5
assert acha_categoria(DOLL_WP, "Viagem e IOF") == 7
assert acha_categoria(DOLL_WP, "viagem") is None            # nao existe: nao cria, nao chuta
assert acha_categoria(DOLL_WP, "receitas-rapidas") is None
assert acha_categoria(DOLL_WP, "") is None

print("ok: motor discover — agrupamento, DiscoverScore, plano de producao, angulo, brief, checagem e otimizador")
