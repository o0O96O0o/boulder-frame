# Debugging Native Code

Source: https://reactnative.dev/docs/debugging-native-code

Version: 0.87 | Retrieved: 2026-09-07

### Projects with Native Code Only

The following section only applies to projects with native code exposed. If you are using the managed Expo workflow, see the guide on [prebuild](https://docs.expo.dev/workflow/prebuild/) to use this API.

<a id="accessing-logs"></a>

## Accessing Logs

You can display the native logs for an iOS or Android app by using the following commands in a terminal while the app is running:

```
# For Android:

npx react-native log-android

# Or, for iOS:

npx react-native log-ios
```

You may also access these through Debug > Open System Log… in the iOS Simulator or by running `adb logcat "*:S" ReactNative:V ReactNativeJS:V` in a terminal while an Android app is running on a device or emulator.

**💡 Custom Native Logs**

If you are writing a Native Module and want to add custom logs to your module for debugging purposes, you can use the following method:

<a id="android-javakotlin"></a>

#### Android (Java/Kotlin)

In your native module, use the `Log` class to add logs that can be viewed in Logcat:

Java

```
import android.util.Log;

private void log(String message) {

    Log.d("YourModuleName", message);

}
```

To view these logs in Logcat, use this command, replacing `YourModuleName` with your custom tag:

```
adb logcat "*:S" ReactNative:V ReactNativeJS:V YourModuleName:D
```

<a id="ios-objective-cswift"></a>

#### iOS (Objective-C/Swift)

In your native module, use `NSLog` for custom logs:

Objective-C

```
NSLog(@"YourModuleName: %@", message);
```

Or, in Swift:

Swift

```
print("YourModuleName: \(message)")
```

These logs will appear in the Xcode console when running the app.

<a id="debugging-in-a-native-ide"></a>

## Debugging in a Native IDE

When working with native code, such as when writing native modules, you can launch the app from Android Studio or Xcode and take advantage of the native debugging features (setting up breakpoints, etc.) as you would in case of building a standard native app.

Another option is to run your application using the React Native CLI and attach the native debugger of the native IDE (Android Studio or Xcode) to the process.

<a id="android-studio"></a>

### Android Studio

On Android Studio you can do this by going on the "Run" option on the menu bar, clicking on "Attach to Process..." and selecting the running React Native app.

<a id="xcode"></a>

### Xcode

On Xcode click on "Debug" on the top menu bar, select the "Attach to process" option, and select the application in the list of "Likely Targets".
