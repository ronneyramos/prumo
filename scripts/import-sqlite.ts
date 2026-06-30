// scripts/import-sqlite.ts
import { parseArgs } from "util";
import Database from "better-sqlite3";
import { createClient } from "@supabase/supabase-js";
import * as fs from "fs";

const { values } = parseArgs({
  args: Bun.argv.slice(2),
  options: {
    db:      { type: "string" },
    empresa: { type: "string" },
    dryRun:  { type: "boolean" },
    verbose: { type: "boolean" },
  },
  strict: true,
});

const dbPath    = values.db      || "./mbr.db";
const empresaId = values.empresa;
const DRY_RUN   = values.dryRun  || false;
const VERBOSE   = values.verbose || false;

if (!empresaId) {
  console.error("❌ Erro: O parâmetro --empresa <UUID> é obrigatório.");
  console.error("   Uso: bun run scripts/import-sqlite.ts --db ./mbr.db --empresa <UUID> [--dry-run] [--verbose]");
  process.exit(1);
}

if (DRY_RUN) console.log("🔍 MODO DRY-RUN ativado — nenhum dado será gravado no Supabase.");

console.log(`🚀 Iniciando migração do MBR ERP v8.0...`);
console.log(`   Banco: ${dbPath} | Empresa: ${empresaId}\n`);

const sqlite = new Database(dbPath);

const supabase = createClient(
  process.env.SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!,
  { auth: { persistSession: false } }
);

// Maps para relacionar registros antigos com novos UUIDs
const mapaObras        = new Map<string, string>(); // nome_lower → uuid
const mapaFornecedores = new Map<string, string>(); // razao_social → uuid

const errosLog: string[] = ["Tabela,Erro,Dados"];

// Contadores por tabela
const contadores: Record<string, { ok: number; erro: number }> = {};
const iniciarContador = (tabela: string) => { contadores[tabela] = { ok: 0, erro: 0 }; };
const contarOk    = (t: string) => contadores[t].ok++;
const contarErro  = (t: string) => contadores[t].erro++;

// ─── Utilitários ────────────────────────────────────────────────────────────

const formatarMoeda = (valor: any): number => {
  if (typeof valor === "string")
    return parseFloat(valor.replace(/[^\d,-]/g, "").replace(",", ".")) || 0;
  return typeof valor === "number" ? valor : 0;
};

const formatarData = (dataStr: string | null | undefined): string | null => {
  if (!dataStr) return null;
  const s = String(dataStr).trim();
  // DD/MM/AAAA → AAAA-MM-DD
  const partes = s.split("/");
  if (partes.length === 3) return `${partes[2]}-${partes[1]}-${partes[0]}`;
  // já está em formato ISO
  if (/^\d{4}-\d{2}-\d{2}/.test(s)) return s.split("T")[0];
  return s;
};

const hoje = () => new Date().toISOString().split("T")[0];

const log = (msg: string) => { if (VERBOSE) console.log("  ", msg); };

// Inserção genérica com suporte a dry-run e upsert
async function inserir(
  tabela: string,
  payload: Record<string, any>,
  onConflict?: string
): Promise<string | null> {
  if (DRY_RUN) {
    log(`[DRY-RUN] ${tabela}: ${JSON.stringify(payload)}`);
    contarOk(tabela);
    return `dry-run-uuid-${Math.random().toString(36).slice(2)}`;
  }

  const query = supabase.from(tabela).upsert(payload, {
    onConflict: onConflict || "id",
    ignoreDuplicates: false,
  }).select("id").single();

  const { data, error } = await query;

  if (error) {
    errosLog.push(`${tabela},${error.message},${JSON.stringify(payload)}`);
    contarErro(tabela);
    log(`⚠️  Erro em ${tabela}: ${error.message}`);
    return null;
  }

  contarOk(tabela);
  return data?.id ?? null;
}

// Verificar se tabela existe no SQLite
const tabelaExiste = (nome: string): boolean => {
  const row = sqlite
    .prepare("SELECT name FROM sqlite_master WHERE type='table' AND name=?")
    .get(nome) as any;
  return !!row;
};

