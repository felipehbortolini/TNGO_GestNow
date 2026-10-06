# API de leitura — contrato para o consumidor

> Documento para o **analista de dados do cliente**, que vai montar o painel
> dele. Tudo o que está aqui pode ser consumido sem perguntar nada a quem
> escreveu o código — inclusive a primeira consulta.

A Programação Semanal oferece uma API **somente de leitura**, em JSON, para
ferramentas como Power BI, data warehouse ou qualquer sistema que faça
requisição HTTPS. Ela devolve a programação da semana, os indicadores e os
cadastros — **nunca** aceita escrita: criar ou alterar atividade continua
acontecendo só pela tela, com janela, validação e aprovação.

## O que você precisa para começar

1. **Um token de leitura**, emitido pela equipe Timenow na tela Tokens (área
   do operador). O valor completo aparece **uma única vez**, no momento da
   emissão — copie na hora. Depois disso só o prefixo fica visível.
2. **O endereço da aplicação.** A API vive em `/api/dados/v1/`:

   ```
   https://<endereco-da-aplicacao>/api/dados/v1/...
   ```

3. **A credencial** vai no cabeçalho de toda requisição:

   ```
   Authorization: Bearer tn_xxxxxxxx_...
   ```

> **O que o token entrega.** O token é vinculado a **um** ambiente e lê a base
> daquele cliente **inteira** — sem recorte por empresa contratada, porque não
> há pessoa atrás da credencial. Trate o valor como segredo daquela base.

## O envelope

Toda resposta bem-sucedida tem o mesmo formato, para você conferir **de onde e
de quando** é o dado que carregou:

```json
{
  "ambiente": { "id": "mccain01", "projeto": "Projeto McCain", "cliente": "McCain" },
  "gerado_em": "2026-08-26T17:03:00Z",
  "dados": { ... }
}
```

`dados` é o conteúdo do recurso — uma lista ou um objeto, conforme o caso. No
Power BI, expanda o campo `dados` uma vez e siga em frente.

## Os quatro recursos

### 1. `GET /api/dados/v1/saude`

Sonda de conectividade. Não precisa de token — é a primeira chamada para
conferir que o endereço e a liberação da borda funcionam.

```json
{ "status": "ok" }
```

### 2. `GET /api/dados/v1/ambiente`

Identifica o ambiente do token e traz a semana que a aplicação abre por
padrão. Sem filtros.

### 3. `GET /api/dados/v1/atividades`

As atividades de uma semana, com previsto e realizado por dia.

| Parâmetro | Obrigatório? | O que faz |
|---|---|---|
| `semana` | **sim** | A semana no formato `S.30/2026` |
| `empresa` | não | Só atividades daquela empresa contratada |
| `local` | não | Só atividades daquele local |
| `situacao` | não | `em_elaboracao`, `validada` ou `publicada` |

Cada atividade traz: `item`, `id_exclusiva`, `atividade`, `local`, `empresa`,
`encarregado`, `responsavel` (o fiscal), `unidade`, `dias_previsto`
(sete valores), `dias_realizado` (turno dia), `dias_noite` (turno noite),
`situacao`, `aprovacao_realizado`, `ppc` e os totais. **A unidade vem junto de
cada linha** — unidades diferentes não se somam entre si, e o consumidor
precisa saber o que está agregando.

A semana é obrigatória **de propósito**: sem ela, uma chamada puxaria a base
inteira do cliente.

### 4. `GET /api/dados/v1/resumo`

O resumo da semana — os mesmos números que a tela mostra para a mesma semana.

| Parâmetro | Obrigatório? |
|---|---|
| `semana` | **sim** |

Devolve `aderencia`, `ppc_medio`, as faixas de cada um (`alta` ≥ 80%,
`media` 60–79%, `baixa` < 60%), os totais de previsto e realizado, a situação
e as quebras por dia e por empresa.

### 5. `GET /api/dados/v1/cadastros`

Locais, empresas e unidades do ambiente do token — para montar seus próprios
filtros.

## Recusas — o que cada resposta quer dizer

Toda recusa é JSON com um motivo legível no campo `erro`:

| Resposta | Significado | O que fazer |
|---|---|---|
| `401` "Credencial ausente…" | O cabeçalho `Authorization` não veio | Apresente o token como `Bearer …` |
| `401` "Token malformado." | O valor não tem o formato `tn_…` | Confira se copiou o valor inteiro |
| `401` "Token inexistente ou incorreto." | O valor não confere com nenhum token | Copie de novo ou peça outra emissão |
| `401` "Token revogado." | O token foi desligado pela Timenow | Peça a emissão de outro |
| `401` "Token expirado." | A validade definida na emissão passou | Peça a emissão de outro |
| `403` "Este ambiente foi arquivado." | O contrato daquele ambiente foi suspenso | Fale com a Timenow — nada foi apagado |
| `422` "Informe a semana…" | Faltou o parâmetro `semana` obrigatório | Informe `semana=S.30/2026` |

## Versionamento

A versão está no caminho (`v1`), e a regra é simples: **campo novo** nas
respostas não quebra a sua integração e não muda a versão; **remover ou
renomear campo** exige uma versão nova (`v2`), e a antiga continua no ar.

## A primeira consulta, do zero

1. `GET /api/dados/v1/saude` — confere que a borda libera o espaço.
2. `GET /api/dados/v1/ambiente` com o bearer — confere o token e vê o ambiente.
3. `GET /api/dados/v1/atividades?semana=S.30/2026` — traz a semana.
4. Expanda `dados` e monte o painel.

---

### Nota de publicação (quem implanta)

Ao publicar, confira que a entrada anônima de `/api/dados/v1/*` está **acima**
da entrada geral de `/api/*` no array `routes` de
`app/staticwebapp.config.json` — a borda avalia na ordem, e a primeira que
casa vence. Colocada abaixo, o consumidor recebe redirecionamento para o
login em vez de JSON — e isso não aparece em desenvolvimento, porque o
servidor local não aplica esse arquivo.
