# Introduction

Source: https://reactnative.dev/docs/getting-started

Version: 0.87 | Retrieved: 2026-09-07

Welcome to the very start of your React Native journey! If you're looking for getting started instructions, they've moved to [their own section](environment-setup.md). Continue reading for an introduction to the documentation, Native Components, React, and more!

![ ](https://reactnative.dev/docs/assets/p_android-ios-devices.svg)

Many different kinds of people use React Native: from advanced iOS developers to React beginners, to people getting started programming for the first time in their career. These docs were written for all learners, no matter their experience level or background.

<a id="how-to-use-these-docs"></a>

## How to use these docs

You can start here and read through these docs linearly like a book; or you can read the specific sections you need. Already familiar with React? You can skip [that section](intro-react.md)—or read it for a light refresher.

<a id="prerequisites"></a>

## Prerequisites

To work with React Native, you will need to have an understanding of JavaScript fundamentals. If you’re new to JavaScript or need a refresher, you can [dive in](https://developer.mozilla.org/en-US/docs/Web/JavaScript) or [brush up](https://developer.mozilla.org/en-US/docs/Web/JavaScript/A_re-introduction_to_JavaScript) at Mozilla Developer Network.

info

While we do our best to assume no prior knowledge of React, Android, or iOS development, these are valuable topics of study for the aspiring React Native developer. Where sensible, we have linked to resources and articles that go more in depth.

<a id="interactive-examples"></a>

## Interactive examples

This introduction lets you get started immediately in your browser with interactive examples like this one:

The above is a Snack Player. It’s a handy tool created by Expo to embed and run React Native projects and share how they render in platforms like Android and iOS. The code is live and editable, so you can play directly with it in your browser. Go ahead and try changing the "Try editing me!" text above to "Hello, world!"

tip

Optionally, if you want to set up a local development environment, [you can follow our guide to setting up your environment on your local machine](set-up-your-environment.md) and paste the code examples into your project. (If you are a web developer, you may already have a local environment set up for mobile browser testing!)

<a id="developer-notes"></a>

## Developer Notes

People from many different development backgrounds are learning React Native. You may have experience with a range of technologies, from web to Android to iOS and more. We try to write for developers from all backgrounds. Sometimes we provide explanations specific to one platform or another like so:

* Android
* iOS
* Web

info

Android developers may be familiar with this concept.

info

iOS developers may be familiar with this concept.

info

Web developers may be familiar with this concept.

<a id="formatting"></a>

## Formatting

Menu paths are written in bold and use carets to navigate submenus. Example: **Android Studio > Preferences**

***

Now that you know how this guide works, it's time to get to know the foundation of React Native: [Native Components](intro-react-native-components.md).

## Embedded example source

Code extracted from this page’s Expo Snack embeds; interactive previews require the original website.

### Hello World

Dependencies: `react-native-safe-area-context`

#### `App.tsx`

```tsx
import {Text, View} from 'react-native';

const YourApp = () => {
  return (
    <View
      style={{
        flex: 1,
        justifyContent: 'center',
        alignItems: 'center',
      }}>
      <Text>Try editing me! 🎉</Text>
    </View>
  );
};

export default YourApp;
```
