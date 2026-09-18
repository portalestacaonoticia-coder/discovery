"""Publica no WordPress pela REST API.

Autenticacao por Application Password (Usuarios -> Perfil -> Senhas de aplicativo).
Nunca a senha da conta: a senha de aplicativo se revoga sozinha sem derrubar o login.

Idempotente: o artigo guarda o id do post no banco. Rodar duas vezes atualiza o
mesmo post em vez de criar duplicata — importante porque duplicata em site de
noticia e' problema de indexacao, nao so' bagunca. A imagem destacada segue a
mesma regra: o id da midia fica no artigo e nao se reenvia a cada rodada, senao
a biblioteca do WP enche de copias do mesmo arquivo.

Imagem destacada (radar/imagens.py) e' o que destrava o Google Discover: sem
imagem >= 1200px declarada, o card praticamente nao aparece. Passar `site` para
`publica()` liga a busca; sem ele, o post sai sem imagem, como antes.
"""
from __future__ import annotations

import base64
import json
import re
import unicodedata

import requests

TEMPO_LIMITE = 30
TEMPO_LIMITE_MIDIA = 60      # upload de imagem e' mais lento que um POST de texto


class ErroWordPress(Exception):
    pass


def _cabecalho(usuario: str, senha_app: str) -> dict:
    credencial = base64.b64encode(f"{usuario}:{senha_app}".encode()).decode()
    return {"Authorization": f"Basic {credencial}",
            "Content-Type": "application/json",
            "User-Agent": "RadarPautas/1.0"}


def markdown_para_html(md: str) -> str:
    """Conversor minimo — o gerador produz markdown previsivel, entao nao vale
    arrastar dependencia pesada. Cobre: h1-h3, tabela, negrito, italico, link,
    paragrafo e regua."""
    linhas = md.split("\n")
    saida, tabela = [], []

    def fecha_tabela():
        if not tabela:
            return
        cabecalho, *resto = tabela
        corpo = [l for l in resto if not re.match(r"^\|[\s:|-]+\|$", l)]
        def celulas(linha, tag):
            partes = [c.strip() for c in linha.strip().strip("|").split("|")]
            return "".join(f"<{tag}>{c}</{tag}>" for c in partes)
        html = ["<figure class=\"wp-block-table\"><table><thead><tr>",
                celulas(cabecalho, "th"), "</tr></thead><tbody>"]
        for linha in corpo:
            html += ["<tr>", celulas(linha, "td"), "</tr>"]
        html.append("</tbody></table></figure>")
        saida.append("".join(html))
        tabela.clear()

    paragrafo: list[str] = []

    def fecha_paragrafo():
        if paragrafo:
            saida.append(f"<p>{' '.join(paragrafo).strip()}</p>")
            paragrafo.clear()

    for linha in linhas:
        crua = linha.rstrip()
        if crua.startswith("|"):
            fecha_paragrafo()
            tabela.append(crua)
            continue
        fecha_tabela()

        if not crua.strip():
            fecha_paragrafo()
        elif crua.startswith("### "):
            fecha_paragrafo(); saida.append(f"<h3>{crua[4:]}</h3>")
        elif crua.startswith("## "):
            fecha_paragrafo(); saida.append(f"<h2>{crua[3:]}</h2>")
        elif crua.startswith("# "):
            fecha_paragrafo()   # o H1 e' o titulo do post; nao repetir no corpo
        elif crua.strip() == "---":
            fecha_paragrafo(); saida.append("<hr/>")
        else:
            paragrafo.append(crua.strip())

    fecha_paragrafo(); fecha_tabela()

    html = "\n".join(saida)
    html = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r'<a href="\2">\1</a>', html)
    html = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", html)
    html = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", html)
    return html


def _categoria_id(base: str, cab: dict, nome: str) -> int | None:
    """Acha a categoria do hub, cria se nao existir. Categoria = hub mantem o
    cluster arrumado sem trabalho manual."""
    r = requests.get(f"{base}/wp-json/wp/v2/categories", headers=cab,
                     params={"search": nome, "per_page": 10}, timeout=TEMPO_LIMITE)
    r.raise_for_status()
    for c in r.json():
        if c["name"].lower() == nome.lower():
            return c["id"]
    r = requests.post(f"{base}/wp-json/wp/v2/categories", headers=cab,
                      json={"name": nome}, timeout=TEMPO_LIMITE)
    if r.status_code >= 400:
        return None
    return r.json().get("id")


def _nome_arquivo(titulo: str, tipo: str) -> str:
    """Slug ASCII + extensao. O WP usa o nome do arquivo na URL da midia, e
    acento ali vira %C3%A3 no og:image."""
    sem_acento = (unicodedata.normalize("NFKD", titulo)
                  .encode("ascii", "ignore").decode())
    slug = re.sub(r"[^a-z0-9]+", "-", sem_acento.lower()).strip("-")[:60] or "imagem"
    ext = {"image/jpeg": "jpg", "image/png": "png",
           "image/webp": "webp", "image/gif": "gif"}.get(tipo, "jpg")
    return f"{slug}.{ext}"


