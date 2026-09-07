# Linking Libraries

Source: https://reactnative.dev/docs/linking-libraries-ios

Version: 0.87 | Retrieved: 2026-09-07

Not every app uses all the native capabilities, and including the code to support all those features would impact the binary size... But we still want to support adding these features whenever you need them.

With that in mind we exposed many of these features as independent static libraries.

For most of the libs it will be as quick as dragging two files, sometimes a third step will be necessary, but no more than that.

note

All the libraries we ship with React Native live in the `Libraries` folder in the root of the repository. Some of them are pure JavaScript, and you only need to `require` it. Other libraries also rely on some native code, in that case you'll have to add these files to your app, otherwise the app will throw an error as soon as you try to use the library.

<a id="here-are-the-few-steps-to-link-your-libraries-that-contain-native-code"></a>

## Here are the few steps to link your libraries that contain native code

<a id="automatic-linking"></a>

### Automatic linking

Install a library with native dependencies:

```
npm install <library-with-native-dependencies> --save
```

info

`--save` or `--save-dev` flag is very important for this step. React Native will link your libs based on `dependencies` and `devDependencies` in your `package.json` file.

That's it! Next time you build your app the native code will be linked thanks to the [autolinking](https://github.com/react-native-community/cli/blob/main/docs/autolinking.md) mechanism.

<a id="manual-linking"></a>

### Manual linking

<a id="step-1"></a>

#### Step 1

If the library has native code, there must be an `.xcodeproj` file inside its folder. Drag this file to your project on Xcode (usually under the `Libraries` group on Xcode);

![](https://reactnative.dev/assets/images/AddToLibraries-92a6a7f58c75a8344d9bbeeae4ac167b.png)

<a id="step-2"></a>

#### Step 2

Click on your main project file (the one that represents the `.xcodeproj`) select `Build Phases` and drag the static library from the `Products` folder inside the Library you are importing to `Link Binary With Libraries`

![](https://reactnative.dev/assets/images/AddToBuildPhases-3e79422ff24780db618eae2d7a5ea604.png)

<a id="step-3"></a>

#### Step 3

Not every library will need this step, what you need to consider is:

*Do I need to know the contents of the library at compile time?*

What that means is, are you using this library on the native side or only in JavaScript? If you are only using it in JavaScript, you are good to go!

If you do need to call it from native, then we need to know the library's headers. To achieve that you have to go to your project's file, select `Build Settings` and search for `Header Search Paths`. There you should include the path to your library. (This documentation used to recommend using `recursive`, but this is no longer recommended, as it can cause subtle build failures, especially with CocoaPods.)

![](https://reactnative.dev/assets/images/AddToSearchPaths-721692ba7f3a91a1f4e4f73e7d88f2ca.png)
