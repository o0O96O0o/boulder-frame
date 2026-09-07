# TargetEvent Object Type

Source: https://reactnative.dev/docs/targetevent

Version: 0.87 | Retrieved: 2026-09-07

`TargetEvent` object is returned in the callback as a result of focus change, for example `onFocus` or `onBlur` in the [TextInput](textinput.md) component.

<a id="example"></a>

## Example

```
{

    target: 1127

}
```

<a id="keys-and-values"></a>

## Keys and values

<a id="target"></a>

### `target`

The node id of the element receiving the TargetEvent.

| Type                        | Optional |
| --------------------------- | -------- |
| number, `null`, `undefined` | No       |

<a id="used-by"></a>

## Used by

* [`TextInput`](textinput.md)
* [`TouchableWithoutFeedback`](touchablewithoutfeedback.md)
