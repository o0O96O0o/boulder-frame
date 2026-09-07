# Share

Source: https://reactnative.dev/docs/share

Version: 0.87 | Retrieved: 2026-09-07

<a id="example"></a>

## Example

* TypeScript
* JavaScript

# Reference

<a id="methods"></a>

## Methods

<a id="share"></a>

### `share()`

React TSX

```
static share(content: ShareContent, options?: ShareOptions);
```

Open a dialog to share text content.

In iOS, returns a Promise which will be invoked with an object containing `action` and `activityType`. If the user dismissed the dialog, the Promise will still be resolved with action being `Share.dismissedAction` and all the other keys being undefined. Note that some share options will not appear or work on the iOS simulator.

In Android, returns a Promise which will always be resolved with action being `Share.sharedAction`.

**Properties:**

| Name            | Type   | Description                                                                                                                                                                                                        |
| --------------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| contentRequired | object | `message` - a message to share<br />`url` - a URL to shareiOS<br />`title` - title of the messageAndroid***At least one of `url` and `message` is required.                                                        |
| options         | object | `dialogTitle`Android<br />`excludedActivityTypes`iOS<br />`subject` - a subject to share via emailiOS<br />`tintColor`iOS<br />`anchor` - the node to which the action sheet should be anchored (used for iPad)iOS |

***

<a id="properties"></a>

## Properties

<a id="sharedaction"></a>

### `sharedAction`

React TSX

```
static sharedAction: 'sharedAction';
```

The content was successfully shared.

***

<a id="dismissedaction-ios"></a>

### `dismissedAction`iOS

React TSX

```
static dismissedAction: 'dismissedAction';
```

The dialog has been dismissed.

## Embedded example source

Code extracted from this page’s Expo Snack embeds; interactive previews require the original website.

### Example

Dependencies: `react-native-safe-area-context`

#### `App.js`

```jsx
import {Alert, Share, Button} from 'react-native';
import {SafeAreaView, SafeAreaProvider} from 'react-native-safe-area-context';

const ShareExample = () => {
  const onShare = async () => {
    try {
      const result = await Share.share({
        message:
          'React Native | A framework for building native apps using React',
      });
      if (result.action === Share.sharedAction) {
        if (result.activityType) {
          // shared with activity type of result.activityType
        } else {
          // shared
        }
      } else if (result.action === Share.dismissedAction) {
        // dismissed
      }
    } catch (error) {
      Alert.alert(error.message);
    }
  };
  return (
    <SafeAreaProvider>
      <SafeAreaView>
        <Button onPress={onShare} title="Share" />
      </SafeAreaView>
    </SafeAreaProvider>
  );
};

export default ShareExample;
```

### Example

Dependencies: `react-native-safe-area-context`

#### `App.tsx`

```tsx
import {Alert, Share, Button} from 'react-native';
import {SafeAreaView, SafeAreaProvider} from 'react-native-safe-area-context';

const ShareExample = () => {
  const onShare = async () => {
    try {
      const result = await Share.share({
        message:
          'React Native | A framework for building native apps using React',
      });
      if (result.action === Share.sharedAction) {
        if (result.activityType) {
          // shared with activity type of result.activityType
        } else {
          // shared
        }
      } else if (result.action === Share.dismissedAction) {
        // dismissed
      }
    } catch (error: any) {
      Alert.alert(error.message);
    }
  };
  return (
    <SafeAreaProvider>
      <SafeAreaView>
        <Button onPress={onShare} title="Share" />
      </SafeAreaView>
    </SafeAreaProvider>
  );
};

export default ShareExample;
```
