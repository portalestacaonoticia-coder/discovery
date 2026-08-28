import { createClient } from '@supabase/supabase-js';
import type { Database } from './types';

// Supabase do conteudo.tihee, so para AUTH (mesmas contas em todos os apps).
// URL e chave anon sao publicas por design (vao no bundle de qualquer forma);
// o fallback literal dispensa configurar VITE_* na Vercel.
const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL ||
  'https://eprnygwxuysygloerbav.supabase.co';
const SUPABASE_PUBLISHABLE_KEY = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY ||
  'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImVwcm55Z3d4dXlzeWdsb2VyYmF2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQzOTgyODUsImV4cCI6MjA4OTk3NDI4NX0.hAXbTBbp2iWnb-vbKRCOTO15HkdCpwGOm_3R_xQGSn4';

// Import the supabase client like this:
// import { supabase } from "@/integrations/supabase/client";

export const supabase = createClient<Database>(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY, {
  auth: {
    storage: localStorage,
    persistSession: true,
    autoRefreshToken: true,
  }
});