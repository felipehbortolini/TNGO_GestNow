# Loading States

## Submit button disabling

When a form submission triggers an AJAX request, the form's submit button is **automatically disabled** until the response arrives. This prevents double-submissions.

## `aria-busy`

During an AJAX request, `aria-busy="true"` is set on all target elements. Use this in CSS for loading indicators:

```css
[aria-busy="true"] {
  opacity: 0.5;
  pointer-events: none;
}
```

Or show a spinner:

```css
[aria-busy="true"]::after {
  content: "";
  /* spinner styles */
}
```

Both mechanisms are automatic — no additional attributes needed.