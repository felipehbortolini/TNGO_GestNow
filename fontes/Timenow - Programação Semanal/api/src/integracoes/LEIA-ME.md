# Integrações

Ganchos para sistemas externos. Todos **desligados por padrão** e todos
escritos até o ponto em que falta só a credencial — a parte que se perde
entre uma pessoa e outra é o mapa de campos, não o `pip install`.

| Arquivo | O que é | Como liga |
|---|---|---|
| `sharepoint.py` | A porta de persistência sobre listas do SharePoint | `PROGRAMACAO_ORIGEM=sharepoint` |
| `notificacao.py` | Aviso por e-mail via Microsoft Graph | `EMAIL_ATIVO=true` |

---

## SharePoint

Implementa `core.repositorio.Repositorio`, a mesma porta do JSON local.
Ligar não toca em nenhuma tela, blueprint ou regra de domínio:

```powershell
setx PROGRAMACAO_ORIGEM     sharepoint
setx SHAREPOINT_SITE_ID     "contoso.sharepoint.com,<guid>,<guid>"
setx SHAREPOINT_TENANT_ID   "<guid>"
setx SHAREPOINT_CLIENT_ID   "<guid>"
setx SHAREPOINT_CLIENT_SECRET "<segredo>"
```

O mapa de listas e o nome interno de cada coluna já estão no arquivo. Os
sete dias viajam em colunas próprias (`Prev2a`…`PrevDom`) em vez de um JSON
em texto, para a lista continuar filtrável e somável dentro do próprio
SharePoint — que é metade do motivo de usá-lo.

**Falta:** `_token()` e `_chamar()`. Enquanto não existirem, a integração
recusa a operação com uma mensagem que diz o que configurar, em vez de
falhar com 500 no meio da tela.

---

## E-mail

Modo seco por padrão: registra no log o que enviaria e devolve sucesso.
Um gancho de e-mail ligado por acidente manda mensagem para gente de
verdade, e o app roda em demonstração na maior parte do tempo.

`montar_mensagem` já produz o corpo que o Graph espera e é testável sem
rede. Falta o `POST` e a aquisição de token.

**Onde ele entraria:** na facade, depois de `validar_atividade` (avisar o
fornecedor) e depois de `registrar_realizado` (avisar o fiscal). Ficou fora
desta entrega porque avisar automaticamente é decisão de processo, e ela
ainda não foi tomada.

---

## O que saiu, e por quê

Dois ganchos do projeto anterior não vieram:

**Databricks** (`databricks-sql-connector`) — a Programação Semanal não lê
nem escreve no data warehouse. A conexão existia como sobra do template
genérico. Se um dia for preciso publicar a semana para o BI, o caminho é
uma nova implementação de `core.repositorio.Repositorio`, ou um exportador
ao lado — não um cliente SQL solto no meio do domínio.

**Power Automate** — era um caminho alternativo para chegar ao SharePoint,
por fluxos com gatilho HTTP. Com `sharepoint.py` falando Graph direto, os
dois caminhos para o mesmo destino significariam duas versões do mapa de
colunas para manter em sincronia. Se o fluxo for o caminho escolhido, ele
substitui o `_chamar()` de `sharepoint.py` e o mapa continua um só.
