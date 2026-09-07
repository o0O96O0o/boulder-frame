# StatusBar

Source: https://reactnative.dev/docs/statusbar

Version: 0.87 | Retrieved: 2026-09-07

Component to control the app's status bar. The status bar is the zone, typically at the top of the screen, that displays the current time, Wi-Fi and cellular network information, battery level and/or other status icons.

<a id="usage-with-navigator"></a>

### Usage with Navigator

It is possible to have multiple `StatusBar` components mounted at the same time. The props will be merged in the order the `StatusBar` components were mounted.

* TypeScript
* JavaScript

<a id="imperative-api"></a>

### Imperative API

For cases where using a component is not ideal, there is also an imperative API exposed as static functions on the component. It is however not recommended to use the static API and the component for the same prop because any value set by the static API will get overridden by the one set by the component in the next render.

***

# Reference

<a id="constants"></a>

## Constants

<a id="currentheight-android"></a>

### `currentHeight`Android

The height of the status bar, which includes the notch height, if present.

***

<a id="props"></a>

## Props

<a id="animated"></a>

### `animated`

If the transition between status bar property changes should be animated. Supported for `barStyle` and `hidden` properties.

| Type    | Required | Default |
| ------- | -------- | ------- |
| boolean | No       | `false` |

***

<a id="barstyle"></a>

### `barStyle`

Sets the color of the status bar text.

On Android, this will only have an impact on API versions 23 and above.

