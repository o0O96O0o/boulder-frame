# Handling Text Input

Source: https://reactnative.dev/docs/handling-text-input

Version: 0.87 | Retrieved: 2026-09-07

[`TextInput`](https://reactnative.dev/docs/textinput#content) is a [Core Component](intro-react-native-components.md) that allows the user to enter text. It has an `onChangeText` prop that takes a function to be called every time the text changed, and an `onSubmitEditing` prop that takes a function to be called when the text is submitted.

For example, let's say that as the user types, you're translating their words into a different language. In this new language, every single word is written the same way: 🍕. So the sentence "Hello there Bob" would be translated as "🍕 🍕 🍕".

In this example, we store `text` in the state, because it changes over time.

There are a lot more things you might want to do with a text input. For example, you could validate the text inside while the user types. For more detailed examples, see the [React docs on controlled components](https://react.dev/reference/react-dom/components/input#controlling-an-input-with-a-state-variable), or the [reference docs for TextInput](textinput.md).

A `TextInput` is one of many ways for the user to interact with your app. For examples of other ways to handle input, see the documentation on [how to handle touches](handling-touches.md).

Now, let's take a look at [ScrollView](using-a-scrollview.md), another Core Component.

## Embedded example source

Code extracted from this page’s Expo Snack embeds; interactive previews require the original website.

### Handling Text Input

Dependencies: `react-native-safe-area-context`

#### `App.tsx`

```tsx
import {useState} from 'react';
import {Text, TextInput, View} from 'react-native';

const PizzaTranslator = () => {
  const [text, setText] = useState('');
  return (
    <View style={{flex: 1, justifyContent: 'center'}}>
      <TextInput
        placeholder="Type here to translate!"
        onChangeText={newText => setText(newText)}
        defaultValue={text}
        style={{
          height: 40,
          padding: 5,
          marginHorizontal: 8,
          borderWidth: 1,
        }}
      />
      <Text style={{padding: 10, fontSize: 42}}>
        {text
          .split(' ')
          .map(word => word && '🍕')
          .join(' ')}
      </Text>
    </View>
  );
};

export default PizzaTranslator;
```
