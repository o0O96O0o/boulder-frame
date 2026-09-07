# IntersectionObserverEntry 🧪

Source: https://reactnative.dev/docs/global-intersectionobserverentry

Version: 0.87 | Retrieved: 2026-09-07

Canary 🧪

**This API is currently only available in React Native’s Canary and Experimental channels.**

If you want to try it out, please [enable the Canary Channel](release-levels.md) in your app.

The [`IntersectionObserverEntry`](https://developer.mozilla.org/en-US/docs/Web/API/IntersectionObserverEntry) interface, as defined in Web specifications. It describes the intersection between the target element and its root container at a specific moment of transition.

Instances of `IntersectionObserverEntry` are delivered to an [`IntersectionObserver`](global-intersectionobserver.md) callback in its `entries` parameter.

***

# Reference

<a id="instance-properties"></a>

## Instance properties

<a id="boundingclientrect"></a>

### `boundingClientRect`

See [documentation in MDN](https://developer.mozilla.org/en-US/docs/Web/API/IntersectionObserverEntry/boundingClientRect).

Returns the bounds rectangle of the target element as a `DOMRectReadOnly`.

<a id="intersectionratio"></a>

### `intersectionRatio`

See [documentation in MDN](https://developer.mozilla.org/en-US/docs/Web/API/IntersectionObserverEntry/intersectionRatio).

Returns the ratio of the `intersectionRect` to the `boundingClientRect`.

<a id="intersectionrect"></a>

### `intersectionRect`

See [documentation in MDN](https://developer.mozilla.org/en-US/docs/Web/API/IntersectionObserverEntry/intersectionRect).

Returns a `DOMRectReadOnly` representing the target's visible area.

<a id="isintersecting"></a>

### `isIntersecting`

See [documentation in MDN](https://developer.mozilla.org/en-US/docs/Web/API/IntersectionObserverEntry/isIntersecting).

A Boolean value which is `true` if the target element intersects with the intersection observer's root. If this is `true`, then the `IntersectionObserverEntry` describes a transition into a state of intersection; if it's `false`, then you know the transition is from intersecting to not-intersecting.

<a id="rnrootintersectionratio-️"></a>

### `rnRootIntersectionRatio` ⚠️

Non-standard

This is a React Native specific extension.

Returns the ratio of the `intersectionRect` to the `rootBounds`.

TypeScript

```
get rnRootIntersectionRatio(): number;
```

This is analogous to `intersectionRatio`, but computed relative to the root's bounding box instead of the target's bounding box. This corresponds to the `rnRootThreshold` option and allows you to determine what percentage of the root area is covered by the target element.

<a id="rootbounds"></a>

### `rootBounds`

See [documentation in MDN](https://developer.mozilla.org/en-US/docs/Web/API/IntersectionObserverEntry/rootBounds).

Returns a `DOMRectReadOnly` for the intersection observer's root.

<a id="target"></a>

### `target`

See [documentation in MDN](https://developer.mozilla.org/en-US/docs/Web/API/IntersectionObserverEntry/target).

The `Element` whose intersection with the root changed.

<a id="time"></a>

### `time`

See [documentation in MDN](https://developer.mozilla.org/en-US/docs/Web/API/IntersectionObserverEntry/time).

A `DOMHighResTimeStamp` indicating the time at which the intersection was recorded, relative to the `IntersectionObserver`'s time origin.
