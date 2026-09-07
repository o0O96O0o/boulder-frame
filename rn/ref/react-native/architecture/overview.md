# Architecture Overview

Source: https://reactnative.dev/architecture/overview

Version: current | Retrieved: 2026-09-07

info

Welcome to the Architecture Overview! If you're getting started with React Native, please refer to [Guides](../docs/getting-started.md) section. Continue reading to learn how internals of React Native work!

This section is a work in progress and more material will be added in the future. Please make sure to come back later to check for new information.

Architecture Overview is intended to share conceptual overview of how React Native's internals work. The intended audience includes library authors and core contributors. If you are an app developer, it is not a requirement to be familiar with this material to be effective with React Native. You can still benefit from the overview as it will give you insights into how React Native works under the hood. Feel free to share your feedback on the [discussion inside the working group](https://github.com/reactwg/react-native-new-architecture/discussions/9) for this section.

<a id="table-of-contents"></a>

## Table of Contents

* [About the New Architecture](landing-page.md)

* Rendering

  <!-- -->

  * [Fabric](fabric-renderer.md)
  * [Render, Commit, and Mount](render-pipeline.md)
  * [Cross Platform Implementation](xplat-implementation.md)
  * [View Flattening](view-flattening.md)
  * [Threading Model](threading-model.md)

* Build Tools
  <!-- -->
  * [Bundled Hermes](bundled-hermes.md)

* [Glossary](glossary.md)
