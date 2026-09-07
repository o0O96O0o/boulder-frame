# performance

Source: https://reactnative.dev/docs/global-performance

Version: 0.87 | Retrieved: 2026-09-07

The global [`performance`](https://developer.mozilla.org/en-US/docs/Web/API/Window/performance) object, as defined in Web specifications.

***

# Reference

<a id="instance-properties"></a>

## Instance properties

<a id="eventcounts"></a>

### `eventCounts`

See [documentation in MDN](https://developer.mozilla.org/en-US/docs/Web/API/Performance/eventCounts).

<a id="memory"></a>

### `memory`

See [documentation in MDN](https://developer.mozilla.org/en-US/docs/Web/API/Performance/memory).

<a id="rnstartuptiming-️"></a>

### `rnStartupTiming` ⚠️

Non-standard

This is a React Native specific extension.

Provides information about the startup time of the application.

TypeScript

```
get rnStartupTiming(): ReactNativeStartupTiming;
```

The `ReactNativeStartupTiming` interface provides the following fields:

| Name                                     | Type           | Description                                               |
| ---------------------------------------- | -------------- | --------------------------------------------------------- |
| `startTime`                              | number \| void | When the React Native runtime initialization was started. |
| `executeJavaScriptBundleEntryPointStart` | number \| void | When the execution of the application bundle was started. |
| `endTime`                                | number \| void | When the React Native runtime was fully initialized.      |

<a id="timeorigin"></a>

### `timeOrigin`

Partial support

Provides the number of milliseconds from the UNIX epoch until system boot, instead of the number of milliseconds from the UNIX epoch until app startup.

See [documentation in MDN](https://developer.mozilla.org/en-US/docs/Web/API/Performance/timeOrigin).

<a id="instance-methods"></a>

## Instance methods

<a id="clearmarks"></a>

### `clearMarks()`

See [documentation in MDN](https://developer.mozilla.org/en-US/docs/Web/API/Performance/clearMarks).

<a id="clearmeasures"></a>

### `clearMeasures()`

See [documentation in MDN](https://developer.mozilla.org/en-US/docs/Web/API/Performance/clearMeasures).

<a id="getentries"></a>

### `getEntries()`

See [documentation in MDN](https://developer.mozilla.org/en-US/docs/Web/API/Performance/getEntries).

<a id="getentriesbyname"></a>

### `getEntriesByName()`

See [documentation in MDN](https://developer.mozilla.org/en-US/docs/Web/API/Performance/getEntriesByName).

<a id="getentriesbytype"></a>

### `getEntriesByType()`

See [documentation in MDN](https://developer.mozilla.org/en-US/docs/Web/API/Performance/getEntriesByType).

<a id="mark"></a>

### `mark()`

See [documentation in MDN](https://developer.mozilla.org/en-US/docs/Web/API/Performance/mark).

<a id="measure"></a>

### `measure()`

See [documentation in MDN](https://developer.mozilla.org/en-US/docs/Web/API/Performance/measure).

<a id="now"></a>

### `now()`

Partial support

Provides the number of milliseconds from system boot, instead of the number of milliseconds from app startup.

See [documentation in MDN](https://developer.mozilla.org/en-US/docs/Web/API/Performance/now).
