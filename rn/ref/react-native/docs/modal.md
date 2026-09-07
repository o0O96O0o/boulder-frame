# Modal

Source: https://reactnative.dev/docs/modal

Version: 0.87 | Retrieved: 2026-09-07

The Modal component is a basic way to present content above an enclosing view.

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

<a id="animationtype"></a>

### `animationType`

The `animationType` prop controls how the modal animates.

Possible values:

* `slide` slides in from the bottom
* `fade` fades into view
* `none` appears without an animation

| Type                                | Default |
| ----------------------------------- | ------- |
| enum(`'none'`, `'slide'`, `'fade'`) | `none`  |

***

<a id="backdropcolor"></a>

### `backdropColor`

The `backdropColor` of the modal (or background color of the modal's container.) Defaults to `white` if not provided and transparent is `false`. Ignored if `transparent` is `true`.

| Type                     | Default |
| ------------------------ | ------- |
| [color](colors.md) | white   |

***

<a id="hardwareaccelerated-android"></a>

### `hardwareAccelerated`Android

The `hardwareAccelerated` prop controls whether to force hardware acceleration for the underlying window.

| Type | Default |
| ---- | ------- |
| bool | `false` |

***

<a id="navigationbartranslucent-android"></a>

### `navigationBarTranslucent`Android

The `navigationBarTranslucent` prop determines whether your modal should go under the system navigation bar. However, `statusBarTranslucent` also needs to be set to `true` to make navigation bar translucent.

| Type | Default |
| ---- | ------- |
| bool | `false` |

***

<a id="ondismiss-ios"></a>

### `onDismiss`iOS

The `onDismiss` prop allows passing a function that will be called once the modal has been dismissed.

| Type     |
| -------- |
| function |

***

<a id="onorientationchange-ios"></a>

### `onOrientationChange`iOS

The `onOrientationChange` callback is called when the orientation changes while the modal is being displayed. The orientation provided is only 'portrait' or 'landscape'. This callback is also called on initial render, regardless of the current orientation.

| Type     |
| -------- |
| function |

***

<a id="allowswipedismissal-ios"></a>

### `allowSwipeDismissal`iOS

Controls whether the modal can be dismissed by swiping down on iOS. This requires you to implement the `onRequestClose` prop to handle the dismissal.

| Type | Default |
| ---- | ------- |
| bool | `false` |

***

<a id="ref"></a>

### `ref`

A ref setter that will be assigned an [element node](element-nodes.md) when mounted.

***

<a id="onrequestclose"></a>

### `onRequestClose`

The `onRequestClose` callback is called when the user taps the hardware back button on Android or the menu button on Apple TV. Because of this required prop, be aware that `BackHandler` events will not be emitted as long as the modal is open. On iOS, this callback is called when a Modal is being dismissed using a drag gesture when `presentationStyle` is `pageSheet` or `formSheet`. When `allowSwipeDismissal` is enabled this callback will be called after dismissing the modal.

| Type                                    |
| --------------------------------------- |
| functionRequiredAndroidTV***functioniOS |

***

<a id="onshow"></a>

### `onShow`

The `onShow` prop allows passing a function that will be called once the modal has been shown.

| Type     |
| -------- |
| function |

***

<a id="presentationstyle-ios"></a>

### `presentationStyle`iOS

The `presentationStyle` prop controls how the modal appears (generally on larger devices such as iPad or plus-sized iPhones). See <https://developer.apple.com/reference/uikit/uimodalpresentationstyle> for details.

Possible values:

* `fullScreen` covers the screen completely
* `pageSheet` covers portrait-width view centered (only on larger devices)
* `formSheet` covers narrow-width view centered (only on larger devices)
* `overFullScreen` covers the screen completely, but allows transparency

| Type                                                                   | Default                                                                          |
| ---------------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| enum(`'fullScreen'`, `'pageSheet'`, `'formSheet'`, `'overFullScreen'`) | `fullScreen` if `transparent={false}`***`overFullScreen` if `transparent={true}` |

***

<a id="statusbartranslucent-android"></a>

### `statusBarTranslucent`Android

The `statusBarTranslucent` prop determines whether your modal should go under the system statusbar.

| Type | Default |
| ---- | ------- |
| bool | `false` |

***

<a id="supportedorientations-ios"></a>

### `supportedOrientations`iOS

The `supportedOrientations` prop allows the modal to be rotated to any of the specified orientations. On iOS, the modal is still restricted by what's specified in your app's Info.plist's UISupportedInterfaceOrientations field.

note

When using `presentationStyle` of `pageSheet` or `formSheet`, this property will be ignored on iOS.

| Type                                                                                                           | Default        |
| -------------------------------------------------------------------------------------------------------------- | -------------- |
| array of enums(`'portrait'`, `'portrait-upside-down'`, `'landscape'`, `'landscape-left'`, `'landscape-right'`) | `['portrait']` |

***

<a id="transparent"></a>

### `transparent`

The `transparent` prop determines whether your modal will fill the entire view. Setting this to `true` will render the modal over a transparent background.

| Type | Default |
| ---- | ------- |
| bool | `false` |

***

<a id="visible"></a>

### `visible`

The `visible` prop determines whether your modal is visible.

| Type | Default |
| ---- | ------- |
| bool | `true`  |

## Embedded example source

Code extracted from this page’s Expo Snack embeds; interactive previews require the original website.

### Modal

Dependencies: `react-native-safe-area-context`

#### `App.tsx`

```tsx
import {useState} from 'react';
import {Alert, Modal, StyleSheet, Text, Pressable, View} from 'react-native';
import {SafeAreaView, SafeAreaProvider} from 'react-native-safe-area-context';

const App = () => {
  const [modalVisible, setModalVisible] = useState(false);
  return (
    <SafeAreaProvider>
      <SafeAreaView style={styles.centeredView}>
        <Modal
          animationType="slide"
          transparent={true}
          visible={modalVisible}
          onRequestClose={() => {
            Alert.alert('Modal has been closed.');
            setModalVisible(!modalVisible);
          }}>
          <View style={styles.centeredView}>
            <View style={styles.modalView}>
              <Text style={styles.modalText}>Hello World!</Text>
              <Pressable
                style={[styles.button, styles.buttonClose]}
                onPress={() => setModalVisible(!modalVisible)}>
                <Text style={styles.textStyle}>Hide Modal</Text>
              </Pressable>
            </View>
          </View>
        </Modal>
        <Pressable
          style={[styles.button, styles.buttonOpen]}
          onPress={() => setModalVisible(true)}>
          <Text style={styles.textStyle}>Show Modal</Text>
        </Pressable>
      </SafeAreaView>
    </SafeAreaProvider>
  );
};

const styles = StyleSheet.create({
  centeredView: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  modalView: {
    margin: 20,
    backgroundColor: 'white',
    borderRadius: 20,
    padding: 35,
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: {
      width: 0,
      height: 2,
    },
    shadowOpacity: 0.25,
    shadowRadius: 4,
    elevation: 5,
  },
  button: {
    borderRadius: 20,
    padding: 10,
    elevation: 2,
  },
  buttonOpen: {
    backgroundColor: '#F194FF',
  },
  buttonClose: {
    backgroundColor: '#2196F3',
  },
  textStyle: {
    color: 'white',
    fontWeight: 'bold',
    textAlign: 'center',
  },
  modalText: {
    marginBottom: 15,
    textAlign: 'center',
  },
});

export default App;
```
