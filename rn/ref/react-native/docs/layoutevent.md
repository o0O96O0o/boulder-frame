# LayoutEvent Object Type

Source: https://reactnative.dev/docs/layoutevent

Version: 0.87 | Retrieved: 2026-09-07

`LayoutEvent` object is returned in the callback as a result of component layout change, for example `onLayout` in [View](view.md) component.

<a id="example"></a>

## Example

JavaScript

```
{

    layout: {

        width: 520,

        height: 70.5,

        x: 0,

        y: 42.5

    },

    target: 1127

}
```

<a id="keys-and-values"></a>

## Keys and values

<a id="height"></a>

### `height`

Height of the component after the layout changes.

| Type   | Optional |
| ------ | -------- |
| number | No       |

<a id="width"></a>

### `width`

Width of the component after the layout changes.

| Type   | Optional |
| ------ | -------- |
| number | No       |

<a id="x"></a>

### `x`

Component X coordinate inside the parent component.

| Type   | Optional |
| ------ | -------- |
| number | No       |

<a id="y"></a>

### `y`

Component Y coordinate inside the parent component.

| Type   | Optional |
| ------ | -------- |
| number | No       |

<a id="target"></a>

### `target`

The node id of the element receiving the LayoutEvent.

| Type                        | Optional |
| --------------------------- | -------- |
| number, `null`, `undefined` | No       |

<a id="used-by"></a>

## Used by

* [`Image`](image.md)
* [`Pressable`](pressable.md)
* [`ScrollView`](scrollview.md)
* [`Text`](text.md)
* [`TextInput`](textinput.md)
* [`TouchableWithoutFeedback`](touchablewithoutfeedback.md)
* [`View`](view.md)
