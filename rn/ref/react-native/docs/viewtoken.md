# ViewToken Object Type

Source: https://reactnative.dev/docs/viewtoken

Version: 0.87 | Retrieved: 2026-09-07

`ViewToken` object is returned as one of the properties in the `onViewableItemsChanged` callback (for example, in the [FlatList](flatlist.md) component). It is exported by [`ViewabilityHelper.js`](https://github.com/facebook/react-native/blob/main/packages/react-native/Libraries/Lists/ViewabilityHelper.js).

<a id="example"></a>

## Example

JavaScript

```
{

  item: {key: "key-12"},

  key: "key-12",

  index: 11,

  isViewable: true

}
```

<a id="keys-and-values"></a>

## Keys and values

<a id="index"></a>

### `index`

Unique numeric identifier assigned to the data element.

| Type   | Optional |
| ------ | -------- |
| number | Yes      |

<a id="isviewable"></a>

### `isViewable`

Specifies if at least some part of list element is visible in the viewport.

| Type    | Optional |
| ------- | -------- |
| boolean | No       |

<a id="item"></a>

### `item`

Item data

| Type | Optional |
| ---- | -------- |
| any  | No       |

<a id="key"></a>

### `key`

Key identifier assigned to the data element extracted to the top level.

| Type   | Optional |
| ------ | -------- |
| string | No       |

<a id="section"></a>

### `section`

Item section data when used with `SectionList`.

| Type | Optional |
| ---- | -------- |
| any  | Yes      |

<a id="used-by"></a>

## Used by

* [`FlatList`](flatlist.md)
* [`SectionList`](sectionlist.md)
* [`VirtualizedList`](virtualizedlist.md)
