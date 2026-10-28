"""Conferente do satelite escrito pelo modelo (19/10/2026).

No ensaio local, sem o pensamento, o Qwen errou o que o codigo sabe de cor:
inverteu alta e queda ("queda de 0,60%" num dia de alta), inventou cotacao
("fecha acima de R$ 5,22" com a PTAX a R$ 5,0826) e chamou a manchete de
duas semanas antes de "nesta segunda-feira (19)". Aqui nada depende do
modelo: cada valor, percentual, direcao e data do texto e' conferido contra
os numeros que o proprio gerador entregou (`_numeros`) e contra a manchete.

    problemas = confere(titulo, corpo, n, manchete, hoje, data_manchete)
    [] = aprovado; senao, uma frase por problema, pronta para o modelo ler.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date
from difflib import SequenceMatcher

from .gerador_dolar import DIAS, MESES, brl, pct

_RE_BRL = re.compile(r"R\$\s?(\d{1,3}(?:\.\d{3})*(?:,\d+)?)")
_RE_PCT = re.compile(r"(\d+(?:,\d+)?)\s?%")
_RE_SEQ = re.compile(r"seguid[oa]s?\s+de\s+(alta|queda|valoriza\w*|desvaloriza\w*)", re.I)
# "16 de outubro", "(16)", "16/10"
_RE_DATA_EXT = re.compile(r"\b(\d{1,2})(?:º)?\s+de\s+(" + "|".join(MESES) + r")\b", re.I)
_RE_DATA_PAR = re.compile(r"\((\d{1,2})\)")
_RE_DATA_BAR = re.compile(r"\b(\d{1,2})/(\d{1,2})(?:/\d{2,4})?\b")

# Ultima palavra de direcao antes do numero decide o que o texto afirmou.
_SOBE = r"alta|subi\w*|sobe|avan\w*|positiv\w*|ganh\w*|valoriz\w*"
_DESCE = r"queda|ca[ií]\w*|recu\w*|negativ\w*|perd\w*|desvaloriz\w*|baixa"
_RE_DIRECAO = re.compile(rf"\b({_SOBE}|{_DESCE})\b", re.I)


# Estilo (19/10/2026, 2a rodada do ensaio): termos que o Qwen repetia e que
# o portal nao assina. (padrao, por que) — o motivo vai para o modelo.
_PROIBIDOS = [
    (r"d[oó]lar comercial", "a PTAX e' a taxa de referencia do BC, nao o 'dolar comercial'"),
    (r"(m[aá]xima|m[ií]nima|pico|topo|piso|patamar|n[ií]vel)s? (\w+ ){0,2}?hist[oó]ric[ao]s?"
     r"|hist[oó]ric[ao]s? (mais )?(baix|alt)\w*",
     "os extremos fornecidos sao do ultimo ano, nao 'historicos'"),
    (r"segundo o ve[ií]culo|o ve[ií]culo\b", "fonte sem nome e' 'a imprensa', nunca 'o veiculo'"),
    (r"\b(suporte|resist[eê]ncia|barreiras? t[eé]cnicas?|rompimento|rota[cç][aã]o de posi[cç][oõ]es"
     r"|derivativos|hedge)\b", "sem analise tecnica ou de mercado propria: so' os numeros"),
]


_RE_ATRIBUI = re.compile(r"segundo (a|o)s? (?!ptax|banco|base|tabela|dados|taxa|bc\b)|"
                         r"noticiou|informou|reportou|"
                         r"de acordo com a (imprensa|reportagem|publica)", re.I)


def posicao(valor: float, piso: float, topo: float) -> str:
    """'piso', 'topo' ou 'meio' — o modelo errava essa leitura (ensaio de
    19/10: 4 de 10 viam 'metade superior' estando mais perto do piso)."""
    amplitude = topo - piso
    if amplitude <= 0:
        return "meio"
    lugar = (valor - piso) / amplitude
    return "piso" if lugar < 0.45 else "topo" if lugar > 0.55 else "meio"


# Palavras de posicao: (regex, lado). Frase sobre o ano compara com a faixa
# do ano; as outras, com a faixa dos 22 pregoes.
_POSICOES = [
    (re.compile(r"(metade|parte|extremidade|zona|faixa) (superior|alta|de cima)|"
                r"(perto|pr[oó]xim[oa]|colad[oa]|encost\w*) (d[oa]s? )?(topo|teto|m[aá]xima|pico)",
                re.I), "topo"),
    (re.compile(r"(metade|parte|extremidade|zona|faixa) (inferior|baixa|de baixo)|"
                r"(perto|pr[oó]xim[oa]|colad[oa]|encost\w*) (d[oa]s? )?(piso|fundo|m[ií]nima)",
                re.I), "piso"),
]
_RE_ANO = re.compile(r"\bano\b|12 meses|doze meses|285 preg|um ano", re.I)


def _frases(texto: str) -> list[str]:
    return [f for f in re.split(r"(?<=[.!?])\s+|\n+", texto) if f.strip()]


def _num(texto: str) -> float:
    return float(texto.replace(".", "").replace(",", "."))


def _sentido(palavra: str) -> int:
    return 1 if re.fullmatch(_SOBE, palavra, re.I) else -1


def _bate(valor: float, permitidos: list[float]) -> bool:
    """O valor e' um dos permitidos, aceitando arredondamento (R$ 5,08 para
    R$ 5,0826; 1,7% para 1,68%)."""
    for p in permitidos:
        for casas in (4, 3, 2, 1, 0):
            if abs(round(p, casas) - valor) < 1e-9:
                return True
    return False


def _trecho_antes(texto: str, pos: int) -> str:
    """Do inicio da frase (ou da virgula anterior) ate o numero."""
    inicio = max(texto.rfind(s, 0, pos) for s in (". ", "; ", "\n", ": "))
    return texto[inicio + 1:pos]


def _trecho_antes_oracao(texto: str, pos: int) -> str:
    """Da virgula/ponto anterior ate o valor: so' a oracao que o precede."""
    inicio = max(texto.rfind(s, 0, pos) for s in (". ", "; ", "\n", ": ", ", "))
    return texto[inicio + 1:pos]


