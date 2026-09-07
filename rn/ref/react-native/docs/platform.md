# Platform

Source: https://reactnative.dev/docs/platform

Version: 0.87 | Retrieved: 2026-09-07

<a id="example"></a>

## Example

***

# Reference

<a id="properties"></a>

## Properties

<a id="constants"></a>

### `constants`

React TSX

```
static constants: PlatformConstants;
```

Returns an object which contains all available common and specific constants related to the platform.

**Properties:**

| Name                   | Type    | Optional | Description                                                                                                                                                                                       |
| ---------------------- | ------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| isTesting              | boolean | No       |                                                                                                                                                                                                   |
| reactNativeVersion     | object  | No       | Information about React Native version. Keys are `major`, `minor`, `patch` with optional `prerelease` and values are `number`s.                                                                   |
| VersionAndroid         | number  | No       | OS version constant specific to Android.                                                                                                                                                          |
| ReleaseAndroid         | string  | No       |                                                                                                                                                                                                   |
| SerialAndroid          | string  | No       | Hardware serial number of an Android device.                                                                                                                                                      |
| FingerprintAndroid     | string  | No       | A string that uniquely identifies the build.                                                                                                                                                      |
| ModelAndroid           | string  | No       | The end-user-visible name for the Android device.                                                                                                                                                 |
| BrandAndroid           | string  | No       | The consumer-visible brand with which the product/hardware will be associated.                                                                                                                    |
| ManufacturerAndroid    | string  | No       | The manufacturer of the Android device.                                                                                                                                                           |
| ServerHostAndroid      | string  | Yes      |                                                                                                                                                                                                   |
| uiModeAndroid          | string  | No       | Possible values are: `'car'`, `'desk'`, `'normal'`,`'tv'`, `'watch'` and `'unknown'`. Read more about [Android ModeType](https://developer.android.com/reference/android/app/UiModeManager.html). |
| forceTouchAvailableiOS | boolean | No       | Indicate the availability of 3D Touch on a device.                                                                                                                                                |
| interfaceIdiomiOS      | string  | No       | The interface type for the device. Read more about [UIUserInterfaceIdiom](https://developer.apple.com/documentation/uikit/uiuserinterfaceidiom).                                                  |
| osVersioniOS           | string  | No       | OS version constant specific to iOS.                                                                                                                                                              |
| systemNameiOS          | string  | No       | OS name constant specific to iOS.                                                                                                                                                                 |

***

<a id="ispad-ios"></a>

### `isPad`iOS

React TSX

```
static isPad: boolean;
```

Returns a boolean which defines if device is an iPad.

| Type    |
| ------- |
| boolean |

***

<a id="istv"></a>

### `isTV`

React TSX

```
static isTV: boolean;
```

Returns a boolean which defines if device is a TV.

| Type    |
| ------- |
| boolean |

***

<a id="isvision"></a>

### `isVision`

React TSX

```
static isVision: boolean;
```

Returns a boolean which defines if device is an Apple Vision. *If you are using [Apple Vision Pro (Designed for iPad)](https://developer.apple.com/documentation/visionos/determining-whether-to-bring-your-app-to-visionos) `isVision` will be `false` but `isPad` will be `true`*

| Type    |
| ------- |
| boolean |

***

<a id="istesting"></a>

### `isTesting`

React TSX

```
static isTesting: boolean;
```

Returns a boolean which defines if application is running in Developer Mode with testing flag set.

| Type    |
| ------- |
| boolean |

***

<a id="os"></a>

### `OS`

React TSX

```
static OS: 'android' | 'ios';
```

Returns string value representing the current OS.

| Type                       |
| -------------------------- |
| enum(`'android'`, `'ios'`) |

***

<a id="version"></a>

### `Version`

React TSX

```
static Version: 'number' | 'string';
```

Returns the version of the OS.

| Type                      |
| ------------------------- |
| numberAndroid***stringiOS |

<a id="methods"></a>

## Methods

<a id="select"></a>

### `select()`

React TSX

```
static select(config: Record<string, T>): T;
```

Returns the most fitting value for the platform you are currently running on.

<a id="parameters"></a>

#### Parameters:

| Name   | Type   | Required | Description                   |
| ------ | ------ | -------- | ----------------------------- |
| config | object | Yes      | See config description below. |

Select method returns the most fitting value for the platform you are currently running on. That is, if you're running on a phone, `android` and `ios` keys will take preference. If those are not specified, `native` key will be used and then the `default` key.

The `config` parameter is an object with the following keys:

* `android` (any)
* `ios` (any)
* `native` (any)
* `default` (any)

**Example usage:**

React TSX

```
import {Platform, StyleSheet} from 'react-native';

const styles = StyleSheet.create({

  container: {

    flex: 1,

    ...Platform.select({

      android: {

        backgroundColor: 'green',

      },

      ios: {

        backgroundColor: 'red',

      },

      default: {

        // other platforms, web for example

        backgroundColor: 'blue',

      },

    }),

  },

});
```

This will result in a container having `flex: 1` on all platforms, a green background color on Android, a red background color on iOS, and a blue background color on other platforms.

Since the value of the corresponding platform key can be of type `any`, [`select`](platform.md#select) method can also be used to return platform-specific components, like below:

React TSX

```
const Component = Platform.select({

  ios: () => require('ComponentIOS'),

  android: () => require('ComponentAndroid'),

})();

<Component />;
```

React TSX

```
const Component = Platform.select({

  native: () => require('ComponentForNative'),

  default: () => require('ComponentForWeb'),

})();

<Component />;
```

## Embedded example source

Code extracted from this page’s Expo Snack embeds; interactive previews require the original website.

### Platform API Example

Dependencies: `react-native-safe-area-context`

#### `App.tsx`

```tsx
import {Platform, StyleSheet, Text, ScrollView} from 'react-native';
import {SafeAreaView, SafeAreaProvider} from 'react-native-safe-area-context';

const App = () => {
  return (
    <SafeAreaProvider>
      <SafeAreaView style={styles.safeArea}>
        <ScrollView contentContainerStyle={styles.container}>
          <Text>OS</Text>
          <Text style={styles.value}>{Platform.OS}</Text>
          <Text>OS Version</Text>
          <Text style={styles.value}>{Platform.Version}</Text>
          <Text>isTV</Text>
          <Text style={styles.value}>{Platform.isTV.toString()}</Text>
          {Platform.OS === 'ios' && (
            <>
              <Text>isPad</Text>
              <Text style={styles.value}>{Platform.isPad.toString()}</Text>
            </>
          )}
          <Text>Constants</Text>
          <Text style={styles.value}>
            {JSON.stringify(Platform.constants, null, 2)}
          </Text>
        </ScrollView>
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
  value: {
    fontWeight: '600',
    padding: 4,
    marginBottom: 8,
  },
  safeArea: {
    flex: 1,
  },
});

export default App;
```
