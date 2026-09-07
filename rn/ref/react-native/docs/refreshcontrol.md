# RefreshControl

Source: https://reactnative.dev/docs/refreshcontrol

Version: 0.87 | Retrieved: 2026-09-07

This component is used inside a ScrollView or ListView to add pull to refresh functionality. When the ScrollView is at `scrollY: 0`, swiping down triggers an `onRefresh` event.

<a id="example"></a>

## Example

note

`refreshing` is a controlled prop, this is why it needs to be set to `true` in the `onRefresh` function otherwise the refresh indicator will stop immediately.

***

# Reference

<a id="props"></a>

## Props

<a id="view-props"></a>

### [View Props](view.md#props)

Inherits [View Props](view.md#props).

***

<a id="requiredrefreshing"></a>

### Require&#x64;**`refreshing`**

Whether the view should be indicating an active refresh.

| Type    |
| ------- |
| boolean |

***

<a id="colors-android"></a>

### `colors`Android

The colors (at least one) that will be used to draw the refresh indicator.

| Type                               |
| ---------------------------------- |
| array of [colors](colors.md) |

***

<a id="enabled-android"></a>

### `enabled`Android

Whether the pull to refresh functionality is enabled.

| Type    | Default |
| ------- | ------- |
| boolean | `true`  |

***

<a id="onrefresh"></a>

### `onRefresh`

Called when the view starts refreshing.

| Type     |
| -------- |
| function |

***

<a id="progressbackgroundcolor-android"></a>

### `progressBackgroundColor`Android

The background color of the refresh indicator.

| Type                     |
| ------------------------ |
| [color](colors.md) |

***

<a id="progressviewoffset"></a>

### `progressViewOffset`

Progress view top offset.

| Type   | Default |
| ------ | ------- |
| number | `0`     |

***

<a id="size-android"></a>

### `size`Android

Size of the refresh indicator.

| Type                         | Default     |
| ---------------------------- | ----------- |
| enum(`'default'`, `'large'`) | `'default'` |

***

<a id="tintcolor-ios"></a>

### `tintColor`iOS

The color of the refresh indicator.

| Type                     |
| ------------------------ |
| [color](colors.md) |

***

<a id="title-ios"></a>

### `title`iOS

The title displayed under the refresh indicator.

| Type   |
| ------ |
| string |

***

<a id="titlecolor-ios"></a>

### `titleColor`iOS

The color of the refresh indicator title.

| Type                     |
| ------------------------ |
| [color](colors.md) |

## Embedded example source

Code extracted from this page’s Expo Snack embeds; interactive previews require the original website.

### RefreshControl

Dependencies: `react-native-safe-area-context`

#### `App.tsx`

```tsx
import {useCallback, useState} from 'react';
import {RefreshControl, ScrollView, StyleSheet, Text} from 'react-native';
import {SafeAreaView, SafeAreaProvider} from 'react-native-safe-area-context';

const App = () => {
  const [refreshing, setRefreshing] = useState(false);

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    setTimeout(() => {
      setRefreshing(false);
    }, 2000);
  }, []);

  return (
    <SafeAreaProvider>
      <SafeAreaView style={styles.container}>
        <ScrollView
          contentContainerStyle={styles.scrollView}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
          }>
          <Text>Pull down to see RefreshControl indicator</Text>
        </ScrollView>
      </SafeAreaView>
    </SafeAreaProvider>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  scrollView: {
    flex: 1,
    backgroundColor: 'pink',
    alignItems: 'center',
    justifyContent: 'center',
  },
});

export default App;
```
