# Switch

Source: https://reactnative.dev/docs/switch

Version: 0.87 | Retrieved: 2026-09-07

Renders a boolean input.

This is a controlled component that requires an `onValueChange` callback that updates the `value` prop in order for the component to reflect user actions. If the `value` prop is not updated, the component will continue to render the supplied `value` prop instead of the expected result of any user actions.

<a id="example"></a>

## Example

***

# Reference

<a id="props"></a>

## Props

<a id="view-props"></a>

### [View Props](view.md#props)

Inherits [View Props](view.md#props).

***

<a id="disabled"></a>

### `disabled`

If true the user won't be able to toggle the switch.

| Type | Default |
| ---- | ------- |
| bool | `false` |

***

<a id="ios_backgroundcolor-ios"></a>

### `ios_backgroundColor`iOS

On iOS, custom color for the background. This background color can be seen either when the switch value is `false` or when the switch is disabled (and the switch is translucent).

| Type                     |
| ------------------------ |
| [color](colors.md) |

***

<a id="onchange"></a>

### `onChange`

Invoked when the user tries to change the value of the switch. Receives the change event as an argument. If you want to only receive the new value, use `onValueChange` instead.

| Type     |
| -------- |
| function |

***

<a id="onvaluechange"></a>

### `onValueChange`

Invoked when the user tries to change the value of the switch. Receives the new value as an argument. If you want to instead receive an event, use `onChange`.

| Type     |
| -------- |
| function |

***

<a id="ref"></a>

### `ref`

A ref setter that will be assigned an [element node](element-nodes.md) when mounted.

***

<a id="thumbcolor"></a>

### `thumbColor`

Color of the foreground switch grip. If this is set on iOS, the switch grip will lose its drop shadow.

| Type                     |
| ------------------------ |
| [color](colors.md) |

***

<a id="trackcolor"></a>

### `trackColor`

Custom colors for the switch track.

*iOS*: When the switch value is `false`, the track shrinks into the border. If you want to change the color of the background exposed by the shrunken track, use [`ios_backgroundColor`](https://reactnative.dev/docs/switch#ios_backgroundColor).

| Type                                  |
| ------------------------------------- |
| `object: {false: color, true: color}` |

***

<a id="value"></a>

### `value`

The value of the switch. If true the switch will be turned on. Default value is false.

| Type |
| ---- |
| bool |

## Embedded example source

Code extracted from this page’s Expo Snack embeds; interactive previews require the original website.

### Switch

Dependencies: `react-native-safe-area-context`

#### `App.tsx`

```tsx
import {useState} from 'react';
import {Switch, StyleSheet} from 'react-native';
import {SafeAreaView, SafeAreaProvider} from 'react-native-safe-area-context';

const App = () => {
  const [isEnabled, setIsEnabled] = useState(false);
  const toggleSwitch = () => setIsEnabled(previousState => !previousState);

  return (
    <SafeAreaProvider>
      <SafeAreaView style={styles.container}>
        <Switch
          trackColor={{false: '#767577', true: '#81b0ff'}}
          thumbColor={isEnabled ? '#f5dd4b' : '#f4f3f4'}
          ios_backgroundColor="#3e3e3e"
          onValueChange={toggleSwitch}
          value={isEnabled}
        />
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
