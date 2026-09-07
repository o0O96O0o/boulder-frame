# VirtualizedList

Source: https://reactnative.dev/docs/virtualizedlist

Version: 0.87 | Retrieved: 2026-09-07

Base implementation for the more convenient [`<FlatList>`](flatlist.md) and [`<SectionList>`](sectionlist.md) components, which are also better documented. In general, this should only really be used if you need more flexibility than [`FlatList`](flatlist.md) provides, e.g. for use with immutable data instead of plain arrays.

Virtualization massively improves memory consumption and performance of large lists by maintaining a finite render window of active items and replacing all items outside of the render window with appropriately sized blank space. The window adapts to scrolling behavior, and items are rendered incrementally with low-pri (after any running interactions) if they are far from the visible area, or with hi-pri otherwise to minimize the potential of seeing blank space.

<a id="example"></a>

## Example

* TypeScript
* JavaScript

***

Some caveats:

* Internal state is not preserved when content scrolls out of the render window. Make sure all your data is captured in the item data or external stores like Flux, Redux, or Relay.
* This is a `PureComponent` which means that it will not re-render if `props` are shallow-equal. Make sure that everything your `renderItem` function depends on is passed as a prop (e.g. `extraData`) that is not `===` after updates, otherwise your UI may not update on changes. This includes the `data` prop and parent component state.
* In order to constrain memory and enable smooth scrolling, content is rendered asynchronously offscreen. This means it's possible to scroll faster than the fill rate and momentarily see blank content. This is a tradeoff that can be adjusted to suit the needs of each application, and we are working on improving it behind the scenes.
* By default, the list looks for a `key` prop on each item and uses that for the React key. Alternatively, you can provide a custom `keyExtractor` prop.

***

# Reference

<a id="props"></a>

## Props

<a id="scrollview-props"></a>

### [ScrollView Props](scrollview.md#props)

