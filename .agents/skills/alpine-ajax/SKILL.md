---
name: alpine-ajax
description: Add AJAX functionality to Alpine.js apps using declarative HTML attributes (x-target, x-merge, x-sync) and the $ajax helper. Use when building Alpine.js frontends that need server-side rendering, form submissions with validation, inline editing, dynamic content updates, loading states, or any HTMX-like pattern with Alpine.js.
---

# Alpine AJAX

## Quick start

Add `x-target` to any form or link to enable AJAX behavior:

```html
<ul id="comments">
  <li>Comment #1</li>
</ul>
<form x-target="comments" method="post" action="/comment">
  <input name="text" required />
  <button>Submit</button>
</form>
```

## Core concepts

**Progressive enhancement first.** Build your UI without AJAX, make it work with standard requests, then sprinkle in Alpine AJAX attributes. This ensures graceful degradation when JS is unavailable.

## Directives reference

| Directive | Purpose | File |
|---|---|---|
| `x-target` | Enable AJAX on forms/links, target elements by ID | [x-target.md](x-target.md) |
| `x-merge` | Control how incoming HTML merges (replace, append, morph, etc.) | [x-merge.md](x-merge.md) |
| `x-sync` | Auto-update elements across any request | [x-sync.md](x-sync.md) |
| `x-autofocus` | Restore keyboard focus after AJAX updates | [x-autofocus.md](x-autofocus.md) |
| `x-headers` | Add custom request headers | [x-headers.md](x-headers.md) |

## Programmatic API

| Feature | Purpose | File |
|---|---|---|
| `$ajax` | Issue AJAX requests from event handlers | [ajax-helper.md](ajax-helper.md) |
| Events | Hook into request lifecycle (`ajax:before`, `ajax:success`, etc.) | [events.md](events.md) |
| Loading states | `aria-busy`, disabled submit buttons during requests | [loading-states.md](loading-states.md) |

## Configuration & tooling

| Topic | File |
|---|---|
| Global defaults (headers, merge strategy) | [configuration.md](configuration.md) |
| SPA vs MPA navigation considerations | [navigation.md](navigation.md) |

## Common patterns

**Form with validation errors (status-code targeting):**
```html
<form x-target="login" x-target.away="_top" id="login" method="post" action="/login">
  <!-- 422 responses render here; success redirects with full page reload -->
</form>
```

**Appending to a list:**
```html
<ul id="messages" x-merge="append">
  <li>First message</li>
</ul>
```

**Programmatic request on input change:**
```html
<div @change="$ajax('/validate', { method: 'post', body: { email } })">
  <input x-model="email" />
</div>
```