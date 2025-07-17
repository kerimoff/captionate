# Captionato

A powerful image captioning library available in both Python and JavaScript. Add styled text captions to images with support for HTML formatting, custom fonts, and flexible positioning.

## Features

- ✨ **HTML Text Formatting**: Support for `<b>`, `<i>`, `<u>`, and `<br>` tags
- 🎨 **Custom Fonts**: Google Fonts integration (Montserrat, Nunito, Poppins, Roboto)
- 📐 **Flexible Positioning**: Top or bottom text placement
- 🎛️ **Customizable Styling**: Background colors, margins, gradients
- 🔧 **Auto Font Sizing**: Automatically fits text to available space
- 🌐 **Cross-Platform**: Python (FastAPI) and JavaScript (Browser) versions

## Python Version (main branch)

FastAPI-based image captioning service.

### Installation

```bash
pip install -r requirements.txt
```

### Usage

```bash
python main.py
```

### API Example

```bash
curl -X POST "http://localhost:8000/caption-image" \
  -H "Content-Type: application/json" \
  -d '{
    "image_url": "https://example.com/image.jpg",
    "texts": ["<b>Hello</b><br><i>World</i>"],
    "font_family": "Montserrat",
    "text_position": "bottom"
  }'
```

## JavaScript Version (web branch)

Browser-ready JavaScript library for client-side image captioning.

### Installation

```bash
npm install captionato-js
```

Or use directly in browser:

```html
<script src="https://unpkg.com/captionato-js/dist/captionato.js"></script>
```

### Usage

#### ES Modules

```javascript
import { captionImage } from 'captionato-js';

const results = await captionImage({
  imageUrl: 'https://example.com/image.jpg',
  texts: ['<b>Hello</b><br><i>World</i>'],
  fontFamily: 'Montserrat',
  textPosition: 'bottom'
});

// Access the captioned image
const canvas = results[0].canvas;
const dataUrl = results[0].dataUrl;
```

#### Browser Script Tag

```html
<script src="dist/captionato.js"></script>
<script>
async function addCaption() {
  const results = await Captionato.captionImage({
    imageUrl: 'https://example.com/image.jpg',
    texts: ['<b>Amazing View</b><br><i>Nature at its finest</i>'],
    fontFamily: 'Poppins',
    textPosition: 'bottom'
  });
  
  document.body.appendChild(results[0].canvas);
}
</script>
```

### JavaScript API Options

```typescript
interface CaptionOptions {
  imageUrl?: string;           // Image URL (with CORS support)
  imageElement?: HTMLImageElement; // Or existing image element
  imageCanvas?: HTMLCanvasElement; // Or existing canvas
  texts: string[];            // Array of caption texts
  fontFamily?: 'Montserrat' | 'Nunito' | 'Poppins' | 'Roboto';
  textPosition?: 'top' | 'bottom';
  backgroundHeight?: number;   // 0.0 - 1.0
  backgroundColor?: string;    // rgba(r, g, b, a) format
  marginHorizontal?: number;   // Percentage
  marginTop?: number;         // Percentage
  marginBottom?: number;      // Percentage
  transitionProportion?: number; // 0.0 - 1.0
}
```

## Development (JavaScript)

```bash
# Install dependencies
npm install

# Build the library
npm run build

# Development with watch mode
npm run dev

# Run tests
npm test
```

## Examples

See `example.html` for a complete browser demo with interactive controls.

## Browser Compatibility

- Modern browsers with Canvas API support
- ES2018+ features
- Automatic Google Fonts loading

## License

MIT
