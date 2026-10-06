# Publicação da Entrega 1 — primeiro SSO real

Roteiro da ISSUE-010 (`docs/tasks/multi-ambiente/010-primeira-publicacao-com-sso-real.md`).
É a primeira vez que a aplicação recebe um principal de verdade — o risco aceito
nº 1 da spec. Cada passo abaixo existe para separar uma causa da outra; registre
o resultado de cada um, **na ordem**.

> Decisões humanas da implantação (registradas em 26/08/2026):
>
> - **Operadores:** `felipe.bortolini@timenow.com.br;leonardo.gomes@timenow.com.br`
> - **Ambiente 1:** `mccain01` — Projeto McCain · McCain
> - **Ambiente 2:** `suzano01` — Suzano RangX · Aracruz

---

## 0. Configuração da implantação

No Static Web App (Function app), definir:

| Variável | Valor |
|---|---|
| `PROGRAMACAO_MODO` | `producao` |
| `PROGRAMACAO_OPERADORES` | `felipe.bortolini@timenow.com.br;leonardo.gomes@timenow.com.br` |
| `PROGRAMACAO_ORIGEM` | `json` |

Criar os dois ambientes pelo comando de administração — os mesmos caminhos que
a tela da Entrega 2 vai usar:

```
python scripts/ambiente.py criar --id mccain01 --projeto "Projeto McCain" \
    --cliente "McCain" --ator felipe.bortolini@timenow.com.br
python scripts/ambiente.py criar --id suzano01 --projeto "Suzano RangX" \
    --cliente "Aracruz" --ator felipe.bortolini@timenow.com.br
```

Conceder os membros de cada ambiente (um `conceder` por e-mail).

**Resultado:** _a preencher_

---

## 1. A sessão existe

`GET /.auth/me` responde com `clientPrincipal`.

**Resultado:** _a preencher_

## 2. A guarda nomeia o e-mail recebido

Entrar com uma conta que não está em ambiente nenhum. A tela de recusa (ou o
seletor com a mensagem) nomeia o e-mail que o Azure entregou. Se vier vazio ou
como UPN, a reivindicação é outra e a leitura em `auth._principal` precisa de
ajuste — este é o passo que a decisão 19 existe para tornar barato.

**Resultado:** _a preencher_

## 3. O e-mail casa com o membro do registro

O e-mail nomeado acima confere com o cadastrado no registro de ambientes (a
primeira camada). Se divergir, é caso de nome de conta diferente do e-mail.

**Resultado:** _a preencher_

## 4. A pessoa entra no ambiente

Escolhe a caixa, o cookie grava e a aplicação abre apontada para a base certa —
a segunda camada (cadastro de colaboradores) aprova com o perfil certo.

**Resultado:** _a preencher_

## 5. O cookie sobrevive no domínio publicado

Recarregar a página, abrir aba nova e abrir link direto mantêm o ambiente;
`Secure` vale no domínio publicado (https). Fechar o navegador pede a escolha de
novo.

**Resultado:** _a preencher_

## 6. Downloads e relatório trazem o dado do ambiente ativo

A planilha, o modelo e o relatório para impressão trazem nome e dado do
ambiente em que foram abertos.

**Resultado:** _a preencher_

---

## Teste final de isolamento

Duas pessoas reais, uma em cada ambiente, abrem matriz, dashboard, cadastros,
colaboradores e governança — nenhuma tela de uma mostra dado da outra. Um
operador entra nos dois.

**Resultado:** _a preencher_
