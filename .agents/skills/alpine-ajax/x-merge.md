# x-merge

Controls how incoming HTML merges into the target element. Add `x-merge` to the **targeted element** (the one being replaced).

## Merge strategies

| Strategy | Behavior |
|---|---|
| `replace` | **(Default)** Replace target with incoming element |
| `update` | Replace target's inner content only |
| `prepend` | Insert incoming content at start of target |
| `append` | Insert incoming content at end of target |
| `before` | Insert incoming element before target |
| `after` | Insert incoming element after target |
| `morph` | Use Alpine Morph Plugin for fine-grained DOM diffing |

**Example** — appending to a list:

```html
<ul id="messages" x-merge="append">
  <li>First message</li>
</ul>
```

Server responds with `<ul id="messages"><li>Second message</li></ul>`. Result:

```html
<ul id="messages" x-merge="append">
  <li>First message</li>
  <li>Second message</li>
</ul>
```

## Morphing

Install the Alpine Morph Plugin **before** Alpine AJAX:

**CDN:**
```html
<script defer src="https://cdn.jsdelivr.net/npm/@alpinejs/morph@3.14.1/dist/cdn.min.js"></script>
<script defer src="https://cdn.jsdelivr.net/npm/@imacrayon/alpine-ajax@0.12.7/dist/cdn.min.js"></script>
<script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.14.1/dist/cdn.min.js"></script>
```

**NPM:**
```js
import Alpine from 'alpinejs'
import morph from '@alpinejs/morph'
import ajax from '@imacrayon/alpine-ajax'

Alpine.plugin(morph)
Alpine.plugin(ajax)
```

Then use `x-merge="morph"` to morph changes instead of replacing. Morphing preserves DOM state (focus, selection, etc.) when the structure is similar enough.

## View transitions & animations

Add `x-merge.transition` to animate DOM changes via the [View Transitions API](https://developer.mozilla.org/en-US/docs/Web/API/View_Transitions_API) (Chrome-only, graceful fallback elsewhere):

```html
<ul id="messages" x-merge="append" x-merge.transition>
```

Customize animations via CSS — see [Chrome's View Transitions docs](https://developer.chrome.com/docs/web-platform/view-transitions/#simple-customization).

## Global default

Set the default merge strategy globally via configuration:
```js
Alpine.plugin(ajax.configure({ mergeStrategy: 'morph' }))
```