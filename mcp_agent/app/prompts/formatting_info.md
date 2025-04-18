# Formatting Specifications

## Code Formatting Rules
- 2-space indentation for all code files
- No trailing whitespace
- Unix line endings (LF)
- UTF-8 encoding

```html
<!-- HTML Example -->
<obc-top-bar 
  apptitle="Demo" 
  pagename="Home"
  showclock>
</obc-top-bar>
```

## Message Formatting
### Allowed Tags:
- `<p>`, `<pre>`, `<code>`
- `<ul>`, `<ol>`, `<li>`
- `<strong>`, `<em>`, `<br>`

### Forbidden Tags:
- `<script>`, `<style>`, `<iframe>`
- Any attributes except code language hints:
  ```ts
  // Allowed
  const example: string = "test";
  ```

## OpenBridge Specific Formatting
1. Component attributes must be lowercase:
   ```html
   <!-- Good -->
   <obc-top-bar showclock>
   
   <!-- Bad -->
   <obc-top-bar showClock>
   ```

2. Always use double quotes for attributes
3. Self-close void elements:
   ```html
   <obc-brilliance-menu/>
