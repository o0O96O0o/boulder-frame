# useColorScheme

Source: https://reactnative.dev/docs/usecolorscheme

Version: 0.87 | Retrieved: 2026-09-07

React TSX

```
import {useColorScheme} from 'react-native';
```

The `useColorScheme` React hook provides and subscribes to color scheme updates from the [`Appearance`](appearance.md) module. The return value indicates the active color scheme. The value may be updated later, either through direct user action (e.g. theme selection in device settings or application-level selected user interface style via [`setColorScheme`](appearance.md#setcolorscheme)) or on a schedule (e.g. light and dark themes that follow the day/night cycle).

<a id="return-values"></a>

### Return values

* `'light'`: The light color scheme is applied.
* `'dark'`: The dark color scheme is applied.
* `null`: May be returned if the native Appearance module is not available.

***

<a id="example"></a>

## Example

You can find a complete example that demonstrates the use of this hook alongside a React context to add support for light and dark themes to your application in [`AppearanceExample.js`](https://github.com/facebook/react-native/blob/main/packages/rn-tester/js/examples/Appearance/AppearanceExample.js).

## Embedded example source

Code extracted from this page’s Expo Snack embeds; interactive previews require the original website.

### Example

Dependencies: `react-native-safe-area-context`

#### `App.tsx`

```tsx
import {Text, StyleSheet, useColorScheme} from 'react-native';
import {SafeAreaView, SafeAreaProvider} from 'react-native-safe-area-context';

const App = () => {
  const colorScheme = useColorScheme();
  return (
    <SafeAreaProvider>
      <SafeAreaView style={styles.container}>
        <Text>useColorScheme(): {colorScheme}</Text>
      </SafeAreaView>
    </SafeAreaProvider>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
});

export default App;
```
