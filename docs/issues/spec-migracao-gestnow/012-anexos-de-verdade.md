---
id: ISSUE-012
title: "Anexos de verdade: pasta local ou Blob, limites por parâmetro e download com a permissão do registro de origem"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 2
onda: 4
blocked_by:
  - ISSUE-011
  - ISSUE-007
blocks:
  - ISSUE-019
  - ISSUE-023
  - ISSUE-029
  - ISSUE-044
  - ISSUE-045
  - ISSUE-051
  - ISSUE-064
  - ISSUE-072
labels:
  - ready-for-agent
source_requirements:
  - HU-140
  - HU-141
  - HU-142
  - HU-143
spec_decisions:
  - D5a
  - D14
---

# Anexos de verdade: pasta local ou Blob, limites por parâmetro e download com a permissão do registro de origem

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D5a, D14.
> Entrega 2 (Plataforma no ar), onda 4 (Serviços transversais).
> Histórias: 140, 141, 142, 143. Bloqueada por: ISSUE-011, ISSUE-007.

## O que construir

A porta de arquivos tem duas implementações escolhidas por variável de
ambiente: a pasta de anexos local do GestNow e o Azure Blob Storage. O banco
guarda os metadados (nome, tipo, tamanho, hash, quem enviou, quando e o
registro de origem); o arquivo fica no armazenamento.

O componente de upload do Design System envia o arquivo à rota de anexos, que
recusa com 422 e mensagem no campo quando o tamanho passa do limite ou o tipo
está fora da lista, ambos lidos do grupo Anexos dos parâmetros vigentes. A
lista de anexos de um registro mostra nome, tamanho, quem enviou e quando.

O download passa pela API (exceção de download do Padrão) e checa a permissão
de leitura do **registro de origem**, perguntando à fachada do módulo dono;
anexo de dado pessoal segue a mesma restrição do campo. "Evidência
obrigatória" passa a significar ao menos um anexo gravado, e uma função de
plataforma responde isso para os módulos.

## Critérios de aceite

- [ ] Upload acima do limite ou de tipo fora da lista é recusado com 422 e a mensagem no campo.
- [ ] Os metadados aparecem na lista de anexos do registro.
- [ ] Download de quem não pode ler o registro de origem é recusado; de quem pode, entrega o arquivo com o nome original.
- [ ] Trocar a variável de ambiente troca a implementação sem mudar código (o adaptador Blob é testado com dublê).
- [ ] A função de evidência responde se um registro tem ao menos um anexo.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Teste transversal de anexos da spec (limite, tipo e permissão do registro de
origem) e teste do adaptador Blob com dublê. `npm run verificar` passa.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `js/components/upload.js` do protótipo, que guardava só o nome. Os
anexos locais ficam fora do git. A ligação com cada registro chega nas issues
dos módulos.
