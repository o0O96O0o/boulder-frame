# Debugging Basics

Source: https://reactnative.dev/docs/debugging

Version: 0.87 | Retrieved: 2026-09-07

note

Debugging features, such as the Dev Menu, LogBox, and React Native DevTools are disabled in release (production) builds.

<a id="opening-the-dev-menu"></a>

## Opening the Dev Menu

React Native provides an in-app developer menu providing access to debugging features. You can access the Dev Menu by shaking your device or via keyboard shortcuts:

* iOS Simulator: `Ctrl` + `Cmd ⌘` + `Z` (or Device > Shake)
* Android emulators: `Cmd ⌘` + `M` (macOS) or `Ctrl` + `M` (Windows and Linux)

Alternative (Android): `adb shell input keyevent 82`.

![The React Native Dev Menu](https://reactnative.dev/assets/images/debugging-dev-menu-083-70616da2986550a977feb0158f218bdd.jpg)

<a id="opening-devtools"></a>

## Opening DevTools

[React Native DevTools](react-native-devtools.md) is our built-in debugger for React Native. It allows you to inspect and understand how your JavaScript code is running, similar to a web browser.

To open DevTools, either:

* Select "Open DevTools" in the Dev Menu.
* Press `j` from the CLI.

![React Native DevTools opened to the \&quot;Welcome\&quot; pane](https://reactnative.dev/assets/images/debugging-rndt-welcome-083-9f56f0124de2d2607022330b0ce41d85.jpg)

On first launch, DevTools will open to a welcome panel, along with an open console drawer where you can view logs and interact with the JavaScript runtime. From the top of the window, you can navigate to other panels, including the integrated React Components Inspector and Profiler.

Learn more in our [React Native DevTools guide](react-native-devtools.md).

<a id="logbox"></a>

## LogBox

LogBox is an in-app tool that displays when warnings or errors are logged by your app.

![A LogBox warning and an expanded LogBox syntax error](https://reactnative.dev/assets/images/debugging-logbox-076-0191f48c03cc7b550d749c4f100fab47.jpg)

<a id="fatal-errors"></a>

### Fatal Errors

When an unrecoverable error occurs, such as a JavaScript syntax error, LogBox will open with the location of the error. In this state, LogBox is not dismissable since your code cannot be executed. LogBox will automatically dismiss once the syntax error is fixed — either via Fast Refresh or after a manual reload.

<a id="console-errors-and-warnings"></a>

### Console Errors and Warnings

Console errors and warnings are displayed as on-screen notifications with a red or yellow badge.

* **Errors** will display with a notification count. Tap the notification to see an expanded view and to paginate through other logs.
* **Warnings** will display a notification banner without details, prompting you to open React Native DevTools.

When React Native DevTools is open, all errors except fatal errors will be hidden to LogBox. We recommend using the Console panel within React Native DevTools as a source of truth, due to various LogBox options which can hide or adjust the level of certain logs.

**💡 Ignoring logs**

LogBox can be configured via the `LogBox` API.

JavaScript

```
import {LogBox} from 'react-native';
```

<a id="ignore-all-logs"></a>

#### Ignore all logs

LogBox notifications can be disabled using `LogBox.ignoreAllLogs()`. This can be useful in situations such as giving product demos.

JavaScript

```
LogBox.ignoreAllLogs();
```

<a id="ignore-specific-logs"></a>

#### Ignore specific logs

Notifications can be disabled on a per-log basis via `LogBox.ignoreLogs()`. This can be useful for noisy warnings or those that cannot be fixed, e.g. in a third-party dependency.

JavaScript

```
LogBox.ignoreLogs([

  // Exact message

  'Warning: componentWillReceiveProps has been renamed',

  // Substring or regex match

  /GraphQL error: .*/,

]);
```

note

LogBox will treat certain errors from React as warnings, which will mean they don't display as an in-app error notification. Advanced users can change this behaviour by customising LogBox's warning filter using [`LogBoxData.setWarningFilter()`](https://github.com/facebook/react-native/blob/d334f4d77eea538dff87fdcf2ebc090246cfdbb0/packages/react-native/Libraries/LogBox/Data/LogBoxData.js#L338).

<a id="performance-monitor"></a>

## Performance Monitor

On Android and iOS, an in-app performance overlay can be toggled during development by selecting **"Perf Monitor"** in the Dev Menu. Learn more about this feature [here](performance.md).

![The Performance Monitor overlay on iOS and Android](https://reactnative.dev/assets/images/debugging-performance-monitor-3e0023c343ba59b5f62e563a4aa2741a.jpg)

info

The Performance Monitor runs in-app and is a guide. We recommend investigating the native tooling under Android Studio and Xcode for accurate performance measurements.
