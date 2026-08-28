export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export type Database = {
  // Allows to automatically instantiate createClient with right options
  // instead of createClient<Database, { PostgrestVersion: 'XX' }>(URL, KEY)
  __InternalSupabase: {
    PostgrestVersion: "14.5"
  }
  public: {
    Tables: {
      content_briefs: {
        Row: {
          categoria: string | null
          created_at: string
          data_publicar_alvo: string | null
          estrutura_sugerida: string | null
          id: string
          instrucoes: string | null
          intencao: string | null
          keyword_opportunity_id: string | null
          keyword_principal: string
          keywords_secundarias: string[]
          links_internos_sugeridos: Json | null
          origem: string
          projeto_id: string
          status: string
          tamanho: string
          tipo_pauta: string
          titulo: string
          updated_at: string
          url_existente: string | null
          wp_category_id: number | null
          wp_category_nome: string | null
        }
        Insert: {
          categoria?: string | null
          created_at?: string
          data_publicar_alvo?: string | null
          estrutura_sugerida?: string | null
          id?: string
          instrucoes?: string | null
          intencao?: string | null
          keyword_opportunity_id?: string | null
          keyword_principal: string
          keywords_secundarias?: string[]
          links_internos_sugeridos?: Json | null
          origem?: string
          projeto_id: string
          status?: string
          tamanho?: string
          tipo_pauta?: string
          titulo: string
          updated_at?: string
          url_existente?: string | null
          wp_category_id?: number | null
          wp_category_nome?: string | null
        }
        Update: {
          categoria?: string | null
          created_at?: string
          data_publicar_alvo?: string | null
          estrutura_sugerida?: string | null
          id?: string
          instrucoes?: string | null
          intencao?: string | null
          keyword_opportunity_id?: string | null
          keyword_principal?: string
          keywords_secundarias?: string[]
          links_internos_sugeridos?: Json | null
          origem?: string
          projeto_id?: string
          status?: string
          tamanho?: string
          tipo_pauta?: string
          titulo?: string
          updated_at?: string
          url_existente?: string | null
          wp_category_id?: number | null
          wp_category_nome?: string | null
        }
        Relationships: []
      }
      content_audit_rules: {
        Row: {
          ativo: boolean
          category_id: number
          category_nome: string | null
          created_at: string
          frequencia_dias: number
          id: string
          idioma: string
          last_run_at: string | null
          max_posts_por_run: number
          min_score_fila: number
          projeto_id: string
          tamanho: string
          tom: string
          updated_at: string
          user_id: string | null
        }
        Insert: {
          ativo?: boolean
          category_id: number
          category_nome?: string | null
          created_at?: string
          frequencia_dias?: number
          id?: string
          idioma?: string
          last_run_at?: string | null
          max_posts_por_run?: number
          min_score_fila?: number
          projeto_id: string
          tamanho?: string
          tom?: string
          updated_at?: string
          user_id?: string | null
        }
        Update: {
          ativo?: boolean
          category_id?: number
          category_nome?: string | null
          created_at?: string
          frequencia_dias?: number
          id?: string
          idioma?: string
          last_run_at?: string | null
          max_posts_por_run?: number
          min_score_fila?: number
          projeto_id?: string
          tamanho?: string
          tom?: string
          updated_at?: string
          user_id?: string | null
        }
        Relationships: []
      }
      content_audits: {
        Row: {
          categoria_id: number | null
          contexto_atualizacao: string | null
          created_at: string
          decided_at: string | null
          decided_by: string | null
          diagnostico: string | null
          erro_msg: string | null
          evidencias: Json
          id: string
          pauta_id: string | null
          post_modified_at: string | null
          post_titulo: string | null
          post_url: string | null
          projeto_id: string
          rule_id: string | null
          score: number
          status: string
          tipo_problema: string[]
          titulo_sugerido: string | null
          user_id: string | null
          wp_post_id: number
        }
        Insert: {
          categoria_id?: number | null
          contexto_atualizacao?: string | null
          created_at?: string
          decided_at?: string | null
          decided_by?: string | null
          diagnostico?: string | null
          erro_msg?: string | null
          evidencias?: Json
          id?: string
          pauta_id?: string | null
          post_modified_at?: string | null
          post_titulo?: string | null
          post_url?: string | null
          projeto_id: string
          rule_id?: string | null
          score?: number
          status?: string
          tipo_problema?: string[]
          titulo_sugerido?: string | null
          user_id?: string | null
          wp_post_id: number
        }
        Update: {
          categoria_id?: number | null
          contexto_atualizacao?: string | null
          created_at?: string
          decided_at?: string | null
          decided_by?: string | null
          diagnostico?: string | null
          erro_msg?: string | null
          evidencias?: Json
          id?: string
          pauta_id?: string | null
          post_modified_at?: string | null
          post_titulo?: string | null
          post_url?: string | null
          projeto_id?: string
          rule_id?: string | null
          score?: number
          status?: string
          tipo_problema?: string[]
          titulo_sugerido?: string | null
          user_id?: string | null
          wp_post_id?: number
        }
        Relationships: []
      }
      keyword_opportunities: {
        Row: {
          cliques: number | null
          created_at: string
          ctr: number | null
          decisao: string | null
          dificuldade: number | null
          embedding: string | null
          fonte: string
          id: string
          impressoes: number | null
          intencao: string | null
          keyword: string
          posicao_atual: number | null
          projeto_id: string
          raw: Json | null
          score: number
          similaridade: number | null
          status: string
          trend_score: number | null
          updated_at: string
          url_existente_id: string | null
          volume: number | null
          wp_category_id: number | null
          wp_category_nome: string | null
        }
        Insert: {
          cliques?: number | null
          created_at?: string
          ctr?: number | null
          decisao?: string | null
          dificuldade?: number | null
          embedding?: string | null
          fonte?: string
          id?: string
          impressoes?: number | null
          intencao?: string | null
          keyword: string
          posicao_atual?: number | null
          projeto_id: string
          raw?: Json | null
          score?: number
          similaridade?: number | null
          status?: string
          trend_score?: number | null
          updated_at?: string
          url_existente_id?: string | null
          volume?: number | null
          wp_category_id?: number | null
          wp_category_nome?: string | null
        }
        Update: {
          cliques?: number | null
          created_at?: string
          ctr?: number | null
          decisao?: string | null
          dificuldade?: number | null
          embedding?: string | null
          fonte?: string
          id?: string
          impressoes?: number | null
          intencao?: string | null
          keyword?: string
          posicao_atual?: number | null
          projeto_id?: string
          raw?: Json | null
          score?: number
          similaridade?: number | null
          status?: string
          trend_score?: number | null
          updated_at?: string
          url_existente_id?: string | null
          volume?: number | null
          wp_category_id?: number | null
          wp_category_nome?: string | null
        }
        Relationships: []
      }
      project_publication_rules: {
        Row: {
          ativo: boolean
          buffer_dias_alvo: number
          categorias: string[]
          created_at: string
          dias_permitidos: number[]
          frequencia_semanal: number
          horarios_permitidos: string[]
          ia_provider: string
          id: string
          idioma: string
          keywords_prioritarias: string[]
          keywords_proibidas: string[]
          limite_posts_dia: number
          limite_posts_semana: number
          projeto_id: string
          publico_alvo: string | null
          serpapi_ai_overview: boolean
          serpapi_habilitado: boolean
          serpapi_news: boolean
          serpapi_trends: boolean
          timezone: string
          tipos_conteudo: string[]
          tom: string | null
          updated_at: string
          validation_gate: boolean
          web_search_enabled: boolean
        }
        Insert: {
          ativo?: boolean
          buffer_dias_alvo?: number
          categorias?: string[]
          created_at?: string
          dias_permitidos?: number[]
          frequencia_semanal?: number
          horarios_permitidos?: string[]
          ia_provider?: string
          id?: string
          idioma?: string
          keywords_prioritarias?: string[]
          keywords_proibidas?: string[]
          limite_posts_dia?: number
          limite_posts_semana?: number
          projeto_id: string
          publico_alvo?: string | null
          serpapi_ai_overview?: boolean
          serpapi_habilitado?: boolean
          serpapi_news?: boolean
          serpapi_trends?: boolean
          timezone?: string
          tipos_conteudo?: string[]
          tom?: string | null
          updated_at?: string
          validation_gate?: boolean
          web_search_enabled?: boolean
        }
        Update: {
          ativo?: boolean
          buffer_dias_alvo?: number
          categorias?: string[]
          created_at?: string
          dias_permitidos?: number[]
          frequencia_semanal?: number
          horarios_permitidos?: string[]
          ia_provider?: string
          id?: string
          idioma?: string
          keywords_prioritarias?: string[]
          keywords_proibidas?: string[]
          limite_posts_dia?: number
          limite_posts_semana?: number
          projeto_id?: string
          publico_alvo?: string | null
          serpapi_ai_overview?: boolean
          serpapi_habilitado?: boolean
          serpapi_news?: boolean
          serpapi_trends?: boolean
          timezone?: string
          tipos_conteudo?: string[]
          tom?: string | null
          updated_at?: string
          validation_gate?: boolean
          web_search_enabled?: boolean
        }
        Relationships: []
      }
      guardrail_prompts: {
        Row: {
          ativo: boolean
          conteudo: string
          created_at: string
          descricao: string | null
          formato: string
          id: string
          projeto_id: string | null
          slot: string
          updated_at: string
          updated_by: string | null
        }
        Insert: {
          ativo?: boolean
          conteudo: string
          created_at?: string
          descricao?: string | null
          formato?: string
          id?: string
          projeto_id?: string | null
          slot: string
          updated_at?: string
          updated_by?: string | null
        }
        Update: {
          ativo?: boolean
          conteudo?: string
          created_at?: string
          descricao?: string | null
          formato?: string
          id?: string
          projeto_id?: string | null
          slot?: string
          updated_at?: string
          updated_by?: string | null
        }
        Relationships: []
      }
      existing_urls: {
        Row: {
          categoria: string | null
          content_hash: string | null
          created_at: string
          data_publicacao: string | null
          embedding: string | null
          id: string
          keyword_inferida: string | null
          last_crawled_at: string | null
          projeto_id: string
          slug: string | null
          titulo: string | null
          url: string
        }
        Insert: {
          categoria?: string | null
          content_hash?: string | null
          created_at?: string
          data_publicacao?: string | null
          embedding?: string | null
          id?: string
          keyword_inferida?: string | null
          last_crawled_at?: string | null
          projeto_id: string
          slug?: string | null
          titulo?: string | null
          url: string
        }
        Update: {
          categoria?: string | null
          content_hash?: string | null
          created_at?: string
          data_publicacao?: string | null
          embedding?: string | null
          id?: string
          keyword_inferida?: string | null
          last_crawled_at?: string | null
          projeto_id?: string
          slug?: string | null
          titulo?: string | null
          url?: string
        }
        Relationships: []
      }
      configuracoes: {
        Row: {
          anthropic_key: string | null
          deepseek_key: string | null
          drive_folder_id: string | null
          gemini_key: string | null
          id: string
          openai_key: string | null
          updated_at: string
          user_id: string
          wp_app_password: string | null
          wp_url: string | null
          wp_user: string | null
        }
        Insert: {
          anthropic_key?: string | null
          deepseek_key?: string | null
          drive_folder_id?: string | null
          gemini_key?: string | null
          id?: string
          openai_key?: string | null
          updated_at?: string
          user_id: string
          wp_app_password?: string | null
          wp_url?: string | null
          wp_user?: string | null
        }
        Update: {
          anthropic_key?: string | null
          deepseek_key?: string | null
          drive_folder_id?: string | null
          gemini_key?: string | null
          id?: string
          openai_key?: string | null
          updated_at?: string
          user_id?: string
          wp_app_password?: string | null
          wp_url?: string | null
          wp_user?: string | null
        }
        Relationships: []
      }
      estrutura_templates: {
        Row: {
          conteudo: string
          tipo: string
          updated_at: string
        }
        Insert: {
          conteudo: string
          tipo: string
          updated_at?: string
        }
        Update: {
          conteudo?: string
          tipo?: string
          updated_at?: string
        }
        Relationships: []
      }
      pautas: {
        Row: {
          canal: string | null
          categoria: string | null
          codigo_php_h1: string | null
          created_at: string
          data_publicar: string | null
          drive_file_id: string | null
          drive_file_url: string | null
          erro_msg: string | null
          estrutura_post: string | null
          id: string
          instrucoes: string | null
          keywords: string | null
          projeto_id: string | null
          referencias_posts: string | null
          snippet_conversao: string | null
          status: string
          tipo_pauta: string
          titulo: string
          topicos: string | null
          updated_at: string
          url_post: string | null
          user_id: string | null
          wp_post_id: number | null
        }
        Insert: {
          canal?: string | null
          categoria?: string | null
          codigo_php_h1?: string | null
          created_at?: string
          data_publicar?: string | null
          drive_file_id?: string | null
          drive_file_url?: string | null
          erro_msg?: string | null
          estrutura_post?: string | null
          id?: string
          instrucoes?: string | null
          keywords?: string | null
          projeto_id?: string | null
          referencias_posts?: string | null
          snippet_conversao?: string | null
          status?: string
          tipo_pauta?: string
          titulo: string
          topicos?: string | null
          updated_at?: string
          url_post?: string | null
          user_id?: string | null
          wp_post_id?: number | null
        }
        Update: {
          canal?: string | null
          categoria?: string | null
          codigo_php_h1?: string | null
          created_at?: string
          data_publicar?: string | null
          drive_file_id?: string | null
          drive_file_url?: string | null
          erro_msg?: string | null
          estrutura_post?: string | null
          id?: string
          instrucoes?: string | null
          keywords?: string | null
          projeto_id?: string | null
          referencias_posts?: string | null
          snippet_conversao?: string | null
          status?: string
          tipo_pauta?: string
          titulo?: string
          topicos?: string | null
          updated_at?: string
          url_post?: string | null
          user_id?: string | null
          wp_post_id?: number | null
        }
        Relationships: [
          {
            foreignKeyName: "pautas_projeto_id_fkey"
            columns: ["projeto_id"]
            isOneToOne: false
            referencedRelation: "projetos"
            referencedColumns: ["id"]
          },
        ]
      }
      calendario_slots: {
        Row: {
          cor: string | null
          created_at: string
          dia_semana: number
          hora_publicacao: string | null
          id: string
          posicao: number
          projeto_id: string | null
          responsavel: string | null
          texto: string
          updated_at: string
          user_id: string | null
        }
        Insert: {
          cor?: string | null
          created_at?: string
          dia_semana: number
          hora_publicacao?: string | null
          id?: string
          posicao?: number
          projeto_id?: string | null
          responsavel?: string | null
          texto: string
          updated_at?: string
          user_id?: string | null
        }
        Update: {
          cor?: string | null
          created_at?: string
          dia_semana?: number
          hora_publicacao?: string | null
          id?: string
          posicao?: number
          projeto_id?: string | null
          responsavel?: string | null
          texto?: string
          updated_at?: string
          user_id?: string | null
        }
        Relationships: []
      }
      projeto_calendario: {
        Row: {
          concluida: boolean
          created_at: string
          data: string
          descricao: string | null
          id: string
          projeto_id: string
          tipo: string
          titulo: string
          updated_at: string
          user_id: string | null
        }
        Insert: {
          concluida?: boolean
          created_at?: string
          data: string
          descricao?: string | null
          id?: string
          projeto_id: string
          tipo?: string
          titulo: string
          updated_at?: string
          user_id?: string | null
        }
        Update: {
          concluida?: boolean
          created_at?: string
          data?: string
          descricao?: string | null
          id?: string
          projeto_id?: string
          tipo?: string
          titulo?: string
          updated_at?: string
          user_id?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "projeto_calendario_projeto_id_fkey"
            columns: ["projeto_id"]
            isOneToOne: false
            referencedRelation: "projetos"
            referencedColumns: ["id"]
          },
        ]
      }
      projetos: {
        Row: {
          cms_tipo: string
          created_at: string
          dominio: string | null
          id: string
          nome: string
          p0_shortcode_default: string | null
          p0_template_slug: string | null
          p1_categorias: Json
          p2_categorias: Json
          pais_idioma: string | null
          permalink_type: string | null
          posicao: number
          redirect_plugin: string | null
          sitemap_url: string | null
          vertical: string | null
          wp_app_password: string | null
          wp_url: string | null
          wp_user: string | null
        }
        Insert: {
          cms_tipo?: string
          created_at?: string
          dominio?: string | null
          id?: string
          nome: string
          p0_shortcode_default?: string | null
          p0_template_slug?: string | null
          p1_categorias?: Json
          p2_categorias?: Json
          pais_idioma?: string | null
          permalink_type?: string | null
          posicao?: number
          redirect_plugin?: string | null
          sitemap_url?: string | null
          vertical?: string | null
          wp_app_password?: string | null
          wp_url?: string | null
          wp_user?: string | null
        }
        Update: {
          cms_tipo?: string
          created_at?: string
          dominio?: string | null
          id?: string
          nome?: string
          p0_shortcode_default?: string | null
          p0_template_slug?: string | null
          p1_categorias?: Json
          p2_categorias?: Json
          pais_idioma?: string | null
          permalink_type?: string | null
          posicao?: number
          redirect_plugin?: string | null
          sitemap_url?: string | null
          vertical?: string | null
          wp_app_password?: string | null
          wp_url?: string | null
          wp_user?: string | null
        }
        Relationships: []
      }
      taxonomy_runs: {
        Row: {
          categorias_criar: Json
          created_at: string
          decided_at: string | null
          decided_by: string | null
          diagnostico: Json
          id: string
          projeto_id: string
          relatorio: string | null
          status: string
          tags_criar: Json
          total_changes: number
          total_posts: number
          user_id: string | null
        }
        Insert: {
          categorias_criar?: Json
          created_at?: string
          decided_at?: string | null
          decided_by?: string | null
          diagnostico?: Json
          id?: string
          projeto_id: string
          relatorio?: string | null
          status?: string
          tags_criar?: Json
          total_changes?: number
          total_posts?: number
          user_id?: string | null
        }
        Update: {
          categorias_criar?: Json
          created_at?: string
          decided_at?: string | null
          decided_by?: string | null
          diagnostico?: Json
          id?: string
          projeto_id?: string
          relatorio?: string | null
          status?: string
          tags_criar?: Json
          total_changes?: number
          total_posts?: number
          user_id?: string | null
        }
        Relationships: []
      }
      taxonomy_post_changes: {
        Row: {
          categoria_atual_ids: number[]
          categoria_atual_nome: string | null
          categoria_id_aplicada: number | null
          confianca: number
          created_at: string
          decided_at: string | null
          decided_by: string | null
          erro_msg: string | null
          id: string
          justificativa: string | null
          post_titulo: string | null
          post_url: string | null
          projeto_id: string
          run_id: string
          status: string
          target_categoria_nome: string | null
          target_categoria_slug: string | null
          target_tags: string[]
          wp_post_id: number
        }
        Insert: {
          categoria_atual_ids?: number[]
          categoria_atual_nome?: string | null
          categoria_id_aplicada?: number | null
          confianca?: number
          created_at?: string
          decided_at?: string | null
          decided_by?: string | null
          erro_msg?: string | null
          id?: string
          justificativa?: string | null
          post_titulo?: string | null
          post_url?: string | null
          projeto_id: string
          run_id: string
          status?: string
          target_categoria_nome?: string | null
          target_categoria_slug?: string | null
          target_tags?: string[]
          wp_post_id: number
        }
        Update: {
          categoria_atual_ids?: number[]
          categoria_atual_nome?: string | null
          categoria_id_aplicada?: number | null
          confianca?: number
          created_at?: string
          decided_at?: string | null
          decided_by?: string | null
          erro_msg?: string | null
          id?: string
          justificativa?: string | null
          post_titulo?: string | null
          post_url?: string | null
          projeto_id?: string
          run_id?: string
          status?: string
          target_categoria_nome?: string | null
          target_categoria_slug?: string | null
          target_tags?: string[]
          wp_post_id?: number
        }
        Relationships: []
      }
      dedup_groups: {
        Row: {
          created_at: string
          decided_at: string | null
          decided_by: string | null
          id: string
          label: string
          motivo: string | null
          pilar_slug: string | null
          pilar_titulo: string | null
          pilar_url: string | null
          projeto_id: string
          sinais: string[]
          size: number
          status: string
          user_id: string | null
        }
        Insert: {
          created_at?: string
          decided_at?: string | null
          decided_by?: string | null
          id?: string
          label?: string
          motivo?: string | null
          pilar_slug?: string | null
          pilar_titulo?: string | null
          pilar_url?: string | null
          projeto_id: string
          sinais?: string[]
          size?: number
          status?: string
          user_id?: string | null
        }
        Update: {
          created_at?: string
          decided_at?: string | null
          decided_by?: string | null
          id?: string
          label?: string
          motivo?: string | null
          pilar_slug?: string | null
          pilar_titulo?: string | null
          pilar_url?: string | null
          projeto_id?: string
          sinais?: string[]
          size?: number
          status?: string
          user_id?: string | null
        }
        Relationships: []
      }
      dedup_members: {
        Row: {
          acao: string
          created_at: string
          decided_at: string | null
          decided_by: string | null
          erro_msg: string | null
          group_id: string
          id: string
          is_pilar: boolean
          projeto_id: string
          redirect_status: string | null
          redirect_target: string | null
          slug: string | null
          status: string
          titulo: string | null
          url: string
          wp_post_id: number | null
        }
        Insert: {
          acao?: string
          created_at?: string
          decided_at?: string | null
          decided_by?: string | null
          erro_msg?: string | null
          group_id: string
          id?: string
          is_pilar?: boolean
          projeto_id: string
          redirect_status?: string | null
          redirect_target?: string | null
          slug?: string | null
          status?: string
          titulo?: string | null
          url: string
          wp_post_id?: number | null
        }
        Update: {
          acao?: string
          created_at?: string
          decided_at?: string | null
          decided_by?: string | null
          erro_msg?: string | null
          group_id?: string
          id?: string
          is_pilar?: boolean
          projeto_id?: string
          redirect_status?: string | null
          redirect_target?: string | null
          slug?: string | null
          status?: string
          titulo?: string | null
          url?: string
          wp_post_id?: number | null
        }
        Relationships: []
      }
      link_audits: {
        Row: {
          categoria_id: number | null
          checked_at: string
          created_at: string
          erro_msg: string | null
          http_status: number
          id: string
          link_anchor: string | null
          link_tipo: string
          link_url: string
          post_titulo: string | null
          post_url: string | null
          projeto_id: string
          redirect_para: string | null
          resultado: string
          status: string
          user_id: string | null
          wp_post_id: number
        }
        Insert: {
          categoria_id?: number | null
          checked_at?: string
          created_at?: string
          erro_msg?: string | null
          http_status?: number
          id?: string
          link_anchor?: string | null
          link_tipo?: string
          link_url: string
          post_titulo?: string | null
          post_url?: string | null
          projeto_id: string
          redirect_para?: string | null
          resultado?: string
          status?: string
          user_id?: string | null
          wp_post_id: number
        }
        Update: {
          categoria_id?: number | null
          checked_at?: string
          created_at?: string
          erro_msg?: string | null
          http_status?: number
          id?: string
          link_anchor?: string | null
          link_tipo?: string
          link_url?: string
          post_titulo?: string | null
          post_url?: string | null
          projeto_id?: string
          redirect_para?: string | null
          resultado?: string
          status?: string
          user_id?: string | null
          wp_post_id?: number
        }
        Relationships: []
      }
    }
    Views: {
      [_ in never]: never
    }
    Functions: {
      [_ in never]: never
    }
    Enums: {
      [_ in never]: never
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

type DatabaseWithoutInternals = Omit<Database, "__InternalSupabase">

type DefaultSchema = DatabaseWithoutInternals[Extract<keyof Database, "public">]

export type Tables<
  DefaultSchemaTableNameOrOptions extends
    | keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
        DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
      DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])[TableName] extends {
      Row: infer R
    }
    ? R
    : never
  : DefaultSchemaTableNameOrOptions extends keyof (DefaultSchema["Tables"] &
        DefaultSchema["Views"])
    ? (DefaultSchema["Tables"] &
        DefaultSchema["Views"])[DefaultSchemaTableNameOrOptions] extends {
        Row: infer R
      }
      ? R
      : never
    : never

