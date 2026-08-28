import { useEffect } from "react";

const BASE_TITLE = "THC · Tihee Conteúdo";

/**
 * Define o `<title>` da página. Quando `prefix` é fornecido, vira
 * "${prefix} - Conteúdo | Planejamento - Tihee"; caso contrário usa o base.
 * Restaura o título base ao desmontar, para as demais telas não ficarem
 * herdando o prefixo de uma tela anterior.
 */
export function useDocumentTitle(prefix?: string | null) {
  useEffect(() => {
    document.title = prefix ? `${prefix} - ${BASE_TITLE}` : BASE_TITLE;
    return () => {
      document.title = BASE_TITLE;
    };
  }, [prefix]);
}
