import { useEffect, useMemo, useState } from "react";
import { Compass, ExternalLink, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useDiscoveryConfig, useSalvarDiscovery } from "@/hooks/useDiscovery";
import {
  termosIguais,
  termosParaTexto,
  textoParaTermos,
  type DiscoverySite,
} from "@/lib/discovery";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";

export default function Discovery() {
  useDocumentTitle("Discovery — termos e consultas");
  const { data, isLoading, error } = useDiscoveryConfig();
  const [site, setSite] = useState<string | null>(null);

  useEffect(() => {
    if (!site && data?.sites.length) setSite(data.sites[0].id);
  }, [data, site]);

  const atual = data?.sites.find((s) => s.id === site) ?? null;

  return (
    <div className="space-y-6 p-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold">
            <Compass className="h-6 w-6" /> Discovery
          </h1>
          <p className="text-sm text-muted-foreground">
            Termos e consultas do sites.yaml — salvar aqui commita no repo; o radar usa na próxima rodada.
          </p>
        </div>
        {data && data.sites.length > 0 && (
          <Tabs value={site ?? undefined} onValueChange={setSite}>
            <TabsList>
              {data.sites.map((s) => (
                <TabsTrigger key={s.id} value={s.id}>{s.id}</TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
        )}
      </div>

      {error && (
        <Card className="p-6 text-sm text-destructive">
          Não consegui ler o sites.yaml: {(error as Error).message}
        </Card>
      )}

      {isLoading && !error && (
        <div className="space-y-4">
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      )}

      {atual && data && (
        // key com o sha: depois de um commit (ou refetch) o formulário renasce
        // do arquivo novo, sem rascunho velho pendurado
        <FormularioSite key={`${atual.id}-${data.sha}`} sha={data.sha} site={atual} />
      )}
    </div>
  );
}

function FormularioSite({ sha, site }: { sha: string; site: DiscoverySite }) {
  const salvar = useSalvarDiscovery();
  const [termosPorHub, setTermosPorHub] = useState<Record<string, string>>(() =>
    Object.fromEntries(site.hubs.map((hub) => [hub.id, termosParaTexto(hub.termos)])),
  );
  const [consultas, setConsultas] = useState<Record<number, string>>(() =>
    Object.fromEntries(
      site.fontes.filter((f) => f.tipo === "google_news").map((f) => [f.indice, f.consulta ?? ""]),
    ),
  );

  const hubsMudados = useMemo(
    () =>
      site.hubs
        .map((hub) => ({ id: hub.id, termos: textoParaTermos(termosPorHub[hub.id] ?? "") }))
        .filter((edicao) => {
          const original = site.hubs.find((hub) => hub.id === edicao.id)!.termos;
          return !termosIguais(edicao.termos, original);
        }),
    [site.hubs, termosPorHub],
  );
  const fontesMudadas = useMemo(
    () =>
      site.fontes
        .filter((fonte) => fonte.tipo === "google_news")
        .map((fonte) => ({ indice: fonte.indice, consulta: (consultas[fonte.indice] ?? "").trim() }))
        .filter((edicao) => {
          const original = site.fontes.find((fonte) => fonte.indice === edicao.indice)!;
          return edicao.consulta !== (original.consulta ?? "");
        }),
    [site.fontes, consultas],
  );

  const mudou = hubsMudados.length > 0 || fontesMudadas.length > 0;
  const invalido =
    hubsMudados.some((hub) => hub.termos.length === 0) ||
    fontesMudadas.some((fonte) => !fonte.consulta);

  function submete() {
    salvar.mutate(
      {
        sha,
        site: site.id,
        ...(hubsMudados.length ? { hubs: hubsMudados } : {}),
        ...(fontesMudadas.length ? { fontes: fontesMudadas } : {}),
      },
      {
        onSuccess: () =>
          toast.success(`Commit feito no sites.yaml (${site.id}) — o radar usa na próxima rodada.`),
        onError: (erro) => toast.error((erro as Error).message),
      },
    );
  }

  return (
    <div className="space-y-6">
      <Card className="p-6">
        <div className="flex flex-wrap items-center gap-x-6 gap-y-1 text-sm">
          <span className="font-semibold">{site.entidade || site.id}</span>
          <a
            href={`https://${site.dominio}`}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 text-muted-foreground hover:underline"
          >
            {site.dominio} <ExternalLink className="h-3 w-3" />
          </a>
        </div>
      </Card>

      <Card className="p-6">
        <h2 className="text-lg font-semibold">Consultas das fontes</h2>
        <p className="mb-4 text-sm text-muted-foreground">
          O que o radar busca no Google News a cada rodada. Frases curtas e específicas rendem mais que genéricas.
        </p>
        <div className="space-y-3">
          {site.fontes.map((fonte) =>
            fonte.tipo === "google_news" ? (
              <div key={fonte.indice} className="flex items-center gap-3">
                <Badge variant="outline" className="shrink-0">google_news</Badge>
                <Input
                  value={consultas[fonte.indice] ?? ""}
                  maxLength={120}
                  onChange={(e) =>
                    setConsultas((atual) => ({ ...atual, [fonte.indice]: e.target.value }))
                  }
                />
              </div>
            ) : (
              <div key={fonte.indice} className="flex items-center gap-3 text-sm text-muted-foreground">
                <Badge variant="outline" className="shrink-0">{fonte.tipo}</Badge>
                <span className="truncate">{fonte.url ?? fonte.consulta ?? "—"} (só no repo)</span>
              </div>
            ),
          )}
          {site.fontes.length === 0 && (
            <p className="text-sm text-muted-foreground">Nenhuma fonte configurada — adicione no sites.yaml.</p>
          )}
        </div>
      </Card>

      <Card className="p-6">
        <h2 className="text-lg font-semibold">Termos por hub</h2>
        <p className="mb-4 text-sm text-muted-foreground">
          Palavras que classificam cada pauta no hub certo (separe por vírgula). Pauta sem termo casado fica sem hub.
        </p>
        <div className="space-y-5">
          {site.hubs.map((hub) => {
            const termos = textoParaTermos(termosPorHub[hub.id] ?? "");
            return (
              <div key={hub.id} className="space-y-1.5">
                <div className="flex items-baseline justify-between gap-3">
                  <Label htmlFor={`termos-${hub.id}`}>{hub.titulo}</Label>
                  <span className="text-xs text-muted-foreground">
                    {hub.id} · {termos.length} {termos.length === 1 ? "termo" : "termos"}
                  </span>
                </div>
                <Textarea
                  id={`termos-${hub.id}`}
                  value={termosPorHub[hub.id] ?? ""}
                  rows={2}
                  onChange={(e) =>
                    setTermosPorHub((atual) => ({ ...atual, [hub.id]: e.target.value }))
                  }
                />
                {termos.length === 0 && (
                  <p className="text-xs text-destructive">Informe ao menos um termo.</p>
                )}
              </div>
            );
          })}
        </div>
      </Card>

      <div className="flex items-center gap-3">
        <Button onClick={submete} disabled={!mudou || invalido || salvar.isPending}>
          {salvar.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          Salvar no repositório
        </Button>
        {mudou && !salvar.isPending && (
          <span className="text-sm text-muted-foreground">
            {hubsMudados.length + fontesMudadas.length}{" "}
            {hubsMudados.length + fontesMudadas.length === 1 ? "alteração vira" : "alterações viram"} um commit na main.
          </span>
        )}
      </div>
    </div>
  );
}
