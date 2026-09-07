# Document nodes

Source: https://reactnative.dev/docs/document-nodes

Version: 0.87 | Retrieved: 2026-09-07

Document nodes represent a complete native view tree. Apps using native navigation would provide a separate document node for each screen. Apps not using native navigation would generally provide a single document for the whole app (similar to single-page apps on Web).

***

<a id="reference"></a>

## Reference

<a id="web-compatible-api"></a>

### Web-compatible API

From [`Document`](https://developer.mozilla.org/en-US/docs/Web/API/HTMLElement):

* Properties

  <!-- -->

  * [`childElementCount`](https://developer.mozilla.org/en-US/docs/Web/API/Document/childElementCount)
  * [`children`](https://developer.mozilla.org/en-US/docs/Web/API/Document/children)
  * [`documentElement`](https://developer.mozilla.org/en-US/docs/Web/API/Document/documentElement)
  * [`firstElementChild`](https://developer.mozilla.org/en-US/docs/Web/API/Document/firstElementChild)
  * [`lastElementChild`](https://developer.mozilla.org/en-US/docs/Web/API/Document/lastElementChild)

* Methods
  <!-- -->
  * [`getElementById()`](https://developer.mozilla.org/en-US/docs/Web/API/Document/getElementById)

From [`Node`](https://developer.mozilla.org/en-US/docs/Web/API/Node):

* Properties

  <!-- -->

  * [`childNodes`](https://developer.mozilla.org/en-US/docs/Web/API/Node/childNodes)
  * [`firstChild`](https://developer.mozilla.org/en-US/docs/Web/API/Node/firstChild)
  * [`isConnected`](https://developer.mozilla.org/en-US/docs/Web/API/Node/isConnected)
  * [`lastChild`](https://developer.mozilla.org/en-US/docs/Web/API/Node/lastChild)
  * [`nextSibling`](https://developer.mozilla.org/en-US/docs/Web/API/Node/nextSibling)
  * [`nodeName`](https://developer.mozilla.org/en-US/docs/Web/API/Node/nodeName)
  * [`nodeType`](https://developer.mozilla.org/en-US/docs/Web/API/Node/nodeType)
  * [`nodeValue`](https://developer.mozilla.org/en-US/docs/Web/API/Node/nodeValue)
  * [`ownerDocument`](https://developer.mozilla.org/en-US/docs/Web/API/Node/ownerDocument)
  * [`parentElement`](https://developer.mozilla.org/en-US/docs/Web/API/Node/parentElement)
  * [`parentNode`](https://developer.mozilla.org/en-US/docs/Web/API/Node/parentNode)
  * [`previousSibling`](https://developer.mozilla.org/en-US/docs/Web/API/Node/previousSibling)
  * [`textContent`](https://developer.mozilla.org/en-US/docs/Web/API/Node/textContent)

* Methods

  <!-- -->

  * [`compareDocumentPosition()`](https://developer.mozilla.org/en-US/docs/Web/API/Node/compareDocumentPosition)
  * [`contains()`](https://developer.mozilla.org/en-US/docs/Web/API/Node/contains)
  * [`getRootNode()`](https://developer.mozilla.org/en-US/docs/Web/API/Node/getRootNode)
  * [`hasChildNodes()`](https://developer.mozilla.org/en-US/docs/Web/API/Node/hasChildNodes)

## Embedded example source

Code extracted from this page’s Expo Snack embeds; interactive previews require the original website.

### Document instance example

Dependencies: `react-native-safe-area-context`

#### `App.js`

```jsx
import {useEffect, useRef} from 'react';
import {Text, TextInput, View} from 'react-native';

function MyComponent(props) {
  return (
    <View ref={props.ref}>
      <Text>Start typing below</Text>
      <TextInput id="main-text-input" />
    </View>
  )
}

export default function AccessingDocument() {
  const ref = useRef(null);

  useEffect(() => {
    // Get the main text input in the screen and focus it after initial load.
    const element = ref.current;
    const doc = element.ownerDocument;
    const textInput = doc.getElementById('main-text-input');
    textInput?.focus();
  }, []);

  return (
    <MyComponent ref={ref} />
  );
}
```
