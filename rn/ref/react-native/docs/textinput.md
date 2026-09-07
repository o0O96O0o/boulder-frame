# TextInput

Source: https://reactnative.dev/docs/textinput

Version: 0.87 | Retrieved: 2026-09-07

A foundational component for inputting text into the app via a keyboard. Props provide configurability for several features, such as auto-correction, auto-capitalization, placeholder text, and different keyboard types, such as a numeric keypad.

The most basic use case is to plop down a `TextInput` and subscribe to the `onChangeText` events to read the user input. There are also other events, such as `onSubmitEditing` and `onFocus` that can be subscribed to. A minimal example:

Two methods exposed via the native element are `.focus()` and `.blur()` that will focus or blur the TextInput programmatically.

Note that some props are only available with `multiline={true/false}`:

`TextInput` has a border at the bottom of its view by default. This border has its padding set by the background image provided by the system, and it cannot be changed. Solutions to avoid this are to either not set height explicitly, in which case the system will take care of displaying the border in the correct position, or to not display the border by setting `underlineColorAndroid` to transparent.

Note that on Android performing text selection in an input can change the app's activity `windowSoftInputMode` param to `adjustResize`. This may cause issues with components that have position: 'absolute' while the keyboard is active. To avoid this behavior either specify `windowSoftInputMode` in AndroidManifest.xml ( <https://developer.android.com/guide/topics/manifest/activity-element.html> ) or control this param programmatically with native code.

***

# Reference

<a id="props"></a>

## Props

<a id="view-props"></a>

### [View Props](view.md#props)

