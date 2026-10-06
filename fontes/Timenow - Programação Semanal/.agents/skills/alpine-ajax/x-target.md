# x-target

## Basic usage

Add `x-target` to forms or links. The value is the `id` of the target element to replace with the server response.

```html
<ul id="comments">
  <li>Comment #1</li>
</ul>
<form x-target="comments" method="post" action="/comment">
  <input name="text" required />
  <button>Submit</button>
</form>
```

## Multiple targets

Separate IDs with a space:

```html
<form x-target="comments comments_count" method="post" action="/comment">
```

## Target aliases

When page element ID ≠ response element ID, use `page_id:response_id`:

```html
<a x-target="modal_body:page_body">Load modal</a>
<div id="modal_body"></div>
```

`#modal_body` will be replaced with the `#page_body` element from the response.

## Self-targeting (shorthand)

When a form or link targets itself, leave `x-target` blank (the element must still have an `id`):

```html
<form x-target id="star_repo" method="post" action="/repos/1/star">
  <button>Star Repository</button>
</form>
```

Alias shorthand: `x-target=":alias_id"` — the `:` prefix means "target myself with this alias."

## Status-code modifiers

Different targets based on response status:

| Modifier | Triggers on |
|---|---|
| `x-target.422="el"` | 422 status |
| `x-target.4xx="el"` | Any 4xx status |
| `x-target.error="el"` | Any 4xx or 5xx |
| `x-target.back="el"` | Redirect back to same page |
| `x-target.away="el"` | Redirect away to different page |

**Example** — validation errors stay in-page, success does full reload:

```html
<form x-target="login" x-target.away="_top" id="login" method="post" action="/login">
```

**Example** — errors only update the form, success updates both form and list:

```html
<form x-target="todo_list add_todo_form" x-target.back="add_todo_form" id="add_todo_form" method="post" action="/todos">
```

**Redirect note:** The Fetch API follows redirects transparently, so all 3xx modifiers (e.g. `x-target.302`) will capture any 3xx response.

## Special targets

| Keyword | Behavior |
|---|---|
| `_top` | Full page reload |
| `_none` | Do nothing |
| `_self` | _(deprecated)_ Use `x-target.away="_top"` instead |

## Dynamic target names

Use `x-target:dynamic` with a JavaScript expression for dynamically-generated IDs:

```html
<template x-for="comment in comments" :key="comment.id">
  <li :id="'comment_'+comment.id">
    <form x-target:dynamic="'comment_'+comment.id" :action="'/comments/'+comment.id" method="post">
      <button>Edit</button>
    </form>
  </li>
</template>
```

## History & URL

| Modifier | Behavior |
|---|---|
| `x-target.replace` | Replace browser URL without history entry |
| `x-target.push` | Push new history entry (Back button works) |

## Disable AJAX per submit button

Add `formnoajax` to a submit button to force a standard full-page submission:

```html
<form x-target method="post" action="/checkout">
  <button name="procedure" value="increment">Increment</button>
  <button formnoajax name="procedure" value="purchase">Purchase</button>
</form>
```