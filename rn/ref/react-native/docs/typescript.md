# Using TypeScript

Source: https://reactnative.dev/docs/typescript

Version: 0.87 | Retrieved: 2026-09-07

[TypeScript](https://www.typescriptlang.org/) is a language which extends JavaScript by adding type definitions. New React Native projects target TypeScript by default, but also support JavaScript and Flow.

<a id="getting-started-with-typescript"></a>

## Getting Started with TypeScript

New projects created by the [React Native CLI](https://reactnative.dev/docs/getting-started-without-a-framework.md#step-1-creating-a-new-application) or popular templates like [Ignite](https://github.com/infinitered/ignite) will use TypeScript by default.

TypeScript may also be used with [Expo](https://expo.io), which maintains TypeScript templates, or will prompt you to automatically install and configure TypeScript when a `.ts` or `.tsx` file is added to your project.

```
npx create-expo-app --template
```

<a id="adding-typescript-to-an-existing-project"></a>

## Adding TypeScript to an Existing Project

1. Add TypeScript, types, and ESLint plugins to your project.

* npm
* Yarn

```
npm install -D typescript @react-native/typescript-config @types/jest @types/react @types/react-test-renderer
```

```
yarn add --dev typescript @react-native/typescript-config @types/jest @types/react @types/react-test-renderer
```

note

This command adds the latest version of every dependency. The versions may need to be changed to match the existing packages used by your project. You can use a tool like [React Native Upgrade Helper](https://react-native-community.github.io/upgrade-helper/) to see the versions shipped by React Native.

2. Add a TypeScript config file. Create a `tsconfig.json` in the root of your project:

tsconfig.json

```
{

  "extends": "@react-native/typescript-config"

}
```

3. Rename a JavaScript file to be `*.tsx`

warning

You should leave the `./index.js` entrypoint file as it is otherwise you may run into an issue when it comes to bundling a production build.

4. Run `tsc` to type-check your new TypeScript files.

* npm
* Yarn

```
npx tsc
```

```
yarn tsc
```

<a id="using-javascript-instead-of-typescript"></a>

## Using JavaScript Instead of TypeScript

React Native defaults new applications to TypeScript, but JavaScript may still be used. Files with a `.jsx` extension are treated as JavaScript instead of TypeScript, and will not be typechecked. JavaScript modules may still be imported by TypeScript modules, along with the reverse.

<a id="how-typescript-and-react-native-works"></a>

## How TypeScript and React Native works

Out of the box, TypeScript sources are transformed by [Babel](javascript-environment.md#javascript-syntax-transformers) during bundling. We recommend that you use the TypeScript compiler only for type checking. This is the default behavior of `tsc` for newly created applications. If you have existing TypeScript code being ported to React Native, there are [one or two caveats](https://babeljs.io/docs/en/next/babel-plugin-transform-typescript) to using Babel instead of TypeScript.

<a id="what-does-react-native--typescript-look-like"></a>

## What does React Native + TypeScript look like

You can provide an interface for a React Component's [Props](https://reactnative.dev/docs/props.md) and [State](https://reactnative.dev/docs/state.md) via `React.Component<Props, State>` which will provide type-checking and editor auto-completing when working with that component in JSX.

components/Hello.tsx

```
import {useState} from 'react';

import {Button, StyleSheet, Text, View} from 'react-native';

export type Props = {

  name: string;

  baseEnthusiasmLevel?: number;

};

function Hello({name, baseEnthusiasmLevel = 0}: Props) {

  const [enthusiasmLevel, setEnthusiasmLevel] = useState(

    baseEnthusiasmLevel,

  );

  const onIncrement = () =>

    setEnthusiasmLevel(enthusiasmLevel + 1);

  const onDecrement = () =>

    setEnthusiasmLevel(

      enthusiasmLevel > 0 ? enthusiasmLevel - 1 : 0,

    );

  const getExclamationMarks = (numChars: number) =>

    numChars > 0 ? Array(numChars + 1).join('!') : '';

  return (

    <View style={styles.container}>

      <Text style={styles.greeting}>

        Hello {name}

        {getExclamationMarks(enthusiasmLevel)}

      </Text>

      <View>

        <Button

          title="Increase enthusiasm"

          accessibilityLabel="increment"

          onPress={onIncrement}

          color="blue"

        />

        <Button

          title="Decrease enthusiasm"

          accessibilityLabel="decrement"

          onPress={onDecrement}

          color="red"

        />

      </View>

    </View>

  );

}

const styles = StyleSheet.create({

  container: {

    flex: 1,

    alignItems: 'center',

    justifyContent: 'center',

  },

  greeting: {

    fontSize: 20,

    fontWeight: 'bold',

    margin: 16,

  },

});

export default Hello;
```

You can explore the syntax more in the [TypeScript playground](https://www.typescriptlang.org/play?strictNullChecks=false\&jsx=3#code/JYWwDg9gTgLgBAJQKYEMDG8BmUIjgcilQ3wG4BYAKFEljgG8AhAVxhggDsAaOAZRgCeAGyS8AFkiQweAFSQAPaXABqwJAHcAvnGy4CRdDAC0HFDGAA3JGSpUFteILBI4ABRxgAznAC8DKnBwpiBIAFxwnjBQwBwA5hSUgQBGKJ5IAKIcMGLMnsCpIAAySFZCAPzhHMwgSUhQCZq2lGickXAAEkhCQhDhyIYAdABiAMIAPO4QXgB8vnAAFPRBKCE8KWmZ2bn5nkUlXXMADHCaAJS+s-QBcC0cbQDaSFk5eQXFpTxpMJsvO3ulAF05v0MANcqIYGYkPN1hlnts3vshKcEtdbm1OABJDhoIghLJzebnHyzL4-BG7d5deZPLavSlIuAAajgAEYUWjWvBOAARJC4pD4+B+IkXCJScn0-7U2m-RGlOCzY5lOCyinSoRwIxsuDhQ4cyicu7wWIS+RoIQrMzATgAWRQUAA1t4RVUQCMxA7PJVqrUoMTZm6PV7FXBlXAAIJQKAoATzIOeqDeFnsgYAKwgMXm+AAhPhzuF8DZDYk4EQYMwoBwFtdAmNVBoIoIRD56JFhEhPANbpCYnVNNNa4E4GM5Iomx3W+2RF3YkQpDFYgOh8OOl0evR8ARGqXV4F6MEkDu98P6KbvubLSBrXaHc6afCpVTkce92MAPRjmCD3fD+tqdQfxPOsWDYTgVz3cwYBbAAibEBVSFw1SlGCINXdA0E7PIkmAIRgEEQoUFqIQfBgmIBSFVDfxPTh3Cw1ssRxPFaVfYCbggHooFIpIhGYJAqLY98gOAsZQPYDg0OHKDYL5BC0lVR8-gEti4AwrDgBwvCCKIrpSIAE35ZismUtjaKITxPAYjhZKMmBWOAlpONIog9JMvchIgj8G0AocvIA4SDU0VFmi5CcZzmfgO3ESQYG7AwYGhK5Sx7FA+ygcIktXTARHkcJWS4IcUDw2IOExBKQG9OAYMwrI6hggrfzTXJzEwAQRk4BKsnCaraTq65NAawI5xixcMqHTAOt4YAAC8wjgAAmQ5BuHCasgAdSQYBYjEGBCySDi9PwZbAmvKBYhiPKADZloGqgzmC+xoHgAzMBQZghHgTpuggBIgA).

<a id="where-to-find-useful-advice"></a>

## Where to Find Useful Advice

* [TypeScript Handbook](https://www.typescriptlang.org/docs/handbook/intro.html)
* [React's documentation on TypeScript](https://react.dev/learn/typescript)
* [React + TypeScript Cheatsheets](https://github.com/typescript-cheatsheets/react-typescript-cheatsheet#reacttypescript-cheatsheets) has a good overview on how to use React with TypeScript

<a id="using-custom-path-aliases-with-typescript"></a>

## Using Custom Path Aliases with TypeScript

To use custom path aliases with TypeScript, you need to set the path aliases to work from both Babel and TypeScript. Here's how:

1. Edit your `tsconfig.json` to have your [custom path mappings](https://www.typescriptlang.org/docs/handbook/module-resolution.html#path-mapping). Set anything in the root of `src` to be available with no preceding path reference, and allow any test file to be accessed by using `tests/File.tsx`:

Diff

```
{

-  "extends": "@react-native/typescript-config"

+  "extends": "@react-native/typescript-config",

+  "compilerOptions": {

+    "baseUrl": ".",

+    "paths": {

+      "*": ["src/*"],

+      "tests": ["tests/*"],

+      "@components/*": ["src/components/*"],

+    },

+  }

}
```

2. Add [`babel-plugin-module-resolver`](https://github.com/tleunen/babel-plugin-module-resolver) as a development package to your project:

* npm
* Yarn

```
npm install --save-dev babel-plugin-module-resolver
```

```
yarn add --dev babel-plugin-module-resolver
```

3. Finally, configure your `babel.config.js` (note that the syntax for your `babel.config.js` is different from your `tsconfig.json`):

Diff

```
{

   presets: ['module:metro-react-native-babel-preset'],

+  plugins: [

+    [

+       'module-resolver',

+       {

+         root: ['./src'],

+         extensions: ['.ios.js', '.android.js', '.js', '.ts', '.tsx', '.json'],

+         alias: {

+           tests: ['./tests/'],

+           "@components": "./src/components",

+         }

+       }

+    ]

+  ]

}
```
