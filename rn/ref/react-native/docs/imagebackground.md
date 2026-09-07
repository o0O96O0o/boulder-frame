# ImageBackground

Source: https://reactnative.dev/docs/imagebackground

Version: 0.87 | Retrieved: 2026-09-07

A common feature request from developers familiar with the web is `background-image`. To handle this use case, you can use the `<ImageBackground>` component, which has the same props as `<Image>`, and add whatever children to it you would like to layer on top of it.

You might not want to use `<ImageBackground>` in some cases, since the implementation is basic. Refer to `<ImageBackground>`'s [source code](https://github.com/facebook/react-native/blob/main/packages/react-native/Libraries/Image/ImageBackground.js) for more insight, and create your own custom component when needed.

Note that you must specify some width and height style attributes.

<a id="example"></a>

## Example

***

# Reference

<a id="props"></a>

## Props

<a id="image-props"></a>

### [Image Props](image.md#props)

Inherits [Image Props](image.md#props).

***

<a id="imagestyle"></a>

### `imageStyle`

| Type                                      |
| ----------------------------------------- |
| [Image Style](image-style-props.md) |

***

<a id="imageref"></a>

### `imageRef`

A ref setter that will be assigned the [element node](element-nodes.md) of the inner `Image` component when mounted.

***

<a id="style"></a>

### `style`

| Type                                    |
| --------------------------------------- |
| [View Style](view-style-props.md) |

## Embedded example source

Code extracted from this page’s Expo Snack embeds; interactive previews require the original website.

### ImageBackground

Dependencies: `react-native-safe-area-context`

#### `App.tsx`

```tsx
import {ImageBackground, StyleSheet, Text} from 'react-native';
import {SafeAreaView, SafeAreaProvider} from 'react-native-safe-area-context';

const image = {uri: 'https://legacy.reactjs.org/logo-og.png'};

const App = () => (
  <SafeAreaProvider>
    <SafeAreaView style={styles.container} edges={['left', 'right']}>
      <ImageBackground source={image} resizeMode="cover" style={styles.image}>
        <Text style={styles.text}>Inside</Text>
      </ImageBackground>
    </SafeAreaView>
  </SafeAreaProvider>
);

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  image: {
    flex: 1,
    justifyContent: 'center',
  },
  text: {
    color: 'white',
    fontSize: 42,
    lineHeight: 84,
    fontWeight: 'bold',
    textAlign: 'center',
    backgroundColor: '#000000c0',
  },
});

export default App;
```
