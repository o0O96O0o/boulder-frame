# DropShadowValue Object Type

Source: https://reactnative.dev/docs/dropshadowvalue

Version: 0.87 | Retrieved: 2026-09-07

The `DropShadowValue` object is taken by the [`filter`](view-style-props.md#filter) style prop for the `dropShadow` function. It is comprised of 2 or 3 lengths and an optional color. These values collectively define the drop shadow's color, position, and blurriness.

<a id="example"></a>

## Example

JavaScript

```
{

  offsetX: 10,

  offsetY: -3,

  standardDeviation: '15px',

  color: 'blue',

}
```

<a id="keys-and-values"></a>

## Keys and values

<a id="offsetx"></a>

### `offsetX`

The offset on the x-axis. This can be positive or negative. A positive value indicates right and negative indicates left.

| Type             | Optional |
| ---------------- | -------- |
| number \| string | No       |

<a id="offsety"></a>

### `offsetY`

The offset on the y-axis. This can be positive or negative. A positive value indicates up and negative indicates down.

| Type             | Optional |
| ---------------- | -------- |
| number \| string | No       |

<a id="standarddeviation"></a>

### `standardDeviation`

Represents the standard deviation used in the [Gaussian blur](https://en.wikipedia.org/wiki/Gaussian_blur) algorithm. The larger the value the blurrier the shadow is. Only non-negative values are valid. The default is 0.

| Type             | Optional |
| ---------------- | -------- |
| number \| string | Yes      |

<a id="color"></a>

### `color`

The color of the shadow. The default is `black`.

| Type                     | Optional |
| ------------------------ | -------- |
| [color](colors.md) | Yes      |

<a id="used-by"></a>

## Used by

* [`filter`](view-style-props.md#filter)