def envia_midia(base: str, cab: dict, imagem: dict, titulo: str) -> dict | None:
    """Sobe a imagem para a biblioteca e devolve {id, source_url}.

    Falha aqui NAO derruba a publicacao: post sem imagem e' melhor que post
    nenhum. Devolve None e quem chama segue sem imagem destacada.
    """
    nome = _nome_arquivo(titulo, imagem.get("tipo", "image/jpeg"))
    cabecalho = {"Authorization": cab["Authorization"],
                 "User-Agent": cab["User-Agent"],
                 "Content-Type": imagem.get("tipo", "image/jpeg"),
                 "Content-Disposition": f'attachment; filename="{nome}"'}
    try:
        r = requests.post(f"{base}/wp-json/wp/v2/media", headers=cabecalho,
                          data=imagem["conteudo"], timeout=TEMPO_LIMITE_MIDIA)
        if r.status_code >= 400:
            print(f"  [imagem] WP recusou o upload ({r.status_code}): {r.text[:200]}")
            return None
        midia = r.json()
    except Exception as erro:
        print(f"  [imagem] falha no upload: {erro}")
        return None

    # alt e legenda vao num segundo POST: o upload binario nao carrega campo.
    # O alt descreve a ILUSTRACAO, nao o fato — ver docstring de imagens.py.
    alt = (imagem.get("alt") or "").strip()[:200]
    credito = (imagem.get("credito") or "").strip()
    if alt or credito:
        try:
            requests.post(f"{base}/wp-json/wp/v2/media/{midia['id']}", headers=cab,
                          json={k: v for k, v in
                                (("alt_text", alt), ("caption", credito)) if v},
                          timeout=TEMPO_LIMITE)
        except Exception:
            pass      # imagem ja' esta' no ar; alt e' um plus, nao um portao
    return {"id": midia["id"], "source_url": midia.get("source_url")}


def _jsonld_com_imagem(jsonld: str | None, url_imagem: str | None,
                       largura: int | None = None,
                       altura: int | None = None) -> str:
    """Injeta a imagem no schema.org do artigo — a declaracao que o Discover
    le. Mantem o ImageObject com largura/altura para o card nao depender do
    Google inferir o tamanho. JSON invalido passa intacto."""
    if not jsonld or not url_imagem:
        return jsonld or ""
    try:
        dados = json.loads(jsonld)
    except (json.JSONDecodeError, TypeError):
        return jsonld
    if not isinstance(dados, dict):
        return jsonld
    imagem = {"@type": "ImageObject", "url": url_imagem}
    if largura and altura:
        imagem["width"], imagem["height"] = largura, altura
    dados["image"] = [imagem]
    return json.dumps(dados, ensure_ascii=False, indent=2)


def publica(artigo: dict, wp: dict, site: dict | None = None) -> dict:
    """artigo: linha da tabela 'artigos'. wp: bloco 'wordpress' do sites.yaml
    ja' com usuario e senha resolvidos. site: bloco inteiro do site — quando
    vem, o post ganha imagem destacada (exigencia do Discover).

    Devolve {id, link, status, midia_id, imagem_url, imagem_credito}.
    """
    base = wp["url"].rstrip("/")
    cab = _cabecalho(wp["usuario"], wp["senha_app"])

    # -- imagem destacada ---------------------------------------------------
    # Reaproveita a midia ja' enviada (rerodada nao duplica a biblioteca).
    midia_id = artigo.get("wp_media_id")
    imagem_url = artigo.get("imagem_url")
    imagem_credito = artigo.get("imagem_credito")
    largura = altura = None

    if site and not midia_id:
        from . import imagens
        consulta = imagens.consulta_do_hub(site, artigo.get("hub"))
        achada = imagens.busca(consulta) if consulta else None
        if achada:
            enviada = envia_midia(base, cab, achada, artigo["titulo"])
            if enviada:
                midia_id = enviada["id"]
                imagem_url = enviada["source_url"]
                imagem_credito = achada.get("credito")
                largura, altura = achada.get("largura"), achada.get("altura")
                print(f"  [imagem] {largura}x{altura} de {achada.get('fonte')} "
                      f"-> midia {midia_id}")
        elif consulta:
            print(f"  [imagem] nada >= {imagens.MIN_LARGURA}px para “{consulta}”")

    corpo = {
        "title": artigo["titulo"],
        "content": markdown_para_html(artigo["corpo_md"]),
        "excerpt": (artigo.get("resumo") or "")[:300],
        "status": "publish" if artigo["status"] == "publicada" else "draft",
        # O JSON-LD vai em meta, nao no corpo: o WordPress limpa <script> do
        # conteudo. O mu-plugin em wordpress/ imprime isso no <head>.
        "meta": {"radar_jsonld": _jsonld_com_imagem(
            artigo.get("jsonld"), imagem_url, largura, altura)},
    }
    if midia_id:
        # E' daqui que saem o og:image e o card do Discover.
        corpo["featured_media"] = midia_id

    if artigo.get("hub") and wp.get("categoria_por_hub", True):
        cid = _categoria_id(base, cab, artigo["hub"])
        if cid:
            corpo["categories"] = [cid]

    post_id = artigo.get("wp_post_id")
    if post_id:
        url = f"{base}/wp-json/wp/v2/posts/{post_id}"
    else:
        url = f"{base}/wp-json/wp/v2/posts"

    r = requests.post(url, headers=cab, json=corpo, timeout=TEMPO_LIMITE)
    if r.status_code >= 400:
        raise ErroWordPress(f"{r.status_code}: {r.text[:300]}")
    dados = r.json()
    return {"id": dados["id"], "link": dados.get("link"),
            "status": dados.get("status"), "midia_id": midia_id,
            "imagem_url": imagem_url, "imagem_credito": imagem_credito}