// ─── Migrações ──────────────────────────────────────────────────────────────

async function migrarObras() {
  console.log("📦 Migrando Obras...");
  iniciarContador("obras");
  if (!tabelaExiste("obras")) { console.log("   Tabela 'obras' não encontrada — pulando."); return; }

  const rows = sqlite.prepare("SELECT * FROM obras").all() as any[];
  let i = 0;
  for (const ob of rows) {
    i++;
    process.stdout.write(`\r   ${i}/${rows.length}`);
    const id = await inserir("obras", {
      empresa_id:      empresaId,
      nome:            ob.nome,
      localizacao:     ob.localizacao || "Não Informado",
      status:          ob.status      || "Ativa",
      orcamento_global: formatarMoeda(ob.orcamento_ou_valor || ob.valor || ob.orcamento),
      data_inicio:     formatarData(ob.data_inicio) || hoje(),
    }, "empresa_id,nome");

    if (id) mapaObras.set((ob.nome as string).toLowerCase(), id);
  }
  console.log();
}

async function migrarFornecedores() {
  console.log("🚚 Migrando Fornecedores...");
  iniciarContador("fornecedores");
  if (!tabelaExiste("notas_fiscais")) { console.log("   Tabela 'notas_fiscais' não encontrada — pulando."); return; }

  const rows = sqlite
    .prepare("SELECT DISTINCT fornecedor FROM notas_fiscais WHERE fornecedor IS NOT NULL AND fornecedor != ''")
    .all() as any[];

  let i = 0;
  for (const forn of rows) {
    i++;
    process.stdout.write(`\r   ${i}/${rows.length}`);
    const id = await inserir("fornecedores", {
      empresa_id:  empresaId,
      razao_social: forn.fornecedor,
      cnpj:        forn.cnpj || "00.000.000/0001-00",
    }, "empresa_id,razao_social");

    if (id) mapaFornecedores.set(forn.fornecedor, id);
  }
  console.log();
}

async function migrarNotasFiscais() {
  console.log("💰 Migrando Notas Fiscais → Contas a Pagar...");
  iniciarContador("contas_a_pagar");
  if (!tabelaExiste("notas_fiscais")) { console.log("   Tabela 'notas_fiscais' não encontrada — pulando."); return; }

  const rows = sqlite.prepare("SELECT * FROM notas_fiscais").all() as any[];
  let i = 0;
  for (const nf of rows) {
    i++;
    process.stdout.write(`\r   ${i}/${rows.length}`);

    const obraUuid = mapaObras.get((nf.obra as string || "").toLowerCase());
    if (!obraUuid) {
      errosLog.push(`notas_fiscais,Obra não mapeada: "${nf.obra}",${JSON.stringify(nf)}`);
      contarErro("contas_a_pagar");
      continue;
    }

    const fornUuid = mapaFornecedores.get(nf.fornecedor) || null;

    await inserir("contas_a_pagar", {
      empresa_id:     empresaId,
      obra_id:        obraUuid,
      fornecedor_id:  fornUuid,
      descricao:      `NF ${nf.numero || "S/N"} - ${nf.item || "Insumos"}`,
      categoria:      "Materiais",
      valor:          formatarMoeda(nf.valor_total || nf.valor),
      vencimento:     formatarData(nf.data_vencimento || nf.data) || hoje(),
      status:         nf.status === "Pago" ? "Pago" : "A Pagar",
      data_pagamento: nf.status === "Pago"
        ? (formatarData(nf.data_pagamento || nf.data) || null)
        : null,
    });
  }
  console.log();
}

