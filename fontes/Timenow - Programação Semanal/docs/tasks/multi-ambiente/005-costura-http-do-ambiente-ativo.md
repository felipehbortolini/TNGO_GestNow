---
id: ISSUE-005
title: Costura HTTP do ambiente ativo — resolução por requisição, recusa por redirecionamento e guarda que nomeia a causa
status: done
type: task
parent: docs/PLANO-MULTI-AMBIENTE.md
spec: docs/SPEC-MULTI-AMBIENTE.md
entrega: 1
blocked_by:
  - ISSUE-001
  - ISSUE-002
  - ISSUE-004
blocks:
  - ISSUE-006
labels:
  - ready-for-agent
source_requirements:
  - HU-09
  - HU-13
  - HU-14
  - HU-22
  - HU-23
  - HU-25
  - HU-26
  - HU-40
plan_tasks:
  - E1.6
  - E1.7
  - E1.8
  - E1.14 (parcial — identidade fixa da demonstração)
  - E1.16 (parcial)
  - Documentação transversal — ARCHITECTURE.md
spec_decisions:
  - 5
  - 6
  - 9
  - 19
  - 20
  - 26
---

# Costura HTTP do ambiente ativo — resolução por requisição, recusa por redirecionamento e guarda que nomeia a causa

## O que construir

A costura única por onde toda requisição de fragmento já passa ganha um passo
novo, **antes** da resolução do usuário. A ordem passa a ser: gate do fragmento
→ ambiente ativo → usuário → permissão. A ordem importa e não é negociável: a
resolução do usuário lê o cadastro de colaboradores, que agora vive **dentro**
de um ambiente; invertida, ela resolveria a pessoa contra o ambiente errado.

O ambiente ativo viaja em **cookie e em cabeçalho, e os dois são conferidos**.
O cookie é pista, nunca autorização: em toda requisição ele é conferido contra
o registro — o ambiente existe, está ativo, e o e-mail autenticado é membro
dele (ou é operador). O cabeçalho existe por causa das abas: cookie é estado
por navegador, não por aba, e sem ele quem tem Suzano numa aba e Alcoa noutra
teria a primeira aba re-apontada em silêncio, mostrando uma matriz e gravando
na outra base. Cabeçalho divergente do cookie é **recusa**, com a mensagem de
que aquela aba está em outro ambiente. Os dois downloads e o relatório para
impressão, que são navegação real do navegador e não têm o cabeçalho do Alpine,
levam o identificador na query e são conferidos do mesmo jeito.

O cookie é de sessão — sem prazo — com `HttpOnly`, `SameSite=Lax`, `Secure`
fora do modo local e caminho raiz. Ele sobrevive a recarregamento, a aba nova e
a link direto; o que ele não sobrevive é a fechar o navegador, e isso é de
propósito: quem tem vários ambientes é justamente quem precisa escolher
conscientemente a cada dia.

Entra também o **decorador irmão**, para o que roda sem ambiente: ele resolve
só a identidade do provedor de identidade e consulta o registro, sem tocar o
cadastro de colaboradores e sem exigir ambiente. Serve o seletor e a
administração do registro, e nada mais. Ele mantém o gate de fragmento e a tela
de guarda — que é o motivo de morar junto do decorador atual, em vez de virar
código solto no blueprint do seletor.

**O decorador irmão precisa nascer sabendo do modo demonstração.** Ele resolve
a pessoa pelo cabeçalho do provedor de identidade, que não existe quando a
aplicação roda por duplo clique — e o contorno de hoje (resolver pelo cadastro
de colaboradores) deixa de funcionar exatamente aqui, porque o cadastro passou a
viver dentro de um ambiente e este decorador roda **antes** de qualquer ambiente
existir. Então, em modo demonstração, ele devolve uma identidade fixa
(`demo@timenow.local`), sempre operadora. Sem isso, nada do que esta issue e a
ISSUE-006 entregam é verificável localmente — só depois de publicar.

