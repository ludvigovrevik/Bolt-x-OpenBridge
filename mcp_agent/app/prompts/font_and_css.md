# Font & CSS Implementation Guide

## Noto Sans Font Setup
1. Download font files:
```shell
mkdir -p public/fonts && cd public/fonts
wget https://fonts.gstatic.com/s/notosans/v27/o-0IIpQlx3QUlC5A4PNr5TRASf6M7Q.woff2 -O NotoSans.woff2
wget https://fonts.gstatic.com/s/notosans/v27/o-0IIpQlx3QUlC5A4PNr4TRASf6M7Q.woff2 -O NotoSans-Italic.woff2
```

2. Add @font-face rules:
```css
@font-face {
  font-family: 'Noto Sans';
  font-style: normal;
  font-weight: 400;
  src: url(/fonts/NotoSans.woff2) format('woff2');
}

@font-face {
  font-family: 'Noto Sans';
  font-style: italic;
  font-weight: 400;
  src: url(/fonts/NotoSans-Italic.woff2) format('woff2');
}

* {
  font-family: "Noto Sans", sans-serif;
}
```

3. Import OpenBridge variables:
```html
<link rel="stylesheet" 
  href="/node_modules/@oicl/openbridge-webcomponents/src/palettes/variables.css">
