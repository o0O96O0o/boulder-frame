# Core Components and APIs

Source: https://reactnative.dev/docs/components-and-apis

Version: 0.87 | Retrieved: 2026-09-07

React Native provides a number of built-in [Core Components](intro-react-native-components.md) ready for you to use in your app. You can find them all in the left sidebar (or menu above, if you are on a narrow screen). If you're not sure where to get started, take a look at the following categories:

* [Basic Components](components-and-apis.md#basic-components)
* [User Interface](components-and-apis.md#user-interface)
* [List Views](components-and-apis.md#list-views)
* [Android-specific](components-and-apis.md#android-components-and-apis)
* [iOS-specific](components-and-apis.md#ios-components-and-apis)
* [Others](components-and-apis.md#others)

You're not limited to the components and APIs bundled with React Native. React Native has a community of thousands of developers. If you're looking for a library that does something specific, please refer to [this guide about finding libraries](libraries.md#finding-libraries).

<a id="basic-components"></a>

## Basic Components

Most apps will end up using one or more of these basic components.

### [View](view.md)

[The most fundamental component for building a UI.](view.md)

### [Text](text.md)

[A component for displaying text.](text.md)

### [Image](image.md)

[A component for displaying images.](image.md)

### [TextInput](textinput.md)

[A component for inputting text into the app via a keyboard.](textinput.md)

### [Pressable](pressable.md)

[A wrapper component that can detect various stages of press interactions on any of its children.](pressable.md)

### [ScrollView](scrollview.md)

[Provides a scrolling container that can host multiple components and views.](scrollview.md)

### [StyleSheet](stylesheet.md)

[Provides an abstraction layer similar to CSS stylesheets.](stylesheet.md)

<a id="user-interface"></a>

## User Interface

These common user interface controls will render on any platform.

### [Button](button.md)

[A basic button component for handling touches that should render nicely on any platform.](button.md)

### [Switch](switch.md)

[Renders a boolean input.](switch.md)

<a id="list-views"></a>

## List Views

Unlike the more generic [`ScrollView`](scrollview.md), the following list view components only render elements that are currently showing on the screen. This makes them a performant choice for displaying long lists of data.

### [FlatList](flatlist.md)

[A component for rendering performant scrollable lists.](flatlist.md)

### [SectionList](sectionlist.md)

[Like `FlatList`, but for sectioned lists.](sectionlist.md)

<a id="android-components-and-apis"></a>

## Android Components and APIs

Many of the following components provide wrappers for commonly used Android classes.

### [BackHandler](backhandler.md)

[Detect hardware button presses for back navigation.](backhandler.md)

### [DrawerLayoutAndroid](drawerlayoutandroid.md)

[Renders a `DrawerLayout` on Android.](drawerlayoutandroid.md)

### [PermissionsAndroid](permissionsandroid.md)

[Provides access to the permissions model introduced in Android M.](permissionsandroid.md)

### [ToastAndroid](toastandroid.md)

[Create an Android Toast alert.](toastandroid.md)

<a id="ios-components-and-apis"></a>

## iOS Components and APIs

Many of the following components provide wrappers for commonly used UIKit classes.

### [ActionSheetIOS](actionsheetios.md)

[API to display an iOS action sheet or share sheet.](actionsheetios.md)

<a id="others"></a>

## Others

These components may be useful for certain applications. For an exhaustive list of components and APIs, check out the sidebar to the left (or menu above, if you are on a narrow screen).

### [ActivityIndicator](activityindicator.md)

[Displays a circular loading indicator.](activityindicator.md)

### [Alert](alert.md)

[Launches an alert dialog with the specified title and message.](alert.md)

### [Animated](animated.md)

[A library for creating fluid, powerful animations that are easy to build and maintain.](animated.md)

### [Dimensions](dimensions.md)

[Provides an interface for getting device dimensions.](dimensions.md)

### [KeyboardAvoidingView](keyboardavoidingview.md)

[Provides a view that moves out of the way of the virtual keyboard automatically.](keyboardavoidingview.md)

### [Linking](linking.md)

[Provides a general interface to interact with both incoming and outgoing app links.](linking.md)

### [Modal](modal.md)

[Provides a simple way to present content above an enclosing view.](modal.md)

### [PixelRatio](pixelratio.md)

[Provides access to the device pixel density.](pixelratio.md)

### [RefreshControl](refreshcontrol.md)

[This component is used inside a `ScrollView` to add pull to refresh functionality.](refreshcontrol.md)

### [StatusBar](statusbar.md)

[Component to control the app status bar.](statusbar.md)
