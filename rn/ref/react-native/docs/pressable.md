# Pressable

Source: https://reactnative.dev/docs/pressable

Version: 0.87 | Retrieved: 2026-09-07

Pressable is a Core Component wrapper that can detect various stages of press interactions on any of its defined children.

React TSX

```
<Pressable onPress={onPressFunction}>

  <Text>I'm pressable!</Text>

</Pressable>
```

<a id="how-it-works"></a>

## How it works

On an element wrapped by `Pressable`:

* [`onPressIn`](#onpressin) is called when a press is activated.
* [`onPressOut`](#onpressout) is called when the press gesture is deactivated.

After pressing [`onPressIn`](#onpressin), one of two things will happen:

1. The person will remove their finger, triggering [`onPressOut`](#onpressout) followed by [`onPress`](#onpress).
2. If the person leaves their finger longer than 500 milliseconds before removing it, [`onLongPress`](#onlongpress) is triggered. ([`onPressOut`](#onpressout) will still fire when they remove their finger.)

![Diagram of the onPress events in sequence.](https://reactnative.dev/docs/assets/d_pressable_pressing.svg)

Fingers are not the most precise instruments, and it is common for users to accidentally activate the wrong element or miss the activation area. To help, `Pressable` has an optional `HitRect` you can use to define how far a touch can register away from the wrapped element. Presses can start anywhere within a `HitRect`.

`PressRect` allows presses to move beyond the element and its `HitRect` while maintaining activation and being eligible for a "press"—think of sliding your finger slowly away from a button you're pressing down on.

note

The touch area never extends past the parent view bounds and the Z-index of sibling views always takes precedence if a touch hits two overlapping views.

![Diagram of HitRect and PressRect and how they work.](https://reactnative.dev/docs/assets/d_pressable_anatomy.svg)

You can set `HitRect` with `hitSlop` and set `PressRect` with `pressRetentionOffset`.

info

`Pressable` uses React Native's `Pressability` API. For more information around the state machine flow of Pressability and how it works, check out the implementation for [Pressability](https://github.com/facebook/react-native/blob/main/packages/react-native/Libraries/Pressability/Pressability.js#L350).

<a id="example"></a>

## Example

<a id="props"></a>

## Props

<a id="android_disablesound-android"></a>

### `android_disableSound`Android

If true, doesn't play Android system sound on press.

| Type    | Default |
| ------- | ------- |
| boolean | `false` |

<a id="android_ripple-android"></a>

### `android_ripple`Android

Enables the Android ripple effect and configures its properties. The `color` field accepts both plain colors and [`PlatformColor`](platformcolor.md) values, so you can reference theme attributes like `?attr/colorAccent`. When a `PlatformColor` is used, the ripple is automatically updated when the system configuration changes (for example, when switching between light and dark mode).

| Type                                            |
| ----------------------------------------------- |
| [RippleConfig](pressable.md#rippleconfig) |

<a id="children"></a>

### `children`

Either children or a function that receives a boolean reflecting whether the component is currently pressed.

| Type                              |
| --------------------------------- |
| [React Node](react-node.md) |

<a id="unstable_pressdelay"></a>

### `unstable_pressDelay`

Duration (in milliseconds) to wait after press down before calling `onPressIn`.

| Type   |
| ------ |
| number |

<a id="delaylongpress"></a>

### `delayLongPress`

Duration (in milliseconds) from `onPressIn` before `onLongPress` is called.

| Type   | Default |
| ------ | ------- |
| number | `500`   |

<a id="disabled"></a>

### `disabled`

Whether the press behavior is disabled.

| Type    | Default |
| ------- | ------- |
| boolean | `false` |

<a id="hitslop"></a>

### `hitSlop`

Sets additional distance outside of element in which a press can be detected.

| Type                            |
| ------------------------------- |
| [Rect](rect.md) or number |

<a id="onhoverin"></a>

### `onHoverIn`

Called when the hover is activated to provide visual feedback.

| Type                                    |
| --------------------------------------- |
| `({ nativeEvent: MouseEvent }) => void` |

<a id="onhoverout"></a>

### `onHoverOut`

Called when the hover is deactivated to undo visual feedback.

| Type                                    |
| --------------------------------------- |
| `({ nativeEvent: MouseEvent }) => void` |

<a id="onlongpress"></a>

### `onLongPress`

Called if the time after `onPressIn` lasts longer than 500 milliseconds. This time period can be customized with [`delayLongPress`](#delaylongpress).

| Type                                  |
| ------------------------------------- |
| `({nativeEvent: PressEvent}) => void` |

<a id="onpress"></a>

### `onPress`

Called after `onPressOut`.

| Type                                  |
| ------------------------------------- |
| `({nativeEvent: PressEvent}) => void` |

<a id="onpressin"></a>

### `onPressIn`

Called immediately when a touch is engaged, before `onPressOut` and `onPress`.

| Type                                  |
| ------------------------------------- |
| `({nativeEvent: PressEvent}) => void` |

<a id="onpressmove"></a>

### `onPressMove`

Called when the press location moves.

| Type                                  |
| ------------------------------------- |
| `({nativeEvent: PressEvent}) => void` |

<a id="onpressout"></a>

### `onPressOut`

Called when a touch is released.

| Type                                  |
| ------------------------------------- |
| `({nativeEvent: PressEvent}) => void` |

<a id="pressretentionoffset"></a>

### `pressRetentionOffset`

Additional distance outside of this view in which a touch is considered a press before `onPressOut` is triggered.

| Type                            | Default                                      |
| ------------------------------- | -------------------------------------------- |
| [Rect](rect.md) or number | `{bottom: 30, left: 20, right: 20, top: 20}` |

<a id="style"></a>

### `style`

Either view styles or a function that receives a boolean reflecting whether the component is currently pressed and returns view styles.

| Type                                                                              |
| --------------------------------------------------------------------------------- |
| [View Style](view-style-props.md) or `({ pressed: boolean }) => View Style` |

<a id="testonly_pressed"></a>

### `testOnly_pressed`

Used only for documentation or testing (e.g. snapshot testing).

| Type    | Default |
| ------- | ------- |
| boolean | `false` |

<a id="type-definitions"></a>

## Type Definitions

<a id="rippleconfig"></a>

### RippleConfig

Ripple effect configuration for the `android_ripple` property.

| Type   |
| ------ |
| object |

**Properties:**

| Name       | Type                                                                | Required | Description                                                                                                                                                                                                                                                  |
| ---------- | ------------------------------------------------------------------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| color      | [color](colors.md) or [PlatformColor](platformcolor.md) | No       | Defines the color of the ripple effect.                                                                                                                                                                                                                      |
| borderless | boolean                                                             | No       | Defines if ripple effect should not include border.                                                                                                                                                                                                          |
| radius     | number                                                              | No       | Defines the radius of the ripple effect.                                                                                                                                                                                                                     |
| foreground | boolean                                                             | No       | Set to true to add the ripple effect to the foreground of the view, instead of the background. This is useful if one of your child views has a background of its own, or you're e.g. displaying images, and you don't want the ripple to be covered by them. |
| alpha      | number                                                              | No       | Controls the opacity of the ripple. Accepts a value between `0.0` (fully transparent) and `1.0` (fully opaque). The value is applied on top of any alpha already present in the color.                                                                       |

## Embedded example source

Code extracted from this page’s Expo Snack embeds; interactive previews require the original website.

### Pressable

Dependencies: `react-native-safe-area-context`

#### `App.tsx`

```tsx
import {useState} from 'react';
import {Pressable, StyleSheet, Text, View} from 'react-native';
import {SafeAreaView, SafeAreaProvider} from 'react-native-safe-area-context';

const App = () => {
  const [timesPressed, setTimesPressed] = useState(0);

  let textLog = '';
  if (timesPressed > 1) {
    textLog = timesPressed + 'x onPress';
  } else if (timesPressed > 0) {
    textLog = 'onPress';
  }

  return (
    <SafeAreaProvider>
      <SafeAreaView style={styles.container}>
        <Pressable
          onPress={() => {
            setTimesPressed(current => current + 1);
          }}
          style={({pressed}) => [
            {
              backgroundColor: pressed ? 'rgb(210, 230, 255)' : 'white',
            },
            styles.wrapperCustom,
          ]}>
          {({pressed}) => (
            <Text style={styles.text}>{pressed ? 'Pressed!' : 'Press Me'}</Text>
          )}
        </Pressable>
        <View style={styles.logBox}>
          <Text testID="pressable_press_console">{textLog}</Text>
        </View>
      </SafeAreaView>
    </SafeAreaProvider>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
  },
  text: {
    fontSize: 16,
  },
  wrapperCustom: {
    borderRadius: 8,
    padding: 6,
  },
  logBox: {
    padding: 20,
    margin: 10,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: '#f0f0f0',
    backgroundColor: '#f9f9f9',
  },
});

export default App;
```
