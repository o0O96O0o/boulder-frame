# TouchableOpacity

Source: https://reactnative.dev/docs/touchableopacity

Version: 0.87 | Retrieved: 2026-09-07

tip

If you're looking for a more extensive and future-proof way to handle touch-based input, check out the [Pressable](pressable.md) API.

A wrapper for making views respond properly to touches. On press down, the opacity of the wrapped view is decreased, dimming it.

Opacity is controlled by wrapping the children in an `Animated.View`, which is added to the view hierarchy. Be aware that this can affect layout.

<a id="example"></a>

## Example

***

# Reference

<a id="props"></a>

## Props

<a id="touchablewithoutfeedback-props"></a>

### [TouchableWithoutFeedback Props](touchablewithoutfeedback.md#props)

Inherits [TouchableWithoutFeedback Props](touchablewithoutfeedback.md#props).

***

<a id="style"></a>

### `style`

| Type                                    |
| --------------------------------------- |
| [View.style](view-style-props.md) |

***

<a id="activeopacity"></a>

### `activeOpacity`

Determines what the opacity of the wrapped view should be when touch is active. Defaults to `0.2`.

| Type   |
| ------ |
| number |

***

<a id="hastvpreferredfocus-ios"></a>

### `hasTVPreferredFocus`iOS

*(Apple TV only)* TV preferred focus (see documentation for the View component).

| Type |
| ---- |
| bool |

***

<a id="nextfocusdown-android"></a>

### `nextFocusDown`Android

TV next focus down (see documentation for the View component).

| Type   |
| ------ |
| number |

***

<a id="nextfocusforward-android"></a>

### `nextFocusForward`Android

TV next focus forward (see documentation for the View component).

| Type   |
| ------ |
| number |

***

<a id="nextfocusleft-android"></a>

### `nextFocusLeft`Android

TV next focus left (see documentation for the View component).

| Type   |
| ------ |
| number |

***

<a id="nextfocusright-android"></a>

### `nextFocusRight`Android

TV next focus right (see documentation for the View component).

| Type   |
| ------ |
| number |

***

<a id="nextfocusup-android"></a>

### `nextFocusUp`Android

TV next focus up (see documentation for the View component).

| Type   |
| ------ |
| number |

***

<a id="ref"></a>

### `ref`

A ref setter that will be assigned an [element node](element-nodes.md) when mounted.

## Embedded example source

Code extracted from this page’s Expo Snack embeds; interactive previews require the original website.

### TouchableOpacity Example

Dependencies: `react-native-safe-area-context`

#### `App.tsx`

```tsx
import {useState} from 'react';
import {StyleSheet, Text, TouchableOpacity, View} from 'react-native';
import {SafeAreaView, SafeAreaProvider} from 'react-native-safe-area-context';

const App = () => {
  const [count, setCount] = useState(0);
  const onPress = () => setCount(prevCount => prevCount + 1);

  return (
    <SafeAreaProvider>
      <SafeAreaView style={styles.container}>
        <View style={styles.countContainer}>
          <Text>Count: {count}</Text>
        </View>
        <TouchableOpacity style={styles.button} onPress={onPress}>
          <Text>Press Here</Text>
        </TouchableOpacity>
      </SafeAreaView>
    </SafeAreaProvider>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    paddingHorizontal: 10,
  },
  button: {
    alignItems: 'center',
    backgroundColor: '#DDDDDD',
    padding: 10,
  },
  countContainer: {
    alignItems: 'center',
    padding: 10,
  },
});

export default App;
```
