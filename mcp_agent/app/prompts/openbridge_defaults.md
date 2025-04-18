# OpenBridge Component Standards

## Required Components
- Always include `<obc-top-bar>` with attributes:
  ```html
  <obc-top-bar 
    apptitle="Application Name" 
    pagename="Current Page"
    showclock
    showdimmingbutton
    showappsbutton>
  </obc-top-bar>
  ```

## Theme Implementation
1. Include brilliance menu component:
   ```html
   <obc-brilliance-menu @paletteChanged=${handlePaletteChange}>
   </obc-brilliance-menu>
   ```
2. Theme handling JavaScript:
   ```js
   function handlePaletteChange(event) {
     document.documentElement.setAttribute('data-obc-theme', event.detail.palette);
   }
   ```

## Styling Requirements
- Set body background using OpenBridge variable:
  ```css
  body {
    background: var(--container-background-color);
    margin: 0;
  }
  ```

## Import Guidelines
- Required Web Component imports:
  ```html
  <script type="module" src="/node_modules/@oicl/openbridge-webcomponents/top-bar.js"></script>
  <script type="module" src="/node_modules/@oicl/openbridge-webcomponents/icon-button.js"></script>
  ```
- Forbidden imports:
  ```html
  <!-- NEVER import these -->
  <script type="module" src="icon-alert-bell-indicator-iec.js"></script>
