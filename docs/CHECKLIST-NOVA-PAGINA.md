# Checklist — página nova

Porta de aceite antes de abrir PR. Leva menos de 5 minutos.

---

## 1. Automático

```bash
node scripts/verificar.mjs
```

Cinco etapas, todas obrigatórias: `ruff check`, `ruff format`, `ty check`,
`eslint` e as verificações do padrão Timenow (inclusive a `trio-da-tela`). Se
falhar, o relatório diz a etapa, o arquivo e o motivo.

Boa parte costuma ser automática:

```bash
node scripts/verificar.mjs --corrigir
```

**Nunca desligue uma regra para o gate passar.** Ver
[PADRAO-DE-CODIGO.md](PADRAO-DE-CODIGO.md), regra de ouro sobre supressão.

---

## 2. Clean code — o que a máquina não pega

O gate já cobriu complexidade, argumentos, código morto e afins. Estes exigem
leitura. Detalhes e exemplos em [CLEAN-CODE.md](CLEAN-CODE.md).

- [ ] Todo nome dispensa comentário ao lado explicando o que é
- [ ] Vocabulário do [CONTEXT.md](../CONTEXT.md) — mesma coisa, mesma palavra
- [ ] Cada função fica num nível de abstração só (nada de regra de negócio
      misturada com montagem de HTML)
- [ ] Nenhuma função muta o que recebeu nem toca no DOM sem anunciar
- [ ] Condição booleana longa virou variável com nome
- [ ] Comentários explicam **por que**, não o quê
- [ ] Nada foi abstraído na segunda ocorrência — só na terceira

## 3. Estrutura

- [ ] A view está em `app/_views/`, e a raiz é `<main id="app-shell" class="content">`
- [ ] O fragmento não tem `<html>`, `<head>`, `<body>`, `<link>`, `<style>` nem `<script src>`
- [ ] A tela foi acrescentada na lista de navegação, `api/src/core/navegacao.json` (módulo, id, título e, se for detalhe, a lista de origem)
- [ ] A tela tem o trio: a view, `app/paginas/<modulo>/<tela>.css` e `.js`, e o shell (`app/index.html`) vincula o CSS e o JS; a verificação `trio-da-tela` confere
- [ ] A raiz da view leva a classe `pagina--<modulo>-<tela>` e aciona `TN.paginas["<modulo>/<tela>"].iniciar($el)` por `x-init`; o CSS é escopado por essa classe
- [ ] O ícone escolhido existe em `app/ds/icons.js`
- [ ] Endpoint novo? Está atrás de `is_alpine_request()` e responde por `AlpineAjaxResponse`
- [ ] Template Jinja2 novo? Estende `base_fragment.html` e usa `{{ target_id }}` — nunca id fixo

---

## 4. Visual

- [ ] Anatomia: `.page` › `.page-head` › conteúdo em `.card`
- [ ] Nenhuma cor, espaçamento, raio ou sombra em valor fixo — tudo por token
- [ ] Nenhuma classe do Tailwind ou do DaisyUI
- [ ] Componente novo virou classe em `ds/patterns.css`, não CSS solto na página
- [ ] Assets referenciados por nome semântico e caminho absoluto (`/ds/assets/...`)

---

## 5. Estados

Toda tela que carrega dados precisa dos cinco. Falta de estado é o defeito mais
comum em revisão.

- [ ] **Carregando** — `.spinner` ou `TN.loading()`
- [ ] **Vazio de origem** — nada cadastrado ainda; `.empty` com ilustração e ação de saída
- [ ] **Vazio por filtro** — busca sem resultado; texto diferente do anterior
- [ ] **Erro** — `.aviso--erro` ou toast; nunca falha em silêncio
- [ ] **Sem permissão** — `.guard` com `ilustra-acesso-negado.png`

---

## 6. Formulário

- [ ] Validação no **servidor**, respondendo 422 com o formulário reexibido
- [ ] Valores digitados voltam preenchidos no 422 — ninguém redigita
- [ ] Erro de campo em `.field__erro`, com `aria-invalid` e `aria-describedby`
- [ ] `<label for="...">` em todo campo
- [ ] Confirmação de ação destrutiva por `TN.confirmarExclusao()`
- [ ] Saída com dados não salvos protegida por `TN.confirmarSaida()`

---

## 7. Acessibilidade

- [ ] Navegação completa só pelo teclado, incluindo abrir e fechar modal
- [ ] Foco visível em todo elemento interativo
- [ ] Contraste mínimo de 4,5:1 no texto (3:1 em texto grande)
- [ ] Imagem decorativa com `alt=""`; imagem informativa com texto real
- [ ] Botão só de ícone tem `aria-label`
- [ ] Item de navegação ativo marcado com `aria-current="page"`
- [ ] Nada depende só de cor para comunicar estado
- [ ] **Cabeçalhos sem pular nível** — `h1` → `h2` → `h3`, sem saltos. O nível é
      semântico e **independe** da classe visual: `.h-card5` pode ser `h2`
- [ ] Diálogo tem nome acessível, por `aria-labelledby` no título ou `aria-label`

Auditoria automatizada, se quiser ir além do olho — baixa o axe-core e roda no
console do navegador:

```bash
npm install axe-core
```

Sirva `node_modules/axe-core/axe.min.js`, injete na página e rode
`axe.run().then(r => console.log(r.violations))`. Repita **com o modal aberto e com
o formulário em erro** — os defeitos deste modelo estavam justamente aí, não na
carga inicial.

---

## 8. Responsivo

- [ ] Testado em 1280px, 1100px e 760px
- [ ] Sem rolagem horizontal; tabela larga dentro de `.tbl-wrap`
- [ ] Ação primária alcançável no celular sem rolar

---

## 9. Na mão

- [ ] Deep link funciona: recarregar direto na URL da página traz a tela certa
- [ ] Navegar para fora e voltar não duplica requisição nem perde estado
- [ ] Console sem erro
- [ ] Aba de rede sem nenhuma requisição a domínio externo
