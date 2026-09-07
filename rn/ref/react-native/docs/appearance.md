# Appearance

Source: https://reactnative.dev/docs/appearance

Version: 0.87 | Retrieved: 2026-09-07

React TSX

```
import {Appearance} from 'react-native';
```

The `Appearance` module exposes information about the user's appearance preferences, such as their preferred system color scheme (light or dark).

<a id="developer-notes"></a>

#### Developer notes

* Android
* iOS
* Web

info

The `Appearance` API is inspired by the [Media Queries draft](https://drafts.csswg.org/mediaqueries-5/) from the W3C. The color scheme preference is modeled after the [`prefers-color-scheme` CSS media feature](https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-color-scheme).

info

The color scheme preference will map to the user's Light or [Dark theme](https://developer.android.com/guide/topics/ui/look-and-feel/darktheme) preference on Android 10 (API level 29) devices and higher.

info

The color scheme preference will map to the user's Light or [Dark Mode](https://developer.apple.com/design/human-interface-guidelines/ios/visual-design/dark-mode/) preference on iOS 13 devices and higher.

note

When taking a screenshot, by default, the color scheme may flicker between light and dark mode. It happens because the iOS takes snapshots on both color schemes and updating the user interface with color scheme is asynchronous.

<a id="example"></a>

## Example

You can use the `Appearance` module to determine if the user prefers a dark color scheme:

React TSX

```
const colorScheme = Appearance.getColorScheme();

if (colorScheme === 'dark') {

  // Use dark color scheme

}
```

Although the color scheme is available immediately, this may change when not overridden via `setColorScheme()` (e.g. scheduled color scheme change at sunrise or sunset). Any rendering logic or styles that depend on the user preferred color scheme should try to call this function on every render, rather than caching the value.

**Recommended:** Use the [`useColorScheme`](usecolorscheme.md) hook.

<a id="app-level-overriding"></a>

### App-level overriding

`setColorScheme()` overrides the color scheme at the application level — it does not affect the system setting or other applications. Passing `'auto'` removes any override, restoring the system preference.

<!-- -->

***

# Reference

<a id="methods"></a>

## Methods

<a id="getcolorscheme"></a>

### `getColorScheme()`

React TSX

```
static getColorScheme(): 'light' | 'dark' | null;
```

Returns the active color scheme. This value may change at runtime, either at the system level (e.g. scheduled color scheme change at sunrise or sunset) or when overridden at the app level via `setColorScheme()`.

Return values:

* `'light'`: The light color scheme is applied.
* `'dark'`: The dark color scheme is applied.
* `null`: May be returned if the native Appearance module is not available.

See also: [`useColorScheme`](usecolorscheme.md) (hook).

***

<a id="setcolorscheme"></a>

### `setColorScheme()`

React TSX

```
static setColorScheme('light' | 'dark' | 'auto' | 'unspecified'): void;
```

Forces the application to always adopt a light or dark interface style. The change applies to the application and all native elements within it (Alerts, Pickers, etc.).

This is an app-level override — it does not affect the system's selected interface style or any style set in other applications.

Supported values:

* `'light'`: Apply light color scheme.
* `'dark'`: Apply dark color scheme.
* `'auto'`: Follow the system color scheme (removes any override).
* `'unspecified'` (**deprecated**): Follow the system color scheme (removes any override).

***

<a id="addchangelistener"></a>

### `addChangeListener()`

React TSX

```
static addChangeListener(

  listener: (preferences: {colorScheme: 'light' | 'dark' | null}) => void,

): NativeEventSubscription;
```

Add an event handler that is fired when appearance preferences change. On iOS and Android, the `colorScheme` value in the callback is always `'light'` or `'dark'`.
