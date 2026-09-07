# console

Source: https://reactnative.dev/docs/global-console

Version: 0.87 | Retrieved: 2026-09-07

warning

🚧 This page is work in progress, so please refer to the [MDN documentation](https://developer.mozilla.org/en-US/docs/Web/API/console) for more information.

The global `console` object, as defined in Web specifications.

***

<a id="methods"></a>

## Methods

<a id="timestamp"></a>

### `timeStamp()`

React TSX

```
console.timeStamp(

  label: string,

  start?: string | number,

  end?: string | number,

  trackName?: string,

  trackGroup?: string,

  color?: DevToolsColor

): void;
```

The `console.timeStamp` API allows you to add custom timing entries in the Performance panel timeline.

**Parameters:**

| Name       | Type               | Required | Description                                                                                                                                                                                                                                                                                 |
| ---------- | ------------------ | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| label      | `string`           | Yes      | The label for the timing entry.                                                                                                                                                                                                                                                             |
| start      | `string \| number` | No       | - If string, the name of a previously recorded timestamp with `console.timeStamp`.<br />- If number, the [DOMHighResTimeStamp](https://developer.mozilla.org/en-US/docs/Web/API/DOMHighResTimeStamp). For example, from `performance.now()`.<br />- If undefined, the current time is used. |
| end        | `string \| number` | No       | - If string, the name of a previously recorded timestamp with `console.timeStamp`.<br />- If number, the [DOMHighResTimeStamp](https://developer.mozilla.org/en-US/docs/Web/API/DOMHighResTimeStamp). For example, from `performance.now()`.<br />- If undefined, the current time is used. |
| trackName  | `string`           | No       | The name of the custom track.                                                                                                                                                                                                                                                               |
| trackGroup | `string`           | No       | The name of the track group.                                                                                                                                                                                                                                                                |
| color      | `DevToolsColor`    | No       | The color of the entry.                                                                                                                                                                                                                                                                     |

React TSX

```
type DevToolsColor =

  | 'primary'

  | 'primary-light'

  | 'primary-dark'

  | 'secondary'

  | 'secondary-light'

  | 'secondary-dark'

  | 'tertiary'

  | 'tertiary-light'

  | 'tertiary-dark'

  | 'warning'

  | 'error';
```
