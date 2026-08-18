# Tailwind Plus UI Blocks Reference

Source: [Tailwind Plus UI Blocks documentation](https://tailwindcss.com/plus/ui-blocks/documentation). Retrieved 2026-08-18.

This is a working reference for adapting licensed Tailwind Plus blocks into Boulder Frame. It summarizes public documentation only; do not commit licensed Tailwind Plus block source or Elements documentation not authorized for this project.

## Project Baseline

- Tailwind Plus blocks target Tailwind CSS v4.2 or later. The frontend uses Tailwind CSS v4 with the Vite plugin.
- Tailwind Plus examples use Inter. Boulder Frame currently uses Geist through shadcn/ui; do not add Inter unless a UI decision requires it.
- For a full-page dark interface, Tailwind recommends `bg-white dark:bg-gray-950 scheme-light dark:scheme-dark` on `<html>` so native browser UI follows the color scheme.

## React Blocks

- React blocks require React 18 or newer plus `@headlessui/react` and `@heroicons/react` for interactive behavior and icons.
- Tailwind Plus examples are deliberately single components. Adapt and split them according to Boulder Frame domain boundaries and data flow rather than treating them as a fixed component API.
- Prefer existing shadcn/ui components before introducing Tailwind Plus dependencies. Do not install Headless UI or Heroicons until a selected licensed block requires them.

## HTML Blocks And Elements

- Interactive HTML blocks depend on commercial `@tailwindplus/elements`.
- Elements supports Autocomplete, Command palette, Dialog, Disclosure, Dropdown menu, Popover, Select, and Tabs.
- It supports current Tailwind v4 browsers: Chrome 111+, Safari 16.4+, and Firefox 128+.
- For React, use `@tailwindplus/elements/react` exports rather than custom elements to avoid hydration conflicts.

## Assets

- Icons in Tailwind Plus examples use MIT-licensed Heroicons.
- Images commonly come from Unsplash. Verify each image's usage terms before production use.
- Some examples use Lucid Illustrations; confirm its license before use.
- The downloadable Figma kit is discontinued and does not contain updates after 2021-07-14.

## Sources

- [Getting set up](https://tailwindcss.com/plus/ui-blocks/documentation)
- [Using React](https://tailwindcss.com/plus/ui-blocks/documentation/using-react)
- [Using HTML](https://tailwindcss.com/plus/ui-blocks/documentation/using-html)
- [Using Vue](https://tailwindcss.com/plus/ui-blocks/documentation/using-vue)
- [Assets](https://tailwindcss.com/plus/ui-blocks/documentation/assets)
- [Elements](https://tailwindcss.com/plus/ui-blocks/documentation/elements)