async function migrarRequisicoes() {
  console.log("📋 Migrando Requisições...");
  iniciarContador("requisicoes");
  if (!tabelaExiste("requisicoes")) { console.log("   Tabela 'requisicoes' não encontrada — pulando."); return; }

  const rows = sqlite.prepare("SELECT * FROM requisicoes").all() as any[];
  let i = 0;
  for (const req of rows) {
    i++;
    process.stdout.write(`\r   ${i}/${rows.length}`);

    const obraUuid = mapaObras.get((req.obra as string || "").toLowerCase());

    await inserir("requisicoes", {
      empresa_id:  empresaId,
      obra_id:     obraUuid || null,
      item:        req.item,
      quantidade:  req.quantidade || req.qtd || 0,
      unidade:     req.unidade    || "un",
      status:      req.status     || "Pendente",
      criado_em:   formatarData(req.data) || hoje(),
    });
  }
  console.log();
}

async function migrarEstoque() {
  console.log("📦 Migrando Estoque...");
  iniciarContador("estoque");
  if (!tabelaExiste("estoque")) { console.log("   Tabela 'estoque' não encontrada — pulando."); return; }

  const rows = sqlite.prepare("SELECT * FROM estoque").all() as any[];
  let i = 0;
  for (const item of rows) {
    i++;
    process.stdout.write(`\r   ${i}/${rows.length}`);

    await inserir("estoque", {
      empresa_id:  empresaId,
      item:        item.item  || item.descricao,
      unidade:     item.unidade || "un",
      saldo:       item.saldo  || item.quantidade || 0,
      preco_unit:  formatarMoeda(item.preco || item.preco_unit),
    }, "empresa_id,item");
  }
  console.log();
}

async function migrarFuncionarios() {
  console.log("👷 Migrando Funcionários...");
  iniciarContador("funcionarios");
  if (!tabelaExiste("funcionarios")) { console.log("   Tabela 'funcionarios' não encontrada — pulando."); return; }

  const rows = sqlite.prepare("SELECT * FROM funcionarios").all() as any[];
  let i = 0;
  for (const func of rows) {
    i++;
    process.stdout.write(`\r   ${i}/${rows.length}`);

    await inserir("funcionarios", {
      empresa_id: empresaId,
      nome:       func.nome,
      cargo:      func.cargo   || "Não Informado",
      cpf:        func.cpf     || null,
      admissao:   formatarData(func.admissao || func.data_admissao) || null,
      status:     func.status  || "Ativo",
    }, "empresa_id,cpf");
  }
  console.log();
}

// ─── Principal ──────────────────────────────────────────────────────────────

async function migrar() {
  // Validar conexão com Supabase antes de começar
  if (!DRY_RUN) {
    const { error } = await supabase.from("obras").select("id").limit(1);
    if (error) {
      console.error("❌ Não foi possível conectar ao Supabase:", error.message);
      console.error("   Verifique SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY.");
      process.exit(1);
    }
    console.log("✅ Conexão com Supabase confirmada.\n");
  }

  try {
    await migrarObras();
    await migrarFornecedores();
    await migrarNotasFiscais();
    await migrarRequisicoes();
    await migrarEstoque();
    await migrarFuncionarios();
  } catch (err: any) {
    console.error("\n❌ Erro crítico durante a migração:", err.message);
  }

  // ─── Resumo final ──────────────────────────────────────────────────────
  console.log("\n🏁 ─── MIGRAÇÃO FINALIZADA ───");
  console.log("┌──────────────────┬────────┬────────┐");
  console.log("│ Tabela           │   OK   │  Erro  │");
  console.log("├──────────────────┼────────┼────────┤");
  for (const [tabela, cnt] of Object.entries(contadores)) {
    const nome  = tabela.padEnd(16);
    const ok    = String(cnt.ok).padStart(6);
    const erro  = String(cnt.erro).padStart(6);
    console.log(`│ ${nome} │ ${ok} │ ${erro} │`);
  }
  console.log("└──────────────────┴────────┴────────┘");

  if (errosLog.length > 1) {
    fs.writeFileSync("import-errors.csv", errosLog.join("\n"), "utf-8");
    console.log(`\n⚠️  ${errosLog.length - 1} aviso(s) salvo(s) em 'import-errors.csv'.`);
  } else {
    console.log("\n🎉 Sucesso total! Todos os dados importados sem erros.");
  }

  if (DRY_RUN) console.log("\n🔍 DRY-RUN concluído — nenhum dado foi gravado.");
}

migrar();
