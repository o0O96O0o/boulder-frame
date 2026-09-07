# JavaScript Environment

Source: https://reactnative.dev/docs/javascript-environment

Version: 0.87 | Retrieved: 2026-09-07

<a id="javascript-runtime"></a>

## JavaScript Runtime

When using React Native, you're going to be running your JavaScript code in up to three environments:

* In most cases, React Native will use [Hermes](hermes.md), an open-source JavaScript engine optimized for React Native.
* If Hermes is disabled, React Native will use [JavaScriptCore](https://trac.webkit.org/wiki/JavaScriptCore), the JavaScript engine that powers Safari. Note that on iOS, JavaScriptCore does not use JIT due to the absence of writable executable memory in iOS apps.
* When using Chrome debugging, all JavaScript code runs within Chrome itself, communicating with native code via WebSockets. Chrome uses [V8](https://v8.dev/) as its JavaScript engine.

While these environments are very similar, you may end up hitting some inconsistencies. It is best to avoid relying on specifics of any runtime.

<a id="javascript-syntax-transformers"></a>

## JavaScript Syntax Transformers

Syntax transformers make writing code more enjoyable by allowing you to use new JavaScript syntax without having to wait for support on all interpreters.

React Native ships with the [Babel JavaScript compiler](https://babeljs.io). Check [Babel documentation](https://babeljs.io/docs/plugins/#transform-plugins) on its supported transformations for more details.

A full list of React Native's enabled transformations can be found in [@react-native/babel-preset](https://github.com/facebook/react-native/tree/main/packages/react-native-babel-preset).

| Transformation                                                                                              | Code                                                                             |
| ----------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| ECMAScript 5                                                                                                |                                                                                  |
| Reserved Words                                                                                              | <code>promise.catch(function() {...});</code> |
| ECMAScript 2015 (ES6)                                                                                       |                                                                                  |
| [Arrow functions](https://babeljs.io/docs/learn-es2015/#arrows)                                             | <code>&lt;C onPress={() =&gt; this.setState({pressed: true})} /&gt;</code> |
| [Block scoping](https://babeljs.io/docs/learn-es2015/#let-const)                                            | <code>let greeting = 'hi';</code> |
| [Call spread](https://babeljs.io/docs/learn-es2015/#default-rest-spread)                                    | <code>Math.max(...array);</code> |
| [Classes](https://babeljs.io/docs/learn-es2015/#classes)                                                    | <code>class C extends React.Component {render() { return &lt;View /&gt;; }}</code> |
| [Computed Properties](https://babeljs.io/docs/learn-es2015/#enhanced-object-literals)                       | <code>const key = 'abc'; const obj = {[key]: 10};</code> |
| [Constants](https://babeljs.io/docs/learn-es2015/#let-const)                                                | <code>const answer = 42;</code> |
| [Destructuring](https://babeljs.io/docs/learn-es2015/#destructuring)                                        | <code>const {isActive, style} = this.props;</code> |
| [for…of](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Statements/for...of)             | <code>for (var num of [1, 2, 3]) {...};</code> |
| [Function Name](https://babeljs.io/docs/en/babel-plugin-transform-function-name)                            | <code>let number = x =&gt; x;</code> |
| [Literals](https://babeljs.io/docs/en/babel-plugin-transform-literals)                                      | <code>const b = 0b11; const o = 0o7; const u = 'Hello\u{000A}\u{0009}!';</code> |
| [Modules](https://babeljs.io/docs/learn-es2015/#modules)                                                    | <code>import {Component} from 'react';</code> |
| [Object Concise Method](https://babeljs.io/docs/learn-es2015/#enhanced-object-literals)                     | <code>const obj = {method() { return 10; }};</code> |
| [Object Short Notation](https://babeljs.io/docs/learn-es2015/#enhanced-object-literals)                     | <code>const name = 'vjeux'; const obj = {name};</code> |
| [Parameters](https://babeljs.io/docs/en/babel-plugin-transform-parameters)                                  | <code>function test(x = 'hello', {a, b}, ...args) {}</code> |
| [Rest Params](https://github.com/sebmarkbage/ecmascript-rest-spread)                                        | <code>function(type, ...args) {};</code> |
| [Shorthand Properties](https://babeljs.io/docs/en/babel-plugin-transform-shorthand-properties)              | <code>const o = {a, b, c};</code> |
| [Sticky Regex](https://babeljs.io/docs/en/babel-plugin-transform-sticky-regex)                              | <code>const a = /o+/y;</code> |
| [Template Literals](https://babeljs.io/docs/learn-es2015/#template-strings)                                 | <code>const who = 'world'; const str = `Hello ${who}`;</code> |
| [Unicode Regex](https://babeljs.io/docs/en/babel-plugin-transform-unicode-regex)                            | <code>const string = 'foo💩bar'; const match = string.match(/foo(.)bar/u);</code> |
| ECMAScript 2016 (ES7)                                                                                       |                                                                                  |
| [Exponentiation Operator](https://babeljs.io/docs/en/babel-plugin-transform-exponentiation-operator)        | <code>let x = 10 ** 2;</code> |
| ECMAScript 2017 (ES8)                                                                                       |                                                                                  |
| [Async Functions](https://github.com/tc39/ecmascript-asyncawait)                                            | <code>async function doStuffAsync() {const foo = await doOtherStuffAsync();};</code> |
| [Function Trailing Comma](https://github.com/jeffmo/es-trailing-function-commas)                            | <code>function f(a, b, c,) {};</code> |
| ECMAScript 2018 (ES9)                                                                                       |                                                                                  |
| [Object Spread](https://github.com/tc39/proposal-object-rest-spread)                                        | <code>const extended = {...obj, a: 10};</code> |
| ECMAScript 2019 (ES10)                                                                                      |                                                                                  |
| [Optional Catch Binding](https://babeljs.io/docs/en/babel-plugin-proposal-optional-catch-binding)           | <code>try {throw 0; } catch { doSomethingWhichDoesNotCareAboutTheValueThrown();}</code> |
| ECMAScript 2020 (ES11)                                                                                      |                                                                                  |
| [Dynamic Imports](https://babeljs.io/docs/en/babel-plugin-syntax-dynamic-import)                            | <code>const package = await import('package'); package.function()</code> |
| [Nullish Coalescing Operator](https://babeljs.io/docs/en/babel-plugin-proposal-nullish-coalescing-operator) | <code>const foo = object.foo ?? 'default';</code> |
| [Optional Chaining](https://github.com/tc39/proposal-optional-chaining)                                     | <code>const name = obj.user?.name;</code> |
| ECMAScript 2022 (ES13)                                                                                      |                                                                                  |
| [Class Fields](https://babeljs.io/docs/en/babel-plugin-proposal-class-properties)                           | <code>class Bork {static a = 'foo'; static b; x = 'bar'; y;}</code> |
| Stage 1 Proposal                                                                                            |                                                                                  |
| [Export Default From](https://babeljs.io/docs/en/babel-plugin-proposal-export-default-from)                 | <code>export v from 'mod';</code> |
| Miscellaneous                                                                                               |                                                                                  |
| [Babel Template](https://babeljs.io/docs/en/babel-template)                                                 | <code>template(`const %%importName%% = require(%%source%%);`);</code> |
| [Flow](https://flowtype.org/)                                                                               | <code>function foo(x: ?number): string {};</code> |
| [ESM to CJS](https://babeljs.io/docs/en/babel-plugin-transform-modules-commonjs)                            | <code>export default 42;</code> |
| [JSX](https://react.dev/learn/writing-markup-with-jsx)                                                      | <code>&lt;View style={{color: 'red'}} /&gt;</code> |
| [Object Assign](https://babeljs.io/docs/en/babel-plugin-transform-object-assign)                            | <code>Object.assign(a, b);</code> |
| [React Display Name](https://babeljs.io/docs/en/babel-plugin-transform-react-display-name)                  | <code>const bar = createReactClass({});</code> |
| [TypeScript](https://www.typescriptlang.org/)                                                               | <code>function foo(x: {hello: true, target: 'react native!'}): string {};</code> |

<a id="polyfills"></a>

## Polyfills

Many standard functions are also available on all the supported JavaScript runtimes.

<a id="browser"></a>

#### Browser

* [CommonJS `require`](https://nodejs.org/docs/latest/api/modules.html)
* `console.{log, warn, error, info, debug, trace, table, group, groupCollapsed, groupEnd}`
* [`XMLHttpRequest`, `fetch`](https://reactnative.dev/docs/network#content)
* [`{set, clear}{Timeout, Interval, Immediate}, {request, cancel}AnimationFrame`](https://reactnative.dev/docs/timers#content)

<a id="ecmascript-2015-es6"></a>

#### ECMAScript 2015 (ES6)

* [`Array.from`](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Array/from)
* `Array.prototype.{find, findIndex}`
* [`Object.assign`](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Object/assign)
* `String.prototype.{startsWith, endsWith, repeat, includes}`

<a id="ecmascript-2016-es7"></a>

#### ECMAScript 2016 (ES7)

* `Array.prototype.includes`

<a id="ecmascript-2017-es8"></a>

#### ECMAScript 2017 (ES8)

* `Object.{entries, values}`

<a id="specific"></a>

#### Specific

* `__DEV__`
