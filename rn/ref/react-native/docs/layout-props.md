# Layout Props

Source: https://reactnative.dev/docs/layout-props

Version: 0.87 | Retrieved: 2026-09-07

info

More detailed examples about those properties can be found on the [Layout with Flexbox](flexbox.md) page.

<a id="example"></a>

### Example

The following example shows how different properties can affect or shape a React Native layout. You can try for example to add or remove squares from the UI while changing the values of the property `flexWrap`.

* TypeScript
* JavaScript

***

# Reference

<a id="props"></a>

## Props

<a id="aligncontent"></a>

### `alignContent`

`alignContent` controls how rows align in the cross direction, overriding the `alignContent` of the parent.

See [MDN CSS Reference](https://developer.mozilla.org/en-US/docs/Web/CSS/align-content) for more details.

| Type                                                                                                 | Required |
| ---------------------------------------------------------------------------------------------------- | -------- |
| enum('flex-start', 'flex-end', 'center', 'stretch', 'space-between', 'space-around', 'space-evenly') | No       |

***

<a id="alignitems"></a>

### `alignItems`

`alignItems` aligns children in the cross direction. For example, if children are flowing vertically, `alignItems` controls how they align horizontally. It works like `align-items` in CSS (default: stretch).

See [MDN CSS Reference](https://developer.mozilla.org/en-US/docs/Web/CSS/align-items) for more details.

| Type                                                            | Required |
| --------------------------------------------------------------- | -------- |
| enum('flex-start', 'flex-end', 'center', 'stretch', 'baseline') | No       |

***

<a id="alignself"></a>

### `alignSelf`

`alignSelf` controls how a child aligns in the cross direction, overriding the `alignItems` of the parent. It works like `align-self` in CSS (default: auto).

See [MDN CSS Reference](https://developer.mozilla.org/en-US/docs/Web/CSS/align-self) for more details.

| Type                                                                    | Required |
| ----------------------------------------------------------------------- | -------- |
| enum('auto', 'flex-start', 'flex-end', 'center', 'stretch', 'baseline') | No       |

***

<a id="aspectratio"></a>

### `aspectRatio`

Aspect ratio controls the size of the undefined dimension of a node.

* On a node with a set width/height, aspect ratio controls the size of the unset dimension
* On a node with a set flex basis, aspect ratio controls the size of the node in the cross axis if unset
* On a node with a measure function, aspect ratio works as though the measure function measures the flex basis
* On a node with flex grow/shrink, aspect ratio controls the size of the node in the cross axis if unset
* Aspect ratio takes min/max dimensions into account

See [MDN CSS Reference](https://developer.mozilla.org/en-US/docs/Web/CSS/aspect-ratio) for more details.

| Type           | Required |
| -------------- | -------- |
| number, string | No       |

***

<a id="borderbottomwidth"></a>

### `borderBottomWidth`

`borderBottomWidth` works like `border-bottom-width` in CSS.

See [MDN CSS Reference](https://developer.mozilla.org/en-US/docs/Web/CSS/border-bottom-width) for more details.

| Type   | Required |
| ------ | -------- |
| number | No       |

***

<a id="borderendwidth"></a>

### `borderEndWidth`

When direction is `ltr`, `borderEndWidth` is equivalent to `borderRightWidth`. When direction is `rtl`, `borderEndWidth` is equivalent to `borderLeftWidth`.

| Type   | Required |
| ------ | -------- |
| number | No       |

***

<a id="borderleftwidth"></a>

### `borderLeftWidth`

`borderLeftWidth` works like `border-left-width` in CSS.

See [MDN CSS Reference](https://developer.mozilla.org/en-US/docs/Web/CSS/border-left-width) for more details.

| Type   | Required |
| ------ | -------- |
| number | No       |

***

<a id="borderrightwidth"></a>

### `borderRightWidth`

`borderRightWidth` works like `border-right-width` in CSS.

See [MDN CSS Reference](https://developer.mozilla.org/en-US/docs/Web/CSS/border-right-width) for more details.

| Type   | Required |
| ------ | -------- |
| number | No       |

***

<a id="borderstartwidth"></a>

### `borderStartWidth`

When direction is `ltr`, `borderStartWidth` is equivalent to `borderLeftWidth`. When direction is `rtl`, `borderStartWidth` is equivalent to `borderRightWidth`.

| Type   | Required |
| ------ | -------- |
| number | No       |

***

<a id="bordertopwidth"></a>

### `borderTopWidth`

`borderTopWidth` works like `border-top-width` in CSS.

See [MDN CSS Reference](https://developer.mozilla.org/en-US/docs/Web/CSS/border-top-width) for more details.

| Type   | Required |
| ------ | -------- |
| number | No       |

***

<a id="borderwidth"></a>

### `borderWidth`

`borderWidth` works like `border-width` in CSS.

See [MDN CSS Reference](https://developer.mozilla.org/en-US/docs/Web/CSS/border-width) for more details.

| Type   | Required |
| ------ | -------- |
| number | No       |

***

<a id="bottom"></a>

### `bottom`

`bottom` is the number of logical pixels to offset the bottom edge of this component.

It works similarly to `bottom` in CSS, but in React Native you must use points or percentages. Ems and other units are not supported.

See [MDN CSS Reference](https://developer.mozilla.org/en-US/docs/Web/CSS/bottom) for more details of how `bottom` affects layout.

| Type           | Required |
| -------------- | -------- |
| number, string | No       |

***

<a id="boxsizing"></a>

### `boxSizing`

`boxSizing` defines how the element's various sizing props (`width`, `height`, `minWidth`, `minHeight`, etc.) are computed. If `boxSizing` is `border-box`, these sizes apply to the border box of the element. If it is `content-box`, they apply to the content box of the element. The default value is `border-box`. The [web documentation](https://developer.mozilla.org/en-US/docs/Web/CSS/box-sizing) is a good source of information if you wish to learn more about how this prop works.

| Type                              | Required |
| --------------------------------- | -------- |
| enum('border-box', 'content-box') | No       |

***

<a id="columngap"></a>

### `columnGap`

`columnGap` works like `column-gap` in CSS. Only pixel units are supported in React Native.

See [MDN CSS Reference](https://developer.mozilla.org/en-US/docs/Web/CSS/column-gap) for more details.

| Type   | Required |
| ------ | -------- |
| number | No       |

***

<a id="direction"></a>

### `direction`

`direction` specifies the directional flow of the user interface. The default is `inherit`, except for root node which will have value based on the current locale.

See [MDN CSS Reference](https://www.yogalayout.dev/docs/styling/layout-direction) for more details.

| Type                          | Required |
| ----------------------------- | -------- |
| enum('inherit', 'ltr', 'rtl') | No       |

***

<a id="display"></a>

### `display`

`display` sets the display type of this component.

It works similarly to `display` in CSS but only supports the values 'flex', 'none', and 'contents'. The default is `flex`.

| Type                             | Required |
| -------------------------------- | -------- |
| enum('none', 'flex', 'contents') | No       |

***

<a id="end"></a>

### `end`

When the direction is `ltr`, `end` is equivalent to `right`. When the direction is `rtl`, `end` is equivalent to `left`.

This style takes precedence over the `left` and `right` styles.

| Type           | Required |
| -------------- | -------- |
| number, string | No       |

***

<a id="flex"></a>

### `flex`

In React Native `flex` does not work the same way that it does in CSS. `flex` is a number rather than a string, and it works according to the [Yoga](https://github.com/facebook/yoga) layout engine.

When `flex` is a positive number, it makes the component flexible, and it will be sized proportional to its flex value. So a component with `flex` set to `2` will take twice the space as a component with `flex` set to 1. `flex: <positive number>` equates to `flexGrow: <positive number>, flexShrink: 1, flexBasis: 0`.

When `flex` is `0`, the component is sized according to `width` and `height`, and it is inflexible.

When `flex` is `-1`, the component is normally sized according to `width` and `height`. However, if there's not enough space, the component will shrink to its `minWidth` and `minHeight`.

`flexGrow`, `flexShrink`, and `flexBasis` work the same as in CSS.

| Type   | Required |
| ------ | -------- |
| number | No       |

***

<a id="flexbasis"></a>

### `flexBasis`

`flexBasis` is an axis-independent way of providing the default size of an item along the main axis. Setting the `flexBasis` of a child is similar to setting the `width` of that child if its parent is a container with `flexDirection: row` or setting the `height` of a child if its parent is a container with `flexDirection: column`. The `flexBasis` of an item is the default size of that item, the size of the item before any `flexGrow` and `flexShrink` calculations are performed.

| Type           | Required |
| -------------- | -------- |
| number, string | No       |

***

<a id="flexdirection"></a>

### `flexDirection`

`flexDirection` controls which directions children of a container go. `row` goes left to right, `column` goes top to bottom, and you may be able to guess what the other two do. It works like `flex-direction` in CSS, except the default is `column`.

See [MDN CSS Reference](https://developer.mozilla.org/en-US/docs/Web/CSS/flex-direction) for more details.

| Type                                                   | Required |
| ------------------------------------------------------ | -------- |
| enum('row', 'row-reverse', 'column', 'column-reverse') | No       |

***

<a id="flexgrow"></a>

### `flexGrow`

`flexGrow` describes how any space within a container should be distributed among its children along the main axis. After laying out its children, a container will distribute any remaining space according to the flex grow values specified by its children.

`flexGrow` accepts any floating point value >= 0, with 0 being the default value. A container will distribute any remaining space among its children weighted by the children’s `flexGrow` values.

| Type   | Required |
| ------ | -------- |
| number | No       |

***

<a id="flexshrink"></a>

### `flexShrink`

[`flexShrink`](layout-props.md#flexshrink) describes how to shrink children along the main axis in the case in which the total size of the children overflows the size of the container on the main axis. `flexShrink` is very similar to `flexGrow` and can be thought of in the same way if any overflowing size is considered to be negative remaining space. These two properties also work well together by allowing children to grow and shrink as needed.

`flexShrink` accepts any floating point value >= 0, with 0 being the default value. A container will shrink its children weighted by the children’s `flexShrink` values.

| Type   | Required |
| ------ | -------- |
| number | No       |

***

<a id="flexwrap"></a>

### `flexWrap`

`flexWrap` controls whether children can wrap around after they hit the end of a flex container. It works like `flex-wrap` in CSS (default: nowrap).

Note it does not work anymore with `alignItems: stretch` (the default), so you may want to use `alignItems: flex-start` for example (breaking change details: <https://github.com/facebook/react-native/releases/tag/v0.28.0>).

See [MDN CSS Reference](https://developer.mozilla.org/en-US/docs/Web/CSS/flex-wrap) for more details.

| Type                                   | Required |
| -------------------------------------- | -------- |
| enum('wrap', 'nowrap', 'wrap-reverse') | No       |

***

<a id="gap"></a>

### `gap`

`gap` works like `gap` in CSS. Only pixel units are supported in React Native.

See [MDN CSS Reference](https://developer.mozilla.org/en-US/docs/Web/CSS/gap) for more details.

| Type   | Required |
| ------ | -------- |
| number | No       |

***

<a id="height"></a>

### `height`

`height` sets the height of this component.

It works similarly to `height` in CSS, but in React Native you must use points or percentages. Ems and other units are not supported.

See [MDN CSS Reference](https://developer.mozilla.org/en-US/docs/Web/CSS/height) for more details.

| Type           | Required |
| -------------- | -------- |
| number, string | No       |

***

<a id="inset"></a>

### `inset`

note

`inset` is only available on the [New Architecture](../architecture/landing-page.md)

Setting `inset` has the same effect as setting each of `top`, `bottom`, `right` and `left` props.

See [MDN CSS Reference](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/inset) for more details.

| Type           | Required |
| -------------- | -------- |
| number, string | No       |

***

<a id="insetblock"></a>

### `insetBlock`

note

`insetBlock` is only available on the [New Architecture](../architecture/landing-page.md)

Equivalent to [`top`](layout-props.md#top) and [`bottom`](layout-props.md#bottom).

See [MDN CSS Reference](https://developer.mozilla.org/en-US/docs/Web/CSS/inset-block) for more details.

| Type           | Required |
| -------------- | -------- |
| number, string | No       |

***

<a id="insetblockend"></a>

### `insetBlockEnd`

note

`insetBlockEnd` is only available on the [New Architecture](../architecture/landing-page.md)

Equivalent to [`bottom`](layout-props.md#bottom).

See [MDN CSS Reference](https://developer.mozilla.org/en-US/docs/Web/CSS/inset-block-end) for more details.

| Type           | Required |
| -------------- | -------- |
| number, string | No       |

***

<a id="insetblockstart"></a>

### `insetBlockStart`

note

`insetBlockStart` is only available on the [New Architecture](../architecture/landing-page.md)

Equivalent to [`top`](layout-props.md#top).

See [MDN CSS Reference](https://developer.mozilla.org/en-US/docs/Web/CSS/inset-block-start) for more details.

| Type           | Required |
| -------------- | -------- |
| number, string | No       |

***

<a id="insetinline"></a>

### `insetInline`

note

`insetInline` is only available on the [New Architecture](../architecture/landing-page.md)

Equivalent to [`right`](layout-props.md#right) and [`left`](layout-props.md#left).

See [MDN CSS Reference](https://developer.mozilla.org/en-US/docs/Web/CSS/inset-inline) for more details.

| Type           | Required |
| -------------- | -------- |
| number, string | No       |

***

<a id="insetinlineend"></a>

### `insetInlineEnd`

note

`insetInlineEnd` is only available on the [New Architecture](../architecture/landing-page.md)

When direction is `ltr`, `insetInlineEnd` is equivalent to [`right`](layout-props.md#right). When direction is `rtl`, `insetInlineEnd` is equivalent to [`left`](layout-props.md#left).

See [MDN CSS Reference](https://developer.mozilla.org/en-US/docs/Web/CSS/inset-inline-end) for more details.

| Type           | Required |
| -------------- | -------- |
| number, string | No       |

***

<a id="insetinlinestart"></a>

### `insetInlineStart`

note

`insetInlineStart` is only available on the [New Architecture](../architecture/landing-page.md)

When direction is `ltr`, `insetInlineStart` is equivalent to [`left`](layout-props.md#left). When direction is `rtl`, `insetInlineStart` is equivalent to [`right`](layout-props.md#right).

See [MDN CSS Reference](https://developer.mozilla.org/en-US/docs/Web/CSS/inset-inline-start) for more details.

| Type           | Required |
| -------------- | -------- |
| number, string | No       |

***

<a id="isolation"></a>

### `isolation`

note

`isolation` is only available on the [New Architecture](../architecture/landing-page.md)

`isolation` lets you form a [stacking context](https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_positioned_layout/Stacking_context).

There are two values:

* `auto` (default): Does nothing.
* `isolate`: Forms a stacking context.

| Type                    | Required |
| ----------------------- | -------- |
| enum('auto', 'isolate') | No       |

***

<a id="justifycontent"></a>

### `justifyContent`

`justifyContent` aligns children in the main direction. For example, if children are flowing vertically, `justifyContent` controls how they align vertically. It works like `justify-content` in CSS (default: flex-start).

See [MDN CSS Reference](https://developer.mozilla.org/en-US/docs/Web/CSS/justify-content) for more details.

| Type                                                                                      | Required |
| ----------------------------------------------------------------------------------------- | -------- |
| enum('flex-start', 'flex-end', 'center', 'space-between', 'space-around', 'space-evenly') | No       |

***

<a id="left"></a>

### `left`

`left` is the number of logical pixels to offset the left edge of this component.

It works similarly to `left` in CSS, but in React Native you must use points or percentages. Ems and other units are not supported.

See [MDN CSS Reference](https://developer.mozilla.org/en-US/docs/Web/CSS/left) for more details of how `left` affects layout.

| Type           | Required |
| -------------- | -------- |
| number, string | No       |

***

<a id="margin"></a>

### `margin`

Setting `margin` has the same effect as setting each of `marginTop`, `marginLeft`, `marginBottom`, and `marginRight`.

See [MDN CSS Reference](https://developer.mozilla.org/en-US/docs/Web/CSS/margin) for more details.

| Type           | Required |
| -------------- | -------- |
| number, string | No       |

***

<a id="marginbottom"></a>

### `marginBottom`

`marginBottom` works like `margin-bottom` in CSS. See [MDN CSS Reference](https://developer.mozilla.org/en-US/docs/Web/CSS/margin-bottom) for more details.

| Type           | Required |
| -------------- | -------- |
| number, string | No       |

***

<a id="marginblock"></a>

### `marginBlock`

Equivalent to [`marginVertical`](layout-props.md#marginvertical).

See [MDN CSS Reference](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/margin-block) for more details.

| Type           | Required |
| -------------- | -------- |
| number, string | No       |

***

<a id="marginblockend"></a>

### `marginBlockEnd`

Equivalent to [`marginBottom`](layout-props.md#marginbottom).

See [MDN CSS Reference](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/margin-block-end) for more details.

| Type           | Required |
| -------------- | -------- |
| number, string | No       |

***

<a id="marginblockstart"></a>

### `marginBlockStart`

Equivalent to [`marginTop`](layout-props.md#margintop).

See [MDN CSS Reference](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/margin-block-start) for more details.

| Type           | Required |
| -------------- | -------- |
| number, string | No       |

***

<a id="marginend"></a>

### `marginEnd`

When direction is `ltr`, `marginEnd` is equivalent to `marginRight`. When direction is `rtl`, `marginEnd` is equivalent to `marginLeft`.

| Type           | Required |
| -------------- | -------- |
| number, string | No       |

***

<a id="marginhorizontal"></a>

### `marginHorizontal`

Setting `marginHorizontal` has the same effect as setting both `marginLeft` and `marginRight`.

| Type           | Required |
| -------------- | -------- |
| number, string | No       |

***

<a id="margininline"></a>

### `marginInline`

Equivalent to [`marginHorizontal`](layout-props.md#marginhorizontal).

See [MDN CSS Reference](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/margin-inline) for more details.

| Type           | Required |
| -------------- | -------- |
| number, string | No       |

***

<a id="margininlineend"></a>

### `marginInlineEnd`

When direction is `ltr`, `marginInlineEnd` is equivalent to [`marginEnd`](layout-props.md#marginend) (i.e. `marginRight`). When direction is `rtl`, `marginInlineEnd` is equivalent to [`marginEnd`](layout-props.md#marginend) (i.e. `marginLeft`).

See [MDN CSS Reference](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/margin-inline-end) for more details.

| Type           | Required |
| -------------- | -------- |
| number, string | No       |

***

<a id="margininlinestart"></a>

### `marginInlineStart`

When direction is `ltr`, `marginInlineStart` is equivalent to [`marginStart`](layout-props.md#marginstart) (i.e. `marginLeft`). When direction is `rtl`, `marginInlineStart` is equivalent to [`marginStart`](layout-props.md#marginstart) (i.e. `marginRight`).

See [MDN CSS Reference](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/margin-inline-start) for more details.

| Type           | Required |
| -------------- | -------- |
| number, string | No       |

***

<a id="marginleft"></a>

### `marginLeft`

`marginLeft` works like `margin-left` in CSS. See [MDN CSS Reference](https://developer.mozilla.org/en-US/docs/Web/CSS/margin-left) for more details.

| Type           | Required |
| -------------- | -------- |
| number, string | No       |

***

<a id="marginright"></a>

### `marginRight`

`marginRight` works like `margin-right` in CSS.

See [MDN CSS Reference](https://developer.mozilla.org/en-US/docs/Web/CSS/margin-right) for more details.

| Type           | Required |
| -------------- | -------- |
| number, string | No       |

***

<a id="marginstart"></a>

### `marginStart`

When direction is `ltr`, `marginStart` is equivalent to `marginLeft`. When direction is `rtl`, `marginStart` is equivalent to `marginRight`.

| Type           | Required |
| -------------- | -------- |
| number, string | No       |

***

<a id="margintop"></a>

### `marginTop`

`marginTop` works like `margin-top` in CSS.

See [MDN CSS Reference](https://developer.mozilla.org/en-US/docs/Web/CSS/margin-top) for more details.

| Type           | Required |
| -------------- | -------- |
| number, string | No       |

***

<a id="marginvertical"></a>

### `marginVertical`

Setting `marginVertical` has the same effect as setting both `marginTop` and `marginBottom`.

| Type           | Required |
| -------------- | -------- |
| number, string | No       |

***

<a id="maxheight"></a>

### `maxHeight`

`maxHeight` is the maximum height for this component, in logical pixels.

It works similarly to `max-height` in CSS, but in React Native you must use points or percentages. Ems and other units are not supported.

See [MDN CSS Reference](https://developer.mozilla.org/en-US/docs/Web/CSS/max-height) for more details.

| Type           | Required |
| -------------- | -------- |
| number, string | No       |

***

<a id="maxwidth"></a>

### `maxWidth`

`maxWidth` is the maximum width for this component, in logical pixels.

It works similarly to `max-width` in CSS, but in React Native you must use points or percentages. Ems and other units are not supported.

See [MDN CSS Reference](https://developer.mozilla.org/en-US/docs/Web/CSS/max-width) for more details.

| Type           | Required |
| -------------- | -------- |
| number, string | No       |

***

<a id="minheight"></a>

### `minHeight`

`minHeight` is the minimum height for this component, in logical pixels.

It works similarly to `min-height` in CSS, but in React Native you must use points or percentages. Ems and other units are not supported.

See [MDN CSS Reference](https://developer.mozilla.org/en-US/docs/Web/CSS/min-height) for more details.

| Type           | Required |
| -------------- | -------- |
| number, string | No       |

***

<a id="minwidth"></a>

### `minWidth`

`minWidth` is the minimum width for this component, in logical pixels.

It works similarly to `min-width` in CSS, but in React Native you must use points or percentages. Ems and other units are not supported.

See [MDN CSS Reference](https://developer.mozilla.org/en-US/docs/Web/CSS/min-width) for more details.

| Type           | Required |
| -------------- | -------- |
| number, string | No       |

***

<a id="overflow"></a>

### `overflow`

`overflow` controls how children are measured and displayed. `overflow: hidden` causes views to be clipped while `overflow: scroll` causes views to be measured independently of their parents' main axis. It works like `overflow` in CSS (default: visible).

See [MDN CSS Reference](https://developer.mozilla.org/en-US/docs/Web/CSS/overflow) for more details.

| Type                                | Required |
| ----------------------------------- | -------- |
| enum('visible', 'hidden', 'scroll') | No       |

***

<a id="padding"></a>

### `padding`

Setting `padding` has the same effect as setting each of `paddingTop`, `paddingBottom`, `paddingLeft`, and `paddingRight`.

See [MDN CSS Reference](https://developer.mozilla.org/en-US/docs/Web/CSS/padding) for more details.

| Type           | Required |
| -------------- | -------- |
| number, string | No       |

***

<a id="paddingbottom"></a>

### `paddingBottom`

`paddingBottom` works like `padding-bottom` in CSS.

See [MDN CSS Reference](https://developer.mozilla.org/en-US/docs/Web/CSS/padding-bottom) for more details.

| Type           | Required |
| -------------- | -------- |
| number, string | No       |

***

<a id="paddingblock"></a>

### `paddingBlock`

Equivalent to [`paddingVertical`](layout-props.md#paddingvertical).

See [MDN CSS Reference](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/padding-block) for more details.

| Type           | Required |
| -------------- | -------- |
| number, string | No       |

***

<a id="paddingblockend"></a>

### `paddingBlockEnd`

Equivalent to [`paddingBottom`](layout-props.md#paddingbottom).

See [MDN CSS Reference](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/padding-block-end) for more details.

| Type           | Required |
| -------------- | -------- |
| number, string | No       |

***

<a id="paddingblockstart"></a>

### `paddingBlockStart`

Equivalent to [`paddingTop`](layout-props.md#paddingtop).

See [MDN CSS Reference](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/padding-block-start) for more details.

| Type           | Required |
| -------------- | -------- |
| number, string | No       |

***

<a id="paddingend"></a>

### `paddingEnd`

When direction is `ltr`, `paddingEnd` is equivalent to `paddingRight`. When direction is `rtl`, `paddingEnd` is equivalent to `paddingLeft`.

| Type           | Required |
| -------------- | -------- |
| number, string | No       |

***

<a id="paddinghorizontal"></a>

### `paddingHorizontal`

Setting `paddingHorizontal` is like setting both of `paddingLeft` and `paddingRight`.

| Type           | Required |
| -------------- | -------- |
| number, string | No       |

***

<a id="paddinginline"></a>

### `paddingInline`

Equivalent to [`paddingHorizontal`](layout-props.md#paddinghorizontal).

See [MDN CSS Reference](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/padding-inline) for more details.

| Type           | Required |
| -------------- | -------- |
| number, string | No       |

***

<a id="paddinginlineend"></a>

### `paddingInlineEnd`

When direction is `ltr`, `paddingInlineEnd` is equivalent to [`paddingEnd`](layout-props.md#paddingend) (i.e. `paddingRight`). When direction is `rtl`, `paddingInlineEnd` is equivalent to [`paddingEnd`](layout-props.md#paddingend) (i.e. `paddingLeft`).

See [MDN CSS Reference](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/padding-inline-end) for more details.

| Type           | Required |
| -------------- | -------- |
| number, string | No       |

***

<a id="paddinginlinestart"></a>

### `paddingInlineStart`

When direction is `ltr`, `paddingInlineStart` is equivalent to [`paddingStart`](layout-props.md#paddingstart) (i.e. `paddingLeft`). When direction is `rtl`, `paddingInlineStart` is equivalent to [`paddingStart`](layout-props.md#paddingstart) (i.e. `paddingRight`).

See [MDN CSS Reference](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/padding-inline-start) for more details.

| Type           | Required |
| -------------- | -------- |
| number, string | No       |

***

<a id="paddingleft"></a>

### `paddingLeft`

`paddingLeft` works like `padding-left` in CSS.

See [MDN CSS Reference](https://developer.mozilla.org/en-US/docs/Web/CSS/padding-left) for more details.

| Type           | Required |
| -------------- | -------- |
| number, string | No       |

***

<a id="paddingright"></a>

### `paddingRight`

`paddingRight` works like `padding-right` in CSS.

See [MDN CSS Reference](https://developer.mozilla.org/en-US/docs/Web/CSS/padding-right) for more details.

| Type           | Required |
| -------------- | -------- |
| number, string | No       |

***

<a id="paddingstart"></a>

### `paddingStart`

When direction is `ltr`, `paddingStart` is equivalent to `paddingLeft`. When direction is `rtl`, `paddingStart` is equivalent to `paddingRight`.

| Type           | Required |
| -------------- | -------- |
| number, string | No       |

***

<a id="paddingtop"></a>

### `paddingTop`

`paddingTop` works like `padding-top` in CSS.

See [MDN CSS Reference](https://developer.mozilla.org/en-US/docs/Web/CSS/padding-top) for more details.

| Type           | Required |
| -------------- | -------- |
| number, string | No       |

***

<a id="paddingvertical"></a>

### `paddingVertical`

Setting `paddingVertical` is like setting both of `paddingTop` and `paddingBottom`.

| Type           | Required |
| -------------- | -------- |
| number, string | No       |

***

<a id="position"></a>

### `position`

`position` in React Native is similar to [regular CSS](https://developer.mozilla.org/en-US/docs/Web/CSS/position), but everything is set to `relative` by default.

`relative` will position an element according to the normal flow of the layout. Insets (`top`, `bottom`, `left`, `right`) will offset relative to this layout.

`absolute` takes the element out of the normal flow of the layout. Insets will offset relative to its [containing block](flexbox.md#the-containing-block).

`static` will position an element according to the normal flow of the layout. Insets will have no effect. `static` elements do not form a containing block for absolute descendants.

For more information, see the [Layout with Flexbox docs](flexbox.md#position). Also, [the Yoga documentation](https://www.yogalayout.dev/docs/styling/position) has more details on how `position` differs between React Native and CSS.

| Type                                   | Required |
| -------------------------------------- | -------- |
| enum('absolute', 'relative', 'static') | No       |

***

<a id="right"></a>

### `right`

`right` is the number of logical pixels to offset the right edge of this component.

It works similarly to `right` in CSS, but in React Native you must use points or percentages. Ems and other units are not supported.

See [MDN CSS Reference](https://developer.mozilla.org/en-US/docs/Web/CSS/right) for more details of how `right` affects layout.

| Type           | Required |
| -------------- | -------- |
| number, string | No       |

***

<a id="rowgap"></a>

### `rowGap`

`rowGap` works like `row-gap` in CSS. Only pixel units are supported in React Native.

See [MDN CSS Reference](https://developer.mozilla.org/en-US/docs/Web/CSS/row-gap) for more details.

| Type   | Required |
| ------ | -------- |
| number | No       |

***

<a id="start"></a>

### `start`

When the direction is `ltr`, `start` is equivalent to `left`. When the direction is `rtl`, `start` is equivalent to `right`.

This style takes precedence over the `left`, `right`, and `end` styles.

| Type           | Required |
| -------------- | -------- |
| number, string | No       |

***

<a id="top"></a>

### `top`

`top` is the number of logical pixels to offset the top edge of this component.

It works similarly to `top` in CSS, but in React Native you must use points or percentages. Ems and other units are not supported.

See [MDN CSS Reference](https://developer.mozilla.org/en-US/docs/Web/CSS/top) for more details of how `top` affects layout.

| Type           | Required |
| -------------- | -------- |
| number, string | No       |

***

<a id="width"></a>

### `width`

`width` sets the width of this component.

It works similarly to `width` in CSS, but in React Native you must use points or percentages. Ems and other units are not supported.

See [MDN CSS Reference](https://developer.mozilla.org/en-US/docs/Web/CSS/width) for more details.

| Type           | Required |
| -------------- | -------- |
| number, string | No       |

***

<a id="zindex"></a>

### `zIndex`

`zIndex` controls which components display on top of others. Normally, you don't use `zIndex`. Components render according to their order in the document tree, so later components draw over earlier ones. `zIndex` may be useful if you have animations or custom modal interfaces where you don't want this behavior.

It works like the CSS `z-index` property - components with a larger `zIndex` will render on top. Think of the z-direction like it's pointing from the phone into your eyeball.

On iOS, `zIndex` may require `View`s to be siblings of each other for it to work as expected.

See [MDN CSS Reference](https://developer.mozilla.org/en-US/docs/Web/CSS/z-index) for more details.

| Type   | Required |
| ------ | -------- |
| number | No       |

## Embedded example source

Code extracted from this page’s Expo Snack embeds; interactive previews require the original website.

### LayoutProps Example

Dependencies: `react-native-safe-area-context`

#### `App.js`

```jsx
import {useState} from 'react';
import {Button, ScrollView, StyleSheet, Text, View} from 'react-native';
import {SafeAreaView, SafeAreaProvider} from 'react-native-safe-area-context';

const App = () => {
  const [flexDirection, setFlexDirection] = useState(0);
  const [justifyContent, setJustifyContent] = useState(0);
  const [alignItems, setAlignItems] = useState(0);
  const [direction, setDirection] = useState(0);
  const [wrap, setWrap] = useState(0);

  const [squares, setSquares] = useState([<Square />, <Square />, <Square />]);

  const hookedStyles = {
    flexDirection: flexDirections[flexDirection],
    justifyContent: justifyContents[justifyContent],
    alignItems: alignItemsArr[alignItems],
    direction: directions[direction],
    flexWrap: wraps[wrap],
  };

  const changeSetting = (value, options, setterFunction) => {
    if (value === options.length - 1) {
      setterFunction(0);
      return;
    }
    setterFunction(value + 1);
  };

  return (
    <SafeAreaProvider>
      <SafeAreaView style={styles.container}>
        <View style={[styles.container, styles.playingSpace, hookedStyles]}>
          {squares.map(elem => elem)}
        </View>
        <ScrollView style={styles.layoutContainer}>
          <View style={styles.controlSpace}>
            <View style={styles.buttonView}>
              <Button
                title="Change Flex Direction"
                onPress={() =>
                  changeSetting(flexDirection, flexDirections, setFlexDirection)
                }
              />
              <Text style={styles.text}>{flexDirections[flexDirection]}</Text>
            </View>
            <View style={styles.buttonView}>
              <Button
                title="Change Justify Content"
                onPress={() =>
                  changeSetting(
                    justifyContent,
                    justifyContents,
                    setJustifyContent,
                  )
                }
              />
              <Text style={styles.text}>{justifyContents[justifyContent]}</Text>
            </View>
            <View style={styles.buttonView}>
              <Button
                title="Change Align Items"
                onPress={() =>
                  changeSetting(alignItems, alignItemsArr, setAlignItems)
                }
              />
              <Text style={styles.text}>{alignItemsArr[alignItems]}</Text>
            </View>
            <View style={styles.buttonView}>
              <Button
                title="Change Direction"
                onPress={() =>
                  changeSetting(direction, directions, setDirection)
                }
              />
              <Text style={styles.text}>{directions[direction]}</Text>
            </View>
            <View style={styles.buttonView}>
              <Button
                title="Change Flex Wrap"
                onPress={() => changeSetting(wrap, wraps, setWrap)}
              />
              <Text style={styles.text}>{wraps[wrap]}</Text>
            </View>
            <View style={styles.buttonView}>
              <Button
                title="Add Square"
                onPress={() => setSquares([...squares, <Square />])}
              />
            </View>
            <View style={styles.buttonView}>
              <Button
                title="Delete Square"
                onPress={() =>
                  setSquares(squares.filter((v, i) => i !== squares.length - 1))
                }
              />
            </View>
          </View>
        </ScrollView>
      </SafeAreaView>
    </SafeAreaProvider>
  );
};

const flexDirections = ['row', 'row-reverse', 'column', 'column-reverse'];
const justifyContents = [
  'flex-start',
  'flex-end',
  'center',
  'space-between',
  'space-around',
  'space-evenly',
];
const alignItemsArr = [
  'flex-start',
  'flex-end',
  'center',
  'stretch',
  'baseline',
];
const wraps = ['nowrap', 'wrap', 'wrap-reverse'];
const directions = ['inherit', 'ltr', 'rtl'];

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  layoutContainer: {
    flex: 0.5,
  },
  playingSpace: {
    backgroundColor: 'white',
    borderColor: 'blue',
    borderWidth: 3,
    overflow: 'hidden',
  },
  controlSpace: {
    flexDirection: 'row',
    flexWrap: 'wrap',
  },
  buttonView: {
    width: '50%',
    padding: 10,
  },
  text: {
    textAlign: 'center',
  },
});

const Square = () => (
  <View
    style={{
      width: 50,
      height: 50,
      backgroundColor: randomHexColor(),
    }}
  />
);

const randomHexColor = () => {
  return '#000000'.replace(/0/g, () => {
    return Math.round(Math.random() * 14).toString(16);
  });
};

export default App;
```

### LayoutProps Example

Dependencies: `react-native-safe-area-context`

#### `App.tsx`

```tsx
import {useState} from 'react';
import {
  Button,
  ScrollView,
  StyleSheet,
  Text,
  View,
  ViewStyle,
} from 'react-native';
import {SafeAreaView, SafeAreaProvider} from 'react-native-safe-area-context';

const App = () => {
  const [flexDirection, setFlexDirection] = useState(0);
  const [justifyContent, setJustifyContent] = useState(0);
  const [alignItems, setAlignItems] = useState(0);
  const [direction, setDirection] = useState(0);
  const [wrap, setWrap] = useState(0);

  const [squares, setSquares] = useState([<Square />, <Square />, <Square />]);

  const hookedStyles = {
    flexDirection: flexDirections[flexDirection],
    justifyContent: justifyContents[justifyContent],
    alignItems: alignItemsArr[alignItems],
    direction: directions[direction],
    flexWrap: wraps[wrap],
  };

  const changeSetting = (
    value: number,
    options: any[],
    setterFunction: (index: number) => void,
  ) => {
    if (value === options.length - 1) {
      setterFunction(0);
      return;
    }
    setterFunction(value + 1);
  };

  return (
    <SafeAreaProvider>
      <SafeAreaView style={styles.container}>
        <View style={[styles.container, styles.playingSpace, hookedStyles]}>
          {squares.map(elem => elem)}
        </View>
        <ScrollView style={styles.layoutContainer}>
          <View style={styles.controlSpace}>
            <View style={styles.buttonView}>
              <Button
                title="Change Flex Direction"
                onPress={() =>
                  changeSetting(flexDirection, flexDirections, setFlexDirection)
                }
              />
              <Text style={styles.text}>{flexDirections[flexDirection]}</Text>
            </View>
            <View style={styles.buttonView}>
              <Button
                title="Change Justify Content"
                onPress={() =>
                  changeSetting(
                    justifyContent,
                    justifyContents,
                    setJustifyContent,
                  )
                }
              />
              <Text style={styles.text}>{justifyContents[justifyContent]}</Text>
            </View>
            <View style={styles.buttonView}>
              <Button
                title="Change Align Items"
                onPress={() =>
                  changeSetting(alignItems, alignItemsArr, setAlignItems)
                }
              />
              <Text style={styles.text}>{alignItemsArr[alignItems]}</Text>
            </View>
            <View style={styles.buttonView}>
              <Button
                title="Change Direction"
                onPress={() =>
                  changeSetting(direction, directions, setDirection)
                }
              />
              <Text style={styles.text}>{directions[direction]}</Text>
            </View>
            <View style={styles.buttonView}>
              <Button
                title="Change Flex Wrap"
                onPress={() => changeSetting(wrap, wraps, setWrap)}
              />
              <Text style={styles.text}>{wraps[wrap]}</Text>
            </View>
            <View style={styles.buttonView}>
              <Button
                title="Add Square"
                onPress={() => setSquares([...squares, <Square />])}
              />
            </View>
            <View style={styles.buttonView}>
              <Button
                title="Delete Square"
                onPress={() =>
                  setSquares(squares.filter((v, i) => i !== squares.length - 1))
                }
              />
            </View>
          </View>
        </ScrollView>
      </SafeAreaView>
    </SafeAreaProvider>
  );
};

const flexDirections: ViewStyle['flexDirection'][] = [
  'row',
  'row-reverse',
  'column',
  'column-reverse',
];
const justifyContents: ViewStyle['justifyContent'][] = [
  'flex-start',
  'flex-end',
  'center',
  'space-between',
  'space-around',
  'space-evenly',
];
const alignItemsArr: ViewStyle['alignItems'][] = [
  'flex-start',
  'flex-end',
  'center',
  'stretch',
  'baseline',
];
const wraps: ViewStyle['flexWrap'][] = ['nowrap', 'wrap', 'wrap-reverse'];
const directions: ViewStyle['direction'][] = ['inherit', 'ltr', 'rtl'];

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  layoutContainer: {
    flex: 0.5,
  },
  playingSpace: {
    backgroundColor: 'white',
    borderColor: 'blue',
    borderWidth: 3,
    overflow: 'hidden',
  },
  controlSpace: {
    flexDirection: 'row',
    flexWrap: 'wrap',
  },
  buttonView: {
    width: '50%',
    padding: 10,
  },
  text: {
    textAlign: 'center',
  },
});

const Square = () => (
  <View
    style={{
      width: 50,
      height: 50,
      backgroundColor: randomHexColor(),
    }}
  />
);

const randomHexColor = () => {
  return '#000000'.replace(/0/g, () => {
    return Math.round(Math.random() * 14).toString(16);
  });
};

export default App;
```
