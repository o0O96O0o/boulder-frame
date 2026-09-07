# PressEvent Object Type

Source: https://reactnative.dev/docs/pressevent

Version: 0.87 | Retrieved: 2026-09-07

`PressEvent` object is returned in the callback as a result of user press interaction, for example `onPress` in [Button](button.md) component.

<a id="example"></a>

## Example

JavaScript

```
{

    changedTouches: [PressEvent],

    identifier: 1,

    locationX: 8,

    locationY: 4.5,

    pageX: 24,

    pageY: 49.5,

    target: 1127,

    timestamp: 85131876.58868201,

    touches: []

}
```

<a id="keys-and-values"></a>

## Keys and values

<a id="changedtouches"></a>

### `changedTouches`

Array of all PressEvents that have changed since the last event.

| Type                 | Optional |
| -------------------- | -------- |
| array of PressEvents | No       |

<a id="force-ios"></a>

### `force`iOS

Amount of force used during the 3D Touch press. Returns the float value in range from `0.0` to `1.0`.

| Type   | Optional |
| ------ | -------- |
| number | Yes      |

<a id="identifier"></a>

### `identifier`

Unique numeric identifier assigned to the event.

| Type   | Optional |
| ------ | -------- |
| number | No       |

<a id="locationx"></a>

### `locationX`

Touch origin X coordinate inside touchable area (relative to the element).

| Type   | Optional |
| ------ | -------- |
| number | No       |

<a id="locationy"></a>

### `locationY`

Touch origin Y coordinate inside touchable area (relative to the element).

| Type   | Optional |
| ------ | -------- |
| number | No       |

<a id="pagex"></a>

### `pageX`

Touch origin X coordinate on the screen (relative to the root view).

| Type   | Optional |
| ------ | -------- |
| number | No       |

<a id="pagey"></a>

### `pageY`

Touch origin Y coordinate on the screen (relative to the root view).

| Type   | Optional |
| ------ | -------- |
| number | No       |

<a id="target"></a>

### `target`

The node id of the element receiving the PressEvent.

| Type                        | Optional |
| --------------------------- | -------- |
| number, `null`, `undefined` | No       |

<a id="timestamp"></a>

### `timestamp`

Timestamp value when a PressEvent occurred. Value is represented in milliseconds.

| Type   | Optional |
| ------ | -------- |
| number | No       |

<a id="touches"></a>

### `touches`

Array of all current PressEvents on the screen.

| Type                 | Optional |
| -------------------- | -------- |
| array of PressEvents | No       |

<a id="used-by"></a>

## Used by

* [`Button`](button.md)
* [`PanResponder`](panresponder.md)
* [`Pressable`](pressable.md)
* [`ScrollView`](scrollview.md)
* [`Text`](text.md)
* [`TextInput`](textinput.md)
* [`TouchableHighlight`](touchablenativefeedback.md)
* [`TouchableOpacity`](touchablewithoutfeedback.md)
* [`TouchableNativeFeedback`](touchablenativefeedback.md)
* [`TouchableWithoutFeedback`](touchablewithoutfeedback.md)
* [`View`](view.md)
