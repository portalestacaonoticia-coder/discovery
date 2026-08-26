"""Taxonomia de angulos — o gerador de variacoes.

A ideia: o FATO e' de todo mundo (o show acontece, a cotacao fechou). O que e'
seu e' o angulo somado ao dado da sua base. Cada angulo abaixo vira um artigo
diferente sobre o mesmo fato, sem reescrever ninguem.

Exemplo do Filipe:
  fato    : "Ferrugem faz show em Cabo Frio"
  angulo  : contagem
  dado    : 4 shows na cidade desde 2019, o ultimo em marco de 2025
  artigo  : "Hoje tem show do Ferrugem em Cabo Frio: a 4a vez do cantor na cidade"

Sem o dado da base, o angulo vira texto vazio — e ai' e' conteudo remontado.
Por isso 'exige_dado' existe: angulo sem dado nao vira pauta automatica.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Angulo:
    id: str
    rotulo: str
    molde_titulo: str        # {fato}, {dado}, {lugar} sao preenchidos na hora
    exige_dado: bool
    descricao: str


# Cada site pode sobrescrever qualquer molde em config/sites.yaml, chave 'moldes'.
# Ex.: no site de dolar, 'servico' vira "quanto custa e onde comprar".
ANGULOS = [
    Angulo("contagem", "Contagem / historico",
           "{fato}: a {dado_curto} vez {lugar}", True,
           "Quantas vezes isso ja aconteceu. Usa a base propria. E' o angulo mais dificil de copiar."),
    Angulo("servico", "Guia de servico",
           "{fato}: o que voce precisa saber", False,
           "O que a pessoa precisa saber para agir hoje. Alta busca, baixa concorrencia de qualidade."),
    Angulo("consequencia", "O que muda na pratica",
           "{fato}: o que muda para quem {publico}", False,
           "Traduz o fato em efeito concreto. E' onde o site pequeno ganha do portal grande."),
    Angulo("comparacao", "Comparacao",
           "{fato}: como se compara com {dado_curto}", True,
           "Contra o historico, contra outro periodo, contra outro caso. Precisa de base."),
    Angulo("contexto", "Por que isso acontece",
           "Por que {fato}", False,
           "Explicador. E' o que a IA mais cita, porque responde a pergunta inteira."),
    Angulo("agregado", "Panorama / mapa",
           "{fato}: o retrato completo ate agora ({dado_curto})", True,
           "Soma de tudo que a base sabe. Vira materia forte uma vez por mes."),
]

POR_ID = {a.id: a for a in ANGULOS}


def angulos_possiveis(tem_dado: bool) -> list[Angulo]:
    """Sem dado proprio disponivel, so' sobram os angulos editoriais —
    e nenhum deles pode ir ao ar sozinho (ver portoes no README)."""
    return [a for a in ANGULOS if not a.exige_dado or tem_dado]