export type TablesInsert<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Insert: infer I
    }
    ? I
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Insert: infer I
      }
      ? I
      : never
    : never

export type TablesUpdate<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Update: infer U
    }
    ? U
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Update: infer U
      }
      ? U
      : never
    : never

export type Enums<
  DefaultSchemaEnumNameOrOptions extends
    | keyof DefaultSchema["Enums"]
    | { schema: keyof DatabaseWithoutInternals },
  EnumName extends DefaultSchemaEnumNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"]
    : never = never,
> = DefaultSchemaEnumNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"][EnumName]
  : DefaultSchemaEnumNameOrOptions extends keyof DefaultSchema["Enums"]
    ? DefaultSchema["Enums"][DefaultSchemaEnumNameOrOptions]
    : never

export type CompositeTypes<
  PublicCompositeTypeNameOrOptions extends
    | keyof DefaultSchema["CompositeTypes"]
    | { schema: keyof DatabaseWithoutInternals },
  CompositeTypeName extends PublicCompositeTypeNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"]
    : never = never,
> = PublicCompositeTypeNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"][CompositeTypeName]
  : PublicCompositeTypeNameOrOptions extends keyof DefaultSchema["CompositeTypes"]
    ? DefaultSchema["CompositeTypes"][PublicCompositeTypeNameOrOptions]
    : never

export const Constants = {
  public: {
    Enums: {},
  },
} as const
