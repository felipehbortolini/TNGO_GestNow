# Pastas por módulo em cada camada

Para que uma alteração fique localizável sem depender de quem conhece o repositório, cada módulo usa o mesmo identificador em `app/_views/`, `app/paginas/`, `api/src/modulos/`, `api/src/templates/` e `api/tests/`. No backend, rotas, fachada, cálculos, validação, exportação e modelos têm arquivos próprios; integrações cruzam módulos apenas pelas fachadas donas.
