# Configuration

Set global defaults when registering the plugin:

```js
import ajax from '@imacrayon/alpine-ajax'

Alpine.plugin(ajax.configure({
  headers: { 'X-CSRF-Token': 'token-value' },
  mergeStrategy: 'morph'
}))
```

## Options

| Option | Default | Description |
|---|---|---|
| `headers` | `{}` | Headers included in every AJAX request |
| `mergeStrategy` | `'replace'` | Default merge strategy for all targets (can be overridden per-element with `x-merge`) |