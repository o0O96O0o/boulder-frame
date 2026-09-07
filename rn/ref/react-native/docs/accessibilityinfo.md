# AccessibilityInfo

Source: https://reactnative.dev/docs/accessibilityinfo

Version: 0.87 | Retrieved: 2026-09-07

Sometimes it's useful to know whether or not the device has a screen reader that is currently active. The `AccessibilityInfo` API is designed for this purpose. You can use it to query the current state of the screen reader as well as to register to be notified when the state of the screen reader changes.

<a id="example"></a>

## Example

***

# Reference

<a id="methods"></a>

## Methods

<a id="addeventlistener"></a>

### `addEventListener()`

React TSX

```
static addEventListener(

  eventName: AccessibilityChangeEventName | AccessibilityAnnouncementEventName,

  handler: (

    event: AccessibilityChangeEvent | AccessibilityAnnouncementFinishedEvent,

  ) => void,

): EmitterSubscription;
```

Add an event handler. Supported events:

| Event name                                 | Description                                                                                                                                                                                                                                                                             |
| ------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `accessibilityServiceChanged`<br />Android | Fires when some services such as TalkBack, other Android assistive technologies, and third-party accessibility services are enabled. The argument to the event handler is a boolean. The boolean is `true` when a some accessibility services is enabled and `false` otherwise.         |
| `announcementFinished`<br />iOS            | Fires when the screen reader has finished making an announcement. The argument to the event handler is a dictionary with these keys:- `announcement`: The string announced by the screen reader.<br />- `success`: A boolean indicating whether the announcement was successfully made. |
| `boldTextChanged`<br />iOS                 | Fires when the state of the bold text toggle changes. The argument to the event handler is a boolean. The boolean is `true` when bold text is enabled and `false` otherwise.                                                                                                            |
| `grayscaleChanged`<br />iOS                | Fires when the state of the gray scale toggle changes. The argument to the event handler is a boolean. The boolean is `true` when a gray scale is enabled and `false` otherwise.                                                                                                        |
| `invertColorsChanged`<br />iOS             | Fires when the state of the invert colors toggle changes. The argument to the event handler is a boolean. The boolean is `true` when invert colors is enabled and `false` otherwise.                                                                                                    |
| `reduceMotionChanged`                      | Fires when the state of the reduce motion toggle changes. The argument to the event handler is a boolean. The boolean is `true` when a reduce motion is enabled (or when "Transition Animation Scale" in "Developer options" is "Animation off") and `false` otherwise.                 |
| `reduceTransparencyChanged`<br />iOS       | Fires when the state of the reduce transparency toggle changes. The argument to the event handler is a boolean. The boolean is `true` when reduce transparency is enabled and `false` otherwise.                                                                                        |
| `screenReaderChanged`                      | Fires when the state of the screen reader changes. The argument to the event handler is a boolean. The boolean is `true` when a screen reader is enabled and `false` otherwise.                                                                                                         |

***

<a id="announceforaccessibility"></a>

### `announceForAccessibility()`

React TSX

```
static announceForAccessibility(announcement: string);
```

Post a string to be announced by the screen reader.

***

<a id="announceforaccessibilitywithoptions"></a>

### `announceForAccessibilityWithOptions()`

React TSX

```
static announceForAccessibilityWithOptions(

  announcement: string,

  options: {queue?: boolean},

);
```

Post a string to be announced by the screen reader with modification options. By default announcements will interrupt any existing speech, but on iOS they can be queued behind existing speech by setting `queue` to `true` in the options object.

**Parameters:**

| Name                 | Type   | Description                                                |
| -------------------- | ------ | ---------------------------------------------------------- |
| announcementRequired | string | The string to be announced                                 |
| optionsRequired      | object | `queue` - queue the announcement behind existing speechiOS |

***

<a id="getrecommendedtimeoutmillis-android"></a>

### `getRecommendedTimeoutMillis()`Android

React TSX

```
static getRecommendedTimeoutMillis(originalTimeout: number): Promise<number>;
```

Gets the timeout in millisecond that the user needs. This value is set in "Time to take action (Accessibility timeout)" of "Accessibility" settings.

**Parameters:**

| Name                    | Type   | Description                                                                           |
| ----------------------- | ------ | ------------------------------------------------------------------------------------- |
| originalTimeoutRequired | number | The timeout to return if "Accessibility timeout" is not set. Specify in milliseconds. |

***

<a id="isaccessibilityserviceenabled-android"></a>

### `isAccessibilityServiceEnabled()`Android

React TSX

```
static isAccessibilityServiceEnabled(): Promise<boolean>;
```

