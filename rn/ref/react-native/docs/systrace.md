# Systrace

Source: https://reactnative.dev/docs/systrace

Version: 0.87 | Retrieved: 2026-09-07

`Systrace` is a standard Android marker-based profiling tool (and is installed when you install the Android platform-tools package). Profiled code blocks are surrounded by start/end markers which are then visualized in a colorful chart format. Both the Android SDK and React Native framework provide standard markers that you can visualize.

<a id="example"></a>

## Example

`Systrace` allows you to mark JavaScript (JS) events with a tag and an integer value. Capture the non-Timed JS events in EasyProfiler.

***

# Reference

<a id="methods"></a>

## Methods

<a id="isenabled"></a>

### `isEnabled()`

React TSX

```
static isEnabled(): boolean;
```

***

<a id="beginevent"></a>

### `beginEvent()`

React TSX

```
static beginEvent(eventName: string | (() => string), args?: EventArgs);
```

beginEvent/endEvent for starting and then ending a profile within the same call stack frame.

***

<a id="endevent"></a>

### `endEvent()`

React TSX

```
static endEvent(args?: EventArgs);
```

***

<a id="beginasyncevent"></a>

### `beginAsyncEvent()`

React TSX

```
static beginAsyncEvent(

  eventName: string | (() => string),

  args?: EventArgs,

): number;
```

beginAsyncEvent/endAsyncEvent for starting and then ending a profile where the end can either occur on another thread or out of the current stack frame, eg await the returned cookie variable should be used as input into the endAsyncEvent call to end the profile.

***

<a id="endasyncevent"></a>

### `endAsyncEvent()`

React TSX

```
static endAsyncEvent(

  eventName: EventName,

  cookie: number,

  args?: EventArgs,

);
```

***

<a id="counterevent"></a>

### `counterEvent()`

React TSX

```
static counterEvent(eventName: string | (() => string), value: number);
```

Register the value to the profileName on the systrace timeline.

## Embedded example source

Code extracted from this page’s Expo Snack embeds; interactive previews require the original website.

### Systrace Example

Dependencies: `react-native-safe-area-context`

#### `App.tsx`

```tsx
import {Button, Text, View, StyleSheet, Systrace} from 'react-native';
import {SafeAreaView, SafeAreaProvider} from 'react-native-safe-area-context';

const App = () => {
  const enableProfiling = () => {
    Systrace.setEnabled(true); // Call setEnabled to turn on the profiling.
    Systrace.beginEvent('event_label');
    Systrace.counterEvent('event_label', 10);
  };

  const stopProfiling = () => {
    Systrace.endEvent();
  };

  return (
    <SafeAreaProvider>
      <SafeAreaView style={styles.container}>
        <Text style={[styles.header, styles.paragraph]}>
          React Native Systrace API
        </Text>
        <View style={styles.buttonsColumn}>
          <Button
            title="Capture the non-Timed JS events in EasyProfiler"
            onPress={() => enableProfiling()}
          />
          <Button
            title="Stop capturing"
            onPress={() => stopProfiling()}
            color="#FF0000"
          />
        </View>
      </SafeAreaView>
    </SafeAreaProvider>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#fff',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 8,
    gap: 16,
  },
  header: {
    fontSize: 18,
    fontWeight: 'bold',
    textAlign: 'center',
  },
  paragraph: {
    fontSize: 25,
    textAlign: 'center',
  },
  buttonsColumn: {
    gap: 16,
  },
});

export default App;
```
