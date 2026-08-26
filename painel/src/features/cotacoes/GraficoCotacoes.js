"use client";

import { useState } from "react";
import { dataLonga, moeda } from "@/lib/formata";

// Grafico de linha da serie PTAX, SVG puro. Segue a skill de dataviz:
// linha de 2px numa serie so (sem legenda: o titulo do cartao a nomeia),
// grade horizontal discreta, rotulo direto no ultimo ponto, texto sempre
// em tom de tinta (nunca na cor da serie) e crosshair + dica no hover.
const L = 640;
const A = 220;
const M = { esq: 52, dir: 16, topo: 14, base: 26 };

function passoBonito(bruto) {
  const expoente = Math.pow(10, Math.floor(Math.log10(bruto)));
  const normal = bruto / expoente;
  const fator = normal > 5 ? 10 : normal > 2 ? 5 : normal > 1 ? 2 : 1;
  return fator * expoente;
}

export default function GraficoCotacoes({ pontos }) {
  const [ativo, setAtivo] = useState(null);
  if (!pontos?.length) return null;

  const vendas = pontos.map((p) => Number(p.ptax_venda));
  let min = Math.min(...vendas);
  let max = Math.max(...vendas);
  if (min === max) { min -= 0.05; max += 0.05; }
  const folga = (max - min) * 0.1;
  min -= folga;
  max += folga;

  const x = (i) => M.esq + (i * (L - M.esq - M.dir)) / Math.max(pontos.length - 1, 1);
  const y = (v) => M.topo + (A - M.topo - M.base) * (1 - (v - min) / (max - min));

  const passo = passoBonito((max - min) / 4);
  const grades = [];
  for (let v = Math.ceil(min / passo) * passo; v <= max; v += passo) grades.push(v);

  // ~5 rotulos de data no eixo x, sempre incluindo o primeiro ponto
  const cadaN = Math.max(1, Math.ceil(pontos.length / 5));
  const caminho = vendas
    .map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`)
    .join(" ");
  const ultimo = pontos.length - 1;

  function aoMover(evento) {
    const caixa = evento.currentTarget.getBoundingClientRect();
    const xVista = ((evento.clientX - caixa.left) / caixa.width) * L;
    const fracao = (xVista - M.esq) / (L - M.esq - M.dir);
    const indice = Math.round(fracao * (pontos.length - 1));
    setAtivo(Math.max(0, Math.min(pontos.length - 1, indice)));
  }

  return (
    <div className="grafico-envelope">
      <svg
        viewBox={`0 0 ${L} ${A}`}
        role="img"
        aria-label={`Série da PTAX de venda com ${pontos.length} pregões, de ${dataLonga(pontos[0].data)} a ${dataLonga(pontos[ultimo].data)}`}
        onMouseMove={aoMover}
        onMouseLeave={() => setAtivo(null)}
      >
        {grades.map((v) => (
          <g key={v}>
            <line x1={M.esq} x2={L - M.dir} y1={y(v)} y2={y(v)} stroke="var(--grade)" strokeWidth="1" />
            <text x={M.esq - 6} y={y(v) + 3.5} textAnchor="end" fontSize="11" fill="var(--tinta-suave)" style={{ fontVariantNumeric: "tabular-nums" }}>
              {v.toFixed(2).replace(".", ",")}
            </text>
          </g>
        ))}

        <line x1={M.esq} x2={L - M.dir} y1={A - M.base} y2={A - M.base} stroke="var(--eixo)" strokeWidth="1" />

        {pontos.map((p, i) =>
          i % cadaN === 0 ? (
            <text key={p.data} x={x(i)} y={A - M.base + 16} textAnchor="middle" fontSize="11" fill="var(--tinta-suave)">
              {`${p.data.slice(8, 10)}/${p.data.slice(5, 7)}`}
            </text>
          ) : null,
        )}

        {ativo !== null && (
          <line x1={x(ativo)} x2={x(ativo)} y1={M.topo} y2={A - M.base} stroke="var(--eixo)" strokeWidth="1" strokeDasharray="3 3" />
        )}

        <path d={caminho} fill="none" stroke="var(--serie-1)" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />

        {/* rotulo direto so no ultimo ponto — nunca um numero em cada ponto */}
        <circle cx={x(ultimo)} cy={y(vendas[ultimo])} r="4" fill="var(--serie-1)" stroke="var(--superficie)" strokeWidth="2" />
        <text x={x(ultimo) - 8} y={y(vendas[ultimo]) - 10} textAnchor="end" fontSize="12" fontWeight="600" fill="var(--tinta-2)" style={{ fontVariantNumeric: "tabular-nums" }}>
          {vendas[ultimo].toFixed(4).replace(".", ",")}
        </text>

        {ativo !== null && (
          <circle cx={x(ativo)} cy={y(vendas[ativo])} r="4" fill="var(--serie-1)" stroke="var(--superficie)" strokeWidth="2" />
        )}
      </svg>

      {ativo !== null && (
        <div
          className="grafico-dica"
          style={{ left: `${(x(ativo) / L) * 100}%`, top: `${(y(vendas[ativo]) / A) * 100 - 6}%` }}
        >
          <div className="dica-data">{dataLonga(pontos[ativo].data)}</div>
          <div className="dica-valor">venda {moeda(pontos[ativo].ptax_venda)}</div>
          <div className="dica-valor">compra {moeda(pontos[ativo].ptax_compra)}</div>
        </div>
      )}
    </div>
  );
}
