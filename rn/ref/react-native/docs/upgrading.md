# Upgrading to New Versions

Source: https://reactnative.dev/docs/upgrading

Version: 0.87 | Retrieved: 2026-09-07

Upgrading to new versions of React Native will give you access to more APIs, views, developer tools and other goodies. Upgrading requires a small amount of effort, but we try to make it straightforward for you.

<a id="expo-projects"></a>

## Expo projects

Upgrading your Expo project to a new version of React Native requires updating the `react-native`, `react`, and `expo` package versions in your `package.json` file. Expo recommends upgrading SDK versions incrementally, one at a time. Doing so will help you pinpoint breakages and issues that arise during the upgrade process. See the [Upgrading Expo SDK Walkthrough](https://docs.expo.dev/workflow/upgrading-expo-sdk-walkthrough/) for up-to-date information about upgrading your project.

<a id="react-native-projects"></a>

## React Native projects

Because typical React Native projects are essentially made up of an Android project, an iOS project, and a JavaScript project, upgrading can be rather tricky. The [Upgrade Helper](https://react-native-community.github.io/upgrade-helper/) is a web tool to help you out when upgrading your apps by providing the full set of changes happening between any two versions. It also shows comments on specific files to help understanding why that change is needed.

<a id="1-select-the-versions"></a>

### 1. Select the versions

You first need to select from and to which version you wish to upgrade, by default the latest major versions are selected. After selecting you can click the button "Show me how to upgrade".

💡 Major updates will show a "useful content" section on the top with links to help you out when upgrading.

<a id="2-upgrade-dependencies"></a>

### 2. Upgrade dependencies

The first file that is shown is the `package.json`, it's good to update the dependencies that are showing in there. For example, if `react-native` and `react` appears as changes then you can install it in your project by running following commands:

* npm
* Yarn

```
# {{VERSION}} and {{REACT_VERSION}} are the release versions showing in the diff

npm install react-native@{{VERSION}}

npm install react@{{REACT_VERSION}}
```

```
# {{VERSION}} and {{REACT_VERSION}} are the release versions showing in the diff

yarn add react-native@{{VERSION}}

yarn add react@{{REACT_VERSION}}
```

<a id="3-upgrade-your-project-files"></a>

### 3. Upgrade your project files

The new release may contain updates to other files that are generated when you run `npx react-native init`, those files are listed after the `package.json` in the [Upgrade Helper](https://react-native-community.github.io/upgrade-helper/) page. If there aren't other changes then you only need to rebuild the project to continue developing. In case there are changes you need to manually apply them into your project.

<a id="troubleshooting"></a>

### Troubleshooting

<a id="i-have-done-all-the-changes-but-my-app-is-still-using-an-old-version"></a>

#### I have done all the changes but my app is still using an old version

These sort of errors are usually related to caching, it's recommended to install [react-native-clean-project](https://github.com/pmadruga/react-native-clean-project) to clear all your project's cache and then you can run it again.
