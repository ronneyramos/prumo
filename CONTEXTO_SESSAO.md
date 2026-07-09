# 🏗️ Contexto da Sessão — ERP Prumo / MBR Construções

**Data:** 06/07/2026
**Participante:** Ronney (dev solo)

---

## Perfil da Construtora

- **Porte:** Média (30-100 funcionários)
- **Obras:** 5-8 ativas, 10-15 por ano
- **Usuários do ERP:** Diretoria, Admin/Financeiro, Almoxarife/Suprimentos, Engenheiros, Mestre de Obras, Cliente/Contratante, RH, Qualidade
- **Problema #1:** Não sabem se estão lucrando ou perdendo em cada obra (Orçado x Realizado)
- **Dados atuais:** Tudo em planilhas Excel (obras, contas, funcionários, orçamentos)
- **Bancos:** Mistos (tradicional + digital)
- **Disponibilidade:** 30-40h/semana

---

## Stack Definida

| Camada | Tecnologia |
|---|---|
| Web (admin/escritório) | Streamlit + Supabase |
| Mobile | PWA React (futuro — precisa aprender React primeiro) |
| Banco | Supabase Postgres |
| Auth | Supabase Auth |
| Storage | Supabase Storage |
| Hospedagem | Streamlit Cloud (+ domínio próprio) |

**Decisão:** Não migrar para TanStack Start agora. Focar em entregar valor com Streamlit + Supabase.

---

## Plano de 8 Semanas

### Mês 1 — Streamlit + Supabase

| Semana | Foco | Horas |
|---|---|---|
| 1 | Fundação (segurança, multi-empresa, migrar dados) | 40h |
| 2 | ⭐ Orçado x Realizado (prioridade máxima) | 40h |
| 3 | Financeiro (CP/CR, NF, fluxo caixa, conciliação) | 40h |
| 4 | Suprimentos + Estoque + Subempreiteiros + RDO | 40h |

### Mês 2 — Relatórios + Testes + Deploy

| Semana | Foco | Horas |
|---|---|---|
| 5 | Relatórios PDF + DRE por obra | 40h |
| 6 | Mobile responsivo + Notificações + Testes com 5 usuários | 40h |
| 7 | Correções de bugs + UX + Documentação | 40h |
| 8 | 🚀 Deploy + Treinamento + Rollout | 40h |

**Total:** 320h

---

## Checklist Completo

Arquivo: `CHECKLIST_ERP_8_SEMANAS.md` (na mesma pasta)

---

## Pendências / Dúvidas Abertas

- [ ] Qual banco específico? (dito "mistos" — precisa confirmar para integração OFX/CSV)
- [ ] Aprender React para o PWA mobile (previsto para mês 3+)
- [ ] Orçamento mensal para infraestrutura (~R$ 200-250/mês estimado)