| Type                                                | Required | Default     |
| --------------------------------------------------- | -------- | ----------- |
| [StatusBarStyle](statusbar.md#statusbarstyle) | No       | `'default'` |

***

<a id="hidden"></a>

### `hidden`

If the status bar is hidden.

| Type    | Required | Default |
| ------- | -------- | ------- |
| boolean | No       | `false` |

***

<a id="showhidetransition-ios"></a>

### `showHideTransition`iOS

The transition effect when showing and hiding the status bar using the `hidden` prop.

| Type                                                        | Default  |
| ----------------------------------------------------------- | -------- |
| [StatusBarAnimation](statusbar.md#statusbaranimation) | `'fade'` |

<a id="methods"></a>

## Methods

<a id="popstackentry"></a>

### `popStackEntry()`

React TSX

```
static popStackEntry(entry: StatusBarProps);
```

Get and remove the last StatusBar entry from the stack.

**Parameters:**

| Name          | Type | Description                           |
| ------------- | ---- | ------------------------------------- |
| entryRequired | any  | Entry returned from `pushStackEntry`. |

***

<a id="pushstackentry"></a>

### `pushStackEntry()`

React TSX

```
static pushStackEntry(props: StatusBarProps): StatusBarProps;
```

Push a StatusBar entry onto the stack. The return value should be passed to `popStackEntry` when complete.

**Parameters:**

| Name          | Type | Description                                                      |
| ------------- | ---- | ---------------------------------------------------------------- |
| propsRequired | any  | Object containing the StatusBar props to use in the stack entry. |

***

<a id="replacestackentry"></a>

### `replaceStackEntry()`

React TSX

```
static replaceStackEntry(

  entry: StatusBarProps,

  props: StatusBarProps

): StatusBarProps;
```

Replace an existing StatusBar stack entry with new props.

**Parameters:**

| Name          | Type | Description                                                                  |
| ------------- | ---- | ---------------------------------------------------------------------------- |
| entryRequired | any  | Entry returned from `pushStackEntry` to replace.                             |
| propsRequired | any  | Object containing the StatusBar props to use in the replacement stack entry. |

***

<a id="setbarstyle"></a>

### `setBarStyle()`

React TSX

```
static setBarStyle(style: StatusBarStyle, animated?: boolean);
```

Set the status bar style.

**Parameters:**

| Name          | Type                                                | Description               |
| ------------- | --------------------------------------------------- | ------------------------- |
| styleRequired | [StatusBarStyle](statusbar.md#statusbarstyle) | Status bar style to set.  |
| animated      | boolean                                             | Animate the style change. |

***

<a id="sethidden"></a>

### `setHidden()`

React TSX

```
static setHidden(hidden: boolean, animation?: StatusBarAnimation);
```

Show or hide the status bar.

**Parameters:**

| Name           | Type                                                        | Description                                             |
| -------------- | ----------------------------------------------------------- | ------------------------------------------------------- |
| hiddenRequired | boolean                                                     | Hide the status bar.                                    |
| animationiOS   | [StatusBarAnimation](statusbar.md#statusbaranimation) | Animation when changing the status bar hidden property. |

***

<a id="type-definitions"></a>

## Type Definitions

<a id="statusbaranimation"></a>

### StatusBarAnimation

Status bar animation type for transitions on the iOS.

| Type |
| ---- |
| enum |

**Constants:**

| Value     | Type   | Description     |
| --------- | ------ | --------------- |
| `'fade'`  | string | Fade animation  |
| `'slide'` | string | Slide animation |
| `'none'`  | string | No animation    |

***

<a id="statusbarstyle"></a>

### StatusBarStyle

Status bar style type.

| Type |
| ---- |
| enum |

**Constants:**

| Value             | Type   | Description                                                                                                                         |
| ----------------- | ------ | ----------------------------------------------------------------------------------------------------------------------------------- |
| `'default'`       | string | Default status bar style (light for Android, dark for iOS)                                                                          |
| `'auto'`          | string | Automatically picks `light-content` or `dark-content` based on the current color scheme. Updates whenever the color scheme changes. |
| `'light-content'` | string | White texts and icons                                                                                                               |
| `'dark-content'`  | string | Dark texts and icons (requires API>=23 on Android)                                                                                  |

## Embedded example source

Code extracted from this page’s Expo Snack embeds; interactive previews require the original website.

### StatusBar Component Example

Dependencies: `react-native-safe-area-context`

#### `App.js`

```jsx
import {useState} from 'react';
import {
  Button,
  Platform,
  StatusBar,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import {SafeAreaView, SafeAreaProvider} from 'react-native-safe-area-context';

const STYLES = ['default', 'auto', 'dark-content', 'light-content'];
const TRANSITIONS = ['fade', 'slide', 'none'];

const App = () => {
  const [hidden, setHidden] = useState(false);
  const [statusBarStyle, setStatusBarStyle] = useState(STYLES[0]);
  const [statusBarTransition, setStatusBarTransition] = useState(
    TRANSITIONS[0],
  );

  const changeStatusBarVisibility = () => setHidden(!hidden);

  const changeStatusBarStyle = () => {
    const styleId = STYLES.indexOf(statusBarStyle) + 1;
    if (styleId === STYLES.length) {
      setStatusBarStyle(STYLES[0]);
    } else {
      setStatusBarStyle(STYLES[styleId]);
    }
  };

  const changeStatusBarTransition = () => {
    const transition = TRANSITIONS.indexOf(statusBarTransition) + 1;
    if (transition === TRANSITIONS.length) {
      setStatusBarTransition(TRANSITIONS[0]);
    } else {
      setStatusBarTransition(TRANSITIONS[transition]);
    }
  };

  return (
    <SafeAreaProvider>
      <SafeAreaView style={styles.container}>
        <StatusBar
          animated={true}
          barStyle={statusBarStyle}
          showHideTransition={statusBarTransition}
          hidden={hidden}
        />
        <Text style={styles.textStyle}>
          StatusBar Visibility:{'\n'}
          {hidden ? 'Hidden' : 'Visible'}
        </Text>
        <Text style={styles.textStyle}>
          StatusBar Style:{'\n'}
          {statusBarStyle}
        </Text>
        {Platform.OS === 'ios' ? (
          <Text style={styles.textStyle}>
            StatusBar Transition:{'\n'}
            {statusBarTransition}
          </Text>
        ) : null}
        <View style={styles.buttonsContainer}>
          <Button
            title="Toggle StatusBar"
            onPress={changeStatusBarVisibility}
          />
          <Button
            title="Change StatusBar Style"
            onPress={changeStatusBarStyle}
          />
          {Platform.OS === 'ios' ? (
            <Button
              title="Change StatusBar Transition"
              onPress={changeStatusBarTransition}
            />
          ) : null}
        </View>
      </SafeAreaView>
    </SafeAreaProvider>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    backgroundColor: '#ECF0F1',
  },
  buttonsContainer: {
    padding: 10,
  },
  textStyle: {
    textAlign: 'center',
    marginBottom: 8,
  },
});

export default App;
```

### StatusBar Component Example

Dependencies: `react-native-safe-area-context`

#### `App.tsx`

```tsx
import {useState} from 'react';
import {
  Button,
  Platform,
  StatusBar,
  StyleSheet,
  Text,
  View,
  StatusBarStyle,
} from 'react-native';
import {SafeAreaView, SafeAreaProvider} from 'react-native-safe-area-context';

const STYLES = ['default', 'auto', 'dark-content', 'light-content'] as const;
const TRANSITIONS = ['fade', 'slide', 'none'] as const;

const App = () => {
  const [hidden, setHidden] = useState(false);
  const [statusBarStyle, setStatusBarStyle] = useState<StatusBarStyle>(
    STYLES[0],
  );
  const [statusBarTransition, setStatusBarTransition] = useState<
    'fade' | 'slide' | 'none'
  >(TRANSITIONS[0]);

  const changeStatusBarVisibility = () => setHidden(!hidden);

  const changeStatusBarStyle = () => {
    const styleId = STYLES.indexOf(statusBarStyle) + 1;
    if (styleId === STYLES.length) {
      setStatusBarStyle(STYLES[0]);
    } else {
      setStatusBarStyle(STYLES[styleId]);
    }
  };

  const changeStatusBarTransition = () => {
    const transition = TRANSITIONS.indexOf(statusBarTransition) + 1;
    if (transition === TRANSITIONS.length) {
      setStatusBarTransition(TRANSITIONS[0]);
    } else {
      setStatusBarTransition(TRANSITIONS[transition]);
    }
  };

  return (
    <SafeAreaProvider>
      <SafeAreaView style={styles.container}>
        <StatusBar
          animated={true}
          barStyle={statusBarStyle}
          showHideTransition={statusBarTransition}
          hidden={hidden}
        />
        <Text style={styles.textStyle}>
          StatusBar Visibility:{'\n'}
          {hidden ? 'Hidden' : 'Visible'}
        </Text>
        <Text style={styles.textStyle}>
          StatusBar Style:{'\n'}
          {statusBarStyle}
        </Text>
        {Platform.OS === 'ios' ? (
          <Text style={styles.textStyle}>
            StatusBar Transition:{'\n'}
            {statusBarTransition}
          </Text>
        ) : null}
        <View style={styles.buttonsContainer}>
          <Button
            title="Toggle StatusBar"
            onPress={changeStatusBarVisibility}
          />
          <Button
            title="Change StatusBar Style"
            onPress={changeStatusBarStyle}
          />
          {Platform.OS === 'ios' ? (
            <Button
              title="Change StatusBar Transition"
              onPress={changeStatusBarTransition}
            />
          ) : null}
        </View>
      </SafeAreaView>
    </SafeAreaProvider>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    backgroundColor: '#ECF0F1',
  },
  buttonsContainer: {
    padding: 10,
  },
  textStyle: {
    textAlign: 'center',
    marginBottom: 8,
  },
});

export default App;
```
