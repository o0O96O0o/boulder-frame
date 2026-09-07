# PerformanceObserver

Source: https://reactnative.dev/docs/global-PerformanceObserver

Version: 0.87 | Retrieved: 2026-09-07

The global [`PerformanceObserver`](https://developer.mozilla.org/en-US/docs/Web/API/PerformanceObserver) class, as defined in Web specifications.

<a id="example"></a>

## Example

TypeScript

```
const observer = new PerformanceObserver(

  (list, observer, options) => {

    for (const entry of list.getEntries()) {

      console.log(

        'Received entry with type',

        entry.entryType,

        'and name',

        entry.name,

        'that started at',

        entry.startTime,

        'and took',

        entry.duration,

        'ms',

      );

    }

  },

);

observer.observe({entryTypes: ['mark', 'measure']});
```

***

# Reference

<a id="constructor"></a>

## Constructor

<a id="performanceobserver"></a>

### `PerformanceObserver()`

See [documentation in MDN](https://developer.mozilla.org/en-US/docs/Web/API/PerformanceObserver/PerformanceObserver).

<a id="static-properties"></a>

## Static properties

<a id="supportedentrytypes"></a>

### `supportedEntryTypes`

See [documentation in MDN](https://developer.mozilla.org/en-US/docs/Web/API/PerformanceObserver/supportedEntryTypes).

Returns `['mark', 'measure', 'event', 'longtask', 'resource']`.

<a id="instance-methods"></a>

## Instance methods

<a id="observe"></a>

### `observe()`

See [documentation in MDN](https://developer.mozilla.org/en-US/docs/Web/API/PerformanceObserver/observe).

<a id="disconnect"></a>

### `disconnect()`

See [documentation in MDN](https://developer.mozilla.org/en-US/docs/Web/API/PerformanceObserver/disconnect).
