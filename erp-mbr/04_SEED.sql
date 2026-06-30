-- ============================================================
-- ERP MBR — Seed mínimo
-- ============================================================

-- Plano de contas (resumido)
insert into public.plano_contas (codigo, nome, tipo) values
  ('1','RECEITAS','RECEITA'),
  ('1.1','Receita de Obras','RECEITA'),
  ('1.1.01','Medições de contrato','RECEITA'),
  ('2','DESPESAS','DESPESA'),
  ('2.1','Materiais','DESPESA'),
  ('2.1.01','Cimento e argamassas','DESPESA'),
  ('2.1.02','Aço','DESPESA'),
  ('2.1.03','Concreto usinado','DESPESA'),
  ('2.2','Mão de obra','DESPESA'),
  ('2.2.01','Folha CLT','DESPESA'),
  ('2.2.02','Encargos','DESPESA'),
  ('2.2.03','Empreiteiros','DESPESA'),
  ('2.3','Serviços de terceiros','DESPESA'),
  ('2.4','Equipamentos e locação','DESPESA'),
  ('2.5','Administrativas','DESPESA'),
  ('2.6','Impostos','DESPESA')
on conflict (codigo) do nothing;

-- Centros de custo padrão
insert into public.centros_custo (codigo, nome) values
  ('ADM','Administrativo'),
  ('COM','Comercial')
on conflict (codigo) do nothing;

-- Conta bancária exemplo
insert into public.contas_bancarias (nome, banco, agencia, conta, saldo_inicial)
values ('Conta Principal','Banco do Brasil','0001','12345-6',0)
on conflict do nothing;

-- Checklist exemplo
insert into public.checklists_modelo (nome, servico, itens) values
  ('Concretagem de laje','Concretagem',
   '[{"ordem":1,"descricao":"Formas niveladas e estanques","criterio":"Visual"},
     {"ordem":2,"descricao":"Armadura conforme projeto","criterio":"Visual + medida"},
     {"ordem":3,"descricao":"Slump test realizado","criterio":"NBR NM 67"},
     {"ordem":4,"descricao":"Corpos de prova moldados","criterio":"NBR 5738"},
     {"ordem":5,"descricao":"Cura iniciada em até 12h","criterio":"Registro"}]'::jsonb)
on conflict do nothing;
