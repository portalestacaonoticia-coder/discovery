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
