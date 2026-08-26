# Radar de pautas

Monitora o que sai sobre cada tema, deduplica, classifica no hub certo e devolve
uma fila de pautas — cada uma com o **angulo** e o **dado proprio** que fazem o
artigo existir. Multi-site desde o primeiro commit: site novo e' um bloco em
`config/sites.yaml`, sem tocar em codigo.

Nasce configurado para `ferrugem.com.br` e `doll.com.br`.

## O que escala aqui

O texto nao escala — o **banco** escala. Cada show que entra na tabela `eventos`
torna a proxima pauta de show mais rica ("a 4a vez do cantor na cidade"); cada
PTAX que entra em `cotacoes` torna a proxima materia de dolar mais dificil de
copiar. Site novo comeca com a base vazia e vai ganhando profundidade sozinho, a
cada publicacao. E' esse acumulo que separa "mais um portal que reescreve
noticia" de "a fonte que os outros citam" — inclusive as IAs.

Por isso o radar **nao** sugere angulo de dado quando a base nao tem dado: sem
numero proprio, sobra reescrever o que ja foi publicado, que e' exatamente o que
a politica de conteudo em escala do Google descreve.

## Rodar

```bash
pip install -r requirements.txt
cp .env.example .env          # preencher Supabase; Discord e Anthropic sao opcionais

python testar_local.py                      # teste offline, sem rede e sem banco
python -m radar.principal --seco            # coleta de verdade, nao grava nada
python -m radar.principal --site ferrugem   # um site
python -m radar.principal                   # todos
```

No Supabase, rodar `sql/schema.sql` uma vez. Em producao, o
`.github/workflows/radar.yml` roda a cada 30 minutos — os segredos vao em
Settings → Secrets → Actions (`SUPABASE_URL`, `SUPABASE_SERVICE_KEY`,
`DISCORD_WEBHOOK`, `ANTHROPIC_API_KEY`).

## Configurar um WordPress novo

```bash
python -m radar.configurar_wp --site doll --seco   # mostra o que faria
python -m radar.configurar_wp --site doll          # aplica
```

Ajusta titulo, tagline, fuso e formato de data, manda o conteudo de exemplo para
a lixeira e instala os plugins listados. Idempotente: rodar de novo so' reporta
"ja' ok". O que precisa mudar por site esta' em `wordpress.configuracao_inicial`,
no `sites.yaml`.

Precisa rodar de uma maquina que alcance o site. Se a sua nao alcancar, use o
workflow **configurar-wordpress** no GitHub (Actions -> Run workflow), que serve
de braco remoto — deixe `seco` marcado na primeira vez.

## Site novo em 5 minutos

Copiar um bloco de `config/sites.yaml` e trocar:

1. `dominio` e `entidade` — a entidade e' como o site quer ser entendido por
   buscador e IA. Se o dominio nao diz o tema (caso do `doll.com.br`), a
   entidade precisa dizer.
2. `hubs` — as paginas permanentes. Comece com 4. `termos` alimenta o
   classificador sem LLM.
3. `fontes` — comece com duas consultas de Google News. Depois acrescente o
   `sitemap_news` dos concorrentes: e' publico e atualiza em segundos.
4. `base` — `eventos`, `cotacoes` ou uma tabela nova em `sql/schema.sql`. Sem
   base propria o site so' produz angulo editorial.
5. `moldes` (opcional) — sobrescreve o titulo de um angulo so' naquele site.

## Pauta de calendario pronta: cotacao do dolar

```bash
python testar_dolar.py                          # offline, com serie simulada
python -m radar.dolar_diario --historico 90     # carrega a serie inicial na base
python -m radar.dolar_diario --seco             # roda de verdade, sem gravar
python -m radar.dolar_diario                    # producao (cron ja configurado)
```

Fluxo: PTAX do Banco Central -> grava na base -> portoes -> artigo pronto em
`saida/` (markdown + JSON-LD) e na tabela `artigos`.

Duas decisoes que valem entender antes de mexer:

- **O gerador nao explica causa.** "O dolar subiu porque o Fed sinalizou..." e'
  interpretacao, e interpretacao inventada por robo vira erro factual assinado
  por voce. Tudo que sai dali e' derivavel da serie: valor, variacao, extremos,
  conversao, IOF. O "porque" fica para a materia de consequencia, escrita depois.
- **Fim de semana e feriado nao sao erro.** Nao ha' PTAX; o script sai limpo,
  sem gerar nada.

Portoes do dolar, em ordem: valor dentro da faixa plausivel, compra <= venda,
data nao futura (falha aqui aborta); salto diario <= 5% e serie com pelo menos
dois pontos (falha aqui vira rascunho, nao aborta).

O IOF fica em `config/sites.yaml`, nao no codigo — ele muda por decreto, e o
numero errado sai em toda materia. **Conferir antes da primeira publicacao.**

## Portoes de publicacao — leia antes de ligar o automatico

Publicacao automatica e' permissao **por tipo de pauta**, nunca modo global.
`config/sites.yaml` define, em `publicacao`:

| Tipo | Origem | Padrao | Por que |
|---|---|---|---|
| `calendario` | Data marcada + API oficial + calculo da sua base | `auto` | O dado e' deterministico e vem de fonte primaria. Da' para validar por regra: campo veio? esta' na faixa esperada? bate com o dia? Se qualquer teste falha, cai para rascunho. |
| `radar` | Noticia de terceiro detectada pelo radar | `rascunho` | Voce nao apurou o fato — quem apurou foi o outro portal. Publicar sozinho em cima disso e' herdar o erro dos outros e reescrever conteudo alheio em escala. |

Os tres riscos concretos de publicar radar no automatico, para decidir com os
olhos abertos:

1. **Erro factual herdado.** O portal errou a data do show, voce publica o erro
   com a sua assinatura — e o seu site e' que fica marcado.
2. **Pessoa real.** No `ferrugem.com.br` o assunto e' um cidadao vivo. Boato
   publicado automaticamente vira problema de imagem, nao erro de SEO.
3. **Conteudo em escala.** Muitos artigos derivados de noticia alheia, sem
   apuracao nova, e' o caso literal descrito na politica de spam do Google.
   O estrago cai sobre o dominio inteiro, nao sobre o artigo.

O caminho que sustenta volume: **automatico onde o dado e' seu e verificavel**
(agenda confirmada em fonte oficial, PTAX do Banco Central, contagem da sua
base), **rascunho onde o fato e' de outro**. Isso mantem a escala e tira do ar o
risco que nao vale a pena correr.

## Regras de coleta (nao negociaveis no projeto)

- Coletar titulo, URL, data e o resumo que o proprio feed publica. **Nunca** o
  texto integral de outro site — nem no banco, nem em prompt.
- Preferir RSS e sitemap publicos a raspagem de HTML.
- Um segundo de pausa entre requisicoes (`fontes.PAUSA`) e User-Agent
  identificado com contato real.
- Respeitar `robots.txt` de qualquer alvo novo antes de adiciona-lo.
- O radar **descobre** a pauta. A apuracao acontece depois, na fonte primaria —
  o comunicado, o site oficial, a API. E' isso que diferencia radar de copia.

## Estrutura

Ver `MAPA.md`.
