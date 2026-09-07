# Threading Model

Source: https://reactnative.dev/architecture/threading-model

Version: current | Retrieved: 2026-09-07

caution

This document refers to the [New Architecture](fabric-renderer.md), that is in active roll-out.

<a id="the-react-native-renderer-distributes-the-work-of-the-render-pipeline-across-multiple-threads"></a>

#### The React Native renderer distributes the work of the [render pipeline](render-pipeline.md) across multiple threads.

Here we define the threading model and provide some examples to illustrate thread usage of the render pipeline.

React Native renderer is designed to be thread safe. At a high level thread safety is guaranteed by using immutable data structures in the internals of the framework (enforced by C++ “const correctness” feature). This means that every update in React creates or clones new objects in the renderer instead of updating data structures. This allows the framework to expose thread safe and synchronous APIs to React.

The renderer uses two different threads:

* **UI thread** (often called main): The only thread that can manipulate host views.
* **JavaScript thread**: This is where React’s render phase, as well as layout, are executed.

Let’s review the supported scenarios of execution for each phase:

![Threading model symbols](https://reactnative.dev/docs/assets/Architecture/threading-model/symbols.png)

<a id="render-scenarios"></a>

## Render Scenarios

<a id="render-in-a-js-thread"></a>

### Render in a JS Thread

This is the most common scenario where most of the render pipeline happens on JavaScript thread.

![Threading model use case one](https://reactnative.dev/docs/assets/Architecture/threading-model/case-1.jpg)

***

<a id="render-in-the-ui-thread"></a>

### Render in the UI Thread

When there is a high priority event on the UI Thread, the renderer is able to execute all the render pipeline synchronously on the UI thread.

![Threading model use case two](https://reactnative.dev/docs/assets/Architecture/threading-model/case-2.jpg)

***

<a id="default-or-continuous-event-interruption"></a>

### Default or continuous event interruption

This scenario shows the interruption of the render phase by a low priority event in the UI thread. React and the React Native renderer are able to interrupt the render phase and merge its state with a low priority event that is executed on the UI thread. In this case the render process continues executing in the JS thread.

![Threading model use case three](https://reactnative.dev/docs/assets/Architecture/threading-model/case-3.jpg)

***

<a id="discrete-event-interruption"></a>

### Discrete event interruption

The render phase is interruptible. This scenario shows the interruption of the render phase by a high priority event in the UI thread. React and the renderer are able to interrupt the render phase and merge its state with a high priority event that was executed on the UI thread. The render phase executes synchronously on the UI thread.

![Threading model use case four](https://reactnative.dev/docs/assets/Architecture/threading-model/case-4.jpg)

***

<a id="c-state-update"></a>

### C++ State update

Update originating on UI thread and skips rendering phase. See [React Native Renderer State Updates](render-pipeline.md#react-native-renderer-state-updates) for more details.

![Threading model use case six](https://reactnative.dev/docs/assets/Architecture/threading-model/case-6.jpg)
