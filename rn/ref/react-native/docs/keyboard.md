# Keyboard

Source: https://reactnative.dev/docs/keyboard

Version: 0.87 | Retrieved: 2026-09-07

`Keyboard` module to control keyboard events.

<a id="usage"></a>

### Usage

The Keyboard module allows you to listen for native events and react to them, as well as make changes to the keyboard, like dismissing it.

***

# Reference

<a id="methods"></a>

## Methods

<a id="addlistener"></a>

### `addListener()`

React TSX

```
static addListener: (

  eventType: KeyboardEventName,

  listener: KeyboardEventListener,

) => EmitterSubscription;
```

The `addListener` function connects a JavaScript function to an identified native keyboard notification event.

This function then returns the reference to the listener.

**Parameters:**

| Name              | Type     | Description                                                                    |
| ----------------- | -------- | ------------------------------------------------------------------------------ |
| eventNameRequired | string   | The string that identifies the event you're listening for. See the list below. |
| callbackRequired  | function | The function to be called when the event fires                                 |

**`eventName`**

This can be any of the following:

* `keyboardWillShow`
* `keyboardDidShow`
* `keyboardWillHide`
* `keyboardDidHide`
* `keyboardWillChangeFrame`
* `keyboardDidChangeFrame`

note

Only `keyboardDidShow` and `keyboardDidHide` events are available on Android. The events will not be fired when using Android 10 or below if your activity has `android:windowSoftInputMode` set to `adjustResize` or `adjustNothing`.

***

<a id="dismiss"></a>

### `dismiss()`

React TSX

```
static dismiss();
```

Dismisses the active keyboard and removes focus.

***

<a id="schedulelayoutanimation"></a>

### `scheduleLayoutAnimation`

React TSX

```
static scheduleLayoutAnimation(event: KeyboardEvent);
```

Useful for syncing TextInput (or other keyboard accessory view) size of position changes with keyboard movements.

***

<a id="isvisible"></a>

### `isVisible()`

React TSX

```
static isVisible(): boolean;
```

Whether the keyboard is last known to be visible.

***

<a id="metrics"></a>

### `metrics()`

React TSX

```
static metrics(): KeyboardMetrics | undefined;
```

Return the metrics of the soft-keyboard if visible.

## Embedded example source

Code extracted from this page’s Expo Snack embeds; interactive previews require the original website.

### Keyboard Example

Dependencies: `react-native-safe-area-context`

#### `App.tsx`

```tsx
import {useState, useEffect} from 'react';
import {Keyboard, Text, TextInput, StyleSheet} from 'react-native';
import {SafeAreaView, SafeAreaProvider} from 'react-native-safe-area-context';

const Example = () => {
  const [keyboardStatus, setKeyboardStatus] = useState('Keyboard Hidden');

  useEffect(() => {
    const showSubscription = Keyboard.addListener('keyboardDidShow', () => {
      setKeyboardStatus('Keyboard Shown');
    });
    const hideSubscription = Keyboard.addListener('keyboardDidHide', () => {
      setKeyboardStatus('Keyboard Hidden');
    });

    return () => {
      showSubscription.remove();
      hideSubscription.remove();
    };
  }, []);

  return (
    <SafeAreaProvider>
      <SafeAreaView style={style.container}>
        <TextInput
          style={style.input}
          placeholder="Click here…"
          onSubmitEditing={Keyboard.dismiss}
        />
        <Text style={style.status}>{keyboardStatus}</Text>
      </SafeAreaView>
    </SafeAreaProvider>
  );
};

const style = StyleSheet.create({
  container: {
    flex: 1,
    padding: 36,
  },
  input: {
    padding: 10,
    borderWidth: 0.5,
    borderRadius: 4,
  },
  status: {
    padding: 16,
    textAlign: 'center',
  },
});

export default Example;
```
