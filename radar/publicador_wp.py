"""Publica no WordPress pela REST API.

Autenticacao por Application Password (Usuarios -> Perfil -> Senhas de aplicativo).
Nunca a senha da conta: a senha de aplicativo se revoga sozinha sem derrubar o login.

Idempotente: o artigo guarda o id do post no banco. Rodar duas vezes atualiza o
mesmo post em vez de criar duplicata — importante porque duplicata em site de
noticia e' problema de indexacao, nao so' bagunca.
"""
from __future__ import annotations

import base64
import re

import requests

TEMPO_LIMITE = 30


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


def publica(artigo: dict, wp: dict) -> dict:
    """artigo: linha da tabela 'artigos'. wp: bloco 'wordpress' do sites.yaml
    ja' com usuario e senha resolvidos. Devolve {id, link, status}."""
    base = wp["url"].rstrip("/")
    cab = _cabecalho(wp["usuario"], wp["senha_app"])

    corpo = {
        "title": artigo["titulo"],
        "content": markdown_para_html(artigo["corpo_md"]),
        "excerpt": (artigo.get("resumo") or "")[:300],
        "status": "publish" if artigo["status"] == "publicada" else "draft",
        # O JSON-LD vai em meta, nao no corpo: o WordPress limpa <script> do
        # conteudo. O mu-plugin em wordpress/ imprime isso no <head>.
        "meta": {"radar_jsonld": artigo.get("jsonld") or ""},
    }

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
    return {"id": dados["id"], "link": dados.get("link"), "status": dados.get("status")}
