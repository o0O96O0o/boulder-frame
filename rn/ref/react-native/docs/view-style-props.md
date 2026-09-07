# View Style Props

Source: https://reactnative.dev/docs/view-style-props

Version: 0.87 | Retrieved: 2026-09-07

<a id="example"></a>

### Example

# Reference

<a id="props"></a>

## Props

<a id="backfacevisibility"></a>

### `backfaceVisibility`

| Type                          |
| ----------------------------- |
| enum(`'visible'`, `'hidden'`) |

***

<a id="backgroundcolor"></a>

### `backgroundColor`

| Type                     |
| ------------------------ |
| [color](colors.md) |

***

<a id="backgroundimage"></a>

### `backgroundImage`

`backgroundImage` provides the ability to draw a [`linear-gradient()`](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Values/gradient/linear-gradient) and [`radial-gradient()`](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Values/gradient/radial-gradient) using a web-like syntax.

React TSX

```
// Simple usage:

<View style={{ backgroundImage: 'linear-gradient(45deg, blue, red)' }} />

<View style={{ backgroundImage: 'radial-gradient(ellipse farthest-corner at 30% 40%, red, blue)' }} />

// Also with PlatformColor:

<View

style={{

  backgroundImage: [

    {

      type: 'linear-gradient',

      direction: 'to bottom',

      colorStops: [

        {

          color: Platform.select({

            ios: PlatformColor('systemTealColor'),

            android: PlatformColor('@android:color/holo_purple'),

            default: 'blue',

          }),

          positions: ['0%'],

        },

        {color: 'green', positions: ['100%']},

      ],

    },

  ],

}}

/>
```

More complex examples of usage can be found in the RNTester app (with `PlatformColor` supports):

