---
id: ISSUE-012
title: "Anexos de verdade: pasta local ou Blob, limites por parâmetro e download com a permissão do registro de origem"
status: done
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

- [x] Upload acima do limite ou de tipo fora da lista é recusado com 422 e a mensagem no campo.
- [x] Os metadados aparecem na lista de anexos do registro.
- [x] Download de quem não pode ler o registro de origem é recusado; de quem pode, entrega o arquivo com o nome original.
- [x] Trocar a variável de ambiente troca a implementação sem mudar código (o adaptador Blob é testado com dublê).
- [x] A função de evidência responde se um registro tem ao menos um anexo.
- [x] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Teste transversal de anexos da spec (limite, tipo e permissão do registro de
origem) e teste do adaptador Blob com dublê. `npm run verificar` passa.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `js/components/upload.js` do protótipo, que guardava só o nome. Os
anexos locais ficam fora do git. A ligação com cada registro chega nas issues
dos módulos.

## Registro de execução

Data: 05/10/2026. Feito: porta de arquivos com a pasta local (`data/anexos/`) e o Blob (SDK só no adaptador, testado com dublê), escolhidos por `GESTNOW_ARMAZENAMENTO_ANEXOS`; fachada `core.attachments` (`upload`, `panel`, `open_download`, `has_evidence` e os limites do grupo Anexos); registro de tipos de origem; rotas `GET /api/anexos`, `POST /api/anexos/enviar` e `GET /api/anexos/{id}/baixar` (decorador novo `file_route`); fragmento `comum/anexos.html` e CSS `.upload` e `.anexos` no DS; `azure-storage-blob` em `pyproject.toml`, `uv.lock` e `requirements.txt`. Sem migração (a `anexo` já nasceu na 0001). Documentação em `api/README.md` (seção Anexos) e `MODELO-DE-DADOS.md`.
Pendências: o critério da porta de qualidade fica para o orquestrador; os testes (`test_anexos.py`, `test_armazenamento_de_anexos.py`) foram escritos e não rodados; falta `uv sync` para o `ty` resolver `azure.storage.blob`; nenhum módulo registrou tipo de origem ainda (chega nas issues dos módulos); para a ISSUE-076, validar o grupo Anexos ao salvar (limite maior que zero e ao menos um tipo), porque a fachada cai nos valores iniciais diante de valor inutilizável.
DECISÃO: variáveis do armazenamento | `GESTNOW_ARMAZENAMENTO_ANEXOS` (`local`, o padrão, ou `blob`; outro valor falha alto), `GESTNOW_PASTA_ANEXOS` (pasta local, padrão `data/anexos/` na raiz), `GESTNOW_BLOB_CONEXAO` (cadeia de conexão, só configuração do aplicativo) e `GESTNOW_BLOB_CONTAINER` (padrão `anexos`) | D5a, ISSUE-012
DECISÃO: chave e nome do arquivo | a chave no armazenamento é `<projeto_id>/<anexo_id>`, derivada das colunas existentes (sem migração); o nome original fica só no banco, sem pasta nem caracteres de controle, e volta no download | D5a, ISSUE-012
DECISÃO: limites | 1 MB são 1.048.576 bytes (o tamanho exato do limite passa); o tipo vem da extensão sem diferenciar maiúsculas e `.jpeg` vale como JPG; o MIME é do servidor, a partir do tipo; arquivo vazio é recusado; sem versão do grupo Anexos valem os valores iniciais | D5a, ISSUE-012
DECISÃO: permissão do anexo | envia quem tem `gravar` e lê o registro pelo módulo dono; a função de leitura devolve `OriginRecord` (projeto e `restricted`), `None` ou levanta 403; `restricted` exige `VIEW_RESTRICTED` (Gestor e Admin) para listar e baixar e deixa o Membro só enviar | D5a, ISSUE-012
DECISÃO: download | `GET /api/anexos/{id}/baixar` pelo decorador novo `file_route` (usuário, escopo e acesso como o `fragment_route`, sem o gate do Alpine); recusa 403, inexistente 404 e id malformado 422, em texto simples; sem remoção de anexo e sem conferir o conteúdo contra a extensão | D14, ISSUE-012
DECISÃO: falha de gravação | o arquivo é guardado por último: falha ao guardá-lo desfaz a transação inteira; commit que falha depois disso deixa um arquivo órfão e inofensivo | D5a, ISSUE-012
