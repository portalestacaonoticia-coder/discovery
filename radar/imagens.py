"""Ponte unica com bancos de imagem gratuitos — a imagem que o Discover exige.

O Discover e' uma superficie de CARDS: sem imagem grande declarada, o post
praticamente nao aparece. A exigencia do Google (developers.google.com/search/
docs/appearance/google-discover) e' objetiva:

    largura >= 1200 px  E  largura x altura >= 300.000 px
    declarada em og:image ou schema.org, com max-image-preview:large

Melhoria, nunca dependencia (mesmo padrao do llm.py): sem provedor disponivel
devolve None e o post sai sem imagem, exatamente como saia antes.

DECISAO QUE VALE ENTENDER — a imagem e' ILUSTRACAO TEMATICA, nao registro do
fato. A busca usa o termo do HUB (config/sites.yaml), nunca o titulo da
materia: foto de banco de imagem nao retrata o fato noticiado, e fazer passar
por isso e' legenda enganosa — o mesmo erro que os portoes de publicacao
existem para evitar. Hub sobre pessoa real leva `imagem: false` no yaml: foto
de stock ao lado do nome de um cidadao vivo sugere que e' ele, e nao e'.

Provedores, nesta ordem:
  1. Pexels    (PEXELS_API_KEY) — licenca livre para uso comercial, sem
               exigencia de credito. Melhor qualidade e relevancia.
  2. Openverse (sem chave nenhuma) — agregador de Creative Commons do
               WordPress.org. Filtrado por licenca que permite uso comercial;
               o credito e' OBRIGATORIO (CC-BY), entao ele sempre viaja junto
               e o publicador grava na legenda da midia.

A dimensao nao e' confiada ao provedor: o candidato e' BAIXADO e medido nos
bytes (ver `dimensoes`). E' o mesmo principio dos portoes do dolar — o numero
errado sai em toda materia.
"""
from __future__ import annotations

import requests

from .config import env

MIN_LARGURA = 1200
MIN_PIXELS = 300_000
TEMPO_LIMITE = 20
# Acima disso nao vale a pena: o upload para o WP fica lento e o Core Web
# Vitals (tambem cobrado pelo Discover) piora.
MAX_BYTES = 8 * 1024 * 1024
CANDIDATOS = 8
# Teto do acesso ANONIMO do Openverse: 21 ja' devolve 401 Unauthorized.
# Nao subir sem registrar uma aplicacao e mandar token.
CANDIDATOS_OPENVERSE = 20

CABECALHO = {"User-Agent": "RadarPautas/1.0 (+https://tihee.com.br)"}


# -- medicao real dos bytes -------------------------------------------------

# SOF do JPEG: 0xC0-0xCF menos DHT (C4), JPG (C8) e DAC (CC).
_SOF = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
        0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}


def dimensoes(dados: bytes) -> tuple[int, int] | None:
    """(largura, altura) lidas do cabecalho do arquivo. None se nao reconhecer.

    Puro Python de proposito: arrastar Pillow para ler 8 bytes de cabecalho
    nao se paga num cron que roda de 30 em 30 minutos.
    """
    if len(dados) < 24:
        return None

    if dados[:8] == b"\x89PNG\r\n\x1a\n":
        return (int.from_bytes(dados[16:20], "big"),
                int.from_bytes(dados[20:24], "big"))

    if dados[:6] in (b"GIF87a", b"GIF89a"):
        return (int.from_bytes(dados[6:8], "little"),
                int.from_bytes(dados[8:10], "little"))

    if dados[:4] == b"RIFF" and dados[8:12] == b"WEBP":
        marca = dados[12:16]
        if marca == b"VP8X":
            return (int.from_bytes(dados[24:27], "little") + 1,
                    int.from_bytes(dados[27:30], "little") + 1)
        if marca == b"VP8 ":
            return (int.from_bytes(dados[26:28], "little") & 0x3FFF,
                    int.from_bytes(dados[28:30], "little") & 0x3FFF)
        if marca == b"VP8L":
            b = int.from_bytes(dados[21:25], "little")
            return ((b & 0x3FFF) + 1, ((b >> 14) & 0x3FFF) + 1)
        return None

    if dados[:2] == b"\xff\xd8":                      # JPEG: anda pelos marcadores
        i = 2
        limite = len(dados)
        while i < limite - 9:
            if dados[i] != 0xFF:
                i += 1
                continue
            marcador = dados[i + 1]
            if marcador == 0xFF:                      # preenchimento
                i += 1
                continue
            if marcador in (0xD8, 0x01) or 0xD0 <= marcador <= 0xD7:
                i += 2
                continue
            if marcador == 0xD9 or marcador == 0xDA:  # fim / inicio do scan
                break
            tamanho = int.from_bytes(dados[i + 2:i + 4], "big")
            if tamanho < 2:
                break
            if marcador in _SOF:
                return (int.from_bytes(dados[i + 7:i + 9], "big"),
                        int.from_bytes(dados[i + 5:i + 7], "big"))
            i += 2 + tamanho
    return None