Inherits [ScrollView Props](scrollview.md#props).

***

<a id="data"></a>

### `data`

Opaque data type passed to `getItem` and `getItemCount` to retrieve items.

| Type |
| ---- |
| any  |

***

<a id="required-getitem"></a>

### Require&#x64;**`getItem`**

React TSX

```
(data: any, index: number) => any;
```

A generic accessor for extracting an item from any sort of data blob.

| Type     |
| -------- |
| function |

***

<a id="required-getitemcount"></a>

### Require&#x64;**`getItemCount`**

React TSX

```
(data: any) => number;
```

Determines how many items are in the data blob.

| Type     |
| -------- |
| function |

***

<a id="required-renderitem"></a>

### Require&#x64;**`renderItem`**

React TSX

```
(info: any) => ?React.Element<any>
```

Takes an item from `data` and renders it into the list

| Type     |
| -------- |
| function |

***

<a id="cellrenderercomponent"></a>

### `CellRendererComponent`

CellRendererComponent allows customizing how cells rendered by `renderItem`/`ListItemComponent` are wrapped when placed into the underlying ScrollView. This component must accept event handlers which notify VirtualizedList of changes within the cell.

| Type                                     |
| ---------------------------------------- |
| `React.ComponentType<CellRendererProps>` |

***

<a id="itemseparatorcomponent"></a>

### `ItemSeparatorComponent`

Rendered in between each item, but not at the top or bottom. By default, `highlighted` and `leadingItem` props are provided. `renderItem` provides `separators.highlight`/`unhighlight` which will update the `highlighted` prop, but you can also add custom props with `separators.updateProps`. Can be a React Component (e.g. `SomeComponent`), or a React element (e.g. `<SomeComponent />`).

| Type                         |
| ---------------------------- |
| component, function, element |

***

<a id="listemptycomponent"></a>

### `ListEmptyComponent`

Rendered when the list is empty. Can be a React Component (e.g. `SomeComponent`), or a React element (e.g. `<SomeComponent />`).

| Type               |
| ------------------ |
| component, element |

***

<a id="listitemcomponent"></a>

### `ListItemComponent`

Each data item is rendered using this element. Can be a React Component Class, or a render function.

| Type                |
| ------------------- |
| component, function |

***

<a id="listfootercomponent"></a>

### `ListFooterComponent`

Rendered at the bottom of all the items. Can be a React Component (e.g. `SomeComponent`), or a React element (e.g. `<SomeComponent />`).

| Type               |
| ------------------ |
| component, element |

***

<a id="listfootercomponentstyle"></a>

### `ListFooterComponentStyle`

Styling for internal View for `ListFooterComponent`.

| Type          | Required |
| ------------- | -------- |
| ViewStyleProp | No       |

***

<a id="listheadercomponent"></a>

### `ListHeaderComponent`

Rendered at the top of all the items. Can be a React Component (e.g. `SomeComponent`), or a React element (e.g. `<SomeComponent />`).

| Type               |
| ------------------ |
| component, element |

***

<a id="listheadercomponentstyle"></a>

### `ListHeaderComponentStyle`

Styling for internal View for `ListHeaderComponent`.

| Type                                    |
| --------------------------------------- |
| [View Style](view-style-props.md) |

***

<a id="debug"></a>

### `debug`

`debug` will turn on extra logging and visual overlays to aid with debugging both usage and implementation, but with a significant perf hit.

| Type    |
| ------- |
| boolean |

***

<a id="️-disablevirtualization"></a>

### 🗑️ `disableVirtualization`

Deprecated

Virtualization provides significant performance and memory optimizations, but fully unmounts react instances that are outside of the render window. You should only need to disable this for debugging purposes.

| Type    |
| ------- |
| boolean |

***

<a id="extradata"></a>

### `extraData`

A marker property for telling the list to re-render (since it implements `PureComponent`). If any of your `renderItem`, Header, Footer, etc. functions depend on anything outside of the `data` prop, stick it here and treat it immutably.

| Type |
| ---- |
| any  |

***

<a id="getitemlayout"></a>

### `getItemLayout`

React TSX

```
(

  data: any,

  index: number,

) => {length: number, offset: number, index: number}
```

| Type     |
| -------- |
| function |

***

<a id="horizontal"></a>

### `horizontal`

If `true`, renders items next to each other horizontally instead of stacked vertically.

| Type    |
| ------- |
| boolean |

***

<a id="initialnumtorender"></a>

### `initialNumToRender`

How many items to render in the initial batch. This should be enough to fill the screen but not much more. Note these items will never be unmounted as part of the windowed rendering in order to improve perceived performance of scroll-to-top actions.

| Type   | Default |
| ------ | ------- |
| number | `10`    |

***

<a id="initialscrollindex"></a>

### `initialScrollIndex`

Instead of starting at the top with the first item, start at `initialScrollIndex`. This disables the "scroll to top" optimization that keeps the first `initialNumToRender` items always rendered and immediately renders the items starting at this initial index. Requires `getItemLayout` to be implemented.

| Type   |
| ------ |
| number |

***

<a id="inverted"></a>

### `inverted`

Reverses the direction of scroll. Uses scale transforms of `-1`.

| Type    |
| ------- |
| boolean |

***

<a id="keyextractor"></a>

### `keyExtractor`

React TSX

```
(item: any, index: number) => string;
```

Used to extract a unique key for a given item at the specified index. Key is used for caching and as the react key to track item re-ordering. The default extractor checks `item.key`, then `item.id`, and then falls back to using the index, like React does.

| Type     |
| -------- |
| function |

***

<a id="maxtorenderperbatch"></a>

### `maxToRenderPerBatch`

The maximum number of items to render in each incremental render batch. The more rendered at once, the better the fill rate, but responsiveness may suffer because rendering content may interfere with responding to button taps or other interactions.

| Type   |
| ------ |
| number |

***

<a id="onendreached"></a>

### `onEndReached`

Called once when the scroll position gets within `onEndReachedThreshold` from the logical end of the list.

| Type                                        |
| ------------------------------------------- |
| `(info: {distanceFromEnd: number}) => void` |

***

<a id="onendreachedthreshold"></a>

### `onEndReachedThreshold`

How far from the end (in units of visible length of the list) the trailing edge of the list must be from the end of the content to trigger the `onEndReached` callback. Thus, a value of 0.5 will trigger `onEndReached` when the end of the content is within half the visible length of the list.

| Type   | Default |
| ------ | ------- |
| number | `2`     |

***

<a id="onrefresh"></a>

### `onRefresh`

React TSX

```
() => void;
```

If provided, a standard `RefreshControl` will be added for "Pull to Refresh" functionality. Make sure to also set the `refreshing` prop correctly.

| Type     |
| -------- |
| function |

***

<a id="onscrolltoindexfailed"></a>

### `onScrollToIndexFailed`

React TSX

```
(info: {

  index: number,

  highestMeasuredFrameIndex: number,

  averageItemLength: number,

}) => void;
```

Used to handle failures when scrolling to an index that has not been measured yet. Recommended action is to either compute your own offset and `scrollTo` it, or scroll as far as possible and then try again after more items have been rendered.

| Type     |
| -------- |
| function |

***

<a id="onstartreached"></a>

### `onStartReached`

Called once when the scroll position gets within `onStartReachedThreshold` from the logical start of the list.

| Type                                          |
| --------------------------------------------- |
| `(info: {distanceFromStart: number}) => void` |

***

<a id="onstartreachedthreshold"></a>

### `onStartReachedThreshold`

How far from the start (in units of visible length of the list) the leading edge of the list must be from the start of the content to trigger the `onStartReached` callback. Thus, a value of 0.5 will trigger `onStartReached` when the start of the content is within half the visible length of the list.

| Type   | Default |
| ------ | ------- |
| number | `2`     |

***

<a id="onviewableitemschanged"></a>

### `onViewableItemsChanged`

Called when the viewability of rows changes, as defined by the `viewabilityConfig` prop.

| Type                                                                     |
| ------------------------------------------------------------------------ |
| `(callback: {changed: ViewToken[], viewableItems: ViewToken[]}) => void` |

***

<a id="persistentscrollbar"></a>

### `persistentScrollbar`

| Type |
| ---- |
| bool |

***

<a id="progressviewoffset"></a>

### `progressViewOffset`

Set this when offset is needed for the loading indicator to show correctly.

| Type   |
| ------ |
| number |

***

<a id="refreshcontrol"></a>

### `refreshControl`

A custom refresh control element. When set, it overrides the default `<RefreshControl>` component built internally. The onRefresh and refreshing props are also ignored. Only works for vertical VirtualizedList.

| Type    |
| ------- |
| element |

***

<a id="refreshing"></a>

### `refreshing`

Set this true while waiting for new data from a refresh.

| Type    |
| ------- |
| boolean |

***

<a id="removeclippedsubviews"></a>

### `removeClippedSubviews`

warning

Using this property may lead to bugs (missing content) in some circumstances - use at your own risk.

When `true`, offscreen child views are removed from their native backing superview when offscreen. This may improve scroll performance for large lists. On Android the default value is `true`.

| Type    |
| ------- |
| boolean |

***

<a id="renderscrollcomponent"></a>

### `renderScrollComponent`

React TSX

```
(props: object) => element;
```

Render a custom scroll component, e.g. with a differently styled `RefreshControl`.

| Type     |
| -------- |
| function |

***

<a id="viewabilityconfig"></a>

### `viewabilityConfig`

See `ViewabilityHelper.js` for flow type and further documentation.

| Type              |
| ----------------- |
| ViewabilityConfig |

***

<a id="viewabilityconfigcallbackpairs"></a>

### `viewabilityConfigCallbackPairs`

List of `ViewabilityConfig`/`onViewableItemsChanged` pairs. A specific `onViewableItemsChanged` will be called when its corresponding `ViewabilityConfig`'s conditions are met. See `ViewabilityHelper.js` for flow type and further documentation.

| Type                                   |
| -------------------------------------- |
| array of ViewabilityConfigCallbackPair |

***

<a id="updatecellsbatchingperiod"></a>

### `updateCellsBatchingPeriod`

Amount of time between low-pri item render batches, e.g. for rendering items quite a ways off screen. Similar fill rate/responsiveness tradeoff as `maxToRenderPerBatch`.

| Type   |
| ------ |
| number |

***

<a id="windowsize"></a>

### `windowSize`

Determines the maximum number of items rendered outside of the visible area, in units of visible lengths. So if your list fills the screen, then `windowSize={21}` (the default) will render the visible screen area plus up to 10 screens above and 10 below the viewport. Reducing this number will reduce memory consumption and may improve performance, but will increase the chance that fast scrolling may reveal momentary blank areas of unrendered content.

| Type   |
| ------ |
| number |

<a id="methods"></a>

## Methods

<a id="flashscrollindicators"></a>

### `flashScrollIndicators()`

React TSX

```
flashScrollIndicators();
```

***

<a id="getscrollablenode"></a>

### `getScrollableNode()`

React TSX

```
getScrollableNode(): any;
```

***

<a id="getscrollref"></a>

### `getScrollRef()`

React TSX

```
getScrollRef():

  | React.ElementRef<typeof ScrollView>

  | React.ElementRef<typeof View>

  | null;
```

***

<a id="getscrollresponder"></a>

### `getScrollResponder()`

React TSX

```
getScrollResponder () => ScrollResponderMixin | null;
```

Provides a handle to the underlying scroll responder. Note that `this._scrollRef` might not be a `ScrollView`, so we need to check that it responds to `getScrollResponder` before calling it.

***

<a id="scrolltoend"></a>

### `scrollToEnd()`

React TSX

```
scrollToEnd(params?: {animated?: boolean});
```

Scrolls to the end of the content. May be janky without `getItemLayout` prop.

**Parameters:**

| Name   | Type   |
| ------ | ------ |
| params | object |

Valid `params` keys are:

* `'animated'` (boolean) - Whether the list should do an animation while scrolling. Defaults to `true`.

***

<a id="scrolltoindex"></a>

### `scrollToIndex()`

React TSX

```
scrollToIndex(params: {

  index: number;

  animated?: boolean;

  viewOffset?: number;

  viewPosition?: number;

});
```

Valid `params` consist of:

* 'index' (number). Required.
* 'animated' (boolean). Optional.
* 'viewOffset' (number). Optional.
* 'viewPosition' (number). Optional.

***

<a id="scrolltoitem"></a>

### `scrollToItem()`

React TSX

```
scrollToItem(params: {

  item: ItemT;

  animated?: boolean;

  viewOffset?: number;

  viewPosition?: number;

);
```

Valid `params` consist of:

* 'item' (Item). Required.
* 'animated' (boolean). Optional.
* 'viewOffset' (number). Optional.
* 'viewPosition' (number). Optional.

***

<a id="scrolltooffset"></a>

### `scrollToOffset()`

React TSX

```
scrollToOffset(params: {

  offset: number;

  animated?: boolean;

});
```

Scroll to a specific content pixel offset in the list.

Param `offset` expects the offset to scroll to. In case of `horizontal` is true, the offset is the x-value, in any other case the offset is the y-value.

Param `animated` (`true` by default) defines whether the list should do an animation while scrolling.

## Embedded example source

Code extracted from this page’s Expo Snack embeds; interactive previews require the original website.

### VirtualizedListExample

Dependencies: `react-native-safe-area-context`

#### `App.js`

```jsx
import {View, VirtualizedList, StyleSheet, Text, StatusBar} from 'react-native';
import {SafeAreaView, SafeAreaProvider} from 'react-native-safe-area-context';

const getItem = (_data, index) => ({
  id: Math.random().toString(12).substring(0),
  title: `Item ${index + 1}`,
});

const getItemCount = _data => 50;

const Item = ({title}) => (
  <View style={styles.item}>
    <Text style={styles.title}>{title}</Text>
  </View>
);

const App = () => (
  <SafeAreaProvider>
    <SafeAreaView style={styles.container} edges={['top']}>
      <VirtualizedList
        initialNumToRender={4}
        renderItem={({item}) => <Item title={item.title} />}
        keyExtractor={item => item.id}
        getItemCount={getItemCount}
        getItem={getItem}
      />
    </SafeAreaView>
  </SafeAreaProvider>
);

const styles = StyleSheet.create({
  container: {
    flex: 1,
    marginTop: StatusBar.currentHeight,
  },
  item: {
    backgroundColor: '#f9c2ff',
    height: 150,
    justifyContent: 'center',
    marginVertical: 8,
    marginHorizontal: 16,
    padding: 20,
  },
  title: {
    fontSize: 32,
  },
});

export default App;
```

### VirtualizedListExample

Dependencies: `react-native-safe-area-context`

#### `App.tsx`

```tsx
import {View, VirtualizedList, StyleSheet, Text, StatusBar} from 'react-native';
import {SafeAreaView, SafeAreaProvider} from 'react-native-safe-area-context';

type ItemData = {
  id: string;
  title: string;
};

const getItem = (_data: unknown, index: number): ItemData => ({
  id: Math.random().toString(12).substring(0),
  title: `Item ${index + 1}`,
});

const getItemCount = (_data: unknown) => 50;

type ItemProps = {
  title: string;
};

const Item = ({title}: ItemProps) => (
  <View style={styles.item}>
    <Text style={styles.title}>{title}</Text>
  </View>
);

const App = () => (
  <SafeAreaProvider>
    <SafeAreaView style={styles.container} edges={['top']}>
      <VirtualizedList
        initialNumToRender={4}
        renderItem={({item}) => <Item title={item.title} />}
        keyExtractor={item => item.id}
        getItemCount={getItemCount}
        getItem={getItem}
      />
    </SafeAreaView>
  </SafeAreaProvider>
);

const styles = StyleSheet.create({
  container: {
    flex: 1,
    marginTop: StatusBar.currentHeight,
  },
  item: {
    backgroundColor: '#f9c2ff',
    height: 150,
    justifyContent: 'center',
    marginVertical: 8,
    marginHorizontal: 16,
    padding: 20,
  },
  title: {
    fontSize: 32,
  },
});

export default App;
```
