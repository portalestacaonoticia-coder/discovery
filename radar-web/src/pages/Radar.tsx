import { useEffect, useState } from "react";
import { Radar as RadarIcon, ChevronDown, ExternalLink, Loader2, X } from "lucide-react";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useRadarDoSite, useRadarSites, useSalvarConfig, useTriarPauta } from "@/hooks/useRadar";
import { duracaoRadar, horaRadar, quandoRadar, restanteDoDia, type RadarCriterios } from "@/lib/radar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

// Selos no padrão do STATUS_META do Acompanhamento: cor sempre com rótulo.
const SELO: Record<string, { rotulo: string; cls: string }> = {
  ok: { rotulo: "✓ ok", cls: "bg-green-500/15 text-green-600" },
  publicada: { rotulo: "✓ publicada", cls: "bg-green-500/15 text-green-600" },
  aprovada: { rotulo: "✓ selecionada", cls: "bg-teal-500/15 text-teal-600" },
  rascunho: { rotulo: "◐ rascunho", cls: "bg-amber-500/15 text-amber-600" },
  erro: { rotulo: "✕ erro", cls: "bg-destructive/15 text-destructive" },
  sem_cotacao: { rotulo: "sem cotação", cls: "bg-muted text-muted-foreground" },
  nova: { rotulo: "● nova", cls: "bg-blue-500/15 text-blue-600" },
  descartada: { rotulo: "descartada", cls: "bg-muted text-muted-foreground" },
};

function Selo({ status }: { status: string }) {
  const v = SELO[status] ?? { rotulo: status, cls: "bg-muted text-muted-foreground" };
  return <Badge className={`border-transparent shadow-none hover:bg-transparent ${v.cls}`}>{v.rotulo}</Badge>;
}