def serve(largura: int, altura: int) -> bool:
    """O criterio do Discover, em uma linha."""
    return largura >= MIN_LARGURA and largura * altura >= MIN_PIXELS


# -- provedores -------------------------------------------------------------

def _pexels(consulta: str, chave: str) -> list[dict]:
    r = requests.get("https://api.pexels.com/v1/search",
                     headers={**CABECALHO, "Authorization": chave},
                     params={"query": consulta, "per_page": CANDIDATOS,
                             "orientation": "landscape", "size": "large"},
                     timeout=TEMPO_LIMITE)
    r.raise_for_status()
    saida = []
    for foto in r.json().get("photos", []):
        src = foto.get("src") or {}
        # large2x e' ~1880px de largura — acima do minimo com folga e bem mais
        # leve que o original (que as vezes passa de 5000px).
        url = src.get("large2x") or src.get("original")
        if not url:
            continue
        saida.append({
            "url": url,
            "largura": foto.get("width"), "altura": foto.get("height"),
            "alt": (foto.get("alt") or "").strip(),
            "autor": foto.get("photographer") or "",
            "autor_url": foto.get("photographer_url") or "",
            "origem_url": foto.get("url") or "",
            "fonte": "Pexels", "licenca": "Pexels License",
            "licenca_url": "https://www.pexels.com/license/",
            "credito_obrigatorio": False,
        })
    return saida


def _openverse(consulta: str) -> list[dict]:
    # Os tres parametros abaixo foram medidos contra a API em 18/09, e cada um
    # importa (numa amostra de 3 consultas, 20 resultados cada):
    #   size=large        -> ESSENCIAL. Com ele, 19-20 de 20 passam no criterio
    #                        do Discover; sem ele, ZERO passa.
    #   aspect_ratio=wide -> removido: junto com os outros derrubava tudo, e a
    #                        proporcao nao e' exigencia, so' recomendacao.
    #   page_size<=20     -> teto do acesso anonimo. 21 ja' devolve 401.
    r = requests.get("https://api.openverse.org/v1/images/",
                     headers=CABECALHO,
                     params={"q": consulta, "page_size": CANDIDATOS_OPENVERSE,
                             "license_type": "commercial", "size": "large",
                             "mature": "false"},
                     timeout=TEMPO_LIMITE)
    r.raise_for_status()
    saida = []
    for img in r.json().get("results", []):
        url = img.get("url")
        if not url:
            continue
        licenca = (img.get("license") or "").upper()
        versao = img.get("license_version") or ""
        saida.append({
            "url": url,
            "largura": img.get("width"), "altura": img.get("height"),
            "alt": (img.get("title") or "").strip(),
            "autor": img.get("creator") or "",
            "autor_url": img.get("creator_url") or "",
            "origem_url": img.get("foreign_landing_url") or "",
            "fonte": img.get("source") or "Openverse",
            "licenca": f"{licenca} {versao}".strip(),
            "licenca_url": img.get("license_url") or "",
            # CC-BY e derivados exigem credito visivel. CC0/PDM nao, mas
            # creditar de graca nao custa nada e evita discussao.
            "credito_obrigatorio": licenca not in ("CC0", "PDM"),
        })
    return saida