A recusa **de ambiente, e só ela**, responde com o redirecionamento que o gate
de fragmento já usa, em vez de desenhar a guarda no alvo que o chamador pediu.
Acesso revogado, ambiente arquivado e aba velha não podem ser desenhados dentro
de um painel: o resto da tela continuaria mostrando a matriz do ambiente errado
com a sidebar dizendo o nome errado. As demais recusas continuam como estão.

E a guarda passa a **nomear o e-mail recebido e qual barreira recusou**, porque
uma mensagem só para quatro causas não diagnostica nenhuma:

| Causa | Mensagem |
|---|---|
| Nenhum e-mail na sessão | A sessão do Azure não trouxe um endereço de e-mail |
| E-mail fora do registro | O e-mail não consta no registro de ambientes |
| E-mail fora do cadastro do ambiente | O e-mail não consta no cadastro de colaboradores daquele projeto |
| Ambiente arquivado | Este ambiente foi arquivado |

As decisões de arquitetura do projeto passam a registrar as duas novidades: a
porta de persistência resolvida por ambiente e o decorador irmão.

## Critérios de aceite

- [x] Os cinco casos de recusa recusam: cookie ausente, ambiente inexistente,
      ambiente arquivado, e-mail não membro e cabeçalho divergente do cookie.
- [x] Cookie válido de quem é membro resolve, e o handler roda dentro do
      ambiente certo.
- [x] Nenhum handler roda com ambiente meio resolvido, e o contexto é sempre
      fechado ao fim da requisição, inclusive quando há exceção.
- [x] Os dois downloads e o relatório para impressão conferem o identificador
      da query e trazem o dado do ambiente ativo.
- [x] O cookie é de sessão — `SameSite=Lax`, caminho raiz, sem prazo, `Secure`
      fora do modo local, e legível por JavaScript. (O `HttpOnly` deste
      critério caiu na ISSUE-006: o boot estático precisa enxergar o cookie
      no cliente. A decisão 5 da spec foi anotada na revisão 2.1, e a spec
      vence a issue.)
- [x] Um endpoint decorado com o decorador irmão responde **sem** nenhum
      ambiente ativo e **sem** que exista cadastro de colaboradores.
- [x] Em modo demonstração, o decorador irmão devolve a identidade fixa da
      demonstração, sempre operadora, sem depender de cabeçalho de identidade —
      e um endpoint decorado com ele responde no duplo clique.
- [x] Uma recusa de ambiente disparada de dentro de um painel recarrega o
      shell, em vez de desenhar a guarda dentro do painel.
- [x] Cada uma das quatro causas produz uma mensagem diferente, e a mensagem
      nomeia o e-mail que a sessão entregou.
- [x] O recorte por vínculo de empresa contratada continua valendo por cima do
      recorte por ambiente.
- [x] A resolução do ambiente é função própria chamada pelo decorador, e não
      código embutido nele.
- [x] As decisões de arquitetura do projeto citam a porta por ambiente e o
      decorador irmão.

## Verificação

Testes da resolução do ambiente ativo cobrindo os cinco casos de recusa e o
caso que resolve, mais um caso por barreira de mensagem da guarda.

Revisão de tela do redirecionamento: disparar uma recusa de ambiente de dentro
de um painel e observar o shell recarregando em vez do painel sendo preenchido
com a guarda.

A porta de qualidade das cinco etapas passa.

## Decisões humanas em aberto

Nenhuma.

## Notas

A aplicação continua sem responder ao usuário final até a ISSUE-006, que põe o
seletor no boot e fecha a janela vermelha aberta na ISSUE-001.

O decorador atual não pode virar um decorador que faz quatro coisas embutidas —
a resolução do ambiente é função própria, ou ele fica difícil de ler.

Prefixo de rota e subdomínio foram descartados: o prefixo tocaria as cerca de
quarenta rotas dos dez blueprints, o servidor local, a configuração de rotas do
Static Web Apps e todos os alvos e links das views; o subdomínio exigiria DNS e
certificado por cliente e mataria a troca de ambiente em tela.
