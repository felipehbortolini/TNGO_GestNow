# x-autofocus

Controls keyboard focus after AJAX content changes. Essential for accessibility and meaningful focus order.

## Basic usage

```html
<input type="email" name="email" x-autofocus />
```

This input steals focus whenever it's inserted into the page by Alpine AJAX.

## Standard `autofocus` attribute

Alpine AJAX also respects the native `autofocus` attribute. If both `x-autofocus` and `autofocus` are present, `x-autofocus` wins.

## Disabling autofocus

Use the `nofocus` modifier on `x-target` to suppress autofocus behavior (useful when a third-party component manages focus):

```html
<a href="/preview/1" x-target.nofocus="dialog_content" @ajax:before="$dispatch('dialog:open')">Open</a>
```

## Morph vs autofocus

`x-merge="morph"` can preserve focus naturally by reusing existing DOM nodes. However, when the DOM changes significantly, morph may not reliably preserve focus — `x-autofocus` is more predictable in those cases.