def _candidatos(consulta: str) -> list[dict]:
    chave = env("PEXELS_API_KEY")
    if chave:
        try:
            achados = _pexels(consulta, chave)
            if achados:
                return achados
        except Exception as erro:
            print(f"  [imagem] Pexels falhou ({erro}); tentando Openverse")
    try:
        return _openverse(consulta)
    except Exception as erro:
        print(f"  [imagem] Openverse falhou: {erro}")
        return []


# -- entrada publica --------------------------------------------------------

def credito_de(img: dict) -> str:
    """Linha de credito pronta para a legenda da midia no WordPress."""
    partes = []
    if img.get("autor"):
        partes.append(f"Foto: {img['autor']}")
    if img.get("fonte"):
        partes.append(img["fonte"])
    if img.get("licenca"):
        partes.append(img["licenca"])
    return " / ".join(partes)


def busca(consulta: str) -> dict | None:
    """A primeira imagem que REALMENTE cumpre o criterio do Discover.

    Tenta a consulta do hub e, se nada servir, uma versao encurtada — termo de
    4 palavras acha pouco no acervo livre, e 2 palavras costumam resolver
    ("gas station fuel pump car" -> "gas station").

    Devolve {conteudo: bytes, tipo, largura, altura, alt, credito, ...} ou
    None — sem provedor, sem resultado ou nenhum candidato no tamanho.
    """
    if not consulta:
        return None
    tentativas = [consulta]
    curta = " ".join(consulta.split()[:2])
    if curta and curta != consulta:
        tentativas.append(curta)

    for tentativa in tentativas:
        achada = _tenta(tentativa)
        if achada:
            return achada
    return None


def _tenta(consulta: str) -> dict | None:
    for cand in _candidatos(consulta):
        # Descarta cedo pelo tamanho declarado, para nao baixar o que ja' se
        # sabe pequeno. Sem os campos, segue para a medicao real.
        l, a = cand.get("largura"), cand.get("altura")
        if isinstance(l, int) and isinstance(a, int) and not serve(l, a):
            continue
        try:
            r = requests.get(cand["url"], headers=CABECALHO,
                             timeout=TEMPO_LIMITE, stream=True)
            r.raise_for_status()
            tamanho = int(r.headers.get("content-length") or 0)
            if tamanho > MAX_BYTES:
                continue
            conteudo = r.content
        except Exception:
            continue
        if len(conteudo) > MAX_BYTES:
            continue

        medida = dimensoes(conteudo)
        if not medida or not serve(*medida):
            continue

        tipo = (r.headers.get("content-type") or "").split(";")[0].strip()
        if not tipo.startswith("image/"):
            tipo = "image/jpeg"
        return {**cand, "conteudo": conteudo, "tipo": tipo,
                "largura": medida[0], "altura": medida[1],
                "credito": credito_de(cand)}
    return None


def consulta_do_hub(site: dict, hub_id: str | None) -> str | None:
    """O termo de busca do hub em config/sites.yaml.

    `imagem: false` no hub desliga a imagem ali (hub sobre pessoa real).
    Sem `imagem`, cai no titulo do hub; sem hub, na entidade do site.
    """
    for hub in site.get("hubs", []) or []:
        if hub.get("id") != hub_id:
            continue
        termo = hub.get("imagem", None)
        if termo is False:
            return None
        if isinstance(termo, str) and termo.strip():
            return termo.strip()
        return (hub.get("titulo") or "").strip() or None
    return (site.get("entidade") or "").split("—")[0].strip() or None
