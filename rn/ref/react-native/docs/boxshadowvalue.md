# BoxShadowValue Object Type

Source: https://reactnative.dev/docs/boxshadowvalue

Version: 0.87 | Retrieved: 2026-09-07

The `BoxShadowValue` object is taken by the [`boxShadow`](view-style-props.md#boxshadow) style prop. It is comprised of 2-4 lengths, an optional color, and an optional `inset` boolean. These values collectively define the box shadow's color, position, size, and blurriness.

<a id="example"></a>

## Example

JavaScript

```
{

  offsetX: 10,

  offsetY: -3,

  blurRadius: '15px',

  spreadDistance: '10px',

  color: 'red',

  inset: true,

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

<a id="blurradius"></a>

### `blurRadius`

Represents the radius used in the [Gaussian blur](https://en.wikipedia.org/wiki/Gaussian_blur) algorithm. The larger the value the blurrier the shadow is. Only non-negative values are valid. The default is 0.

| Type             | Optional |
| ---------------- | -------- |
| number \| string | Yes      |

<a id="spreaddistance"></a>

### `spreadDistance`

How much larger or smaller the shadow grows or shrinks. A positive value will grow the shadow, a negative value will shrink the shadow.

| Type             | Optional |
| ---------------- | -------- |
| number \| string | Yes      |

<a id="color"></a>

### `color`

The color of the shadow. The default is `black`.

| Type                     | Optional |
| ------------------------ | -------- |
| [color](colors.md) | Yes      |

<a id="inset"></a>

### `inset`

Whether the shadow is inset or not. Inset shadows will appear around the inside of the element's border box as opposed to the outside.

| Type    | Optional |
| ------- | -------- |
| boolean | Yes      |

<a id="used-by"></a>

## Used by

* [`boxShadow`](view-style-props.md#boxshadow)
