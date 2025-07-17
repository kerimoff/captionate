import { FontFamily, FontStyle, TextSegment, FontMetrics } from './types';

/**
 * Parse RGBA color string to RGBA values
 */
export function parseRgbaString(rgbaStr: string): [number, number, number, number] {
  try {
    const trimmed = rgbaStr.trim().toLowerCase();
    if (!trimmed.startsWith('rgba(') || !trimmed.endsWith(')')) {
      throw new Error('Invalid RGBA string format');
    }
    
    const parts = trimmed.slice(5, -1).split(',');
    if (parts.length !== 4) {
      throw new Error('RGBA string must have 4 parts (r, g, b, a)');
    }
    
    const r = Math.max(0, Math.min(255, Math.round(parseFloat(parts[0].trim()))));
    const g = Math.max(0, Math.min(255, Math.round(parseFloat(parts[1].trim()))));
    const b = Math.max(0, Math.min(255, Math.round(parseFloat(parts[2].trim()))));
    
    const aStr = parts[3].trim();
    const aFloat = parseFloat(aStr);
    
    let a: number;
    if (aStr.includes('.') && aFloat >= 0.0 && aFloat <= 1.0) {
      a = Math.round(aFloat * 255);
    } else {
      a = Math.max(0, Math.min(255, Math.round(aFloat)));
    }
    
    return [r, g, b, a];
  } catch (error) {
    console.error(`Error parsing RGBA string '${rgbaStr}':`, error);
    return [0, 0, 0, 180]; // Default fallback color
  }
}

/**
 * Parse HTML text with styling tags into structured segments
 */
export function parseHtmlText(htmlText: string): TextSegment[][] {
  // Create a temporary DOM element to parse HTML
  const tempDiv = document.createElement('div');
  tempDiv.innerHTML = htmlText;
  
  const logicalLines: TextSegment[][] = [[]];
  
  function processNode(node: Node, activeStyles: Set<FontStyle> = new Set()): void {
    if (node.nodeType === Node.TEXT_NODE) {
      const content = node.textContent || '';
      if (content) {
        logicalLines[logicalLines.length - 1].push({
          text: content,
          styles: new Set(activeStyles)
        });
      }
    } else if (node.nodeType === Node.ELEMENT_NODE) {
      const element = node as Element;
      
      if (element.tagName.toLowerCase() === 'br') {
        logicalLines.push([]);
        return;
      }
      
      const newStyles = new Set(activeStyles);
      const tagName = element.tagName.toLowerCase();
      
      if (tagName === 'b' || tagName === 'strong') {
        newStyles.add('bold');
      } else if (tagName === 'i' || tagName === 'em') {
        newStyles.add('italic');
      } else if (tagName === 'u') {
        newStyles.add('underline');
      }
      
      // Process children with updated styles
      Array.from(element.childNodes).forEach(child => {
        processNode(child, newStyles);
      });
    }
  }
  
  Array.from(tempDiv.childNodes).forEach(child => {
    processNode(child);
  });
  
  // Remove empty lines at the end
  while (logicalLines.length > 1 && logicalLines[logicalLines.length - 1].length === 0) {
    logicalLines.pop();
  }
  
  // If no content, return empty structure
  if (logicalLines.every(line => line.every(seg => !seg.text.trim()))) {
    return [[]];
  }
  
  return logicalLines;
}

/**
 * Get font string for canvas context
 */
export function getFontString(fontSize: number, fontFamily: FontFamily, styles: Set<FontStyle>): string {
  const weight = styles.has('bold') ? 'bold' : 'normal';
  const style = styles.has('italic') ? 'italic' : 'normal';
  
  // Map font families to web-safe fallbacks
  const fontFamilyMap: Record<FontFamily, string> = {
    'Montserrat': 'Montserrat, Arial, sans-serif',
    'Nunito': 'Nunito, Arial, sans-serif', 
    'Poppins': 'Poppins, Arial, sans-serif',
    'Roboto': 'Roboto, Arial, sans-serif'
  };
  
  return `${style} ${weight} ${fontSize}px ${fontFamilyMap[fontFamily]}`;
}

/**
 * Load Google Fonts dynamically
 */
export function loadGoogleFonts(fontFamilies: FontFamily[]): Promise<void> {
  return new Promise((resolve, reject) => {
    // Check if fonts are already loaded
    const existingLink = document.querySelector('link[href*="fonts.googleapis.com"]');
    if (existingLink) {
      resolve();
      return;
    }
    
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = `https://fonts.googleapis.com/css2?${fontFamilies.map(font => 
      `family=${font}:ital,wght@0,400;0,700;1,400;1,700`
    ).join('&')}&display=swap`;
    
    link.onload = () => resolve();
    link.onerror = () => reject(new Error('Failed to load Google Fonts'));
    
    document.head.appendChild(link);
  });
}

/**
 * Get approximate font metrics for canvas text
 */
export function getFontMetrics(ctx: CanvasRenderingContext2D, fontSize: number): FontMetrics {
  // Canvas doesn't provide direct font metrics, so we approximate
  const metrics = ctx.measureText('Mg');
  const ascent = metrics.actualBoundingBoxAscent || fontSize * 0.8;
  const descent = metrics.actualBoundingBoxDescent || fontSize * 0.2;
  
  return {
    ascent,
    descent,
    height: ascent + descent
  };
}

/**
 * Load image from URL and return as canvas
 */
export function loadImageAsCanvas(imageUrl: string): Promise<HTMLCanvasElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.crossOrigin = 'anonymous';
    
    img.onload = () => {
      const canvas = document.createElement('canvas');
      const ctx = canvas.getContext('2d');
      
      if (!ctx) {
        reject(new Error('Failed to get canvas context'));
        return;
      }
      
      canvas.width = img.width;
      canvas.height = img.height;
      ctx.drawImage(img, 0, 0);
      
      resolve(canvas);
    };
    
    img.onerror = () => {
      reject(new Error(`Failed to load image: ${imageUrl}`));
    };
    
    img.src = imageUrl;
  });
}

/**
 * Convert HTMLImageElement to canvas
 */
export function imageElementToCanvas(img: HTMLImageElement): HTMLCanvasElement {
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d');
  
  if (!ctx) {
    throw new Error('Failed to get canvas context');
  }
  
  canvas.width = img.width;
  canvas.height = img.height;
  ctx.drawImage(img, 0, 0);
  
  return canvas;
}