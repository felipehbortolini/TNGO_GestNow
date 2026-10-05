# Fontes

## Montserrat — hospedada no modelo

`Montserrat-latin.woff2` · 38 KB · fonte variável

Um único arquivo cobre toda a faixa de pesos (100 a 900). Não há um arquivo por
peso: a fonte tem eixo de peso, e o navegador interpola. Verificado no navegador —
os pesos 400, 600 e 700 rendem larguras distintas a partir do mesmo arquivo.

Subset **latin** (U+0000–00FF mais pontuação e símbolos comuns), que é o que uma
interface em português usa. O subset completo teria várias vezes o tamanho sem
servir para nada aqui.

### Declaração

Em `ds/tokens.css`, no topo:

```css
@font-face {
  font-family: "Montserrat";
  src: url("assets/fonts/Montserrat-latin.woff2") format("woff2");
  font-weight: 100 900;
  font-style: normal;
  font-display: swap;
}
```

`font-weight: 100 900` é a faixa da fonte variável — não um peso fixo.

`font-display: swap` faz o texto aparecer imediatamente na fonte de fallback e
trocar quando a Montserrat chega. Sem isso, os rótulos ficariam invisíveis no
primeiro carregamento.

### Onde aparece

Tudo que usa `var(--font-label)`:

- `.aglutinador` — rótulo de agrupamento
- `.tbl thead th` — cabeçalho de tabela
- `.guard h1` — título de tela de guarda
- `.modal--gen .modal__title` — título de modal
- `.grupo-label` e `.filtro-panel h3`

### Origem e licença

Baixada de `fonts.gstatic.com` em 13/08/2026, o repositório oficial do Google
Fonts. Licença **SIL Open Font License 1.1**, que permite uso comercial,
modificação e redistribuição junto da aplicação.

**Não é servida por CDN.** A Regra 1 do contrato visual proíbe host externo em
`app/`, e o Google Fonts entregaria a fonte de fora — além de vazar o IP de cada
usuário para um terceiro. O arquivo é servido pelo próprio app.

### O problema que isso resolveu

Antes, `--font-label` declarava `"Montserrat", "Segoe UI", sans-serif` **sem
nenhum arquivo de fonte no projeto**. O navegador procurava a Montserrat instalada
no Windows de cada pessoa: designers costumam ter, usuários finais quase nunca.

O mesmo app renderizava tipografias diferentes conforme a máquina, sem erro e sem
aviso. O designer aprovava uma coisa e o usuário via outra.

### Atualizar

Se um dia precisar de outra versão, baixe pelo `css2` do Google Fonts com
User-Agent moderno (para vir `woff2`), pegue a URL do bloco `/* latin */` e
substitua o arquivo. O `@font-face` não muda.

A verificação `recurso-existe` de `scripts/verificar-padrao.mjs` reprova se o
arquivo sumir.
