# KeyboardAvoidingView

Source: https://reactnative.dev/docs/keyboardavoidingview

Version: 0.87 | Retrieved: 2026-09-07

This component will automatically adjust its height, position, or bottom padding based on the keyboard height to remain visible while the virtual keyboard is displayed.

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

<a id="behavior"></a>

### `behavior`

Specify how to react to the presence of the keyboard.

note

Android and iOS both interact with this prop differently. On both iOS and Android, setting `behavior` is recommended.

| Type                                        |
| ------------------------------------------- |
| enum(`'height'`, `'position'`, `'padding'`) |

***

<a id="contentcontainerstyle"></a>

### `contentContainerStyle`

The style of the content container (View) when behavior is `'position'`.

| Type                                    |
| --------------------------------------- |
| [View Style](view-style-props.md) |

***

<a id="enabled"></a>

### `enabled`

Enabled or disabled KeyboardAvoidingView.

| Type    | Default |
| ------- | ------- |
| boolean | `true`  |

***

<a id="keyboardverticaloffset"></a>

### `keyboardVerticalOffset`

This is the distance between the top of the user screen and the react native view, may be non-zero in some use cases.

| Type   | Default |
| ------ | ------- |
| number | `0`     |

## Embedded example source

Code extracted from this page’s Expo Snack embeds; interactive previews require the original website.

### KeyboardAvoidingView

Dependencies: `react-native-safe-area-context`

#### `App.tsx`

```tsx
import {
  View,
  KeyboardAvoidingView,
  TextInput,
  StyleSheet,
  Text,
  Platform,
  TouchableWithoutFeedback,
  Button,
  Keyboard,
} from 'react-native';

const KeyboardAvoidingComponent = () => {
  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      style={styles.container}>
      <TouchableWithoutFeedback onPress={Keyboard.dismiss}>
        <View style={styles.inner}>
          <Text style={styles.header}>Header</Text>
          <TextInput placeholder="Username" style={styles.textInput} />
          <View style={styles.btnContainer}>
            <Button title="Submit" onPress={() => null} />
          </View>
        </View>
      </TouchableWithoutFeedback>
    </KeyboardAvoidingView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  inner: {
    padding: 24,
    flex: 1,
    justifyContent: 'space-around',
  },
  header: {
    fontSize: 36,
    marginBottom: 48,
  },
  textInput: {
    height: 40,
    borderColor: '#000000',
    borderBottomWidth: 1,
    marginBottom: 36,
  },
  btnContainer: {
    backgroundColor: 'white',
    marginTop: 12,
  },
});

export default KeyboardAvoidingComponent;
```
