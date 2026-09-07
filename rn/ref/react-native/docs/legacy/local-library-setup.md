# Local libraries setup

Source: https://reactnative.dev/docs/legacy/local-library-setup

Version: 0.87 | Retrieved: 2026-09-07

A local library is a library containing views or modules that's local to your app and not published to a registry. This is different from the traditional setup for view and modules in the sense that a local library is decoupled from your app's native code.

The local library is created outside of the `android/` and `ios/` folders and makes use of autolinking to integrate with your app. The structure with a local library may look like this:

Plaintext

```
MyApp

├── node_modules

├── modules <-- folder for your local libraries

│ └── awesome-module <-- your local library

├── android

├── ios

├── src

├── index.js

└── package.json
```

Since a local library's code exists outside of `android/` and `ios/` folders, it makes it easier to upgrade React Native versions in the future, copy to other projects etc.

To create local library we will use [create-react-native-library](https://callstack.github.io/react-native-builder-bob/create). This tool contains all the necessary templates.

<a id="getting-started"></a>

### Getting Started

Inside your React Native application's root folder, run the following command:

```
npx create-react-native-library@latest awesome-module
```

Where `awesome-module` is the name you would like for the new module. After going through the prompts, you will have a new folder called `modules` in your project's root directory which contains the new module.

<a id="linking"></a>

### Linking

By default, the generated library is automatically linked to the project using `link:` protocol when using Yarn and `file:` when using npm:

* npm
* Yarn

JSON

```
"dependencies": {

  "awesome-module": "file:./modules/awesome-module"

}
```

JSON

```
"dependencies": {

  "awesome-module": "link:./modules/awesome-module"

}
```

This creates a symlink to the library under `node_modules` which makes autolinking work.

<a id="installing-dependencies"></a>

### Installing dependencies

To link the module you need to install dependencies:

* npm
* Yarn

```
npm install
```

```
yarn install
```

<a id="using-module-inside-your-app"></a>

### Using module inside your app

To use the module inside your app, you can import it by its name:

JavaScript

```
import {multiply} from 'awesome-module';
```
