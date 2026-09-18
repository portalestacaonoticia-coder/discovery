"""Teste da busca de imagem — mede de verdade, nao confia no provedor.

    python testar_imagem.py                 # so' o medidor, offline
    python testar_imagem.py --rede          # busca de verdade em cada hub

O medidor roda sempre e nao toca a rede: ele e' o portao que garante os
1200px do Discover. Nada e' publicado aqui.
"""
from __future__ import annotations

import argparse
import struct
import sys
import zlib

from radar import imagens
from radar.config import carrega_sites


def _png(largura: int, altura: int) -> bytes:
    """PNG minimo valido, so' para exercitar o leitor de cabecalho."""
    def bloco(tipo: bytes, dados: bytes) -> bytes:
        return (struct.pack(">I", len(dados)) + tipo + dados
                + struct.pack(">I", zlib.crc32(tipo + dados) & 0xFFFFFFFF))
    ihdr = struct.pack(">IIBBBBB", largura, altura, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + bloco(b"IHDR", ihdr) + bloco(b"IEND", b"")


def testa_medidor() -> int:
    casos = [
        (_png(1280, 720), (1280, 720), True,  "16:9 grande — passa"),
        (_png(1200, 250), (1200, 250), False, "larga o bastante, area de menos"),
        (_png(800, 600),  (800, 600),  False, "area ok, largura de menos"),
        (_png(1920, 1080), (1920, 1080), True, "full hd — passa"),
    ]
    falhas = 0
    for dados, esperado, deve_servir, rotulo in casos:
        medido = imagens.dimensoes(dados)
        ok_medida = medido == esperado
        ok_criterio = medido is not None and imagens.serve(*medido) == deve_servir
        marca = "ok  " if (ok_medida and ok_criterio) else "FALHA"
        if marca == "FALHA":
            falhas += 1
        print(f"  [{marca}] {rotulo}: medido {medido}, esperado {esperado}")

    print(f"  [ok  ] lixo nao vira imagem: {imagens.dimensoes(b'nao sou imagem')}")
    if imagens.dimensoes(b"nao sou imagem") is not None:
        falhas += 1
    return falhas


def testa_consultas() -> None:
    """Mostra o termo de busca que cada hub vai usar — inclusive os desligados."""
    for nome, site in carrega_sites().items():
        print(f"\n{nome}:")
        for hub in site.get("hubs", []) or []:
            consulta = imagens.consulta_do_hub(site, hub["id"])
            print(f"  {hub['id']:24} -> "
                  + (f"“{consulta}”" if consulta else "SEM IMAGEM (imagem: false)"))


def testa_rede() -> int:
    falhas = 0
    for nome, site in carrega_sites().items():
        for hub in site.get("hubs", []) or []:
            consulta = imagens.consulta_do_hub(site, hub["id"])
            if not consulta:
                continue
            achada = imagens.busca(consulta)
            if achada:
                print(f"  [ok  ] {nome}/{hub['id']}: {achada['largura']}x"
                      f"{achada['altura']} ({len(achada['conteudo'])//1024} KB) "
                      f"{achada['fonte']} — {achada['credito']}")
            else:
                falhas += 1
                print(f"  [VAZIO] {nome}/{hub['id']}: nada serviu para “{consulta}”")
    return falhas


def main() -> int:
    p = argparse.ArgumentParser(description="Teste da imagem destacada")
    p.add_argument("--rede", action="store_true",
                   help="busca de verdade nos acervos (gasta cota da API)")
    args = p.parse_args()

    print(f"Criterio do Discover: largura >= {imagens.MIN_LARGURA}px "
          f"e area >= {imagens.MIN_PIXELS:,} px\n".replace(",", "."))
    print("Medidor de dimensao (offline):")
    falhas = testa_medidor()

    print("\nConsulta de cada hub (config/sites.yaml):")
    testa_consultas()

    if args.rede:
        print("\nBusca real nos acervos:")
        falhas += testa_rede()
    else:
        print("\n(--rede para buscar de verdade nos acervos)")

    print(f"\n{'FALHAS: ' + str(falhas) if falhas else 'tudo certo'}")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