def _normaliza(titulo: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", titulo.lower())
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", sem_acento).split())


_RE_REAL_SOBE = re.compile(r"(positiv\w*|favor[aá]vel|bom|boa) (para|ao) o? ?real|"
                           r"real se (valoriz|fortalec)\w*|\b(valoriza[cç][aã]o|fortalecimento) do real|"
                           r"\breal (ganh|sob|subi|avan)\w*", re.I)
_RE_REAL_DESCE = re.compile(r"(negativ\w*|desfavor[aá]vel|ruim) (para|ao) o? ?real|"
                            r"real se (desvaloriz|enfraquec)\w*|desvaloriza[cç][aã]o do real|"
                            r"perda (de valor )?do real|\breal (perd|ca[ií]|recu)\w*", re.I)


def confere(titulo: str, corpo: str, n: dict, manchete: str, hoje: date,
            data_manchete: date | None,
            titulos_recentes: list[str] | None = None,
            hoje_valido: bool = False, extras: dict | None = None,
            links_permitidos: list[str] | None = None) -> list[str]:
    """`extras` (radar/dado_categoria.py): numeros da categoria alem da PTAX —
    brl, pct (sem direcao), variacoes_moeda (sinal conta para direcao e efeito
    no real), variacoes_outras (so' direcao) e datas validas. Com extras, as
    regras de faixa/extremos da PTAX (6 e 10a) nao se aplicam."""
    extras = extras or {}
    texto = f"{titulo}\n{corpo}"
    problemas: list[str] = []

    # 1. Cotacoes: so' as da base, as distancias entre elas e as da manchete.
    base = [n["venda"], n["maior"], n["menor"], n["max_ano"], n["min_ano"]]
    distancias = [abs(n["venda"] - x) for x in base[1:]]
    distancias += list(extras.get("brl") or [])
    da_manchete = [_num(m) for m in _RE_BRL.findall(manchete or "")]
    for m in _RE_BRL.finditer(texto):
        v = _num(m.group(1))
        if not _bate(v, base + distancias + da_manchete):
            problemas.append(f"o valor R$ {m.group(1)} nao esta nos dados "
                             f"(a PTAX e' {brl(n['venda'], 4)}); use so' os numeros fornecidos")

    # 2. Percentuais: cada um tem dono (dia, semana, mes, janela) e direcao.
    variacoes = {"no pregao": n.get("var_dia"), "na semana": n.get("var_semana"),
                 "no mes": n.get("var_mes"), "nos ultimos pregoes": n.get("var_janela")}
    variacoes = {k: v for k, v in variacoes.items() if v is not None}
    variacoes_real = {**variacoes, **(extras.get("variacoes_moeda") or {})}
    variacoes = {**variacoes_real, **(extras.get("variacoes_outras") or {})}
    pct_manchete = [_num(p) for p in _RE_PCT.findall(manchete or "")]
    # distancia em % ate os extremos (o prompt pede essa analise)
    pct_distancias = [abs(n["venda"] / x - 1) * 100 for x in base[1:]] \
        + [abs(x / n["venda"] - 1) * 100 for x in base[1:]] \
        + [abs(x) for x in (extras.get("pct") or [])]
    for m in _RE_PCT.finditer(texto):
        v = _num(m.group(1))
        donos = [(k, x) for k, x in variacoes.items() if _bate(v, [abs(x)])]
        if not donos:
            if not _bate(v, pct_manchete + pct_distancias):
                problemas.append(f"o percentual {m.group(1)}% nao esta nos dados; "
                                 "use so' as variacoes fornecidas")
            continue
        sentidos = {1 if x > 0 else -1 for _, x in donos}
        if len(sentidos) != 1:
            continue  # mesmo numero, direcoes opostas: nao da' para cobrar
        certo = sentidos.pop()
        palavras = _RE_DIRECAO.findall(_trecho_antes(texto, m.start()))
        if palavras and _sentido(palavras[-1]) != certo:
            onde = donos[0][0]
            problemas.append(
                f"direcao invertida em \"{palavras[-1]} ... {m.group(1)}%\": "
                f"{onde} o dolar {'SUBIU' if certo > 0 else 'CAIU'} {pct(abs(donos[0][1]))}")

    # 3. A sequencia de pregoes tem a direcao da base.
    if n.get("seq", 0) >= 2:
        for m in _RE_SEQ.finditer(texto):
            if _sentido(m.group(1)) != n["direcao"]:
                problemas.append(
                    f"a sequencia e' de {'alta' if n['direcao'] > 0 else 'queda'}, "
                    f"nao de {m.group(1)}")

    # 4. Datas: so' o pregao, os extremos do ano, a manchete e hoje (hoje so'
    # quando for o proprio pregao ou o dia da manchete).
    validas = {n["data"], n["max_quando"], n["min_quando"], *(extras.get("datas") or [])}
    if data_manchete:
        validas.add(data_manchete)
    # a nota-reserva PODE dizer o dia de hoje ("como hoje e' domingo..."),
    # desde que nao cole o numero da PTAX nele (regra 7, abaixo)
    if hoje in (n["data"], data_manchete) or hoje_valido:
        validas.add(hoje)
    dias_validos = {d.day for d in validas}
    for m in _RE_DATA_EXT.finditer(texto):
        dia, mes = int(m.group(1)), MESES.index(m.group(2).lower()) + 1
        if not any(d.day == dia and d.month == mes for d in validas):
            problemas.append(f"a data \"{m.group(0)}\" nao corresponde ao pregao "
                             "nem a manchete")
    for m in _RE_DATA_BAR.finditer(texto):
        dia, mes = int(m.group(1)), int(m.group(2))
        if 1 <= mes <= 12 and not any(d.day == dia and d.month == mes for d in validas):
            problemas.append(f"a data {m.group(0)} nao corresponde ao pregao nem a manchete")
    for m in _RE_DATA_PAR.finditer(texto):
        if int(m.group(1)) not in dias_validos:
            problemas.append(f"o dia ({m.group(1)}) nao corresponde ao pregao "
                             "nem a manchete")
    nomes_validos = {DIAS[d.weekday()] for d in validas
                     if d not in (n["max_quando"], n["min_quando"]) or d == n["data"]}
    for nome in DIAS:
        if re.search(rf"\b{nome}\b", texto, re.I) and nome not in nomes_validos:
            problemas.append(f"\"{nome}\" nao e' o dia do pregao "
                             f"({DIAS[n['data'].weekday()]}) nem o da manchete; "
                             "nao atribua a noticia a hoje")

    # 5. Dado nosso na boca da imprensa: frase com atribuicao nao pode trazer
    # a PTAX nem uma variacao da base (26641 do ensaio de 19/10).
    # so' a PTAX e as variacoes do dia: numero da categoria (Focus, Selic)
    # costuma ser o proprio assunto da manchete, e citar a fonte e' certo
    proprios = [n["venda"]]
    proprios_pct = [abs(v) for k, v in variacoes.items()
                    if k in ("no pregao", "na semana", "no mes", "nos ultimos pregoes")]
    for frase in _frases(texto):
        if not _RE_ATRIBUI.search(frase):
            continue
        if any(_bate(_num(m), proprios) for m in _RE_BRL.findall(frase)
               if not _bate(_num(m), da_manchete)) or \
           any(_bate(_num(m), proprios_pct) for m in _RE_PCT.findall(frase)
               if not _bate(_num(m), pct_manchete)):
            problemas.append("a frase com 'segundo a imprensa' traz dado do Banco "
                             "Central; a PTAX e as variacoes sao nossas, em frase "
                             f"propria: \"{frase.strip()[:90]}\"")

    # 6. Leitura da posicao: perto do piso, do topo ou no meio (o numero
    # certo com a conclusao errada passava; 4 de 10 na v3 do ensaio).
    lado_faixa = posicao(n["venda"], n["menor"], n["maior"])
    lado_ano = posicao(n["venda"], n["min_ano"], n["max_ano"])
    for frase in (_frases(texto) if not extras else []):
        lado = lado_ano if _RE_ANO.search(frase) else lado_faixa
        if lado == "meio":
            continue
        for regex, diz in _POSICOES:
            m = regex.search(frase)
            # "distante/longe do pico" nao e' afirmacao de proximidade
            if m and diz != lado and not re.search(
                    r"(dist\w*|long\w*|afastad\w*) d[oa]s? " + m.group(0).split()[-1],
                    frase, re.I):
                problemas.append(
                    f"\"{m.group(0)}\" esta' errado: a PTAX esta' mais perto do "
                    f"{'piso' if lado == 'piso' else 'topo'}"
                    f"{' do ano' if lado is lado_ano and _RE_ANO.search(frase) else ' da faixa'}")

    # 7. Data da manchete junto de dado nosso: o fechamento e' do pregao, nao
    # do dia da noticia (26641 da v3: "a PTAX de 5 de agosto").
    alheias = [d for d in (data_manchete, hoje if hoje_valido else None)
               if d and d != n["data"]]
    if alheias:
        marcas = []
        for d in alheias:
            marcas += [rf"\b{d.day}º?\s+de\s+{MESES[d.month - 1]}\b",
                       rf"\b{d.day:02d}/{d.month:02d}\b", rf"\b{d.day}/{d.month}\b"]
            if DIAS[d.weekday()] != DIAS[n["data"].weekday()]:
                marcas.append(rf"\b{DIAS[d.weekday()]}\b")
        nossos_brl = base + distancias
        nossos_pct = proprios_pct + pct_distancias
        for frase in _frases(texto):
            if _RE_ATRIBUI.search(frase):
                continue  # frase da manchete: a data dela pode
            tem_dado = any(_bate(_num(x), nossos_brl) for x in _RE_BRL.findall(frase)) or \
                any(_bate(_num(x), nossos_pct) for x in _RE_PCT.findall(frase))
            if tem_dado and any(re.search(mk, frase, re.I) for mk in marcas):
                problemas.append(
                    "o dado do Banco Central e' do pregao de "
                    f"{DIAS[n['data'].weekday()]}, {n['data'].day}/{n['data'].month}, "
                    "nao do dia da manchete: \"" + frase.strip()[:90] + "\"")

    # 8. Direcao sem percentual: o titulo e a frase da PTAX do dia dizem
    # "alta"/"queda" sem numero (26641 da v4: "Dolar fecha em alta na PTAX a
    # R$ 5,0564" com a PTAX em queda; a "alta" era da manchete de agosto).
    dia = n.get("var_dia")
    if dia is not None and abs(dia) >= 0.005 and not _RE_ATRIBUI.search(titulo):
        certo = 1 if dia > 0 else -1
        trechos = [re.split(r"[;:]|,\s| — | - ", titulo)[0]]   # 1a oracao do titulo
        for m in _RE_BRL.finditer(texto):
            if _bate(_num(m.group(1)), [n["venda"]]):
                trechos.append(_trecho_antes_oracao(texto, m.start()))
        for trecho in trechos:
            if _RE_PCT.search(trecho) or _RE_ATRIBUI.search(trecho) or \
                    re.search(r"semana|m[eê]s|\bano\b|preg[oõ]es", trecho, re.I):
                continue   # percentual ja' conferido; ou outro periodo/fonte
            palavras = _RE_DIRECAO.findall(trecho)
            if palavras and all(_sentido(p) != certo for p in palavras):
                problemas.append(
                    f"\"{trecho.strip()[:70]}\": no pregao a PTAX "
                    f"{'SUBIU' if certo > 0 else 'CAIU'} {pct(abs(dia))}")
                break   # um aviso basta: titulo e frase costumam ser o mesmo erro

    # 9. Efeito no real: dolar sobe = real perde (27688 da v4: "positivo para
    # o real: o dolar subiu 1,35%").
    for frase in _frases(texto):
        diz_real = 1 if _RE_REAL_SOBE.search(frase) else \
            -1 if _RE_REAL_DESCE.search(frase) else 0
        if not diz_real:
            continue
        sentidos = {1 if x > 0 else -1 for m in _RE_PCT.findall(frase)
                    for x in variacoes_real.values() if _bate(_num(m), [abs(x)])}
        if not sentidos and dia and abs(dia) >= 0.005 and \
                any(_bate(_num(m), [n["venda"]]) for m in _RE_BRL.findall(frase)):
            sentidos = {1 if dia > 0 else -1}
        if len(sentidos) == 1 and diz_real == sentidos.pop():
            problemas.append(
                "efeito no real invertido: quando o dolar sobe, o real perde "
                f"valor (e vice-versa): \"{frase.strip()[:90]}\"")

    # 10a. O real nos extremos do ano: na MINIMA do dolar o real esta' no
    # ponto mais FORTE, na maxima, no mais fraco (1o satelite do Mac,
    # 20/10/2026: "distante do nivel mais fraco registrado em maio", quando
    # maio foi a minima do dolar).
    mes_min = MESES[n["min_quando"].month - 1]
    mes_max = MESES[n["max_quando"].month - 1]
    for frase in (_frases(texto) if not extras else []):
        # oracao por oracao, e so' o superlativo ("nivel/ponto mais fraco"):
        # "mais forte do que no pico" e' comparativo e esta' certo
        for oracao in re.split(r",\s*mas\b|;|,\s*e\b|,", frase):
            sup = re.search(r"(n[ií]vel|ponto|patamar|momento)\s+mais\s+(fraco|forte)",
                            oracao, re.I)
            if not sup:
                continue
            perto_min = re.search(rf"{mes_min}|m[ií]nima", oracao, re.I)
            perto_max = re.search(rf"{mes_max}|m[aá]xima|pico", oracao, re.I)
            diz = sup.group(2).lower()
            if diz == "fraco" and perto_min and not perto_max:
                problemas.append("na minima do dolar o real esteve no ponto mais FORTE, "
                                 f"nao no mais fraco: \"{oracao.strip()[:90]}\"")
            if diz == "forte" and perto_max and not perto_min:
                problemas.append("na maxima do dolar o real esteve no ponto mais FRACO, "
                                 f"nao no mais forte: \"{oracao.strip()[:90]}\"")

    # 10b. Data relativa errada para a manchete ("quarta-feira passada" para
    # um boletim de dois meses antes).
    if data_manchete:
        dias = (hoje - data_manchete).days
        m = re.search(r"\b(ontem|anteontem)\b", texto, re.I)
        if m and dias > 2:
            problemas.append(f"\"{m.group(0)}\": a manchete e' de {data_manchete:%d/%m}, "
                             f"ha' {dias} dias; use a data")
        # "nesta terca-feira, 9 de junho" para manchete de meses atras (ensaio
        # por categoria, 21/10/2026): "nesta/desta" e' da semana corrente
        m = re.search(r"\b(n|d)est[ae]s?\s+(segunda|ter[cç]a|quarta|quinta|sexta)"
                      r"(-feira)?|\b(n|d)es[st]e\s+(s[aá]bado|domingo)\b", texto, re.I)
        if m and dias > 6:
            problemas.append(f"\"{m.group(0)}\": a manchete e' de {data_manchete:%d/%m}, "
                             f"ha' {dias} dias; diga a data sem 'nesta'")
        m = re.search(r"\b(semana passada|\w+-feira passada|s[aá]bado passado|"
                      r"domingo passado|recentemente)\b", texto, re.I)
        if m and dias > 7:
            problemas.append(f"\"{m.group(0)}\": a manchete e' de {data_manchete:%d/%m}, "
                             f"ha' {dias} dias; use a data")

    # 10. Titulo unico: dois hubs no mesmo dia saiam com o mesmo titulo
    # (3 iguais em 10 na v4).
    meu = _normaliza(titulo)
    for outro in titulos_recentes or []:
        if outro and SequenceMatcher(None, meu, _normaliza(outro)).ratio() >= 0.85:
            problemas.append(f"titulo quase igual a um ja' usado (\"{outro[:70]}\"); "
                             "escreva outro, com outra estrutura")
            break

    # 12. Ensaio por categoria (21/10/2026): 2 de 17 textos ignoraram os dados,
    # com lista de topicos e link inventado (doll.com.br/guia-cambio).
    if links_permitidos is not None:
        ok = {u.rstrip("/") for u in links_permitidos if u}
        for u in re.findall(r"\]\((https?://[^)\s]+)\)", texto):
            if u.rstrip("/") not in ok:
                problemas.append(f"link {u} nao foi fornecido; o unico link e' o da "
                                 "pagina-guia indicada")
    if re.search(r"^\s*([-*•]|\d+[.)])\s+\S", corpo or "", re.M):
        problemas.append("nada de lista de topicos: escreva em paragrafos")
    chaves = [x for x in (extras.get("brl") or []) + (extras.get("pct") or []) if x]
    texto_inteiro = len((corpo or "").split()) >= 150   # trechos curtos (testes) nao contam
    if not texto_inteiro:
        pass
    elif extras and chaves:
        usados = {round(_num(m), 2) for m in _RE_BRL.findall(texto) + _RE_PCT.findall(texto)}
        achados = {x for x in chaves if _bate(round(x, 2), list(usados))
                   or any(_bate(u, [x]) for u in usados)}
        if len(achados) < 3:
            problemas.append("o texto quase nao usa os dados fornecidos: o assunto e' o "
                             "dado da categoria; use os numeros dados")
    elif not extras and not any(_bate(_num(m), [n["venda"]]) for m in _RE_BRL.findall(texto)):
        problemas.append(f"o texto nao traz a PTAX do dia ({brl(n['venda'], 4)})")
    # fonte errada para o IPCA (ensaio: "dados ... da Fundacao Getulio Vargas")
    m = re.search(r"\bFGV\b|Get[uú]lio Vargas", texto)
    if m and not re.search(r"\bFGV\b|Get[uú]lio Vargas", manchete or ""):
        problemas.append(f"\"{m.group(0)}\": nenhum dado fornecido e' da FGV (o IPCA e' do IBGE)")
    # faixa de ~1 mes chamada de "12 meses"/"do ano" (viagem, ensaio)
    faixa = [x for x in (extras.get("faixa_30d") or []) if x]
    for frase in (_frases(texto) if faixa else []):
        if any(_bate(_num(m), faixa) for m in _RE_BRL.findall(frase)) and \
                re.search(r"12 meses|doze meses|\bdo ano\b|anual|\bno ano\b", frase, re.I):
            problemas.append("a faixa de minima e maxima e' de cerca de um mes (22 pregoes), "
                             f"nao do ano: \"{frase.strip()[:90]}\"")
    # projecao do mercado x PTAX (titulo "dolar a R$ 5,13 no fim de 2026, abaixo da PTAX"
    # com a projecao ACIMA da PTAX)
    proj = extras.get("projecao")
    if proj:
        acima = proj > n["venda"]
        for frase in _frases(texto):
            m1 = re.search(r"(acima|abaixo) da (PTAX|cota[cç][aã]o (atual|de hoje|do dia))", frase, re.I)
            if m1 and re.search(r"proje|Focus|mercado|mediana|R\$ ?\d", frase[:m1.start()], re.I) \
                    and not re.search(r"PTAX[^.]{0,40}$", frase[:m1.start()], re.I):
                if (m1.group(1).lower() == "acima") != acima:
                    problemas.append(f"a projecao ({brl(proj, 2)}) esta' "
                                     f"{'ACIMA' if acima else 'ABAIXO'} da PTAX "
                                     f"({brl(n['venda'], 4)}): \"{frase.strip()[:80]}\"")
            m2 = re.search(r"(PTAX|cota[cç][aã]o atual|cota[cç][aã]o de hoje)[^.]{0,80}?"
                           r"(acima|abaixo) d[ao] (proje|expectativa|mediana)", frase, re.I)
            if m2 and (m2.group(2).lower() == "abaixo") != acima:
                problemas.append(f"a PTAX ({brl(n['venda'], 4)}) esta' "
                                 f"{'ABAIXO' if acima else 'ACIMA'} da projecao "
                                 f"({brl(proj, 2)}): \"{frase.strip()[:80]}\"")

    # atribuicao dobrada ("Segundo a imprensa, a imprensa noticiou")
    m = re.search(r"segundo a imprensa,?\s+a imprensa", texto, re.I)
    if m:
        problemas.append(f"\"{m.group(0)}\": atribuicao repetida")

    # 11. Estilo.
    for padrao, porque in _PROIBIDOS:
        m = re.search(padrao, texto, re.I)
        if m:
            problemas.append(f"\"{m.group(0)}\": {porque}")

    return list(dict.fromkeys(problemas))
