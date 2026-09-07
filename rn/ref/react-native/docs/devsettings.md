# DevSettings

Source: https://reactnative.dev/docs/devsettings

Version: 0.87 | Retrieved: 2026-09-07

The `DevSettings` module exposes methods for customizing settings for developers in development.

***

# Reference

<a id="methods"></a>

## Methods

<a id="addmenuitem"></a>

### `addMenuItem()`

React TSX

```
static addMenuItem(title: string, handler: () => any);
```

Add a custom menu item to the Dev Menu.

**Parameters:**

| Name            | Type     |
| --------------- | -------- |
| titleRequired   | string   |
| handlerRequired | function |

**Example:**

React TSX

```
DevSettings.addMenuItem('Show Secret Dev Screen', () => {

  Alert.alert('Showing secret dev screen!');

});
```

***

<a id="reload"></a>

### `reload()`

React TSX

```
static reload(reason?: string): void;
```

Reload the application. Can be invoked directly or on user interaction.

**Example:**

React TSX

```
<Button title="Reload" onPress={() => DevSettings.reload()} />
```
