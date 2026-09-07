# ActivityIndicator

Source: https://reactnative.dev/docs/activityindicator

Version: 0.87 | Retrieved: 2026-09-07

Displays a circular loading indicator.

<a id="example"></a>

## Example

# Reference

<a id="props"></a>

## Props

<a id="view-props"></a>

### [View Props](view.md#props)

Inherits [View Props](view.md#props).

***

<a id="animating"></a>

### `animating`

Whether to show the indicator (`true`) or hide it (`false`).

| Type | Default |
| ---- | ------- |
| bool | `true`  |

***

<a id="color"></a>

### `color`

The foreground color of the spinner.

| Type                     | Default                                                      |
| ------------------------ | ------------------------------------------------------------ |
| [color](colors.md) | `null` (system accent default color)Android***`'#999999'`iOS |

***

<a id="hideswhenstopped-ios"></a>

### `hidesWhenStopped`iOS

Whether the indicator should hide when not animating.

| Type | Default |
| ---- | ------- |
| bool | `true`  |

***

<a id="ref"></a>

### `ref`

A ref setter that will be assigned an [element node](element-nodes.md) when mounted.

***

<a id="size"></a>

### `size`

Size of the indicator.

| Type                                       | Default   |
| ------------------------------------------ | --------- |
| enum(`'small'`, `'large'`)***numberAndroid | `'small'` |

## Embedded example source

Code extracted from this page’s Expo Snack embeds; interactive previews require the original website.

### ActivityIndicator Example

Dependencies: `react-native-safe-area-context`

#### `App.tsx`

```tsx
import {ActivityIndicator, StyleSheet} from 'react-native';
import {SafeAreaView, SafeAreaProvider} from 'react-native-safe-area-context';

const App = () => (
  <SafeAreaProvider>
    <SafeAreaView style={[styles.container, styles.horizontal]}>
      <ActivityIndicator />
      <ActivityIndicator size="large" />
      <ActivityIndicator size="small" color="#0000ff" />
      <ActivityIndicator size="large" color="#00ff00" />
    </SafeAreaView>
  </SafeAreaProvider>
);

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
  },
  horizontal: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    padding: 10,
  },
});

export default App;
```
