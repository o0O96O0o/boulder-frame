# Text nodes

Source: https://reactnative.dev/docs/text-nodes

Version: 0.87 | Retrieved: 2026-09-07

Text nodes represent raw text content on the tree (similar to [`Text`](https://developer.mozilla.org/en-US/docs/Web/API/Text) nodes on Web). They are not directly accessible via `refs`, but can be accessed using methods like [`childNodes`](https://developer.mozilla.org/en-US/docs/Web/API/Node/childNodes) on element refs.

***

<a id="reference"></a>

## Reference

<a id="web-compatible-api"></a>

### Web-compatible API

From [`CharacterData`](https://developer.mozilla.org/en-US/docs/Web/API/CharacterData):

* Properties

  <!-- -->

  * [`data`](https://developer.mozilla.org/en-US/docs/Web/API/CharacterData/data)
  * [`length`](https://developer.mozilla.org/en-US/docs/Web/API/CharacterData/length)
  * [`nextElementSibling`](https://developer.mozilla.org/en-US/docs/Web/API/CharacterData/nextElementSibling)
  * [`previousElementSibling`](https://developer.mozilla.org/en-US/docs/Web/API/CharacterData/previousElementSibling)

* Methods
  <!-- -->
  * [`substringData()`](https://developer.mozilla.org/en-US/docs/Web/API/CharacterData/substringData)

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
    * ℹ️ Will return the [document node](https://reactnative.dev/docs/next/document-nodes) where this component was rendered.
  * [`parentElement`](https://developer.mozilla.org/en-US/docs/Web/API/Node/parentElement)
  * [`parentNode`](https://developer.mozilla.org/en-US/docs/Web/API/Node/parentNode)
  * [`previousSibling`](https://developer.mozilla.org/en-US/docs/Web/API/Node/previousSibling)
  * [`textContent`](https://developer.mozilla.org/en-US/docs/Web/API/Node/textContent)

* Methods

  <!-- -->

  * [`compareDocumentPosition()`](https://developer.mozilla.org/en-US/docs/Web/API/Node/compareDocumentPosition)
  * [`contains()`](https://developer.mozilla.org/en-US/docs/Web/API/Node/contains)
  * [`getRootNode()`](https://developer.mozilla.org/en-US/docs/Web/API/Node/getRootNode)
    * ℹ️ Will return a reference to itself if the component is not mounted.
  * [`hasChildNodes()`](https://developer.mozilla.org/en-US/docs/Web/API/Node/hasChildNodes)

## Embedded example source

Code extracted from this page’s Expo Snack embeds; interactive previews require the original website.

### Text instances example

Dependencies: `react-native-safe-area-context`

#### `App.js`

```jsx
import {useEffect, useRef, useState} from 'react';
import {SafeAreaView, StyleSheet, Text} from 'react-native';

const TextWithRefs = () => {
  const ref = useRef(null);
  const [viewInfo, setViewInfo] = useState('');

  useEffect(() => {
    // `textElement` is an object implementing the interface described here.
    const textElement = ref.current;
    const textNode = textElement.childNodes[0];
    setViewInfo(
      `Text content is: ${textNode.nodeValue}`,
    );
  }, []);

  return (
    <SafeAreaView style={styles.container}>
      <Text ref={ref}>
        Hello world!
      </Text>
      <Text>{viewInfo}</Text>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  content: {
    padding: 10,
    backgroundColor: 'gray',
  },
});

export default TextWithRefs;
```