Check whether any accessibility service is enabled. This includes TalkBack but also any third-party accessibility app that may be installed. To only check whether TalkBack is enabled, use [isScreenReaderEnabled](#isscreenreaderenabled). Returns a promise which resolves to a boolean. The result is `true` when some accessibility services is enabled and `false` otherwise.

note

Please use [`isScreenReaderEnabled`](#isscreenreaderenabled) if you only want to check the status of TalkBack.

***

<a id="isboldtextenabled-ios"></a>

### `isBoldTextEnabled()`iOS

React TSX

```
static isBoldTextEnabled(): Promise<boolean>:
```

Query whether a bold text is currently enabled. Returns a promise which resolves to a boolean. The result is `true` when bold text is enabled and `false` otherwise.

***

<a id="isgrayscaleenabled-ios"></a>

### `isGrayscaleEnabled()`iOS

React TSX

```
static isGrayscaleEnabled(): Promise<boolean>;
```

Query whether grayscale is currently enabled. Returns a promise which resolves to a boolean. The result is `true` when grayscale is enabled and `false` otherwise.

***

<a id="isinvertcolorsenabled-ios"></a>

### `isInvertColorsEnabled()`iOS

React TSX

```
static isInvertColorsEnabled(): Promise<boolean>;
```

Query whether invert colors is currently enabled. Returns a promise which resolves to a boolean. The result is `true` when invert colors is enabled and `false` otherwise.

***

<a id="isreducemotionenabled"></a>

### `isReduceMotionEnabled()`

React TSX

```
static isReduceMotionEnabled(): Promise<boolean>;
```

Query whether reduce motion is currently enabled. Returns a promise which resolves to a boolean. The result is `true` when reduce motion is enabled and `false` otherwise.

***

<a id="isreducetransparencyenabled-ios"></a>

### `isReduceTransparencyEnabled()`iOS

React TSX

```
static isReduceTransparencyEnabled(): Promise<boolean>;
```

Query whether reduce transparency is currently enabled. Returns a promise which resolves to a boolean. The result is `true` when a reduce transparency is enabled and `false` otherwise.

***

<a id="isscreenreaderenabled"></a>

### `isScreenReaderEnabled()`

React TSX

```
static isScreenReaderEnabled(): Promise<boolean>;
```

Query whether a screen reader is currently enabled. Returns a promise which resolves to a boolean. The result is `true` when a screen reader is enabled and `false` otherwise.

***

<a id="ishightextcontrastenabled-android"></a>

### `isHighTextContrastEnabled()`Android

React TSX

```
static isHighTextContrastEnabled(): Promise<boolean>
```

Query whether high text contrast is currently enabled. Returns a promise which resolves to a boolean. The result is `true` when high text contrast is enabled and `false` otherwise.

***

<a id="isdarkersystemcolorsenabled-ios"></a>

### `isDarkerSystemColorsEnabled()`iOS

React TSX

```
static isDarkerSystemColorsEnabled(): Promise<boolean>
```

Query whether dark system colors is currently enabled. Returns a promise which resolves to a boolean. The result is `true` when dark system colors is enabled and `false` otherwise.

***

<a id="preferscrossfadetransitions-ios"></a>

### `prefersCrossFadeTransitions()`iOS

React TSX

```
static prefersCrossFadeTransitions(): Promise<boolean>;
```

Query whether reduce motion and prefer cross-fade transitions settings are currently enabled. Returns a promise which resolves to a boolean. The result is `true` when prefer cross-fade transitions is enabled and `false` otherwise.

***

<a id="️-setaccessibilityfocus"></a>

### 🗑️ `setAccessibilityFocus()`

Deprecated

Prefer using `sendAccessibilityEvent` with eventType `focus` instead.

React TSX

```
static setAccessibilityFocus(reactTag: number);
```

Set accessibility focus to a React component.

On Android, this calls `UIManager.sendAccessibilityEvent` method with passed `reactTag` and `UIManager.AccessibilityEventTypes.typeViewFocused` arguments.

note

Make sure that any `View` you want to receive the accessibility focus has `accessible={true}`.

***

<a id="sendaccessibilityevent"></a>

### `sendAccessibilityEvent()`

React TSX

```
static sendAccessibilityEvent(host: HostInstance, eventType: AccessibilityEventTypes);
```

Imperatively trigger an accessibility event on a React component, like changing the focused element for a screen reader.

note

Make sure that any `View` you want to receive the accessibility focus has `accessible={true}`.

| Name              | Type                    | Description                                                                                                            |
| ----------------- | ----------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| hostRequired      | HostInstance            | The component ref to send the event to.                                                                                |
| eventTypeRequired | AccessibilityEventTypes | One of `'click'` (Android only), `'focus'`, `'viewHoverEnter'` (Android only), or `'windowStateChange'` (Android only) |

## Embedded example source

Code extracted from this page’s Expo Snack embeds; interactive previews require the original website.

### AccessibilityInfo Example

Dependencies: `react-native-safe-area-context`

#### `App.tsx`

```tsx
import {useState, useEffect} from 'react';
import {AccessibilityInfo, Text, StyleSheet} from 'react-native';
import {SafeAreaView, SafeAreaProvider} from 'react-native-safe-area-context';

const App = () => {
  const [reduceMotionEnabled, setReduceMotionEnabled] = useState(false);
  const [screenReaderEnabled, setScreenReaderEnabled] = useState(false);

  useEffect(() => {
    const reduceMotionChangedSubscription = AccessibilityInfo.addEventListener(
      'reduceMotionChanged',
      isReduceMotionEnabled => {
        setReduceMotionEnabled(isReduceMotionEnabled);
      },
    );
    const screenReaderChangedSubscription = AccessibilityInfo.addEventListener(
      'screenReaderChanged',
      isScreenReaderEnabled => {
        setScreenReaderEnabled(isScreenReaderEnabled);
      },
    );

    AccessibilityInfo.isReduceMotionEnabled().then(isReduceMotionEnabled => {
      setReduceMotionEnabled(isReduceMotionEnabled);
    });
    AccessibilityInfo.isScreenReaderEnabled().then(isScreenReaderEnabled => {
      setScreenReaderEnabled(isScreenReaderEnabled);
    });

    return () => {
      reduceMotionChangedSubscription.remove();
      screenReaderChangedSubscription.remove();
    };
  }, []);

  return (
    <SafeAreaProvider>
      <SafeAreaView style={styles.container}>
        <Text style={styles.status}>
          The reduce motion is {reduceMotionEnabled ? 'enabled' : 'disabled'}.
        </Text>
        <Text style={styles.status}>
          The screen reader is {screenReaderEnabled ? 'enabled' : 'disabled'}.
        </Text>
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
  status: {
    margin: 30,
  },
});

export default App;
```
