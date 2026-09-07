# Animated.ValueXY

Source: https://reactnative.dev/docs/animatedvaluexy

Version: 0.87 | Retrieved: 2026-09-07

2D Value for driving 2D animations, such as pan gestures. Almost identical API to normal [`Animated.Value`](animatedvalue.md), but multiplexed. Contains two regular `Animated.Value`s under the hood.

<a id="example"></a>

## Example

***

# Reference

<a id="methods"></a>

## Methods

<a id="setvalue"></a>

### `setValue()`

React TSX

```
setValue(value: {x: number; y: number});
```

Directly set the value. This will stop any animations running on the value and update all the bound properties.

**Parameters:**

| Name  | Type                     | Required | Description |
| ----- | ------------------------ | -------- | ----------- |
| value | `{x: number; y: number}` | Yes      | Value       |

***

<a id="setoffset"></a>

### `setOffset()`

React TSX

```
setOffset(offset: {x: number; y: number});
```

Sets an offset that is applied on top of whatever value is set, whether via `setValue`, an animation, or `Animated.event`. Useful for compensating things like the start of a pan gesture.

**Parameters:**

| Name   | Type                     | Required | Description  |
| ------ | ------------------------ | -------- | ------------ |
| offset | `{x: number; y: number}` | Yes      | Offset value |

***

<a id="flattenoffset"></a>

### `flattenOffset()`

React TSX

```
flattenOffset();
```

Merges the offset value into the base value and resets the offset to zero. The final output of the value is unchanged.

***

<a id="extractoffset"></a>

### `extractOffset()`

React TSX

```
extractOffset();
```

Sets the offset value to the base value, and resets the base value to zero. The final output of the value is unchanged.

***

<a id="addlistener"></a>

### `addListener()`

React TSX

```
addListener(callback: (value: {x: number; y: number}) => void);
```

Adds an asynchronous listener to the value so you can observe updates from animations. This is useful because there is no way to synchronously read the value because it might be driven natively.

Returns a string that serves as an identifier for the listener.

**Parameters:**

| Name     | Type     | Required | Description                                                                                 |
| -------- | -------- | -------- | ------------------------------------------------------------------------------------------- |
| callback | function | Yes      | The callback function which will receive an object with a `value` key set to the new value. |

***

<a id="removelistener"></a>

### `removeListener()`

React TSX

```
removeListener(id: string);
```

Unregister a listener. The `id` param shall match the identifier previously returned by `addListener()`.

**Parameters:**

| Name | Type   | Required | Description                        |
| ---- | ------ | -------- | ---------------------------------- |
| id   | string | Yes      | Id for the listener being removed. |

***

<a id="removealllisteners"></a>

### `removeAllListeners()`

React TSX

```
removeAllListeners();
```

Remove all registered listeners.

***

<a id="stopanimation"></a>

### `stopAnimation()`

React TSX

```
stopAnimation(callback?: (value: {x: number; y: number}) => void);
```

Stops any running animation or tracking. `callback` is invoked with the final value after stopping the animation, which is useful for updating state to match the animation position with layout.

**Parameters:**

| Name     | Type     | Required | Description                                   |
| -------- | -------- | -------- | --------------------------------------------- |
| callback | function | No       | A function that will receive the final value. |

***

<a id="resetanimation"></a>

### `resetAnimation()`

React TSX

```
resetAnimation(callback?: (value: {x: number; y: number}) => void);
```

Stops any animation and resets the value to its original.

**Parameters:**

| Name     | Type     | Required | Description                                      |
| -------- | -------- | -------- | ------------------------------------------------ |
| callback | function | No       | A function that will receive the original value. |

***

<a id="getlayout"></a>

### `getLayout()`

React TSX

```
getLayout(): {left: Animated.Value, top: Animated.Value};
```

Converts `{x, y}` into `{left, top}` for use in style, e.g.

React TSX

```
style={this.state.anim.getLayout()}
```

***

<a id="gettranslatetransform"></a>

### `getTranslateTransform()`

React TSX

```
getTranslateTransform(): [

  {translateX: Animated.Value},

  {translateY: Animated.Value},

];
```

Converts `{x, y}` into a useable translation transform, e.g.

React TSX

```
style={{

  transform: this.state.anim.getTranslateTransform()

}}
```

## Embedded example source

Code extracted from this page’s Expo Snack embeds; interactive previews require the original website.

### Animated.ValueXY Example

Dependencies: `react-native-safe-area-context`

#### `App.tsx`

```tsx
import {useRef} from 'react';
import {Animated, PanResponder, StyleSheet} from 'react-native';
import {SafeAreaView, SafeAreaProvider} from 'react-native-safe-area-context';

const DraggableView = () => {
  const pan = useRef(new Animated.ValueXY()).current;

  const panResponder = PanResponder.create({
    onStartShouldSetPanResponder: () => true,
    onPanResponderMove: Animated.event(
      [
        null,
        {
          dx: pan.x, // x,y are Animated.Value
          dy: pan.y,
        },
      ],
      {useNativeDriver: false},
    ),
    onPanResponderRelease: () => {
      Animated.spring(
        pan, // Auto-multiplexed
        {toValue: {x: 0, y: 0}, useNativeDriver: true}, // Back to zero
      ).start();
    },
  });

  return (
    <SafeAreaProvider>
      <SafeAreaView style={styles.container}>
        <Animated.View
          {...panResponder.panHandlers}
          style={[pan.getLayout(), styles.box]}
        />
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
  box: {
    backgroundColor: '#61dafb',
    width: 80,
    height: 80,
    borderRadius: 4,
  },
});

export default DraggableView;
```
