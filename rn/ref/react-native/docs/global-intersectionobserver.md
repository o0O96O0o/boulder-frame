# IntersectionObserver 🧪

Source: https://reactnative.dev/docs/global-intersectionobserver

Version: 0.87 | Retrieved: 2026-09-07

Canary 🧪

**This API is currently only available in React Native’s Canary and Experimental channels.**

If you want to try it out, please [enable the Canary Channel](release-levels.md) in your app.

The global [`IntersectionObserver`](https://developer.mozilla.org/en-US/docs/Web/API/IntersectionObserver) interface, as defined in Web specifications. It provides a way to asynchronously observe changes in the intersection of a target element with an ancestor element or with a top-level document's viewport.

***

# Reference

<a id="constructor"></a>

## Constructor

<a id="intersectionobserver"></a>

### `IntersectionObserver()`

See [documentation in MDN](https://developer.mozilla.org/en-US/docs/Web/API/IntersectionObserver/IntersectionObserver).

Creates a new `IntersectionObserver` object which will execute a specified callback function when it detects that a target element's visibility has crossed one or more `threshold` or `rnRootThreshold` values.

TypeScript

```
new IntersectionObserver(callback, options?)
```

<a id="parameters"></a>

#### Parameters

**`callback`**

A function which is called when the percentage of the target element is visible crosses a threshold. The callback receives two parameters:

* `entries`: An array of [`IntersectionObserverEntry`](global-intersectionobserverentry.md) objects, each representing one threshold which was crossed, either becoming more or less visible than the percentage specified by that threshold.
* `observer`: The `IntersectionObserver` instance which invoked the callback.

**`options`** (optional)

An optional object with the following properties:

| Name                 | Type                                      | Description                                                                                                                                                                                                       |
| -------------------- | ----------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `root`               | [Element](element-nodes.md) \| null | An element that is an ancestor of the target, whose bounding rectangle will be considered the viewport. Defaults to the root viewport if not specified or if `null`.                                              |
| `rootMargin`         | string                                    | A string which specifies a set of offsets to add to the root's bounding box when calculating intersections. Defaults to `"0px 0px 0px 0px"`.                                                                      |
| `threshold`          | number \| number\[]                       | Either a single number or an array of numbers between 0.0 and 1.0, specifying a ratio of intersection area to total bounding box area for the observed target. Defaults to `[0]` if `rnRootThreshold` is not set. |
| `rnRootThreshold` ⚠️ | number \| number\[]                       | **React Native specific.** Either a single number or an array of numbers between 0.0 and 1.0, specifying a ratio of intersection area to the total root area.                                                     |

<a id="instance-properties"></a>

## Instance properties

<a id="root"></a>

### `root`

See [documentation in MDN](https://developer.mozilla.org/en-US/docs/Web/API/IntersectionObserver/root).

The element or document whose bounds are used as the bounding box when testing for intersection.

<a id="rootmargin"></a>

### `rootMargin`

See [documentation in MDN](https://developer.mozilla.org/en-US/docs/Web/API/IntersectionObserver/rootMargin).

An offset rectangle applied to the root's bounding box when calculating intersections.

<a id="rnrootthresholds-️"></a>

### `rnRootThresholds` ⚠️

Non-standard

This is a React Native specific extension.

A list of root thresholds, sorted in increasing numeric order, where each threshold is a ratio of intersection area to bounding box area of the specified root view, which defaults to the viewport.

Notifications for a target are generated when any of the thresholds specified in `rnRootThresholds` or `thresholds` are crossed for that target.

TypeScript

```
get rnRootThresholds(): ReadonlyArray<number> | null;
```

<a id="thresholds"></a>

### `thresholds`

See [documentation in MDN](https://developer.mozilla.org/en-US/docs/Web/API/IntersectionObserver/thresholds).

A list of thresholds, sorted in increasing numeric order, where each threshold is a ratio of intersection area to bounding box area of an observed target.

Notifications for a target are generated when any of the thresholds specified in `rnRootThresholds` or `thresholds` are crossed for that target.

<a id="instance-methods"></a>

## Instance methods

<a id="disconnect"></a>

### `disconnect()`

See [documentation in MDN](https://developer.mozilla.org/en-US/docs/Web/API/IntersectionObserver/disconnect).

Stops the `IntersectionObserver` object from observing any target.

<a id="observe"></a>

### `observe()`

See [documentation in MDN](https://developer.mozilla.org/en-US/docs/Web/API/IntersectionObserver/observe).

Tells the `IntersectionObserver` to begin observing a target element.

<a id="takerecords"></a>

### `takeRecords()`

See [documentation in MDN](https://developer.mozilla.org/en-US/docs/Web/API/IntersectionObserver/takeRecords).

Returns an array of `IntersectionObserverEntry` objects for all observed targets.

<a id="unobserve"></a>

### `unobserve()`

See [documentation in MDN](https://developer.mozilla.org/en-US/docs/Web/API/IntersectionObserver/unobserve).

Tells the `IntersectionObserver` to stop observing a particular target element.
