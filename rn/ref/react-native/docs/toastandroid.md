# ToastAndroid

Source: https://reactnative.dev/docs/toastandroid

Version: 0.87 | Retrieved: 2026-09-07

React Native's ToastAndroid API exposes the Android platform's ToastAndroid module as a JS module. It provides the method `show(message, duration)` which takes the following parameters:

* *message* A string with the text to toast
* *duration* The duration of the toast—either `ToastAndroid.SHORT` or `ToastAndroid.LONG`

You can alternatively use `showWithGravity(message, duration, gravity)` to specify where the toast appears in the screen's layout. May be `ToastAndroid.TOP`, `ToastAndroid.BOTTOM` or `ToastAndroid.CENTER`.

The `showWithGravityAndOffset(message, duration, gravity, xOffset, yOffset)` method adds the ability to specify an offset with in pixels.

note

Starting with Android 11 (API level 30), setting the gravity has no effect on text toasts. Read about the changes [here](https://developer.android.com/about/versions/11/behavior-changes-11#text-toast-api-changes).

***

# Reference

<a id="methods"></a>

## Methods

<a id="show"></a>

### `show()`

React TSX

```
static show(message: string, duration: number);
```

***

<a id="showwithgravity"></a>

### `showWithGravity()`

This property will only work on Android API 29 and below. For similar functionality on higher Android APIs, consider using snackbar or notification.

React TSX

```
static showWithGravity(message: string, duration: number, gravity: number);
```

***

<a id="showwithgravityandoffset"></a>

### `showWithGravityAndOffset()`

This property will only work on Android API 29 and below. For similar functionality on higher Android APIs, consider using snackbar or notification.

React TSX

```
static showWithGravityAndOffset(

  message: string,

  duration: number,

  gravity: number,

  xOffset: number,

  yOffset: number,

);
```

<a id="properties"></a>

## Properties

<a id="short"></a>

### `SHORT`

Indicates the duration on the screen.

React TSX

```
static SHORT: number;
```

***

<a id="long"></a>

### `LONG`

Indicates the duration on the screen.

React TSX

```
static LONG: number;
```

***

<a id="top"></a>

### `TOP`

Indicates the position on the screen.

React TSX

```
static TOP: number;
```

***

<a id="bottom"></a>

### `BOTTOM`

Indicates the position on the screen.

React TSX

```
static BOTTOM: number;
```

***

<a id="center"></a>

### `CENTER`

Indicates the position on the screen.

React TSX

```
static CENTER: number;
```

## Embedded example source

Code extracted from this page’s Expo Snack embeds; interactive previews require the original website.

### Toast Android API Example

Dependencies: `react-native-safe-area-context`

#### `App.tsx`

```tsx
import {StyleSheet, ToastAndroid, Button, StatusBar} from 'react-native';
import {SafeAreaView, SafeAreaProvider} from 'react-native-safe-area-context';

const App = () => {
  const showToast = () => {
    ToastAndroid.show('A pikachu appeared nearby !', ToastAndroid.SHORT);
  };

  const showToastWithGravity = () => {
    ToastAndroid.showWithGravity(
      'All Your Base Are Belong To Us',
      ToastAndroid.SHORT,
      ToastAndroid.CENTER,
    );
  };

  const showToastWithGravityAndOffset = () => {
    ToastAndroid.showWithGravityAndOffset(
      'A wild toast appeared!',
      ToastAndroid.LONG,
      ToastAndroid.BOTTOM,
      25,
      50,
    );
  };

  return (
    <SafeAreaProvider>
      <SafeAreaView style={styles.container}>
        <Button title="Toggle Toast" onPress={() => showToast()} />
        <Button
          title="Toggle Toast With Gravity"
          onPress={() => showToastWithGravity()}
        />
        <Button
          title="Toggle Toast With Gravity & Offset"
          onPress={() => showToastWithGravityAndOffset()}
        />
      </SafeAreaView>
    </SafeAreaProvider>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    paddingTop: StatusBar.currentHeight,
    backgroundColor: '#888888',
    padding: 8,
  },
});

export default App;
```
