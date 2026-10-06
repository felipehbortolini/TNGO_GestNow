# x-headers

Add custom request headers to AJAX requests:

```html
<form method="post" action="/comments" x-target="comments" x-headers="{'Custom-Header': 'Shmow-zow!'}">
```

## Default headers

Alpine AJAX automatically adds two headers to every request:

| Header | Value |
|---|---|
| `X-Alpine-Request` | `true` |
| `X-Alpine-Target` | Space-separated list of target IDs |

The example above sends:
```
X-Alpine-Request: true
X-Alpine-Target: comments
Custom-Header: Shmow-zow!
```

Use these on the server to detect AJAX requests and conditionally render partials vs full layouts.