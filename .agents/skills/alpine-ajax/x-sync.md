# x-sync

Elements with `x-sync` are updated whenever **any** server response contains a matching element, even if they weren't explicitly targeted by `x-target`.

## Usage

The element must have a **unique `id`**. Any element in a server response with a matching `id` replaces the existing `x-sync` element.

```html
<!-- Lives in the base layout, outside the content area -->
<div role="status">
  <ul x-sync id="notifications"></ul>
</div>
```

Every server response that includes `<ul id="notifications">` will replace the existing list.

## Use cases

- Unread message counters
- Notification flashes/toasts
- Shopping cart item counts
- Any UI element that lives in the layout chrome and should update across all requests

## Important

- `$ajax()` does **not** target `x-sync` elements by default. Set `sync: true` in `$ajax` options to enable.
- `x-sync` elements must have a unique `id`.
- The entire element is replaced, not merged. Use `x-merge` on the `x-sync` element if you need a different merge strategy.