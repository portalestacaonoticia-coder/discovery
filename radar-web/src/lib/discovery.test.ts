import { describe, expect, it } from "vitest";
import { termosIguais, termosParaTexto, textoParaTermos } from "./discovery";

describe("textoParaTermos", () => {
  it("separa por vírgula, apara espaços e descarta vazios", () => {
    expect(textoParaTermos(" show,  shows , turnê,, ")).toEqual(["show", "shows", "turnê"]);
  });

  it("mantém termos de mais de uma palavra", () => {
    expect(textoParaTermos("cesta basica, air fryer")).toEqual(["cesta basica", "air fryer"]);
  });

  it("texto vazio vira lista vazia", () => {
    expect(textoParaTermos("   ")).toEqual([]);
  });
});

describe("termosParaTexto", () => {
  it("faz o caminho de volta do campo editável", () => {
    const termos = ["dolar", "dólar", "cotacao"];
    expect(textoParaTermos(termosParaTexto(termos))).toEqual(termos);
  });
});

describe("termosIguais", () => {
  it("iguais só com mesmo conteúdo na mesma ordem", () => {
    expect(termosIguais(["a", "b"], ["a", "b"])).toBe(true);
    expect(termosIguais(["a", "b"], ["b", "a"])).toBe(false);
    expect(termosIguais(["a"], ["a", "b"])).toBe(false);
  });
});
