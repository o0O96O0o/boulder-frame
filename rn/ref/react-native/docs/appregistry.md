# AppRegistry

Source: https://reactnative.dev/docs/appregistry

Version: 0.87 | Retrieved: 2026-09-07

### Project with Native Code Required

If you are using the managed Expo workflow there is only ever one entry component registered with `AppRegistry` and it is handled automatically (or through [registerRootComponent](https://docs.expo.dev/versions/latest/sdk/register-root-component/)). You do not need to use this API.

`AppRegistry` is the JS entry point to running all React Native apps. App root components should register themselves with `AppRegistry.registerComponent`, then the native system can load the bundle for the app and then actually run the app when it's ready by invoking `AppRegistry.runApplication`.

React TSX

```
import {Text, AppRegistry} from 'react-native';

const App = () => (

  <View>

    <Text>App1</Text>

  </View>

);

AppRegistry.registerComponent('Appname', () => App);
```

To "stop" an application when a view should be destroyed, call `AppRegistry.unmountApplicationComponentAtRootTag` with the tag that was passed into `runApplication`. These should always be used as a pair.

`AppRegistry` should be required early in the `require` sequence to make sure the JS execution environment is setup before other modules are required.

***

# Reference

<a id="methods"></a>

## Methods

<a id="getappkeys"></a>

### `getAppKeys()`

React TSX

```
static getAppKeys(): string[];
```

Returns an array of strings.

***

<a id="getregistry"></a>

### `getRegistry()`

React TSX

```
static getRegistry(): {sections: string[]; runnables: Runnable[]};
```

Returns a [Registry](appregistry.md#registry) object.

***

<a id="getrunnable"></a>

### `getRunnable()`

React TSX

```
static getRunnable(appKey: string): : Runnable | undefined;
```

Returns a [Runnable](appregistry.md#runnable) object.

**Parameters:**

| Name           | Type   |
| -------------- | ------ |
| appKeyRequired | string |

***

<a id="getsectionkeys"></a>

### `getSectionKeys()`

React TSX

```
static getSectionKeys(): string[];
```

Returns an array of strings.

***

<a id="getsections"></a>

### `getSections()`

React TSX

```
static getSections(): Record<string, Runnable>;
```

Returns a [Runnables](appregistry.md#runnables) object.

***

<a id="registercancellableheadlesstask"></a>

### `registerCancellableHeadlessTask()`

React TSX

```
static registerCancellableHeadlessTask(

  taskKey: string,

  taskProvider: TaskProvider,

  taskCancelProvider: TaskCancelProvider,

);
```

Register a headless task which can be cancelled. A headless task is a bit of code that runs without a UI.

**Parameters:**

| Name                             | Type                                                          | Description                                                                                                                                                                                                                         |
| -------------------------------- | ------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| taskKey<br />Required            | string                                                        | The native id for this task instance that was used when startHeadlessTask was called.                                                                                                                                               |
| taskProvider<br />Required       | [TaskProvider](appregistry.md#taskprovider)             | A promise returning function that takes some data passed from the native side as the only argument. When the promise is resolved or rejected the native side is notified of this event and it may decide to destroy the JS context. |
| taskCancelProvider<br />Required | [TaskCancelProvider](appregistry.md#taskcancelprovider) | a void returning function that takes no arguments; when a cancellation is requested, the function being executed by taskProvider should wrap up and return ASAP.                                                                    |

***

<a id="registercomponent"></a>

### `registerComponent()`

React TSX

```
static registerComponent(

  appKey: string,

  getComponentFunc: ComponentProvider,

  section?: boolean,

): string;
```

**Parameters:**

| Name                      | Type              |
| ------------------------- | ----------------- |
| appKeyRequired            | string            |
| componentProviderRequired | ComponentProvider |
| section                   | boolean           |

***

<a id="registerconfig"></a>

### `registerConfig()`

React TSX

```
static registerConfig(config: AppConfig[]);
```

**Parameters:**

| Name           | Type                                           |
| -------------- | ---------------------------------------------- |
| configRequired | [AppConfig](appregistry.md#appconfig)\[] |

***

<a id="registerheadlesstask"></a>

### `registerHeadlessTask()`

React TSX

```
static registerHeadlessTask(

  taskKey: string,

  taskProvider: TaskProvider,

);
```

Register a headless task. A headless task is a bit of code that runs without a UI.

This is a way to run tasks in JavaScript while your app is in the background. It can be used, for example, to sync fresh data, handle push notifications, or play music.

**Parameters:**

| Name                 | Type                                              | Description                                                                                                                                                                                                                         |
| -------------------- | ------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| taskKeyRequired      | string                                            | The native id for this task instance that was used when startHeadlessTask was called.                                                                                                                                               |
| taskProviderRequired | [TaskProvider](appregistry.md#taskprovider) | A promise returning function that takes some data passed from the native side as the only argument. When the promise is resolved or rejected the native side is notified of this event and it may decide to destroy the JS context. |

***

<a id="registerrunnable"></a>

### `registerRunnable()`

React TSX

```
static registerRunnable(appKey: string, func: Runnable): string;
```

**Parameters:**

| Name           | Type     |
| -------------- | -------- |
| appKeyRequired | string   |
| runRequired    | function |

***

<a id="registersection"></a>

### `registerSection()`

React TSX

```
static registerSection(

  appKey: string,

  component: ComponentProvider,

);
```

**Parameters:**

| Name              | Type              |
| ----------------- | ----------------- |
| appKeyRequired    | string            |
| componentRequired | ComponentProvider |

***

<a id="runapplication"></a>

### `runApplication()`

React TSX

```
static runApplication(appKey: string, appParameters: any): void;
```

Loads the JavaScript bundle and runs the app.

**Parameters:**

| Name                  | Type   |
| --------------------- | ------ |
| appKeyRequired        | string |
| appParametersRequired | any    |

***

<a id="setcomponentproviderinstrumentationhook"></a>

### `setComponentProviderInstrumentationHook()`

React TSX

```
static setComponentProviderInstrumentationHook(

  hook: ComponentProviderInstrumentationHook,

);
```

**Parameters:**

| Name         | Type     |
| ------------ | -------- |
| hookRequired | function |

A valid `hook` function accepts the following as arguments:

| Name                            | Type               |
| ------------------------------- | ------------------ |
| componentRequired               | ComponentProvider  |
| scopedPerformanceLoggerRequired | IPerformanceLogger |

The function must also return a React Component.

***

<a id="setwrappercomponentprovider"></a>

### `setWrapperComponentProvider()`

React TSX

```
static setWrapperComponentProvider(

  provider: WrapperComponentProvider,

);
```

**Parameters:**

| Name             | Type              |
| ---------------- | ----------------- |
| providerRequired | ComponentProvider |

***

<a id="startheadlesstask"></a>

### `startHeadlessTask()`

React TSX

```
static startHeadlessTask(

  taskId: number,

  taskKey: string,

  data: any,

);
```

Only called from native code. Starts a headless task.

**Parameters:**

| Name            | Type   | Description                                                          |
| --------------- | ------ | -------------------------------------------------------------------- |
| taskIdRequired  | number | The native id for this task instance to keep track of its execution. |
| taskKeyRequired | string | The key for the task to start.                                       |
| dataRequired    | any    | The data to pass to the task.                                        |

***

<a id="unmountapplicationcomponentatroottag"></a>

### `unmountApplicationComponentAtRootTag()`

React TSX

```
static unmountApplicationComponentAtRootTag(rootTag: number);
```

Stops an application when a view should be destroyed.

**Parameters:**

| Name            | Type   |
| --------------- | ------ |
| rootTagRequired | number |

<a id="type-definitions"></a>

## Type Definitions

<a id="appconfig"></a>

### AppConfig

Application configuration for the `registerConfig` method.

| Type   |
| ------ |
| object |

**Properties:**

| Name           | Type              |
| -------------- | ----------------- |
| appKeyRequired | string            |
| component      | ComponentProvider |
| run            | function          |
| section        | boolean           |

note

Every config is expected to set either `component` or `run` function.

<a id="registry"></a>

### Registry

| Type   |
| ------ |
| object |

**Properties:**

| Name      | Type                                                |
| --------- | --------------------------------------------------- |
| runnables | array of [Runnables](appregistry.md#runnable) |
| sections  | array of strings                                    |

<a id="runnable"></a>

### Runnable

| Type   |
| ------ |
| object |

**Properties:**

| Name      | Type              |
| --------- | ----------------- |
| component | ComponentProvider |
| run       | function          |

<a id="runnables"></a>

### Runnables

An object with key of `appKey` and value of type of [`Runnable`](appregistry.md#runnable).

| Type   |
| ------ |
| object |

<a id="task"></a>

### Task

A `Task` is a function that accepts any data as argument and returns a Promise that resolves to `undefined`.

| Type     |
| -------- |
| function |

<a id="taskcanceller"></a>

### TaskCanceller

A `TaskCanceller` is a function that accepts no argument and returns void.

| Type     |
| -------- |
| function |

<a id="taskcancelprovider"></a>

### TaskCancelProvider

A valid `TaskCancelProvider` is a function that returns a [`TaskCanceller`](appregistry.md#taskcanceller).

| Type     |
| -------- |
| function |

<a id="taskprovider"></a>

### TaskProvider

A valid `TaskProvider` is a function that returns a [`Task`](appregistry.md#task).

| Type     |
| -------- |
| function |
