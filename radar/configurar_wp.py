"""Configuracao inicial de um WordPress novo, pela REST API.

    python -m radar.configurar_wp --site doll --seco   # so' mostra o que faria
    python -m radar.configurar_wp --site doll

Idempotente: rodar duas vezes nao quebra nada e nao duplica nada. O que ja'
esta' certo e' reportado como "ja' ok".

Site novo: copiar o bloco 'configuracao_inicial' no sites.yaml, trocar os textos
e rodar. E' a parte chata do WordPress feita uma vez, em codigo, para todos os
dominios.

Precisa rodar de uma maquina que ALCANCE o site: a sua, ou o GitHub Actions.
"""
from __future__ import annotations

import argparse
import base64
import os
import sys

import requests

from .config import carrega_sites

TEMPO = 30


def cabecalho(usuario: str, senha: str) -> dict:
    cred = base64.b64encode(f"{usuario}:{senha}".encode()).decode()
    return {"Authorization": f"Basic {cred}", "Content-Type": "application/json",
            "User-Agent": "RadarPautas/1.0"}


class Wp:
    def __init__(self, url: str, usuario: str, senha: str, seco: bool = False):
        self.base = url.rstrip("/") + "/wp-json"
        self.cab = cabecalho(usuario, senha)
        self.seco = seco

    def get(self, caminho: str, **kw):
        return requests.get(self.base + caminho, headers=self.cab, timeout=TEMPO, **kw)

    def post(self, caminho: str, dados: dict):
        if self.seco:
            print(f"  [seco] POST {caminho} {dados}")
            return None
        r = requests.post(self.base + caminho, headers=self.cab, json=dados, timeout=TEMPO)
        if r.status_code >= 400:
            raise RuntimeError(f"POST {caminho} -> {r.status_code}: {r.text[:300]}")
        return r.json()

    def delete(self, caminho: str, **params):
        if self.seco:
            print(f"  [seco] DELETE {caminho} {params}")
            return None
        r = requests.delete(self.base + caminho, headers=self.cab,
                            params=params, timeout=TEMPO)
        if r.status_code >= 400:
            raise RuntimeError(f"DELETE {caminho} -> {r.status_code}: {r.text[:300]}")
        return r.json()


def ajusta_opcoes(wp: Wp, cfg: dict) -> None:
    atual = wp.get("/wp/v2/settings")
    atual.raise_for_status()
    atual = atual.json()

    desejado = {
        "title": cfg["titulo"],
        "description": cfg["tagline"],
        "timezone": cfg.get("fuso", "America/Sao_Paulo"),
        "date_format": cfg.get("formato_data", "j \\d\\e F \\d\\e Y"),
        "time_format": cfg.get("formato_hora", "H:i"),
        "start_of_week": cfg.get("inicio_semana", 1),
    }
    mudar = {k: v for k, v in desejado.items() if atual.get(k) != v}
    if not mudar:
        print("  opcoes: ja' ok")
        return
    for k, v in mudar.items():
        print(f"  opcao {k}: {atual.get(k)!r} -> {v!r}")
    wp.post("/wp/v2/settings", mudar)


def limpa_exemplos(wp: Wp) -> None:
    """Manda para a lixeira (nao apaga de vez): reversivel se voce se arrepender."""
    alvos = [("/wp/v2/posts", "hello-world"), ("/wp/v2/pages", "sample-page")]
    for rota, slug in alvos:
        r = wp.get(rota, params={"slug": slug, "status": "publish,draft"})
        if not r.ok or not r.json():
            print(f"  {slug}: nao encontrado (ja' ok)")
            continue
        for item in r.json():
            print(f"  lixeira: {item['id']} — {item['title']['rendered']}")
            wp.delete(f"{rota}/{item['id']}")


def instala_plugins(wp: Wp, slugs: list[str]) -> None:
    for slug in slugs:
        r = wp.get(f"/wp/v2/plugins", params={"search": slug})
        ja = [p for p in (r.json() if r.ok else []) if p.get("plugin", "").startswith(slug)]
        if ja and ja[0].get("status") == "active":
            print(f"  plugin {slug}: ja' ativo")
            continue
        try:
            wp.post("/wp/v2/plugins", {"slug": slug, "status": "active"})
            print(f"  plugin {slug}: instalado e ativado")
        except RuntimeError as erro:
            # Hospedagem com filesystem travado recusa instalacao por API.
            # Nao e' motivo para abortar o resto: avisa e segue.
            print(f"  plugin {slug}: FALHOU ({erro}). Instale pelo painel.")


def main() -> int:
    p = argparse.ArgumentParser(description="Configuracao inicial do WordPress")
    p.add_argument("--site", required=True)
    p.add_argument("--seco", action="store_true")
    args = p.parse_args()

    site = carrega_sites()[args.site]
    wpcfg = site.get("wordpress") or {}
    cfg = wpcfg.get("configuracao_inicial")
    if not cfg:
        print(f"site '{args.site}' nao tem bloco wordpress.configuracao_inicial")
        return 1

    try:
        usuario = os.environ[wpcfg["usuario_env"]]
        senha = os.environ[wpcfg["senha_env"]]
    except KeyError as erro:
        print(f"variavel de ambiente {erro} nao definida (ver .env.example)")
        return 1

    wp = Wp(wpcfg["url"], usuario, senha, seco=args.seco)

    try:
        eu = wp.get("/wp/v2/users/me")
    except requests.RequestException as erro:
        print(f"nao consegui alcancar {wpcfg['url']}: {erro}\n"
              "Rode da sua maquina ou pelo workflow 'configurar-wordpress' no GitHub.")
        return 1
    if not eu.ok:
        print(f"autenticacao falhou ({eu.status_code}): {eu.text[:200]}")
        return 1
    caps = eu.json().get("capabilities", {})
    print(f"conectado como {eu.json().get('name')} "
          f"(admin: {bool(caps.get('manage_options'))})")

    print("\nopcoes do site:")
    ajusta_opcoes(wp, cfg)

    if cfg.get("limpar_exemplos"):
        print("\nconteudo de exemplo:")
        limpa_exemplos(wp)

    if cfg.get("plugins"):
        print("\nplugins:")
        instala_plugins(wp, cfg["plugins"])

    print("\npronto. Confira em janela anonima:", wpcfg["url"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
