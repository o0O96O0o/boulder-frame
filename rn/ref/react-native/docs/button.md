# Button

Source: https://reactnative.dev/docs/button

Version: 0.87 | Retrieved: 2026-09-07

A basic button component that should render nicely on any platform. Supports a minimal level of customization.

If this button doesn't look right for your app, you can build your own button using [Pressable](pressable.md). For inspiration, look at the [source code for the Button component](https://github.com/facebook/react-native/blob/main/packages/react-native/Libraries/Components/Button.js).

React TSX

```
<Button

  onPress={onPressLearnMore}

  title="Learn More"

  color="#841584"

  accessibilityLabel="Learn more about this purple button"

/>
```

<a id="example"></a>

## Example

***

# Reference

<a id="props"></a>

## Props

<a id="requiredonpress"></a>

### Require&#x64;**`onPress`**

Handler to be called when the user taps the button.

| Type                          |
| ----------------------------- |
| `({nativeEvent: PressEvent})` |

***

<a id="requiredtitle"></a>

### Require&#x64;**`title`**

Text to display inside the button. On Android the given title will be converted to the uppercased form.

| Type   |
| ------ |
| string |

***

<a id="accessibilitylabel"></a>

### `accessibilityLabel`

Text to display for blindness accessibility features.

| Type   |
| ------ |
| string |

***

<a id="accessibilitylanguage-ios"></a>

### `accessibilityLanguage`iOS

A value indicating which language should be used by the screen reader when the user interacts with the element. It should follow the [BCP 47 specification](https://www.rfc-editor.org/info/bcp47).

See the [iOS `accessibilityLanguage` doc](https://developer.apple.com/documentation/objectivec/nsobject/1615192-accessibilitylanguage) for more information.

| Type   |
| ------ |
| string |

***

<a id="accessibilityactions"></a>

### `accessibilityActions`

Accessibility actions allow an assistive technology to programmatically invoke the actions of a component. The `accessibilityActions` property should contain a list of action objects. Each action object should contain the field name and label.

See the [Accessibility guide](accessibility.md#accessibility-actions) for more information.

| Type  | Required |
| ----- | -------- |
| array | No       |

***

<a id="onaccessibilityaction"></a>

### `onAccessibilityAction`

Invoked when the user performs the accessibility actions. The only argument to this function is an event containing the name of the action to perform.

See the [Accessibility guide](accessibility.md#accessibility-actions) for more information.

| Type     | Required |
| -------- | -------- |
| function | No       |

***

<a id="color"></a>

### `color`

Color of the text (iOS), or background color of the button (Android).

<!-- -->

| Type                     | Default                             |
| ------------------------ | ----------------------------------- |
| [color](colors.md) | `'#2196F3'`Android***`'#007AFF'`iOS |

***

<a id="disabled"></a>

### `disabled`

If `true`, disable all interactions for this component.

| Type | Default |
| ---- | ------- |
| bool | `false` |

***

<a id="hastvpreferredfocus-tv"></a>

### `hasTVPreferredFocus`TV

TV preferred focus.

| Type | Default |
| ---- | ------- |
| bool | `false` |

***

<a id="nextfocusdown-androidtv"></a>

### `nextFocusDown`AndroidTV

Designates the next view to receive focus when the user navigates down. See the [Android documentation](https://developer.android.com/reference/android/view/View.html#attr_android:nextFocusDown).

| Type   |
| ------ |
| number |

***

<a id="nextfocusforward-androidtv"></a>

### `nextFocusForward`AndroidTV

Designates the next view to receive focus when the user navigates forward. See the [Android documentation](https://developer.android.com/reference/android/view/View.html#attr_android:nextFocusForward).

| Type   |
| ------ |
| number |

***

<a id="nextfocusleft-androidtv"></a>

### `nextFocusLeft`AndroidTV

Designates the next view to receive focus when the user navigates left. See the [Android documentation](https://developer.android.com/reference/android/view/View.html#attr_android:nextFocusLeft).

| Type   |
| ------ |
| number |

***

<a id="nextfocusright-androidtv"></a>

### `nextFocusRight`AndroidTV

Designates the next view to receive focus when the user navigates right. See the [Android documentation](https://developer.android.com/reference/android/view/View.html#attr_android:nextFocusRight).

| Type   |
| ------ |
| number |

***

<a id="nextfocusup-androidtv"></a>

### `nextFocusUp`AndroidTV

Designates the next view to receive focus when the user navigates up. See the [Android documentation](https://developer.android.com/reference/android/view/View.html#attr_android:nextFocusUp).

| Type   |
| ------ |
| number |

***

<a id="testid"></a>

### `testID`

Used to locate this view in end-to-end tests.

| Type   |
| ------ |
| string |

***

<a id="touchsounddisabled-android"></a>

### `touchSoundDisabled`Android

If `true`, doesn't play system sound on touch.

| Type    | Default |
| ------- | ------- |
| boolean | `false` |

## Embedded example source

Code extracted from this page’s Expo Snack embeds; interactive previews require the original website.

### Button Example

Dependencies: `react-native-safe-area-context`

#### `App.js`

```jsx
import {StyleSheet, Button, View, Text, Alert, Platform} from 'react-native';
import {SafeAreaView, SafeAreaProvider} from 'react-native-safe-area-context';

const Separator = () => <View style={styles.separator} />;

function showAlert(message) {
  if (Platform.OS === 'web') {
    window.alert(message);
  } else {
    Alert.alert(message);
  }
}

const App = () => (
  <SafeAreaProvider>
    <SafeAreaView style={styles.container}>
      <View>
        <Text style={styles.title}>
          The title and onPress handler are required. It is recommended to set
          accessibilityLabel to help make your app usable by everyone.
        </Text>
        <Button
          title="Press me"
          onPress={() => showAlert('Simple Button pressed')}
        />
      </View>
      <Separator />
      <View>
        <Text style={styles.title}>
          Adjust the color in a way that looks standard on each platform. On
          iOS, the color prop controls the color of the text. On Android, the
          color adjusts the background color of the button.
        </Text>
        <Button
          title="Press me"
          color="#f194ff"
          onPress={() => showAlert('Button with adjusted color pressed')}
        />
      </View>
      <Separator />
      <View>
        <Text style={styles.title}>
          All interaction for the component are disabled.
        </Text>
        <Button
          title="Press me"
          disabled
          onPress={() => showAlert('Cannot press this one')}
        />
      </View>
      <Separator />
      <View>
        <Text style={styles.title}>
          This layout strategy lets the title define the width of the button.
        </Text>
        <View style={styles.fixToText}>
          <Button
            title="Left button"
            onPress={() => showAlert('Left button pressed')}
          />
          <Button
            title="Right button"
            onPress={() => showAlert('Right button pressed')}
          />
        </View>
      </View>
    </SafeAreaView>
  </SafeAreaProvider>
);

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    marginHorizontal: 16,
  },
  title: {
    textAlign: 'center',
    marginVertical: 8,
  },
  fixToText: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  separator: {
    marginVertical: 8,
    borderBottomColor: '#737373',
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
});

export default App;
```
