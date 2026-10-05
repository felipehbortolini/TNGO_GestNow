# Navigation

## SPA navigation — think twice

Putting `x-target` on every link to build a Single Page App introduces state management, history, and accessibility problems. Modern browsers have closed the gap:

| Platform feature | What it solves |
|---|---|
| [Paint Holding](https://developer.chrome.com/blog/paint-holding/) | No white flash between pages |
| [Code caching](https://v8.dev/blog/code-caching) | JS compiled once, reused across pages |
| [Speculation Rules API](https://developer.chrome.com/docs/web-platform/prerender-pages) | Preload next page before click |
| [View Transitions (cross-document)](https://developer.mozilla.org/en-US/docs/Web/CSS/@view-transition) | Animated page transitions |
| [Service Workers](https://github.com/DannyMoerkerke/basic-service-worker) | Offline support, advanced caching |

## Recommendation

Use Alpine AJAX for **specific interactions** (forms, inline edits, validations, filtered lists) rather than full SPA navigation. For page-to-page speed, combine a preloading library like [instant.page](https://instant.page/) with cross-document View Transitions.