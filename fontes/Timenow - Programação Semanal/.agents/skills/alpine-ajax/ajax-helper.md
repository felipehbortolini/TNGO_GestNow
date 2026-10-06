# $ajax — Programmatic helper

Use `$ajax` for fine-grained AJAX control from event handlers:

```html
<div id="email_field" @change="$ajax('/validate-email', {
  method: 'post',
  body: { email },
})">
  <input type="email" x-model="email" />
</div>
```

## Options

| Option | Default | Description |
|---|---|---|
| `method` | `'GET'` | Request method |
| `target` | `''` | Target element ID |
| `targets` | `[]` | Array of target IDs (overrides `target` if non-empty) |
| `body` | `{}` | Request body |
| `focus` | `false` | Set to `true` to enable `x-autofocus` / `autofocus` behavior |
| `sync` | `false` | Set to `true` to include `x-sync` targets |
| `headers` | `{}` | Additional request headers |

## Notes

- `$ajax` does **not** target `x-sync` elements or autofocus by default — set `sync: true` or `focus: true` to enable.
- `$ajax` is designed for side effects (event listeners, `x-effect`, etc.), not for inline template expressions.