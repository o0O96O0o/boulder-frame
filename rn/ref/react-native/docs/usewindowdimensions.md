# useWindowDimensions

Source: https://reactnative.dev/docs/usewindowdimensions

Version: 0.87 | Retrieved: 2026-09-07

React TSX

```
import {useWindowDimensions} from 'react-native';
```

`useWindowDimensions` automatically updates all of its values when screen size or font scale changes. You can get your application window's width and height like so:

React TSX

```
const {height, width} = useWindowDimensions();
```

<a id="example"></a>

## Example

<a id="properties"></a>

## Properties

<a id="fontscale"></a>

### `fontScale`

React TSX

```
useWindowDimensions().fontScale;
```

The scale of the font currently used. Some operating systems allow users to scale their font sizes larger or smaller for reading comfort. This property will let you know what is in effect.

***

<a id="height"></a>

### `height`

React TSX

```
useWindowDimensions().height;
```

The height in pixels of the window or screen your app occupies.

***

<a id="scale"></a>

### `scale`

React TSX

```
useWindowDimensions().scale;
```

The pixel ratio of the device your app is running on. The values can be:

* `1` which indicates that one point equals one pixel (usually PPI/DPI of 96, 76 on some platforms).
* `2` or `3` which indicates a Retina or high DPI display.

***

<a id="width"></a>

### `width`

React TSX

```
useWindowDimensions().width;
```

The width in pixels of the window or screen your app occupies.

## Embedded example source

Code extracted from this page’s Expo Snack embeds; interactive previews require the original website.

### useWindowDimensions

Dependencies: `react-native-safe-area-context`

#### `App.tsx`

```tsx
import {StyleSheet, Text, useWindowDimensions} from 'react-native';
import {SafeAreaView, SafeAreaProvider} from 'react-native-safe-area-context';

const App = () => {
  const {height, width, scale, fontScale} = useWindowDimensions();
  return (
    <SafeAreaProvider>
      <SafeAreaView style={styles.container}>
        <Text style={styles.header}>Window Dimension Data</Text>
        <Text>Height: {height}</Text>
        <Text>Width: {width}</Text>
        <Text>Font scale: {fontScale}</Text>
        <Text>Pixel ratio: {scale}</Text>
      </SafeAreaView>
    </SafeAreaProvider>
  );
};
const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  header: {
    fontSize: 20,
    marginBottom: 12,
  },
});

export default App;
```