* [LinearGradientExample.js](https://github.com/facebook/react-native/blob/v0.87.0/packages/rn-tester/js/examples/LinearGradient/LinearGradientExample.js)
* [RadialGradientExample.js](https://github.com/facebook/react-native/blob/v0.87.0/packages/rn-tester/js/examples/RadialGradient/RadialGradientExample.js)

| Type                                                                                                                                                                                               |
| -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| string, array of objects: `{type: 'linear-gradient', direction: string, colorStops: object[] }`, `{type: 'radial-gradient', shape: string, position: object, size: string, colorStops: object[] }` |

***

<a id="backgroundposition"></a>

### `backgroundPosition`

Controls where the background gradient is placed inside the view. This is useful when `backgroundImage` is set, and you want to offset or center it instead of filling the full area.

React TSX

```
<View

  style={{

    backgroundImage: 'radial-gradient(circle, #ff6b6b, #4ecdc4)',

    backgroundPosition: 'center',

    backgroundRepeat: 'no-repeat',

    backgroundSize: '50px 50px',

  }}

/>
```

| Type                                                                                    |
| --------------------------------------------------------------------------------------- |
| string \| array of objects `{top: string, left: string, right: string, bottom: string}` |

***

<a id="backgroundrepeat"></a>

### `backgroundRepeat`

Controls whether the background gradient is repeated, and how. This works together with `backgroundImage` to tile gradients across the view.

React TSX

```
<View

  style={{

    backgroundImage: 'linear-gradient(45deg, #ff6b6b, #4ecdc4)',

    backgroundRepeat: 'repeat',

    backgroundSize: '20px 20px',

  }}

/>
```

| Type                                                                                               |
| -------------------------------------------------------------------------------------------------- |
| enum(`'repeat'`, `'space'`, `'round'`, `'no-repeat'`) \| array of objects `{x: string, y: string}` |

***

<a id="backgroundsize"></a>

### `backgroundSize`

Controls the size of the background gradient. This is most useful when `backgroundImage` is set and the gradient should not fill the entire view by default.

React TSX

```
<View

  style={{

    backgroundImage: 'linear-gradient(90deg, #a8edea, #fed6e3)',

    backgroundRepeat: 'no-repeat',

    backgroundSize: '100px 100px',

  }}

/>
```

| Type                                                |
| --------------------------------------------------- |
| string \| array of objects `{x: number, y: number}` |

***

<a id="borderbottomcolor"></a>

### `borderBottomColor`

| Type                     |
| ------------------------ |
| [color](colors.md) |

***

<a id="borderblockcolor"></a>

### `borderBlockColor`

| Type                     |
| ------------------------ |
| [color](colors.md) |

***

<a id="borderblockendcolor"></a>

### `borderBlockEndColor`

| Type                     |
| ------------------------ |
| [color](colors.md) |

***

<a id="borderblockstartcolor"></a>

### `borderBlockStartColor`

| Type                     |
| ------------------------ |
| [color](colors.md) |

***

<a id="borderbottomendradius"></a>

### `borderBottomEndRadius`

| Type                              |
| --------------------------------- |
| number, string (percentage value) |

***

<a id="borderbottomleftradius"></a>

### `borderBottomLeftRadius`

| Type                              |
| --------------------------------- |
| number, string (percentage value) |

***

<a id="borderbottomrightradius"></a>

### `borderBottomRightRadius`

| Type                              |
| --------------------------------- |
| number, string (percentage value) |

***

<a id="borderbottomstartradius"></a>

### `borderBottomStartRadius`

| Type                              |
| --------------------------------- |
| number, string (percentage value) |

***

<a id="borderstartendradius"></a>

### `borderStartEndRadius`

| Type                              |
| --------------------------------- |
| number, string (percentage value) |

***

<a id="borderstartstartradius"></a>

### `borderStartStartRadius`

| Type                              |
| --------------------------------- |
| number, string (percentage value) |

***

<a id="borderendendradius"></a>

### `borderEndEndRadius`

| Type                              |
| --------------------------------- |
| number, string (percentage value) |

***

<a id="borderendstartradius"></a>

### `borderEndStartRadius`

| Type                              |
| --------------------------------- |
| number, string (percentage value) |

***

<a id="borderbottomwidth"></a>

### `borderBottomWidth`

| Type   |
| ------ |
| number |

***

<a id="bordercolor"></a>

### `borderColor`

| Type                     |
| ------------------------ |
| [color](colors.md) |

***

<a id="bordercurve-ios"></a>

### `borderCurve`iOS

On iOS 13+, it is possible to change the corner curve of borders.

| Type                               |
| ---------------------------------- |
| enum(`'circular'`, `'continuous'`) |

***

<a id="borderendcolor"></a>

### `borderEndColor`

| Type                     |
| ------------------------ |
| [color](colors.md) |

***

<a id="borderleftcolor"></a>

### `borderLeftColor`

| Type                     |
| ------------------------ |
| [color](colors.md) |

***

<a id="borderleftwidth"></a>

### `borderLeftWidth`

| Type   |
| ------ |
| number |

***

<a id="borderradius"></a>

### `borderRadius`

If the rounded border is not visible, try applying `overflow: 'hidden'` as well.

| Type                              |
| --------------------------------- |
| number, string (percentage value) |

***

<a id="borderrightcolor"></a>

### `borderRightColor`

| Type                     |
| ------------------------ |
| [color](colors.md) |

***

<a id="borderrightwidth"></a>

### `borderRightWidth`

| Type   |
| ------ |
| number |

***

<a id="borderstartcolor"></a>

### `borderStartColor`

| Type                     |
| ------------------------ |
| [color](colors.md) |

***

<a id="borderstyle"></a>

### `borderStyle`

| Type                                    |
| --------------------------------------- |
| enum(`'solid'`, `'dotted'`, `'dashed'`) |

***

<a id="bordertopcolor"></a>

### `borderTopColor`

| Type                     |
| ------------------------ |
| [color](colors.md) |

***

<a id="bordertopendradius"></a>

### `borderTopEndRadius`

| Type                              |
| --------------------------------- |
| number, string (percentage value) |

***

<a id="bordertopleftradius"></a>

### `borderTopLeftRadius`

| Type                              |
| --------------------------------- |
| number, string (percentage value) |

***

<a id="bordertoprightradius"></a>

### `borderTopRightRadius`

| Type                              |
| --------------------------------- |
| number, string (percentage value) |

***

<a id="bordertopstartradius"></a>

### `borderTopStartRadius`

| Type                              |
| --------------------------------- |
| number, string (percentage value) |

***

<a id="bordertopwidth"></a>

### `borderTopWidth`

| Type                              |
| --------------------------------- |
| number, string (percentage value) |

***

<a id="borderwidth"></a>

### `borderWidth`

| Type   |
| ------ |
| number |

<a id="boxshadow"></a>

### `boxShadow`

note

`boxShadow` is only available on the [New Architecture](../architecture/landing-page.md). Outset shadows are only supported on **Android 9+**. Inset shadows are only supported on **Android 10+**.

Adds a shadow effect to an element, with the ability to control the position, color, size, and blurriness of the shadow. This shadow either appears around the outside or inside of the border box of the element, depending on whether or not the shadow is *inset*. This is a spec-compliant implementation of the [web style prop of the same name](https://developer.mozilla.org/en-US/docs/Web/CSS/box-shadow). Read more about all the arguments available in the [BoxShadowValue](boxshadowvalue.md) documentation.

These shadows can be composed together so that a single `boxShadow` can be comprised of multiple different shadows.

`boxShadow` takes either a string which mimics the [web syntax](https://developer.mozilla.org/en-US/docs/Web/CSS/box-shadow#syntax) or an array of [BoxShadowValue](boxshadowvalue.md) objects.

| Type                                      |
| ----------------------------------------- |
| array of BoxShadowValue objects \| string |

<a id="cursor-ios"></a>

### `cursor`iOS

On iOS 17+, Setting to `pointer` allows hover effects when a pointer (such as a trackpad or stylus on iOS, or the users' gaze on visionOS) is over the view.

| Type                        |
| --------------------------- |
| enum(`'auto'`, `'pointer'`) |

***

<a id="elevation-android"></a>

### `elevation`Android

Sets the elevation of a view, using Android's underlying [elevation API](https://developer.android.com/training/material/shadows-clipping.html#Elevation). This adds a drop shadow to the item and affects z-order for overlapping views. Only supported on Android 5.0+, has no effect on earlier versions.

| Type   |
| ------ |
| number |

***

<a id="filter"></a>

### `filter`

note

`filter` is only available on the [New Architecture](../architecture/landing-page.md)

Adds a graphical filter to the `View`. This filter is comprised of any number of *filter functions*, which each represent some atomic change to the graphical composition of the `View`. The complete list of valid filter functions is defined below. `filter` will apply to descendants of the `View` as well as the `View` itself. `filter` implies `overflow: hidden`, so descendants will be clipped to fit the bounds of the `View`.

The following filter functions work across all platforms:

* `brightness`: Changes the brightness of the `View`. Takes a non-negative number or percentage.
* `opacity`: Changes the opacity, or alpha, of the `View`. Takes a non-negative number or percentage.

note

Due to issues with performance and spec compliance, these are the only two filter functions available on iOS. There are plans to explore some potential workarounds using SwiftUI instead of UIKit for this implementation.

Android

The following filter functions work on Android only:

* `blur`: Blurs the `View` with a [Gaussian blur](https://en.wikipedia.org/wiki/Gaussian_blur), where the specified length represents the radius used in the blurring algorithm. Any non-negative DIP value is valid (no percents). The larger the value, the blurrier the result.
* `contrast`: Changes the contrast of the `View`. Takes a non-negative number or percentage.
* `dropShadow`: Adds a shadow around the alpha mask of the `View` (only non-zero alpha pixels in the `View` will cast a shadow). Takes an optional color representing the shadow color, and 2 or 3 lengths. If 2 lengths are specified they are interpreted as `offsetX` and `offsetY` which will translate the shadow in the X and Y dimensions respectfully. If a 3rd length is given it is interpreted as the standard deviation of the Gaussian blur used on the shadow - so a larger value will blur the shadow more. Read more about the arguments in [DropShadowValue](dropshadowvalue.md).
* `grayscale`: Converts the `View` to [grayscale](https://en.wikipedia.org/wiki/Grayscale) by the specified amount. Takes a non-negative number or percentage, where `1` or `100%` represents complete grayscale.
* `hueRotate`: Changes the [hue](https://en.wikipedia.org/wiki/Hue) of the View. The argument of this function defines the angle of a color wheel around which the hue will be rotated, so e.g., `360deg` would have no effect. This angle can have either `deg` or `rad` units.
* `invert`: Inverts the colors in the `View`. Takes a non-negative number or percentage, where `1` or `100%` represents complete inversion.
* `sepia`: Converts the `View` to [sepia](https://en.wikipedia.org/wiki/Sepia_\(color\)). Takes a non-negative number or percentage, where `1` or `100%` represents complete sepia.
* `saturate`: Changes the [saturation](https://en.wikipedia.org/wiki/Colorfulness) of the `View`. Takes a non-negative number or percentage.

note

`blur` and `dropShadow` are only supported on **Android 12+**

`filter` takes either an array of objects comprising of the above filter functions or a string which mimics the [web syntax](https://developer.mozilla.org/en-US/docs/Web/CSS/filter#syntax).

| Type                                                                                                                                                                                                                                                                                                                                        |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| array of objects: `{brightness: number\|string}`, `{opacity: number\|string}`, `{blur: number\|string}`, `{contrast: number\|string}`, `{dropShadow: DropShadowValue\|string}`, `{grayscale: number\|string}`, `{hueRotate: number\|string}`, `{invert: number\|string}`, `{sepia: number\|string}`, `{saturate: number\|string}` or string |

***

<a id="mixblendmode"></a>

### `mixBlendMode`

note

`mixBlendMode` is only available on the [New Architecture](../architecture/landing-page.md) and **Android 10+**

Controls how the `View` blends its colors with the other elements in its **stacking context**. Check out the [MDN documentation](https://developer.mozilla.org/en-US/docs/Web/CSS/mix-blend-mode) for a full overview of each blending function.

For more granular control over what should be blending together see [isolation](layout-props.md#isolation).

<a id="mixblendmode-values"></a>

##### mixBlendMode Values

* `normal`: The element is drawn on top of its background without blending.
* `multiply`: The source color is multiplied by the destination color and replaces the destination.
* `screen`: Multiplies the complements of the backdrop and source color values, then complements the result.
* `overlay`: Multiplies or screens the colors, depending on the backdrop color value.
* `darken`: Selects the darker of the backdrop and source colors.
* `lighten`: Selects the lighter of the backdrop and source colors.
* `color-dodge`: Brightens the backdrop color to reflect the source color. Painting with black produces no changes.
* `color-burn`: Darkens the backdrop color to reflect the source color. Painting with white produces no change.
* `hard-light`: Multiplies or screens the colors, depending on the source color value. The effect is similar to shining a harsh spotlight on the backdrop.
* `soft-light`: Darkens or lightens the colors, depending on the source color value. The effect is similar to shining a diffused spotlight on the backdrop.
* `difference`: Subtracts the darker of the two constituent colors from the lighter color.
* `exclusion`: Produces an effect similar to that of the Difference mode but lower in contrast.
* `hue`: Creates a color with the hue of the source color and the saturation and luminosity of the backdrop color.
* `saturation`: Creates a color with the saturation of the source color and the hue and luminosity of the backdrop color.
* `color`: Creates a color with the hue and saturation of the source color and the luminosity of the backdrop color. This preserves the gray levels of the backdrop and is useful for coloring monochrome images or tinting color images.
* `luminosity`: Creates a color with the luminosity of the source color and the hue and saturation of the backdrop color. This produces an inverse effect to that of the Color mode.
* `plus-lighter`: Adds the source and destination color channels, clamping each at maximum value.

| Type                                                                                                                                                                                                                                                   |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| enum(`'normal'`, `'multiply'`, `'screen'`, `'overlay'`, `'darken'`, `'lighten'`, `'color-dodge'`, `'color-burn'`, `'hard-light'`, `'soft-light'`, `'difference'`, `'exclusion'`, `'hue'`, `'saturation'`, `'color'`, `'luminosity'`, `'plus-lighter'`) |

***

<a id="opacity"></a>

### `opacity`

| Type   |
| ------ |
| number |

***

<a id="outlinecolor"></a>

### `outlineColor`

note

`outlineColor` is only available on the [New Architecture](../architecture/landing-page.md)

Sets the color of an element's outline. See [web documentation](https://developer.mozilla.org/en-US/docs/Web/CSS/outline-color) for more details.

| Type                     |
| ------------------------ |
| [color](colors.md) |

***

<a id="outlineoffset"></a>

### `outlineOffset`

note

`outlineOffset` is only available on the [New Architecture](../architecture/landing-page.md)

Sets the amount of space between an outline and the bounds of an element. Does not affect layout. See [web documentation](https://developer.mozilla.org/en-US/docs/Web/CSS/outline-offset) for more details.

| Type   |
| ------ |
| number |

***

<a id="outlinestyle"></a>

### `outlineStyle`

note

`outlineStyle` is only available on the [New Architecture](../architecture/landing-page.md)

Sets the style of an element's outline. See [web documentation](https://developer.mozilla.org/en-US/docs/Web/CSS/outline-style) for more details.

| Type                                    |
| --------------------------------------- |
| enum(`'solid'`, `'dotted'`, `'dashed'`) |

***

<a id="outlinewidth"></a>

### `outlineWidth`

note

`outlineWidth` is only available on the [New Architecture](../architecture/landing-page.md)

The width of an outline which is drawn around an element, outside the border. Does not affect layout. See [web documentation](https://developer.mozilla.org/en-US/docs/Web/CSS/outline-width) for more details.

| Type   |
| ------ |
| number |

***

<a id="pointerevents"></a>

### `pointerEvents`

Controls whether the `View` can be the target of touch events.

* `'auto'`: The View can be the target of touch events.
* `'none'`: The View is never the target of touch events.
* `'box-none'`: The View is never the target of touch events but its subviews can be.
* `'box-only'`: The view can be the target of touch events but its subviews cannot be.

| Type                                                  |
| ----------------------------------------------------- |
| enum(`'auto'`, `'box-none'`, `'box-only'`, `'none'` ) |

## Embedded example source

Code extracted from this page’s Expo Snack embeds; interactive previews require the original website.

### ViewStyleProps

Dependencies: `react-native-safe-area-context`

#### `App.tsx`

```tsx
import {View, StyleSheet} from 'react-native';
import {SafeAreaView, SafeAreaProvider} from 'react-native-safe-area-context';

const App = () => (
  <SafeAreaProvider>
    <SafeAreaView style={styles.container}>
      <View style={styles.top} />
      <View style={styles.middle} />
      <View style={styles.bottom} />
    </SafeAreaView>
  </SafeAreaProvider>
);

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'space-between',
    padding: 20,
    margin: 10,
  },
  top: {
    flex: 0.3,
    backgroundColor: 'grey',
    borderWidth: 5,
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
  },
  middle: {
    flex: 0.3,
    backgroundColor: 'beige',
    borderWidth: 5,
  },
  bottom: {
    flex: 0.3,
    backgroundColor: 'pink',
    borderWidth: 5,
    borderBottomLeftRadius: 20,
    borderBottomRightRadius: 20,
  },
});

export default App;
```
