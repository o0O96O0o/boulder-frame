# Dimensions

Source: https://reactnative.dev/docs/dimensions

Version: 0.87 | Retrieved: 2026-09-07

info

[`useWindowDimensions`](usewindowdimensions.md) is the preferred API for React components. Unlike `Dimensions`, it updates as the window's dimensions update. This works nicely with the React paradigm.

React TSX

```
import {Dimensions} from 'react-native';
```

You can get the application window's width and height using the following code:

React TSX

```
const windowWidth = Dimensions.get('window').width;

const windowHeight = Dimensions.get('window').height;
```

note

Although dimensions are available immediately, they may change (e.g due to device rotation, foldable devices etc) so any rendering logic or styles that depend on these constants should try to call this function on every render, rather than caching the value (for example, using inline styles rather than setting a value in a `StyleSheet`).

If you are targeting foldable devices or devices which can change the screen size or app window size, you can use the event listener available in the Dimensions module as shown in the below example.

<a id="example"></a>

## Example

# Reference

<a id="methods"></a>

## Methods

<a id="addeventlistener"></a>

### `addEventListener()`

React TSX

```
static addEventListener(

  type: 'change',

  handler: ({

    window,

    screen,

  }: DimensionsValue) => void,

): EmitterSubscription;
```

Add an event handler. Supported events:

* `change`: Fires when a property within the `Dimensions` object changes. The argument to the event handler is a [`DimensionsValue`](#dimensionsvalue) type object.

***

<a id="get"></a>

### `get()`

React TSX

```
static get(dim: 'window' | 'screen'): ScaledSize;
```

Initial dimensions are set before `runApplication` is called so they should be available before any other require's are run, but may be updated later.

Example: `const {height, width} = Dimensions.get('window');`

**Parameters:**

| Name        | Type   | Description                                                                       |
| ----------- | ------ | --------------------------------------------------------------------------------- |
| dimRequired | string | Name of dimension as defined when calling `set`. Returns value for the dimension. |

note

For Android the `window` dimension will be reduced by the size of status bar (if not translucent) and bottom navigation bar.

<a id="type-definitions"></a>

## Type Definitions

<a id="dimensionsvalue"></a>

### DimensionsValue

**Properties:**

| Name   | Type                                         | Description                             |
| ------ | -------------------------------------------- | --------------------------------------- |
| window | [ScaledSize](dimensions.md#scaledsize) | Size of the visible Application window. |
| screen | [ScaledSize](dimensions.md#scaledsize) | Size of the device's screen.            |

<a id="scaledsize"></a>

### ScaledSize

| Type   |
| ------ |
| object |

**Properties:**

| Name      | Type   |
| --------- | ------ |
| width     | number |
| height    | number |
| scale     | number |
| fontScale | number |

## Embedded example source

Code extracted from this page’s Expo Snack embeds; interactive previews require the original website.

### Dimensions Example

Dependencies: `react-native-safe-area-context`

#### `App.tsx`

```tsx
import {useState, useEffect} from 'react';
import {
  StyleSheet,
  Text,
  Dimensions,
  type DimensionsPayload,
} from 'react-native';
import {SafeAreaView, SafeAreaProvider} from 'react-native-safe-area-context';

const windowDimensions = Dimensions.get('window');
const screenDimensions = Dimensions.get('screen');

const App = () => {
  const [dimensions, setDimensions] = useState({
    window: windowDimensions,
    screen: screenDimensions,
  });

  useEffect(() => {
    const subscription = Dimensions.addEventListener(
      'change',
      ({window, screen}: DimensionsPayload) => {
        if (window && screen) {
          setDimensions({window, screen});
        }
      },
    );
    return () => subscription?.remove();
  });

  return (
    <SafeAreaProvider>
      <SafeAreaView style={styles.container}>
        <Text style={styles.header}>Window Dimensions</Text>
        {Object.entries(dimensions.window).map(([key, value]) => (
          <Text>
            {key} - {value}
          </Text>
        ))}
        <Text style={styles.header}>Screen Dimensions</Text>
        {Object.entries(dimensions.screen).map(([key, value]) => (
          <Text>
            {key} - {value}
          </Text>
        ))}
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
    fontSize: 16,
    marginVertical: 10,
  },
});

export default App;
```
