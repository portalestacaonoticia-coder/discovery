"""Teste offline: simula o que uma fonte devolveria e mostra as pautas geradas.
Nao acessa rede e nao grava nada. Serve para conferir a logica antes de plugar
fontes e banco de verdade.

    python testar_local.py
"""
from radar.banco import Banco
from radar.classifica import avalia, sugere
from radar.config import carrega_sites
from radar.normaliza import canoniza_url, hash_dedup

EXEMPLOS = {
    "ferrugem": [
        {"titulo": "Ferrugem faz show em Cabo Frio neste sábado", "resumo": "O cantor se apresenta na Praça das Águas."},
        {"titulo": "Ferrugem anuncia novo single com participação especial", "resumo": ""},
        {"titulo": "Receita de bolo de fubá da vovó", "resumo": "nada a ver — deve ser descartada"},
    ],
    "doll": [
        {"titulo": "Dólar fecha em alta após decisão do Fed", "resumo": "Moeda americana subiu ante o real."},
        {"titulo": "Copom mantém Selic e dólar recua", "resumo": ""},
    ],
}


class BancoFalso(Banco):
    """Base propria simulada: o Ferrugem ja tocou 3 vezes em Cabo Frio."""
    def __init__(self):
        super().__init__(seco=True)

    def cidades_conhecidas(self, site):
        return ["Cabo Frio", "Niterói", "São Paulo"]

    def conta_eventos_na_cidade(self, site, cidade):
        return 3 if cidade.lower() == "cabo frio" else 0

    def ultimo_evento_na_cidade(self, site, cidade):
        return {"data": "2025-03-15", "local": "Arena Cabo Frio"}


def main():
    from radar.principal import dado_proprio
    sites = carrega_sites()
    banco = BancoFalso()

    for nome, exemplos in EXEMPLOS.items():
        site = sites[nome]
        print(f"\n=== {nome} ({site['dominio']}) ===")
        for cru in exemplos:
            leitura = avalia(cru["titulo"], cru["resumo"], site)
            marca = "OK " if leitura["relevante"] else "FORA"
            print(f"\n[{marca}] {cru['titulo']}  -> hub: {leitura['hub']}")
            if not leitura["relevante"]:
                continue
            dado = dado_proprio(banco, nome, site, cru["titulo"], leitura)
            print(f"       dado proprio: {dado or '(nenhum — so angulos editoriais)'}")
            for s in sorted(sugere(cru["titulo"], leitura, dado, site),
                            key=lambda x: -x["prioridade"]):
                print(f"       [{s['prioridade']:>2}] {s['angulo']:<12} {s['titulo_sug']}")

    # dedup: mesma noticia, dois portais, no mesmo dia -> um hash so'
    from datetime import date
    a = hash_dedup("Ferrugem faz show em Cabo Frio neste sábado", date(2026, 8, 24))
    b = hash_dedup("Show do Ferrugem em Cabo Frio neste sábado, faz", date(2026, 8, 24))
    print(f"\ndedup (mesma noticia em portais diferentes): {'iguais OK' if a == b else 'diferentes'}")
    print("url canonica:", canoniza_url("https://www.portal.com.br/noticia/?utm_source=fb&id=9"))


if __name__ == "__main__":
    main()
