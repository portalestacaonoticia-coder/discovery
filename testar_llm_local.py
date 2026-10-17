"""Teste offline do modo local (exo + SearXNG). Nao acessa rede: as respostas
do exo, do SearXNG e das paginas sao simuladas. Sai com codigo 1 se algo
quebrar.

    python testar_llm_local.py
"""
import json
import os
import sys

import requests

from radar import busca_local, llm, pesquisa
from radar.config import filtra_sites, site_ativo

falhas = []


def confere(nome, cond):
    print(("  ok   " if cond else "  FALHA ") + nome)
    if not cond:
        falhas.append(nome)


class Resposta:
    def __init__(self, dados=None, status=200, texto="", tipo="application/json"):
        self._dados, self.status_code, self.text = dados, status, texto
        self.ok = status < 400
        self.headers = {"Content-Type": tipo}
        self.content = texto.encode()

    def json(self):
        if self._dados is None:
            raise ValueError("sem json")
        return self._dados

    def raise_for_status(self):
        if not self.ok:
            raise requests.HTTPError(str(self.status_code))


def resposta_exo(conteudo, fim="stop"):
    return Resposta({"choices": [{"message": {"content": conteudo}, "finish_reason": fim}]})


PAGINA_IOF = """<html><body><nav>menu</nav><main><h1>IOF no cambio</h1>
<p>Desde 23 de maio de 2025 a aliquota do IOF na compra de moeda em especie
e' de 3,5%. Para cartao internacional, tambem 3,5%.</p>
<p>O imposto incide sobre o valor convertido em reais e e' recolhido pela
instituicao que vende a moeda, no momento da operacao de cambio.</p></main>
<footer>rodape</footer><script>var x=1;</script></body></html>"""


def main():
    os.environ["LLM_LOCAL_URL"] = "http://exo.teste/v1"
    os.environ["SEARXNG_URL"] = "http://searx.teste"
    os.environ.pop("OPENAI_API_KEY", None)
    pedidos = []
    fila_exo = []

    def post_falso(url, json=None, timeout=None, **_):
        pedidos.append((url, json, timeout))
        return fila_exo.pop(0)

    def get_falso(url, params=None, **_):
        if url.startswith("http://searx.teste"):
            return Resposta({"results": [
                {"url": "https://www.gov.br/receitafederal/iof", "title": "IOF - Receita"},
                {"url": "https://blog-qualquer.com/iof", "title": "fora da lista"},
                {"url": "https://www.gov.br/receitafederal/iof/", "title": "repetida"},
            ]})
        return Resposta(texto=PAGINA_IOF, tipo="text/html; charset=utf-8")

    requests.post, requests.get = post_falso, get_falso

    print("tem_chave / gera")
    confere("modo local conta como chave", llm.tem_chave() and llm.modo_local())
    fila_exo.append(resposta_exo("<think>pensando muito</think>\nOla, mundo"))
    confere("raciocinio removido", llm.gera("oi", max_tokens=100) == "Ola, mundo")
    url, corpo, prazo = pedidos[-1]
    confere("chama /chat/completions", url == "http://exo.teste/v1/chat/completions")
    confere("folga para o raciocinio", corpo["max_tokens"] == 100 + llm.FOLGA_RACIOCINIO)
    confere("ignora o modelo da OpenAI", corpo["model"] == llm.MODELO_LOCAL_PADRAO)
    confere("prazo longo", prazo == llm.TIMEOUT_LOCAL_S)

    fila_exo.append(resposta_exo('pensei</think>Claro! ```json\n{"relevante": true}\n``` pronto'))
    saida = llm.gera("classifique em JSON", json_obj=True, modelo=llm.MODELO_CLASSIFICA)
    confere("JSON extraido do meio do texto", saida == '{"relevante": true}')
    confere("pede JSON no sistema", "JSON" in pedidos[-1][1]["messages"][0]["content"])

    llm.limpa_falhas()
    fila_exo.append(resposta_exo('{"cortado": ', fim="length"))
    confere("corte no teto vira None", llm.gera("x", json_obj=True) is None)
    confere("corte registrado como falha", "incompleta" in llm.resumo_falhas())

    fila_exo.append(resposta_exo("sem json nenhum"))
    confere("JSON invalido vira None", llm.gera("x", json_obj=True) is None)

    print("texto da pagina")
    texto = busca_local.texto_da_pagina(PAGINA_IOF)
    confere("tira menu, rodape e script", "menu" not in texto and "rodape" not in texto
            and "var x" not in texto)
    confere("mantem o conteudo", "3,5%" in texto)

    print("gera_com_busca local")
    fila_exo.append(resposta_exo(json.dumps({"consultas": ["aliquota IOF compra dolar"]})))
    fato = {"afirmacao": "IOF na compra de moeda em especie", "valor": "3,5%",
            "fonte_url": "https://www.gov.br/receitafederal/iof"}
    inventado = dict(fato, valor="1,1%")
    fila_exo.append(resposta_exo(json.dumps({"fatos": [fato, inventado]})))
    texto, citacoes = llm.gera_com_busca("Ideia: IOF do dolar\nLevante os fatos.",
                                         ["gov.br"], max_tokens=3000)
    confere("devolveu texto", bool(texto))
    confere("so' dominio permitido e sem repetir", [c["url"] for c in citacoes]
            == ["https://www.gov.br/receitafederal/iof"])
    confere("citacao leva o texto lido", "3,5%" in citacoes[0]["texto"])
    final = pedidos[-1][1]["messages"]
    confere("material lido vai no pedido", "PAGINAS LIDAS" in final[-1]["content"])
    confere("sistema avisa que a busca ja' foi feita", "JA' FOI FEITA" in final[0]["content"])

    print("valor conferido contra a pagina")
    confere("valor que esta' na pagina entra", pesquisa._valor_lido(fato, citacoes))
    confere("valor inventado fica de fora", not pesquisa._valor_lido(inventado, citacoes))
    confere("'1.000,00' casa com 'R$ 1.000'",
            pesquisa._valor_lido({"valor": "R$ 1.000", "fonte_url": "https://a.gov.br/x"},
                                 [{"url": "https://a.gov.br/x", "texto": "custa 1.000,00 reais"}]))
    confere("citacao da OpenAI (sem texto) passa como antes",
            pesquisa._valor_lido(inventado, [{"url": fato["fonte_url"], "titulo": "x"}]))

    print("sem pagina lida, nada e' escrito")
    fila_exo.append(resposta_exo(json.dumps({"consultas": ["nada"]})))
    requests.get = lambda url, **_: Resposta({"results": []})
    confere("sem resultado -> (None, [])",
            llm.gera_com_busca("Ideia: x", ["gov.br"]) == (None, []))
    os.environ.pop("SEARXNG_URL")
    confere("sem SEARXNG_URL -> (None, [])",
            llm.gera_com_busca("Ideia: x", ["gov.br"]) == (None, []))

    print("quem roda o doll")
    os.environ["RADAR_SITES"] = "doll"
    confere("Mac: so' o doll", filtra_sites({"doll": {}, "broune": {}}) == {"doll": {}})
    os.environ.pop("RADAR_SITES")
    os.environ["RADAR_IGNORA_SITES"] = "doll"
    confere("GitHub: tudo menos o doll", not site_ativo("doll") and site_ativo("broune"))
    os.environ.pop("RADAR_IGNORA_SITES")
    confere("sem variavel: todos", site_ativo("doll") and site_ativo("broune"))

    print("\n" + ("TUDO OK" if not falhas else f"{len(falhas)} FALHA(S)"))
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
