---
id: ISSUE-010
title: Primeira publicação com SSO real e dois clientes isolados em produção
status: proposed
type: task
parent: docs/PLANO-MULTI-AMBIENTE.md
spec: docs/SPEC-MULTI-AMBIENTE.md
entrega: 1
blocked_by:
  - ISSUE-008
  - ISSUE-009
blocks:
  - ISSUE-011
  - ISSUE-016
  - ISSUE-017
labels:
  - ready-for-agent
source_requirements:
  - HU-15
  - HU-23
  - HU-25
  - HU-26
plan_tasks:
  - E1.17
spec_decisions:
  - 19
  - 27
---

# Primeira publicação com SSO real e dois clientes isolados em produção

## O que construir

A publicação da Entrega 1 no Azure, com o provedor de identidade corporativo
ligado e o modo de produção configurado. **Não é implantação de rotina**: é a
primeira vez que a aplicação recebe um principal de verdade, e é o risco aceito
nº 1 da spec — o código lê o e-mail tentando três reivindicações em ordem,
apuradas contra documentação e não contra uma resposta real do tenant.

Se o e-mail vier em outra reivindicação ou vier como UPN, o sintoma será
"ninguém entra em ambiente nenhum", com quatro mecanismos novos por trás para
suspeitar primeiro. Por isso a verificação segue uma ordem que separa as
causas, e por isso a guarda da ISSUE-005 nomeia o e-mail recebido: ela
transforma uma depuração às cegas numa leitura de tela.

Entra também a configuração da implantação: a lista de operadores e o modo de
produção. Não há migração de dado — nada está publicado e o conteúdo do
diretório de dados é carga de demonstração.

Roteiro de verificação, **nesta ordem**:

1. o endpoint de identidade responde com principal — a sessão existe;
2. a guarda nomeia o e-mail recebido — se vier vazio ou como UPN, a
   reivindicação é outra e a leitura do principal precisa de ajuste;
3. o e-mail nomeado casa com o membro do registro — a primeira camada funciona;
4. a pessoa entra no ambiente — a segunda camada funciona;
5. o cookie sobrevive a recarregamento e a aba nova, com `Secure` no domínio
   publicado;
6. os dois downloads e o relatório trazem o dado do ambiente certo.

## Critérios de aceite

- [ ] A aplicação está publicada com o provedor de identidade corporativo e o
      modo de produção.
- [ ] Existem dois ambientes reais criados pelo comando de administração, com
      membros concedidos.
- [ ] **Duas pessoas reais, em dois ambientes reais, trabalham sem se
      enxergar** — nenhuma tela de uma mostra dado da outra.
- [ ] Os seis passos do roteiro estão registrados com o resultado de cada um.
- [ ] O e-mail que a sessão entrega é o esperado; se não for, a leitura do
      principal foi ajustada e o passo repetido com resultado registrado.
- [ ] O cookie sobrevive a recarregamento e a aba nova no domínio publicado,
      com `Secure`.
- [ ] Os dois downloads e o relatório trazem o dado do ambiente ativo.
- [ ] A lista de operadores da implantação está configurada e um operador
      consegue entrar nos dois ambientes.

## Verificação

O próprio roteiro de seis passos, executado no ambiente publicado e registrado
com o resultado de cada passo — é a verificação e o entregável ao mesmo tempo.

Teste de isolamento com duas contas reais em dois ambientes: cada uma abre
matriz, dashboard, cadastros, colaboradores e governança e não encontra nada da
outra.

## Decisões humanas em aberto

- Quais e-mails ocupam o papel de operador na implantação.
- Quais dois ambientes reais são criados primeiro (identificador, nome do
  projeto e nome do cliente de cada um).

## Notas

Esta issue **fecha a Entrega 1**. As Entregas 2 e 3 dependem dela. As
dependências declaradas são ISSUE-008 e ISSUE-009, que fecham transitivamente
todas as demais da Entrega 1 — nenhuma issue de 001 a 009 fica de fora.

Publicar antes o código atual teria isolado a variável do SSO; optou-se
conscientemente por não fazê-lo, e a mitigação é a guarda que nomeia a causa.

A liberação anônima do espaço de rotas da API **não** entra aqui — ela é da
Entrega 3 e vem na ISSUE-016.
