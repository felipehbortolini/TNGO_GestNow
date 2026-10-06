# Assets do Design System

Inventário e mapa de migração dos arquivos de `app/ds/assets/`.

---

## Por que os nomes mudaram

Na origem, todos os assets tinham nome UUID (`85be19f1-70be-4141-ada9-….gif`).
Isso trazia três problemas:

1. **Impossível auditar.** Não dava para saber, olhando a pasta, o que era usado
   nem o que cada arquivo representava.
2. **Duplicação silenciosa.** 11 arquivos existiam duas vezes — uma com UUID e
   outra com nome semântico — somando 2,1 MB desnecessários.
3. **Referência opaca no código.** `js/ui.js:77` do piloto fixava
   `assets/85be19f1-….gif` para o overlay de carregamento. Ninguém lia aquilo e
   sabia que era o spinner.

---

## Assets ativos (11)

| Arquivo | UUID de origem | Uso |
|---|---|---|
| `favicon-timenow.png` | `5984a587-a397-40b3-995e-efc41e41411a` | Ícone da aba do navegador |
| `loading-pequeno.gif` | `85be19f1-70be-4141-ada9-4f8ad6d9da4a` | Overlay de carregamento (`TN.loading()`) |
| `loading-pagina.gif` | `c4b39cf5-bf74-408b-b263-d15ea6040db0` | Splash de página inteira |
| `ilustra-acesso-negado.png` | `83fb9e25-23f5-446f-8305-1840a0ded819` | Tela de guarda: sem permissão |
| `ilustra-manutencao.png` | `a0001111-94f6-429c-8981-ff6eeffdb786` | Tela de guarda: em manutenção |
| `ilustra-atualizacao.png` | `e383ae33-4eb5-4718-9d3e-471ea1bab6d2` | Tela de guarda: versão desatualizada |
| `ilustra-em-construcao.png` | `77f474e5-a0a0-46c6-b80a-4241800b0a29` | Tela de guarda: em construção |
| `ilustra-aviso.png` | `6cb10a8b-080b-48be-b55e-8b46c257eda2` | Guarda de saída (`TN.confirmarSaida()`) |
| `ilustra-erro.png` | `78dca531-8928-4df1-bff8-e40600157202` | Estado de erro |
| `ilustra-sucesso.png` | `13235a03-c406-4f37-9849-588f5ddca3fb` | Confirmação de operação |
| `ilustra-salvo.png` | `ab8087c0-667f-45c3-815b-d59e72975325` | Confirmação de gravação |

Conferido por `md5sum`: cada par UUID/semântico era byte a byte idêntico. A
cópia com nome UUID foi descartada; o conteúdo está preservado sob o nome novo.

**Referência sempre por caminho absoluto**, conforme a Regra 1 do contrato
visual:

```html
<img src="/ds/assets/ilustra-erro.png" alt="">
```

---

## Em quarentena (10)

`app/ds/assets/_nao-utilizados/` — **nenhum destes é referenciado por HTML, CSS
ou JS** em nenhuma das três pastas de origem. Verificado por `grep` sobre o UUID.

Ficam preservados porque podem ter uso futuro, mas fora do conjunto ativo para
não poluir a auditoria.

| Arquivo | UUID de origem | Observação |
|---|---|---|
| `ilustra-revisao.png` | `0412ffcf-b6b8-43cf-a4fb-ef27a645a011` | Homem com lupa e visto sobre prancheta |
| `ilustra-arquivamento.png` | `a8288762-1eae-455c-b141-10b998315172` | Mulher guardando documentos em pasta |
| `icone-documento-novo-112.png` | `877eaf61-c28e-4a76-afe6-622dee31b1a4` | Documento com sinal de mais, 112×112 |
| `icone-roxo-24-nao-identificado.png` | `96408c1c-aa88-4e91-a6ab-69b820c78ba1` | 24×24, conteúdo não identificado |
| `icone-pessoa-48.svg` | `1b9e30c6-d85f-4c87-9d5e-bf186799dd5e` | Ícone Fluent, 48×48 |
| `icone-pessoa-24.svg` | `92a1a9b1-6f26-4875-8ffe-b8385e42bcf8` | Ícone Fluent, 24×24 |
| `icone-documento-28.svg` | `29798062-3b1d-4a3f-add8-80d10cca8644` | Ícone Fluent, 28×28 |
| `icone-editar-24.svg` | `41cbdc6e-dfd2-4543-9879-a064bb1a4cf7` | Ícone Fluent, 24×24 |
| `icone-texto-32.svg` | `a116baad-7c7d-4462-9f8f-d3dc4f170e84` | Ícone Fluent, 32×32 |
| `hero-antigo-texto-vetorizado.svg` | `84c87e11-16d7-4aaf-8f96-effdfb077075` | **Descontinuado** — ver abaixo |

### Sobre `hero-antigo-texto-vetorizado.svg`

1600×900, 128 KB, 28 paths e nenhum elemento `<text>`: é título e descrição
convertidos em curvas. Foi removido do hero pelo próprio piloto, com a
justificativa registrada em `Projeto_Piloto/pages/homepage.html:2-4` — sobrepunha
o conteúdo real e recortava palavras conforme a largura da janela.

**Não reintroduzir.** Texto em hero é tipografia, não imagem: acessível a leitor
de tela, selecionável, traduzível e responsivo. O hero atual (`.home__titulo`)
já resolve isso.

---

## Ponto de atenção: verde das ilustrações

As ilustrações usam um verde claro que **não pertence à paleta Timenow** — não é
`--verde-500` (#00A793) nem nenhum tom da rampa. São arte de banco de imagens
adotada como está.

Não é bloqueante, mas significa que uma tela de guarda exibe dois verdes
diferentes: o da marca nos botões e o da ilustração ao lado. Se a consistência
cromática virar prioridade, é preciso recolorir as ilustrações ou encomendar
arte na paleta correta.

---

## Ícones

Ícones de interface **não são arquivos** — são SVG inline gerados por
`app/ds/icons.js`, na função `icon(nome, tamanho, classe)`. São 40+ ícones
Fluent System em viewBox 20×20, traço 1,5.

```js
elemento.innerHTML = icon("checkCircle", 18);
```

Vantagem sobre `<img>`: herdam `currentColor`, então acompanham o estado do
componente sem precisar de variante por cor.

Os SVG em quarentena acima são de tamanhos diferentes (24, 28, 32, 48) e não
seguem esse padrão — por isso não foram incorporados a `icons.js`.