Inherits [View Props](view.md#props).

***

<a id="allowfontscaling"></a>

### `allowFontScaling`

Specifies whether fonts should scale to respect Text Size accessibility settings. The default is `true`.

| Type |
| ---- |
| bool |

***

<a id="autocapitalize"></a>

### `autoCapitalize`

Tells `TextInput` to automatically capitalize certain characters. This property is not supported by some keyboard types such as `name-phone-pad`.

* `characters`: all characters.
* `words`: first letter of each word.
* `sentences`: first letter of each sentence (*default*).
* `none`: don't auto capitalize anything.

| Type                                             |
| ------------------------------------------------ |
| enum('none', 'sentences', 'words', 'characters') |

***

<a id="autocomplete"></a>

### `autoComplete`

Specifies autocomplete hints for the system, so it can provide autofill. On Android, the system will always attempt to offer autofill by using heuristics to identify the type of content. To disable autocomplete, set `autoComplete` to `off`.

The following values work across platforms:

* `additional-name`
* `address-line1`
* `address-line2`
* `birthdate-day` (iOS 17+)
* `birthdate-full` (iOS 17+)
* `birthdate-month` (iOS 17+)
* `birthdate-year` (iOS 17+)
* `cc-csc` (iOS 17+)
* `cc-exp` (iOS 17+)
* `cc-exp-day` (iOS 17+)
* `cc-exp-month` (iOS 17+)
* `cc-exp-year` (iOS 17+)
* `cc-number`
* `country`
* `current-password`
* `email`
* `family-name`
* `given-name`
* `honorific-prefix`
* `honorific-suffix`
* `name`
* `new-password`
* `off`
* `one-time-code`
* `postal-code`
* `street-address`
* `tel`
* `username`

iOS

The following values work on iOS only:

* `cc-family-name` (iOS 17+)
* `cc-given-name` (iOS 17+)
* `cc-middle-name` (iOS 17+)
* `cc-name` (iOS 17+)
* `cc-type` (iOS 17+)
* `nickname`
* `organization`
* `organization-title`
* `url`

Android

The following values work on Android only:

* `gender`
* `name-family`
* `name-given`
* `name-middle`
* `name-middle-initial`
* `name-prefix`
* `name-suffix`
* `password`
* `password-new`
* `postal-address`
* `postal-address-country`
* `postal-address-extended`
* `postal-address-extended-postal-code`
* `postal-address-locality`
* `postal-address-region`
* `sms-otp`
* `tel-country-code`
* `tel-device`
* `tel-national`
* `username-new`

| Type                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| enum('additional-name', 'address-line1', 'address-line2', 'birthdate-day', 'birthdate-full', 'birthdate-month', 'birthdate-year', 'cc-csc', 'cc-exp', 'cc-exp-day', 'cc-exp-month', 'cc-exp-year', 'cc-number', 'country', 'current-password', 'email', 'family-name', 'given-name', 'honorific-prefix', 'honorific-suffix', 'name', 'new-password', 'off', 'one-time-code', 'postal-code', 'street-address', 'tel', 'username', 'cc-family-name', 'cc-given-name', 'cc-middle-name', 'cc-name', 'cc-type', 'nickname', 'organization', 'organization-title', 'url', 'gender', 'name-family', 'name-given', 'name-middle', 'name-middle-initial', 'name-prefix', 'name-suffix', 'password', 'password-new', 'postal-address', 'postal-address-country', 'postal-address-extended', 'postal-address-extended-postal-code', 'postal-address-locality', 'postal-address-region', 'sms-otp', 'tel-country-code', 'tel-device', 'tel-national', 'username-new') |

***

<a id="autocorrect"></a>

### `autoCorrect`

If `false`, disables auto-correct. The default value is `true`.

| Type |
| ---- |
| bool |

***

<a id="autofocus"></a>

### `autoFocus`

If `true`, focuses the input. The default value is `false`.

| Type |
| ---- |
| bool |

***

<a id="️-bluronsubmit"></a>

### 🗑️ `blurOnSubmit`

Deprecated

Note that `submitBehavior` now takes the place of `blurOnSubmit` and will override any behavior defined by `blurOnSubmit`. See [submitBehavior](textinput.md#submitbehavior).

If `true`, the text field will blur when submitted. The default value is true for single-line fields and false for multiline fields. Note that for multiline fields, setting `blurOnSubmit` to `true` means that pressing return will blur the field and trigger the `onSubmitEditing` event instead of inserting a newline into the field.

| Type |
| ---- |
| bool |

***

<a id="carethidden"></a>

### `caretHidden`

If `true`, caret is hidden. The default value is `false`.

| Type |
| ---- |
| bool |

***

<a id="clearbuttonmode-ios"></a>

### `clearButtonMode`iOS

When the clear button should appear on the right side of the text view. This property is supported only for single-line TextInput component. The default value is `never`.

| Type                                                       |
| ---------------------------------------------------------- |
| enum('never', 'while-editing', 'unless-editing', 'always') |

***

<a id="cleartextonfocus-ios"></a>

### `clearTextOnFocus`iOS

If `true`, clears the text field automatically when editing begins.

| Type |
| ---- |
| bool |

***

<a id="contextmenuhidden"></a>

### `contextMenuHidden`

If `true`, context menu is hidden. The default value is `false`.

| Type |
| ---- |
| bool |

***

<a id="datadetectortypes-ios"></a>

### `dataDetectorTypes`iOS

Determines the types of data converted to clickable URLs in the text input. Only valid if `multiline={true}` and `editable={false}`. By default no data types are detected.

You can provide one type or an array of many types.

Possible values for `dataDetectorTypes` are:

* `'phoneNumber'`
* `'link'`
* `'address'`
* `'calendarEvent'`
* `'none'`
* `'all'`

| Type                                                                                                                                                     |
| -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| enum('phoneNumber', 'link', 'address', 'calendarEvent', 'none', 'all'), ,array of enum('phoneNumber', 'link', 'address', 'calendarEvent', 'none', 'all') |

***

<a id="defaultvalue"></a>

### `defaultValue`

Provides an initial value that will change when the user starts typing. Useful for use-cases where you do not want to deal with listening to events and updating the value prop to keep the controlled state in sync.

| Type   |
| ------ |
| string |

***

<a id="disablekeyboardshortcuts-ios"></a>

### `disableKeyboardShortcuts`iOS

If `true`, the keyboard shortcuts (undo/redo and copy buttons) are disabled.

| Type | Default |
| ---- | ------- |
| bool | `false` |

***

<a id="cursorcolor-android"></a>

### `cursorColor`Android

When provided it will set the color of the cursor (or "caret") in the component. Unlike the behavior of `selectionColor` the cursor color will be set independently from the color of the text selection box.

| Type                     |
| ------------------------ |
| [color](colors.md) |

***

<a id="disablefullscreenui-android"></a>

### `disableFullscreenUI`Android

When `false`, if there is a small amount of space available around a text input (e.g. landscape orientation on a phone), the OS may choose to have the user edit the text inside of a full screen text input mode. When `true`, this feature is disabled and users will always edit the text directly inside of the text input. Defaults to `false`.

| Type |
| ---- |
| bool |

***

<a id="editable"></a>

### `editable`

If `false`, text is not editable. The default value is `true`.

| Type |
| ---- |
| bool |

***

<a id="enablesreturnkeyautomatically-ios"></a>

### `enablesReturnKeyAutomatically`iOS

If `true`, the keyboard disables the return key when there is no text and automatically enables it when there is text. The default value is `false`.

| Type |
| ---- |
| bool |

***

<a id="enterkeyhint"></a>

### `enterKeyHint`

Determines what text should be shown to the return key. Has precedence over the `returnKeyType` prop.

The following values work across platforms:

* `done`
* `next`
* `search`
* `send`
* `go`

*Android Only*

The following values work on Android only:

* `previous`

*iOS Only*

The following values work on iOS only:

* `enter`

| Type                                                              |
| ----------------------------------------------------------------- |
| enum('enter', 'done', 'next', 'previous', 'search', 'send', 'go') |

***

<a id="importantforautofill-android"></a>

### `importantForAutofill`Android

Tells the operating system whether the individual fields in your app should be included in a view structure for autofill purposes on Android API Level 26+. Possible values are `auto`, `no`, `noExcludeDescendants`, `yes`, and `yesExcludeDescendants`. The default value is `auto`.

* `auto`: Let the Android System use its heuristics to determine if the view is important for autofill.
* `no`: This view isn't important for autofill.
* `noExcludeDescendants`: This view and its children aren't important for autofill.
* `yes`: This view is important for autofill.
* `yesExcludeDescendants`: This view is important for autofill, but its children aren't important for autofill.

| Type                                                                       |
| -------------------------------------------------------------------------- |
| enum('auto', 'no', 'noExcludeDescendants', 'yes', 'yesExcludeDescendants') |

***

<a id="inlineimageleft-android"></a>

### `inlineImageLeft`Android

If defined, the provided image resource will be rendered on the left. The image resource must be inside `/android/app/src/main/res/drawable` and referenced like

```
<TextInput

 inlineImageLeft='search_icon'

/>
```

| Type   |
| ------ |
| string |

***

<a id="inlineimagepadding-android"></a>

### `inlineImagePadding`Android

Padding between the inline image, if any, and the text input itself.

| Type   |
| ------ |
| number |

***

<a id="inputaccessoryviewid-ios"></a>

### `inputAccessoryViewID`iOS

An optional identifier which links a custom [InputAccessoryView](inputaccessoryview.md) to this text input. The InputAccessoryView is rendered above the keyboard when this text input is focused.

| Type   |
| ------ |
| string |

***

<a id="inputaccessoryviewbuttonlabel-ios"></a>

### `inputAccessoryViewButtonLabel`iOS

An optional label that overrides the default [InputAccessoryView](inputaccessoryview.md) button label.

By default, the default button label is not localized. Use this property to provide a localized version.

| Type   |
| ------ |
| string |

***

<a id="inputmode"></a>

### `inputMode`

Works like the `inputmode` attribute in HTML, it determines which keyboard to open, e.g. `numeric` and has precedence over `keyboardType`.

Support the following values:

* `none`
* `text`
* `decimal`
* `numeric`
* `tel`
* `search`
* `email`
* `url`

| Type                                                                        |
| --------------------------------------------------------------------------- |
| enum('decimal', 'email', 'none', 'numeric', 'search', 'tel', 'text', 'url') |

***

<a id="keyboardappearance-ios"></a>

### `keyboardAppearance`iOS

Determines the color of the keyboard.

| Type                             |
| -------------------------------- |
| enum('default', 'light', 'dark') |

***

<a id="keyboardtype"></a>

### `keyboardType`

Determines which keyboard to open, e.g.`numeric`.

See screenshots of all the types [here](https://davidl.fr/blog/keyboard-react-native-ios-android#all-react-native-keyboard-type-examples-i-os-on-the-left-android-on-the-right).

The following values work across platforms:

* `default`
* `number-pad`
* `decimal-pad`
* `numeric`
* `email-address`
* `phone-pad`
* `url`

*iOS Only*

The following values work on iOS only:

* `ascii-capable`
* `numbers-and-punctuation`
* `name-phone-pad`
* `twitter`
* `web-search`

*Android Only*

The following values work on Android only:

* `visible-password`

| Type                                                                                                                                                                                                    |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| enum('default', 'email-address', 'numeric', 'phone-pad', 'ascii-capable', 'numbers-and-punctuation', 'url', 'number-pad', 'name-phone-pad', 'decimal-pad', 'twitter', 'web-search', 'visible-password') |

***

<a id="linebreakstrategyios-ios"></a>

### `lineBreakStrategyIOS`iOS

Set line break strategy on iOS 14+. Possible values are `none`, `standard`, `hangul-word` and `push-out`.

| Type                                                        | Default  |
| ----------------------------------------------------------- | -------- |
| enum(`'none'`, `'standard'`, `'hangul-word'`, `'push-out'`) | `'none'` |

***

<a id="linebreakmodeios-ios"></a>

### `lineBreakModeIOS`iOS

Set line break mode on iOS. Possible values are `wordWrapping`, `char`, `clip`, `head`, `middle` and `tail`.

| Type                                                                       | Default          |
| -------------------------------------------------------------------------- | ---------------- |
| enum(`'wordWrapping'`, `'char'`, `'clip'`, `'head'`, `'middle'`, `'tail'`) | `'wordWrapping'` |

***

<a id="maxfontsizemultiplier"></a>

### `maxFontSizeMultiplier`

Specifies largest possible scale a font can reach when `allowFontScaling` is enabled. Possible values:

* `null/undefined` (default): inherit from the parent node or the global default (0)
* `0`: no max, ignore parent/global default
* `>= 1`: sets the `maxFontSizeMultiplier` of this node to this value

| Type   |
| ------ |
| number |

***

<a id="maxlength"></a>

### `maxLength`

Limits the maximum number of characters that can be entered. Use this instead of implementing the logic in JS to avoid flicker.

| Type   |
| ------ |
| number |

***

<a id="multiline"></a>

### `multiline`

If `true`, the text input can be multiple lines. The default value is `false`.

note

It is important to note that this aligns the text to the top on iOS, and centers it on Android. Use with `textAlignVertical` set to `top` for the same behavior in both platforms.

| Type |
| ---- |
| bool |

***

<a id="numberoflines"></a>

### `numberOfLines`

note

`numberOfLines` on iOS is only available on the [New Architecture](../architecture/landing-page.md)

Sets the maximum number of lines for a `TextInput`. Use it with multiline set to `true` to be able to fill the lines.

| Type   |
| ------ |
| number |

***

<a id="onblur"></a>

### `onBlur`

Callback that is called when the text input is blurred.

note

If you are attempting to access the `text` value from `nativeEvent` keep in mind that the resulting value you get can be `undefined` which can cause unintended errors. If you are trying to find the last value of TextInput, you can use the [`onEndEditing`](textinput.md#onendediting) event, which is fired upon completion of editing.

| Type                                   |
| -------------------------------------- |
| `({nativeEvent: TargetEvent}) => void` |

***

<a id="onchange"></a>

### `onChange`

Callback that is called when the text input's text changes.

| Type                                                  |
| ----------------------------------------------------- |
| (`{nativeEvent: {eventCount, target, text}}`) => void |

***

<a id="onchangetext"></a>

### `onChangeText`

Callback that is called when the text input's text changes. Changed text is passed as a single string argument to the callback handler.

| Type     |
| -------- |
| function |

***

<a id="oncontentsizechange"></a>

### `onContentSizeChange`

Callback that is called when the text input's content size changes.

Only called for multiline text inputs.

| Type                                                       |
| ---------------------------------------------------------- |
| (`{nativeEvent: {contentSize: {width, height} }}`) => void |

***

<a id="onendediting"></a>

### `onEndEditing`

Callback that is called when text input ends.

| Type     |
| -------- |
| function |

***

<a id="onpressin"></a>

### `onPressIn`

Callback that is called when a touch is engaged.

| Type                                  |
| ------------------------------------- |
| `({nativeEvent: PressEvent}) => void` |

***

<a id="onpressout"></a>

### `onPressOut`

Callback that is called when a touch is released.

| Type                                  |
| ------------------------------------- |
| `({nativeEvent: PressEvent}) => void` |

***

<a id="onfocus"></a>

### `onFocus`

Callback that is called when the text input is focused.

| Type                                   |
| -------------------------------------- |
| `({nativeEvent: TargetEvent}) => void` |

***

<a id="onkeypress"></a>

### `onKeyPress`

Callback that is called when a key is pressed. This will be called with object where `keyValue` is `'Enter'` or `'Backspace'` for respective keys and the typed-in character otherwise including `' '` for space. Fires before `onChange` callbacks. Note: on Android only the inputs from soft keyboard are handled, not the hardware keyboard inputs.

| Type                                        |
| ------------------------------------------- |
| (`{nativeEvent: {key: keyValue} }`) => void |

***

<a id="onlayout"></a>

### `onLayout`

Invoked on mount and on layout changes.

| Type                                   |
| -------------------------------------- |
| `({nativeEvent: LayoutEvent}) => void` |

***

<a id="onscroll"></a>

### `onScroll`

Invoked on content scroll. May also contain other properties from `ScrollEvent` but on Android `contentSize` is not provided for performance reasons.

| Type                                                |
| --------------------------------------------------- |
| (`{nativeEvent: {contentOffset: {x, y} }}`) => void |

***

<a id="onselectionchange"></a>

### `onSelectionChange`

Callback that is called when the text input selection is changed.

| Type                                                  |
| ----------------------------------------------------- |
| (`{nativeEvent: {selection: {start, end} }}`) => void |

***

<a id="onsubmitediting"></a>

### `onSubmitEditing`

Callback that is called when the text input's submit button is pressed.

| Type                                                  |
| ----------------------------------------------------- |
| (`{nativeEvent: {text, eventCount, target}}`) => void |

Note that on iOS this method isn't called when using `keyboardType="phone-pad"`.

***

<a id="placeholder"></a>

### `placeholder`

The string that will be rendered before text input has been entered.

| Type   |
| ------ |
| string |

***

<a id="placeholdertextcolor"></a>

### `placeholderTextColor`

The text color of the placeholder string.

| Type                     |
| ------------------------ |
| [color](colors.md) |

***

<a id="readonly"></a>

### `readOnly`

If `true`, text is not editable. The default value is `false`.

| Type |
| ---- |
| bool |

***

<a id="returnkeylabel-android"></a>

### `returnKeyLabel`Android

Sets the return key to the label. Use it instead of `returnKeyType`.

| Type   |
| ------ |
| string |

***

<a id="returnkeytype"></a>

### `returnKeyType`

Determines how the return key should look. On Android you can also use `returnKeyLabel`.

*Cross platform*

The following values work across platforms:

* `done`
* `go`
* `next`
* `search`
* `send`

*Android Only*

The following values work on Android only:

* `none`
* `previous`

*iOS Only*

The following values work on iOS only:

* `default`
* `emergency-call`
* `google`
* `join`
* `route`
* `yahoo`

| Type                                                                                                                              |
| --------------------------------------------------------------------------------------------------------------------------------- |
| enum('done', 'go', 'next', 'search', 'send', 'none', 'previous', 'default', 'emergency-call', 'google', 'join', 'route', 'yahoo') |

<a id="rejectrespondertermination-ios"></a>

### `rejectResponderTermination`iOS

If `true`, allows TextInput to pass touch events to the parent component. This allows components such as SwipeableListView to be swipeable from the TextInput on iOS, as is the case on Android by default. If `false`, TextInput always asks to handle the input (except when disabled). The default value is `true`.

| Type |
| ---- |
| bool |

***

<a id="rows-android"></a>

### `rows`Android

Sets the number of lines for a `TextInput`. Use it with multiline set to `true` to be able to fill the lines.

| Type   |
| ------ |
| number |

***

<a id="scrollenabled-ios"></a>

### `scrollEnabled`iOS

If `false`, scrolling of the text view will be disabled. The default value is `true`. Only works with `multiline={true}`.

| Type |
| ---- |
| bool |

***

<a id="securetextentry"></a>

### `secureTextEntry`

If `true`, the text input obscures the text entered so that sensitive text like passwords stay secure. The default value is `false`. Does not work with `multiline={true}`.

| Type |
| ---- |
| bool |

***

<a id="selection"></a>

### `selection`

The start and end of the text input's selection. Set start and end to the same value to position the cursor.

| Type                                  |
| ------------------------------------- |
| object: `{start: number,end: number}` |

***

<a id="selectioncolor"></a>

### `selectionColor`

The highlight, selection handle and cursor color of the text input.

| Type                     |
| ------------------------ |
| [color](colors.md) |

***

<a id="selectionhandlecolor-android"></a>

### `selectionHandleColor`Android

Sets the color of the selection handle. Unlike `selectionColor`, it allows the selection handle color to be customized independently of the selection's color.

| Type                     |
| ------------------------ |
| [color](colors.md) |

***

<a id="selecttextonfocus"></a>

### `selectTextOnFocus`

If `true`, all text will automatically be selected on focus.

| Type |
| ---- |
| bool |

***

<a id="showsoftinputonfocus"></a>

### `showSoftInputOnFocus`

When `false`, it will prevent the soft keyboard from showing when the field is focused. The default value is `true`.

| Type |
| ---- |
| bool |

***

<a id="smartinsertdelete-ios"></a>

### `smartInsertDelete`iOS

If `false`, the iOS system will not insert an extra space after a paste operation neither delete one or two spaces after a cut or delete operation.

| Type | Default |
| ---- | ------- |
| bool | `true`  |

***

<a id="spellcheck-ios"></a>

### `spellCheck`iOS

If `false`, disables spell-check style (i.e. red underlines). The default value is inherited from `autoCorrect`.

| Type |
| ---- |
| bool |

***

<a id="submitbehavior"></a>

### `submitBehavior`

When the return key is pressed,

For single line inputs:

* `'newline'` defaults to `'blurAndSubmit'`
* `undefined` defaults to `'blurAndSubmit'`

For multiline inputs:

* `'newline'` adds a newline
* `undefined` defaults to `'newline'`

For both single line and multiline inputs:

* `'submit'` will only send a submit event and not blur the input
* `'blurAndSubmit`' will both blur the input and send a submit event

| Type                                       |
| ------------------------------------------ |
| enum('submit', 'blurAndSubmit', 'newline') |

***

<a id="textalign"></a>

### `textAlign`

Align the input text to the left, center, or right sides of the input field.

Possible values for `textAlign` are:

* `left`
* `center`
* `right`

| Type                            |
| ------------------------------- |
| enum('left', 'center', 'right') |

***

<a id="textcontenttype-ios"></a>

### `textContentType`iOS

Give the keyboard and the system information about the expected semantic meaning for the content that users enter.

note

[`autoComplete`](#autocomplete), provides the same functionality and is available for all platforms. You can use [`Platform.select`](https://reactnative.dev/docs/next/platform#select) for differing platform behaviors.

Avoid using both `textContentType` and `autoComplete`. For backwards compatibility, `textContentType` takes precedence when both properties are set.

You can set `textContentType` to `username` or `password` to enable autofill of login details from the device keychain.

`newPassword` can be used to indicate a new password input the user may want to save in the keychain, and `oneTimeCode` can be used to indicate that a field can be autofilled by a code arriving in an SMS.

To disable autofill, set `textContentType` to `none`.

Possible values for `textContentType` are:

* `none`
* `addressCity`
* `addressCityAndState`
* `addressState`
* `birthdate` (iOS 17+)
* `birthdateDay` (iOS 17+)
* `birthdateMonth` (iOS 17+)
* `birthdateYear` (iOS 17+)
* `countryName`
* `creditCardExpiration` (iOS 17+)
* `creditCardExpirationMonth` (iOS 17+)
* `creditCardExpirationYear` (iOS 17+)
* `creditCardFamilyName` (iOS 17+)
* `creditCardGivenName` (iOS 17+)
* `creditCardMiddleName` (iOS 17+)
* `creditCardName` (iOS 17+)
* `creditCardNumber`
* `creditCardSecurityCode` (iOS 17+)
* `creditCardType` (iOS 17+)
* `emailAddress`
* `familyName`
* `fullStreetAddress`
* `givenName`
* `jobTitle`
* `location`
* `middleName`
* `name`
* `namePrefix`
* `nameSuffix`
* `newPassword`
* `nickname`
* `oneTimeCode`
* `organizationName`
* `password`
* `postalCode`
* `streetAddressLine1`
* `streetAddressLine2`
* `sublocality`
* `telephoneNumber`
* `URL`
* `username`

| Type                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| enum('none', 'addressCity', 'addressCityAndState', 'addressState', 'birthdate', 'birthdateDay', 'birthdateMonth', 'birthdateYear', 'countryName', 'creditCardExpiration', 'creditCardExpirationMonth', 'creditCardExpirationYear', 'creditCardFamilyName', 'creditCardGivenName', 'creditCardMiddleName', 'creditCardName', 'creditCardNumber', 'creditCardSecurityCode', 'creditCardType', 'emailAddress', 'familyName', 'fullStreetAddress', 'givenName', 'jobTitle', 'location', 'middleName', 'name', 'namePrefix', 'nameSuffix', 'newPassword', 'nickname', 'oneTimeCode', 'organizationName', 'password', 'postalCode', 'streetAddressLine1', 'streetAddressLine2', 'sublocality', 'telephoneNumber', 'URL', 'username') |

***

<a id="passwordrules-ios"></a>

### `passwordRules`iOS

When using `textContentType` as `newPassword` on iOS we can let the OS know the minimum requirements of the password so that it can generate one that will satisfy them. In order to create a valid string for `PasswordRules` take a look to the [Apple Docs](https://developer.apple.com/password-rules/).

tip

If passwords generation dialog doesn't appear please make sure that:

* AutoFill is enabled: **Settings** → **Passwords & Accounts** → toggle "On" the **AutoFill Passwords**,
* iCloud Keychain is used: **Settings** → **Apple ID** → **iCloud** → **Keychain** → toggle "On" the **iCloud Keychain**.

| Type   |
| ------ |
| string |

***

<a id="style"></a>

### `style`

Note that not all Text styles are supported, an incomplete list of what is not supported includes:

* `borderLeftWidth`
* `borderTopWidth`
* `borderRightWidth`
* `borderBottomWidth`
* `borderTopLeftRadius`
* `borderTopRightRadius`
* `borderBottomRightRadius`
* `borderBottomLeftRadius`

[Styles](style.md)

| Type                        |
| --------------------------- |
| [Text](text.md#style) |

***

<a id="textbreakstrategy-android"></a>

### `textBreakStrategy`Android

Set text break strategy on Android API Level 23+, possible values are `simple`, `highQuality`, `balanced` The default value is `highQuality`.

| Type                                      |
| ----------------------------------------- |
| enum('simple', 'highQuality', 'balanced') |

***

<a id="underlinecolorandroid-android"></a>

### `underlineColorAndroid`Android

The color of the `TextInput` underline.

| Type                     |
| ------------------------ |
| [color](colors.md) |

***

<a id="value"></a>

### `value`

The value to show for the text input. `TextInput` is a controlled component, which means the native value will be forced to match this value prop if provided. For most uses, this works great, but in some cases this may cause flickering - one common cause is preventing edits by keeping value the same. In addition to setting the same value, either set `editable={false}`, or set/update `maxLength` to prevent unwanted edits without flicker.

| Type   |
| ------ |
| string |

<a id="methods"></a>

## Methods

<a id="focus"></a>

### `.focus()`

React TSX

```
focus();
```

Makes the native input request focus.

<a id="blur"></a>

### `.blur()`

React TSX

```
blur();
```

Makes the native input lose focus.

<a id="clear"></a>

### `clear()`

React TSX

```
clear();
```

Removes all text from the `TextInput`.

***

<a id="isfocused"></a>

### `isFocused()`

React TSX

```
isFocused(): boolean;
```

Returns `true` if the input is currently focused; `false` otherwise.

# Known issues

* [react-native#19096](https://github.com/facebook/react-native/issues/19096): Doesn't support Android's `onKeyPreIme`.
* [react-native#19366](https://github.com/facebook/react-native/issues/19366): Calling .focus() after closing Android's keyboard via back button doesn't bring keyboard up again.
* [react-native#26799](https://github.com/facebook/react-native/issues/26799): Doesn't support Android's `secureTextEntry` when `keyboardType="email-address"` or `keyboardType="phone-pad"`.

## Embedded example source

Code extracted from this page’s Expo Snack embeds; interactive previews require the original website.

### TextInput Example

Dependencies: `react-native-safe-area-context`

#### `App.tsx`

```tsx
import {useState} from 'react';
import {StyleSheet, TextInput} from 'react-native';
import {SafeAreaView, SafeAreaProvider} from 'react-native-safe-area-context';

const TextInputExample = () => {
  const [text, onChangeText] = useState('Useless Text');
  const [number, onChangeNumber] = useState('');

  return (
    <SafeAreaProvider>
      <SafeAreaView>
        <TextInput
          style={styles.input}
          onChangeText={onChangeText}
          value={text}
        />
        <TextInput
          style={styles.input}
          onChangeText={onChangeNumber}
          value={number}
          placeholder="useless placeholder"
          keyboardType="numeric"
        />
      </SafeAreaView>
    </SafeAreaProvider>
  );
};

const styles = StyleSheet.create({
  input: {
    height: 40,
    margin: 12,
    borderWidth: 1,
    padding: 10,
  },
});

export default TextInputExample;
```

### Multiline TextInput Example

Dependencies: `react-native-safe-area-context`

#### `App.tsx`

```tsx
import {useState} from 'react';
import {TextInput, StyleSheet} from 'react-native';
import {SafeAreaView, SafeAreaProvider} from 'react-native-safe-area-context';

const MultilineTextInputExample = () => {
  const [value, onChangeText] = useState('Useless Multiline Placeholder');

  // If you type something in the text box that is a color,
  // the background will change to that color.
  return (
    <SafeAreaProvider>
      <SafeAreaView
        style={{
          flex: 1,
          backgroundColor: value.toLowerCase(),
        }}>
        <TextInput
          editable
          multiline
          numberOfLines={4}
          maxLength={40}
          onChangeText={text => onChangeText(text)}
          value={value}
          style={styles.textInput}
        />
      </SafeAreaView>
    </SafeAreaProvider>
  );
};

const styles = StyleSheet.create({
  textInput: {
    padding: 10,
    borderColor: '#000',
    borderWidth: 1,
    margin: 12,
  },
});

export default MultilineTextInputExample;
```
