# Running On Simulator

Source: https://reactnative.dev/docs/running-on-simulator-ios

Version: 0.87 | Retrieved: 2026-09-07

<a id="starting-the-simulator"></a>

## Starting the simulator

Once you have your React Native project initialized, you can run the following command inside the newly created project directory.

* npm
* Yarn

```
npm run ios
```

```
yarn ios
```

If everything is set up correctly, you should see your new app running in the iOS Simulator shortly.

<a id="specifying-a-device"></a>

## Specifying a device

You can specify the device the simulator should run with the `--simulator` flag, followed by the device name as a string. The default is `"iPhone 14"`. If you wish to run your app on an iPhone SE (3rd generation), run the following command:

* npm
* Yarn

```
npm run ios -- --simulator="iPhone SE (3rd generation)"
```

```
yarn ios --simulator "iPhone SE (3rd generation)"
```

The device names correspond to the list of devices available in Xcode. You can check your available devices by running `xcrun simctl list devices` from the console.

<a id="specifying-a-version-of-device"></a>

### Specifying a version of device

If you have multiple iOS versions installed, you also need to specify its appropriate version. E.g. To run your app on an iPhone 14 Pro (16.0) run the following command:

* npm
* Yarn

```
npm run ios -- --simulator="iPhone 14 Pro (16.0)"
```

```
yarn ios --simulator "iPhone 14 Pro (16.0)"
```

<a id="specifying-an-udid"></a>

## Specifying an UDID

You can specify the device UDID returned from `xcrun simctl list devices` command. E.g. To run your app with UDID `AAAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA` run the following command:

* npm
* Yarn

```
npm run ios -- --udid="AAAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA"
```

```
yarn ios --udid "AAAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA"
```