export default function Radar() {
  useDocumentTitle("Radar de pautas");
  const { data: sites, isLoading: carregandoSites, error: erroSites } = useRadarSites();
  const [site, setSite] = useState<string | null>(null);

  useEffect(() => {
    if (!site && sites?.length) setSite(sites.includes("doll") ? "doll" : sites[0]);
  }, [sites, site]);

  const { data, isLoading, error } = useRadarDoSite(site);

  return (
    <div className="space-y-6 p-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold">
            <RadarIcon className="h-6 w-6" /> Radar de pautas
          </h1>
          <p className="text-sm text-muted-foreground">
            O radar decide o que soltar dentro da meta; você governa o critério.
          </p>
        </div>
        {sites && sites.length > 0 && (
          <Tabs value={site ?? undefined} onValueChange={setSite}>
            <TabsList>
              {sites.map((s) => (
                <TabsTrigger key={s} value={s}>{s}</TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
        )}
      </div>

      {(erroSites || error) && (
        <Card className="p-6 text-sm text-destructive">
          Não consegui carregar o radar: {String((erroSites || (error as Error))?.message ?? erroSites ?? error)}
        </Card>
      )}

      {(carregandoSites || (isLoading && site)) && !error && !erroSites && (
        <div className="space-y-4">
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      )}

      {sites?.length === 0 && (
        <Card className="p-6 text-sm text-muted-foreground">
          Nenhum site apareceu no banco do radar ainda — assim que os crons rodarem, eles surgem aqui sozinhos.
        </Card>
      )}

      {data && site && (
        <>
          <SecaoCriterios data={data} site={site} />
          <SecaoHoje data={data} site={site} />
          <SecaoSelecao data={data} site={site} />
          <SecaoPautas data={data} />
          <SecaoExecucoes data={data} />
          <SecaoArtigos data={data} />
        </>
      )}
    </div>
  );
}

type Dados = NonNullable<ReturnType<typeof useRadarDoSite>["data"]>;

function SecaoHoje({ data, site }: { data: Dados; site: string }) {
  const resumo = data.resumoDia;
  const salvar = useSalvarConfig(site);
  const [valor, setValor] = useState<string>("");

  useEffect(() => {
    setValor(resumo.pautasPorDia === null ? "" : String(resumo.pautasPorDia));
  }, [site, resumo.pautasPorDia]);

  const restante = restanteDoDia(resumo.pautasPorDia, resumo.sairam);
  const meta = resumo.pautasPorDia;
  const progresso =
    meta && meta > 0 && resumo.sairam !== null ? Math.min(100, (resumo.sairam / meta) * 100) : null;
  const mudou = valor !== "" && Number(valor) !== meta;

  return (
    <Card className="p-6">
      <h2 className="mb-4 text-lg font-semibold">Hoje</h2>
      <div className="flex flex-wrap items-end gap-x-10 gap-y-4">
        <div>
          <p className="text-sm text-muted-foreground">Já saíram no site</p>
          <p className="text-4xl font-bold tabular-nums">{resumo.sairam ?? "—"}</p>
        </div>
        <div>
          <p className="text-sm text-muted-foreground">Ainda vão sair</p>
          <p className="text-4xl font-bold tabular-nums">{restante ?? "—"}</p>
        </div>
        <div>
          <p className="text-sm text-muted-foreground">Selecionadas pelo radar</p>
          <p className="text-4xl font-bold tabular-nums">
            {resumo.selecionadas}
            {meta ? <span className="text-lg font-normal text-muted-foreground"> / {meta}</span> : null}
          </p>
        </div>
        <div>
          <p className="text-sm text-muted-foreground">Meta do dia</p>
          <div className="flex items-center gap-2">
            <Input
              type="number"
              min={0}
              max={200}
              value={valor}
              onChange={(e) => setValor(e.target.value)}
              className="w-24 text-lg font-semibold tabular-nums"
              aria-label="Meta de pautas por dia"
            />
            {mudou && (
              <Button
                size="sm"
                onClick={() => salvar.mutate({ pautasPorDia: Number(valor) })}
                disabled={salvar.isPending}
              >
                {salvar.isPending && <Loader2 className="mr-1 h-3 w-3 animate-spin" />}
                Salvar
              </Button>
            )}
          </div>
        </div>
      </div>

      {progresso !== null && (
        <div className="mt-4 max-w-md">
          <Progress value={progresso} aria-label="Progresso da meta do dia" />
          <p className="mt-1 text-xs text-muted-foreground">
            {resumo.sairam} de {meta} pautas do dia no ar
            {restante === 0 && meta! > 0 ? " — meta batida ✓" : ""}
          </p>
        </div>
      )}

      {!resumo.wpConfigurado && (
        <p className="mt-4 text-xs text-muted-foreground">
          Este site ainda não tem WordPress configurado para contar o que já foi ao ar
          (coluna <code>wp_url</code> na tabela <code>metas</code> do radar).
        </p>
      )}
      {salvar.isError && (
        <p className="mt-2 text-xs text-destructive">Não consegui salvar: {(salvar.error as Error).message}</p>
      )}
    </Card>
  );
}

function SecaoSelecao({ data, site }: { data: Dados; site: string }) {
  const triar = useTriarPauta(site);
  const [pendente, setPendente] = useState<number | null>(null);

  function veta(pautaId: number) {
    setPendente(pautaId);
    // veto abre vaga; o proximo ciclo do radar (30 min) repõe com a proxima melhor
    triar.mutate({ pautaId, status: "descartada" }, { onSettled: () => setPendente(null) });
  }

  return (
    <Card className="p-6">
      <h2 className="mb-1 text-lg font-semibold">Seleção de hoje</h2>
      <p className="mb-4 text-sm text-muted-foreground">
        Escolhidas automaticamente pelo radar, dentro da meta — no máximo uma pauta por fato.
        Quentes saem o quanto antes; fixas se espalham pela janela editorial. O veto abre vaga
        e o próximo ciclo (30 min) repõe.
      </p>

      {data.selecaoDoDia.length === 0 && (
        <p className="text-sm text-muted-foreground">
          O radar ainda não selecionou hoje — a próxima rodada do cron decide com os critérios atuais.
        </p>
      )}

      <div className="space-y-3">
        {data.selecaoDoDia.map((p, i) => {
          const agendada = p.horario_sugerido ? new Date(p.horario_sugerido) : null;
          const paraJa = !agendada || agendada.getTime() <= Date.now();
          return (
          <div key={p.id} className="flex flex-wrap items-start justify-between gap-3 rounded-lg border p-4">
            <div className="min-w-0 flex-1">
              <p className="font-medium">
                <span className="mr-2 text-muted-foreground tabular-nums">{i + 1}.</span>
                {agendada && (
                  <Badge
                    className={`mr-2 border-transparent shadow-none hover:bg-transparent ${
                      paraJa ? "bg-orange-500/15 text-orange-600" : "bg-sky-500/15 text-sky-600"
                    }`}
                  >
                    {paraJa ? "🔥 para já" : `🕐 para ${horaRadar(p.horario_sugerido)}`}
                  </Badge>
                )}
                {p.titulo_sug ?? p.itens?.titulo ?? "—"}
              </p>
              {p.dado_proprio && <p className="text-xs text-muted-foreground">dado próprio: {p.dado_proprio}</p>}
              <p className="mt-1 text-xs text-muted-foreground">
                {p.pontuacao} pts · {p.motivo_selecao}
                {p.hub ? ` · hub ${p.hub}` : ""} · escolhida {quandoRadar(p.selecionada_em)}
                {p.itens?.url && (
                  <>
                    {" · "}
                    <a
                      href={p.itens.url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1 underline-offset-2 hover:underline"
                    >
                      {p.itens.veiculo ?? "origem"} <ExternalLink className="h-3 w-3" />
                    </a>
                  </>
                )}
              </p>
            </div>
            <Button
              size="sm"
              variant="outline"
              onClick={() => veta(p.id)}
              disabled={pendente === p.id}
              title="Descartar esta escolha; o radar repõe no próximo ciclo"
            >
              {pendente === p.id ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : <X className="mr-1 h-3 w-3" />}
              Vetar
            </Button>
          </div>
          );
        })}
      </div>

      {triar.isError && (
        <p className="mt-2 text-xs text-destructive">Não consegui salvar: {(triar.error as Error).message}</p>
      )}
    </Card>
  );
}

const ROTULO_ANGULO: Record<string, string> = {
  contagem: "Contagem (base própria)",
  agregado: "Agregado (base própria)",
  comparacao: "Comparação (base própria)",
  servico: "Serviço",
  contexto: "Contexto (por quê)",
  consequencia: "Consequência",
};

const ROTULO_FRESCOR: Record<string, string> = {
  ate6h: "Até 6 horas",
  ate24h: "Até 24 horas",
  ate48h: "Até 48 horas",
};

const ROTULO_JANELA: Record<string, string> = {
  inicio: "Começa às (h)",
  fim: "Termina às (h)",
};

function SecaoCriterios({ data, site }: { data: Dados; site: string }) {
  const salvar = useSalvarConfig(site);
  const [rascunho, setRascunho] = useState<RadarCriterios>({});
  const [mudou, setMudou] = useState(false);

  useEffect(() => {
    setRascunho(structuredClone(data.criterios ?? {}));
    setMudou(false);
  }, [site, data.criterios]);

  function ajusta(caminho: "dado_proprio" | "minimo" | "quente_ate_horas", valor: string): void;
  function ajusta(caminho: "angulos" | "frescor" | "janela", valor: string, chave: string): void;
  function ajusta(caminho: string, valor: string, chave?: string) {
    const n = Number(valor);
    if (!isFinite(n)) return;
    setRascunho((atual) => {
      const novo = structuredClone(atual);
      if (caminho === "angulos" || caminho === "frescor" || caminho === "janela") {
        (novo[caminho] as Record<string, number>) = { ...(novo[caminho] ?? {}), [chave!]: n };
      } else {
        (novo as Record<string, unknown>)[caminho] = n;
      }
      return novo;
    });
    setMudou(true);
  }

  const campo = (rotulo: string, valor: number | undefined, aoMudar: (v: string) => void) => (
    <div key={rotulo}>
      <Label className="text-xs text-muted-foreground">{rotulo}</Label>
      <Input
        type="number"
        min={0}
        max={100}
        value={valor ?? ""}
        onChange={(e) => aoMudar(e.target.value)}
        className="w-24 tabular-nums"
      />
    </div>
  );

  const [aberto, setAberto] = useState(false);

  return (
    <Card className="p-6">
      <Collapsible open={aberto} onOpenChange={setAberto}>
        <CollapsibleTrigger className="flex w-full items-center justify-between text-left">
          <div>
            <h2 className="text-lg font-semibold">Critérios da seleção</h2>
            <p className="text-sm text-muted-foreground">
              A sua régua: pesos de 0 a 100. O próximo ciclo do radar já decide com o que você salvar aqui.
            </p>
          </div>
          <ChevronDown className={`h-5 w-5 shrink-0 text-muted-foreground transition-transform ${aberto ? "rotate-180" : ""}`} />
        </CollapsibleTrigger>
        <CollapsibleContent className="pt-4">

      <div className="space-y-4">
        <div className="flex flex-wrap gap-4">
          {campo("Bônus dado próprio", rascunho.dado_proprio, (v) => ajusta("dado_proprio", v))}
          {campo("Piso mínimo p/ selecionar", rascunho.minimo, (v) => ajusta("minimo", v))}
        </div>
        <div>
          <p className="mb-2 text-sm font-medium">Peso por ângulo</p>
          <div className="flex flex-wrap gap-4">
            {Object.keys(ROTULO_ANGULO).map((chave) =>
              campo(ROTULO_ANGULO[chave], rascunho.angulos?.[chave], (v) => ajusta("angulos", v, chave)),
            )}
          </div>
        </div>
        <div>
          <p className="mb-2 text-sm font-medium">Bônus de frescor do fato</p>
          <div className="flex flex-wrap gap-4">
            {Object.keys(ROTULO_FRESCOR).map((chave) =>
              campo(ROTULO_FRESCOR[chave], rascunho.frescor?.[chave], (v) => ajusta("frescor", v, chave)),
            )}
          </div>
        </div>
        <div>
          <p className="mb-2 text-sm font-medium">Ritmo do dia</p>
          <div className="flex flex-wrap gap-4">
            {campo("Quente até (horas do fato)", rascunho.quente_ate_horas, (v) => ajusta("quente_ate_horas", v))}
            {Object.keys(ROTULO_JANELA).map((chave) =>
              campo(`Janela das fixas — ${ROTULO_JANELA[chave]}`, rascunho.janela?.[chave], (v) => ajusta("janela", v, chave)),
            )}
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            Fato mais novo que o limite é quente (sai o quanto antes); o resto se espalha pela janela, no fuso de São Paulo.
          </p>
        </div>
      </div>

      <div className="mt-4 flex items-center gap-3">
        <Button
          onClick={() => salvar.mutate({ criterios: rascunho }, { onSuccess: () => setMudou(false) })}
          disabled={!mudou || salvar.isPending}
        >
          {salvar.isPending && <Loader2 className="mr-1 h-3 w-3 animate-spin" />}
          Salvar critérios
        </Button>
        {salvar.isError && (
          <p className="text-xs text-destructive">Não consegui salvar: {(salvar.error as Error).message}</p>
        )}
      </div>
        </CollapsibleContent>
      </Collapsible>
    </Card>
  );
}

function SecaoPautas({ data }: { data: Dados }) {
  return (
    <Card className="p-6">
      <h2 className="mb-4 text-lg font-semibold">Fila de pautas</h2>
      {Object.keys(data.contagens).length > 0 && (
        <p className="mb-4 flex flex-wrap gap-2">
          {Object.entries(data.contagens).map(([st, total]) => (
            <Badge key={st} variant="outline" className="text-muted-foreground">
              {st} <b className="ml-1 text-foreground tabular-nums">{total}</b>
            </Badge>
          ))}
        </p>
      )}
      {data.pautas.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          Nenhuma pauta ainda — elas surgem quando o radar coleta algo relevante.
        </p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Pauta sugerida</TableHead>
              <TableHead>Ângulo</TableHead>
              <TableHead>Hub</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Quando</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.pautas.map((p) => (
              <TableRow key={p.id}>
                <TableCell className="max-w-xl">
                  {p.titulo_sug ?? p.itens?.titulo ?? "—"}
                  {p.dado_proprio && (
                    <div className="text-xs text-muted-foreground">dado próprio: {p.dado_proprio}</div>
                  )}
                  {p.itens?.url && (
                    <a
                      href={p.itens.url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1 text-xs text-muted-foreground underline-offset-2 hover:underline"
                    >
                      {p.itens.veiculo ?? "origem"} <ExternalLink className="h-3 w-3" />
                    </a>
                  )}
                </TableCell>
                <TableCell className="text-muted-foreground">{p.angulo}</TableCell>
                <TableCell className="text-muted-foreground">{p.hub ?? "—"}</TableCell>
                <TableCell><Selo status={p.status} /></TableCell>
                <TableCell className="text-muted-foreground">{quandoRadar(p.criado_em)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </Card>
  );
}

function SecaoExecucoes({ data }: { data: Dados }) {
  return (
    <Card className="p-6">
      <h2 className="mb-4 text-lg font-semibold">Execuções dos crons</h2>
      {data.execucoes.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          Nenhuma execução registrada ainda — a próxima rodada dos crons aparece aqui.
        </p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Fluxo</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Resumo</TableHead>
              <TableHead>Quando</TableHead>
              <TableHead className="text-right">Duração</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.execucoes.map((e) => (
              <TableRow key={e.id}>
                <TableCell>{e.fluxo}</TableCell>
                <TableCell><Selo status={e.status} /></TableCell>
                <TableCell className="max-w-md text-muted-foreground">{e.resumo ?? "—"}</TableCell>
                <TableCell className="text-muted-foreground">{quandoRadar(e.fim)}</TableCell>
                <TableCell className="text-right tabular-nums text-muted-foreground">
                  {duracaoRadar(e.inicio, e.fim)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </Card>
  );
}

function SecaoArtigos({ data }: { data: Dados }) {
  if (data.artigos.length === 0) return null;
  return (
    <Card className="p-6">
      <h2 className="mb-4 text-lg font-semibold">Artigos gerados pelo radar</h2>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Título</TableHead>
            <TableHead>Tipo</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Portão</TableHead>
            <TableHead>Quando</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.artigos.map((a) => (
            <TableRow key={a.id}>
              <TableCell className="max-w-xl">
                {a.url_publicada ? (
                  <a href={a.url_publicada} target="_blank" rel="noreferrer" className="underline-offset-2 hover:underline">
                    {a.titulo}
                  </a>
                ) : (
                  a.titulo
                )}
              </TableCell>
              <TableCell className="text-muted-foreground">{a.tipo}</TableCell>
              <TableCell><Selo status={a.status} /></TableCell>
              <TableCell className="max-w-xs text-muted-foreground">{a.motivo_portao ?? "—"}</TableCell>
              <TableCell className="text-muted-foreground">{quandoRadar(a.criado_em)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Card>
  );
}
