// UNICO ponto de acesso ao Supabase — espelho do banco.py do radar.
// Roda SO no servidor (nenhum componente 'use client' importa daqui): usa a
// service key porque o RLS fica trancado sem policy publica, como o schema exige.
import { createClient } from "@supabase/supabase-js";

let cliente = null;

export function supabase() {
  if (!cliente) {
    cliente = createClient(
      process.env.SUPABASE_URL,
      process.env.SUPABASE_SERVICE_KEY,
      { auth: { persistSession: false } },
    );
  }
  return cliente;
}
