# Events

Hook into the AJAX request lifecycle:

| Event | When | Cancelable |
|---|---|---|
| `ajax:before` | Before request is made | Yes — `$event.preventDefault()` aborts |
| `ajax:send` | Request is issued. `$event.detail` has options; modify to override `fetch` | No |
| `ajax:redirect` | 3xx response. `$event.detail` has response data | No |
| `ajax:success` | 2xx or 3xx response | No |
| `ajax:error` | 4xx or 5xx response | No |
| `ajax:sent` | After any response received | No |
| `ajax:missing` | Target not found in response body | Yes — `$event.preventDefault()` overrides default |
| `ajax:merge` | Content being merged into `$event.target`. `$event.detail` has `response`, `content`, `merge()` | Yes — `$event.preventDefault()` skips merge |
| `ajax:merged` | After content merged | No |
| `ajax:after` | After all merging settled. `$event.target` has `response` and `render[]` | No |

## Examples

**Abort on cancel:**
```html
<form x-target @ajax:before="confirm('Sure?') || $event.preventDefault()">
  <button>Delete</button>
</form>
```

**Modify request options:**
```html
<form @ajax:send="$event.detail.headers['X-Custom'] = 'value'">
```

**Prefer Server Events:** For triggering actions based on response content, [server-dispatched events](https://alpine-ajax.js.org/examples/server-events/) are often cleaner than `ajax:success` / `ajax:error`.