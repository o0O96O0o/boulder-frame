# 🗑️ SafeAreaView

Source: https://reactnative.dev/docs/safeareaview

Version: 0.87 | Retrieved: 2026-09-07

Deprecated

Use [react-native-safe-area-context](https://github.com/AppAndFlow/react-native-safe-area-context) instead.

The purpose of `SafeAreaView` is to render content within the safe area boundaries of a device. It is currently only applicable to iOS devices with iOS version 11 or later.

`SafeAreaView` renders nested content and automatically applies padding to reflect the portion of the view that is not covered by navigation bars, tab bars, toolbars, and other ancestor views. Moreover, and most importantly, Safe Area's paddings reflect the physical limitation of the screen, such as rounded corners or camera notches (i.e. the sensor housing area on iPhone 13).

<a id="example"></a>

## Example

To use, wrap your top level view with a `SafeAreaView` with a `flex: 1` style applied to it. You may also want to use a background color that matches your application's design.

***

# Reference

<a id="props"></a>

## Props

<a id="view-props"></a>

### [View Props](view.md#props)

Inherits [View Props](view.md#props).

note

As padding is used to implement the behavior of the component, padding rules in styles applied to a `SafeAreaView` will be ignored and can cause different results depending on the platform. See [#22211](https://github.com/facebook/react-native/issues/22211) for details.

## Embedded example source

Code extracted from this page’s Expo Snack embeds; interactive previews require the original website.

### SafeAreaView

Dependencies: `react-native-safe-area-context`

#### `App.tsx`

```tsx
import {StyleSheet, Text, SafeAreaView} from 'react-native';

const App = () => {
  return (
    <SafeAreaView style={styles.container}>
      <Text style={styles.text}>Page content</Text>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  text: {
    fontSize: 25,
    fontWeight: '500',
  },
});

export default App;
```
