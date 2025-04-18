# Artifact Creation Standards

## File Structure Requirements
```html
<boltArtifact id="unique-id" title="Descriptive Title">
  <file path="package.json">
  {
    "name": "app-name",
    "dependencies": {
      "@oicl/openbridge-webcomponents": "^2.4.0",
      "vite": "^4.0.0"
    }
  }
  </file>
  
  <action type="shell">
    npm install
  </action>
  
  <action type="shell">
    npm run dev
  </action>
</boltArtifact>
```

## Execution Order Rules
1. Create package.json first with all dependencies
2. Run `npm install` before any other commands
3. Start dev server last

## File Content Requirements
- Always emit complete files - no placeholders
- Use 2-space indentation for JSON/HTML/CSS
- Validate OpenBridge component imports
- Include WebContainer-safe dependencies only

## Diff Specifications
```xml
<modifications>
  <diff>
  <<<<<<< SEARCH
  function oldMethod() {
    return true;
  }
  =======
  function newMethod() {
    return false;
  }
  >>>>>>> REPLACE
  </diff>
  
  <file path="src/index.html">
  <!-- Full file content -->
  </file>
</modifications>
```

## Validation Requirements
1. Run ESLint checks before committing
2. Verify WebContainer compatibility
3. Check OpenBridge component wiring
4. Ensure font paths match public/fonts
