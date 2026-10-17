"""Carrega config/sites.yaml e as variaveis de ambiente."""
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ / ".env")


def carrega_sites(caminho: Path | None = None) -> dict:
    caminho = caminho or RAIZ / "config" / "sites.yaml"
    with open(caminho, encoding="utf-8") as f:
        dados = yaml.safe_load(f)
    return dados.get("sites", {})


def env(nome: str, obrigatorio: bool = False) -> str | None:
    valor = os.getenv(nome)
    if obrigatorio and not valor:
        raise RuntimeError(f"Variavel de ambiente {nome} nao definida (ver .env.example)")
    return valor


def _lista_env(nome: str) -> set[str]:
    return {s.strip() for s in (env(nome) or "").split(",") if s.strip()}


def site_ativo(nome: str) -> bool:
    """Este ambiente roda o site? (16/10/2026, doll no Mac.)

    RADAR_SITES      lista branca: so' estes rodam aqui (o Mac usa "doll").
    RADAR_IGNORA_SITES  lista negra: estes rodam em outro lugar (o GitHub
                     Actions recebe "doll" pela variavel do repositorio
                     quando o Mac assume). Vazias = todos, como antes.
    Sem isso o doll rodaria nos dois lados e publicaria em dobro."""
    so = _lista_env("RADAR_SITES")
    return (not so or nome in so) and nome not in _lista_env("RADAR_IGNORA_SITES")


def filtra_sites(sites: dict) -> dict:
    """Os sites do dict que este ambiente roda (ver site_ativo)."""
    ignorados = [n for n in sites if not site_ativo(n)]
    if ignorados:
        print(f"  (fora deste ambiente: {', '.join(ignorados)})")
    return {n: c for n, c in sites.items() if site_ativo(n)}
