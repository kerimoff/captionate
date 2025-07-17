/**
 * Parse RGBA color string to RGBA values
 */
function parseRgbaString(rgbaStr) {
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
        let a;
        if (aStr.includes('.') && aFloat >= 0.0 && aFloat <= 1.0) {
            a = Math.round(aFloat * 255);
        }
        else {
            a = Math.max(0, Math.min(255, Math.round(aFloat)));
        }
        return [r, g, b, a];
    }
    catch (error) {
        console.error(`Error parsing RGBA string '${rgbaStr}':`, error);
        return [0, 0, 0, 180]; // Default fallback color
    }
}
/**
 * Parse HTML text with styling tags into structured segments
 */
function parseHtmlText(htmlText) {
    // Create a temporary DOM element to parse HTML
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = htmlText;
    const logicalLines = [[]];
    function processNode(node, activeStyles = new Set()) {
        if (node.nodeType === Node.TEXT_NODE) {
            const content = node.textContent || '';
            if (content) {
                logicalLines[logicalLines.length - 1].push({
                    text: content,
                    styles: new Set(activeStyles)
                });
            }
        }
        else if (node.nodeType === Node.ELEMENT_NODE) {
            const element = node;
            if (element.tagName.toLowerCase() === 'br') {
                logicalLines.push([]);
                return;
            }
            const newStyles = new Set(activeStyles);
            const tagName = element.tagName.toLowerCase();
            if (tagName === 'b' || tagName === 'strong') {
                newStyles.add('bold');
            }
            else if (tagName === 'i' || tagName === 'em') {
                newStyles.add('italic');
            }
            else if (tagName === 'u') {
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
function getFontString(fontSize, fontFamily, styles) {
    const weight = styles.has('bold') ? 'bold' : 'normal';
    const style = styles.has('italic') ? 'italic' : 'normal';
    // Map font families to web-safe fallbacks
    const fontFamilyMap = {
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
function loadGoogleFonts(fontFamilies) {
    return new Promise((resolve, reject) => {
        // Check if fonts are already loaded
        const existingLink = document.querySelector('link[href*="fonts.googleapis.com"]');
        if (existingLink) {
            resolve();
            return;
        }
        const link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = `https://fonts.googleapis.com/css2?${fontFamilies.map(font => `family=${font}:ital,wght@0,400;0,700;1,400;1,700`).join('&')}&display=swap`;
        link.onload = () => resolve();
        link.onerror = () => reject(new Error('Failed to load Google Fonts'));
        document.head.appendChild(link);
    });
}
/**
 * Get approximate font metrics for canvas text
 */
function getFontMetrics(ctx, fontSize) {
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
function loadImageAsCanvas(imageUrl) {
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
function imageElementToCanvas(img) {
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

class Captionato {
    /**
     * Create captions on images
     */
    static async captionImages(options) {
        const opts = { ...this.DEFAULT_OPTIONS, ...options };
        // Load Google Fonts if needed
        try {
            await loadGoogleFonts([opts.fontFamily]);
        }
        catch (error) {
            console.warn('Failed to load Google Fonts:', error);
        }
        // Get source canvas
        let sourceCanvas;
        try {
            if (options.imageUrl) {
                sourceCanvas = await loadImageAsCanvas(options.imageUrl);
            }
            else if (options.imageElement) {
                sourceCanvas = imageElementToCanvas(options.imageElement);
            }
            else if (options.imageCanvas) {
                sourceCanvas = options.imageCanvas;
            }
            else {
                throw new Error('No image source provided');
            }
        }
        catch (error) {
            return [{
                    success: false,
                    error: error instanceof Error ? error.message : 'Failed to load image'
                }];
        }
        const results = [];
        for (const text of opts.texts) {
            try {
                const canvas = await this.captionImageInternal(sourceCanvas, text, opts.fontFamily, opts.textPosition, opts.backgroundHeight, opts.backgroundColor, opts.marginHorizontal, opts.marginTop, opts.marginBottom, opts.transitionProportion);
                results.push({
                    success: true,
                    canvas,
                    dataUrl: canvas.toDataURL('image/png')
                });
            }
            catch (error) {
                results.push({
                    success: false,
                    error: error instanceof Error ? error.message : 'Failed to process text'
                });
            }
        }
        return results;
    }
    static async captionImageInternal(originalCanvas, textContent, fontFamily, textPosition, backgroundHeight, backgroundColor, marginHorizontal, marginTop, marginBottom, transitionProportion) {
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        if (!ctx) {
            throw new Error('Failed to get canvas context');
        }
        // Copy original image
        canvas.width = originalCanvas.width;
        canvas.height = originalCanvas.height;
        ctx.drawImage(originalCanvas, 0, 0);
        const width = canvas.width;
        const height = canvas.height;
        // Calculate dimensions
        const bgHeight = Math.floor(height * backgroundHeight);
        const marginXPx = Math.floor((marginHorizontal / 100) * width / 2);
        const marginTopPx = Math.floor((marginTop / 100) * bgHeight);
        const marginBottomPx = Math.floor((marginBottom / 100) * bgHeight);
        // Create overlay canvas
        const overlayCanvas = document.createElement('canvas');
        const overlayCtx = overlayCanvas.getContext('2d');
        if (!overlayCtx) {
            throw new Error('Failed to get overlay canvas context');
        }
        overlayCanvas.width = width;
        overlayCanvas.height = bgHeight;
        // Parse color
        const [baseR, baseG, baseB, baseA] = parseRgbaString(backgroundColor);
        // Create background with gradient transition
        this.createBackgroundWithTransition(overlayCtx, width, bgHeight, baseR, baseG, baseB, baseA, textPosition, transitionProportion);
        // Parse and render text
        const logicalLinesStyled = parseHtmlText(textContent);
        if (logicalLinesStyled.some(line => line.length > 0)) {
            const { fontSize, renderableLines } = this.calculateOptimalFontSize(overlayCtx, logicalLinesStyled, fontFamily, width, bgHeight, marginXPx, marginTopPx, marginBottomPx);
            if (fontSize > 0 && renderableLines.length > 0) {
                this.renderText(overlayCtx, renderableLines, fontFamily, fontSize, width, bgHeight, marginXPx, marginTopPx, marginBottomPx);
            }
        }
        // Composite overlay onto main canvas
        const yPosition = textPosition === 'bottom' ? height - bgHeight : 0;
        ctx.drawImage(overlayCanvas, 0, yPosition);
        return canvas;
    }
    static createBackgroundWithTransition(ctx, width, bgHeight, baseR, baseG, baseB, baseA, textPosition, transitionProportion) {
        const transitionHeightPx = Math.floor(bgHeight * transitionProportion);
        if (transitionHeightPx > 0 && bgHeight > 0) {
            // Create gradient
            const gradient = ctx.createLinearGradient(0, 0, 0, bgHeight);
            if (textPosition === 'bottom') {
                // Gradient from transparent at top to opaque at bottom
                gradient.addColorStop(0, `rgba(${baseR}, ${baseG}, ${baseB}, 0)`);
                gradient.addColorStop(transitionProportion, `rgba(${baseR}, ${baseG}, ${baseB}, ${baseA / 255})`);
                gradient.addColorStop(1, `rgba(${baseR}, ${baseG}, ${baseB}, ${baseA / 255})`);
            }
            else {
                // Gradient from opaque at top to transparent at bottom
                gradient.addColorStop(0, `rgba(${baseR}, ${baseG}, ${baseB}, ${baseA / 255})`);
                gradient.addColorStop(1 - transitionProportion, `rgba(${baseR}, ${baseG}, ${baseB}, ${baseA / 255})`);
                gradient.addColorStop(1, `rgba(${baseR}, ${baseG}, ${baseB}, 0)`);
            }
            ctx.fillStyle = gradient;
        }
        else {
            ctx.fillStyle = `rgba(${baseR}, ${baseG}, ${baseB}, ${baseA / 255})`;
        }
        ctx.fillRect(0, 0, width, bgHeight);
    }
    static calculateOptimalFontSize(ctx, logicalLinesStyled, fontFamily, width, bgHeight, marginXPx, marginTopPx, marginBottomPx) {
        let bestFontSize = 0;
        let finalRenderableLines = [];
        const maxFontSize = Math.min(bgHeight, width, 200);
        const availableWidth = width - 2 * marginXPx;
        const availableHeight = bgHeight - marginTopPx - marginBottomPx;
        for (let fontSize = 1; fontSize <= maxFontSize; fontSize++) {
            const renderableLines = [];
            let totalHeight = 0;
            let canFit = true;
            for (const logicalLine of logicalLinesStyled) {
                if (!canFit)
                    break;
                if (logicalLine.length === 0) {
                    // Empty line
                    ctx.font = getFontString(fontSize, fontFamily, new Set());
                    const metrics = getFontMetrics(ctx, fontSize);
                    renderableLines.push({
                        segments: [],
                        height: metrics.height,
                        maxAscent: metrics.ascent
                    });
                    totalHeight += metrics.height;
                    continue;
                }
                // Break line into words and fit within width
                const lineSegments = this.fitLineToWidth(ctx, logicalLine, fontFamily, fontSize, availableWidth);
                if (lineSegments.length === 0) {
                    canFit = false;
                    break;
                }
                for (const segments of lineSegments) {
                    const maxAscent = Math.max(...segments.map(s => getFontMetrics(ctx, fontSize).ascent));
                    const lineHeight = getFontMetrics(ctx, fontSize).height;
                    renderableLines.push({
                        segments,
                        height: lineHeight,
                        maxAscent
                    });
                    totalHeight += lineHeight;
                }
            }
            if (canFit && totalHeight <= availableHeight) {
                bestFontSize = fontSize;
                finalRenderableLines = renderableLines;
            }
            else {
                break;
            }
        }
        return { fontSize: bestFontSize, renderableLines: finalRenderableLines };
    }
    static fitLineToWidth(ctx, logicalLine, fontFamily, fontSize, availableWidth) {
        const lines = [];
        let currentLine = [];
        let currentWidth = 0;
        for (const segment of logicalLine) {
            const words = segment.text.split(/(\s+)/);
            for (const word of words) {
                if (!word)
                    continue;
                ctx.font = getFontString(fontSize, fontFamily, segment.styles);
                const wordWidth = ctx.measureText(word).width;
                const metrics = ctx.measureText(word);
                const renderableSegment = {
                    text: word,
                    styles: segment.styles,
                    width: wordWidth,
                    metrics
                };
                // Check if word fits on current line
                if (currentWidth + wordWidth > availableWidth && currentLine.length > 0) {
                    // Start new line
                    lines.push(currentLine);
                    currentLine = [renderableSegment];
                    currentWidth = wordWidth;
                }
                else {
                    currentLine.push(renderableSegment);
                    currentWidth += wordWidth;
                }
            }
        }
        if (currentLine.length > 0) {
            lines.push(currentLine);
        }
        return lines;
    }
    static renderText(ctx, renderableLines, fontFamily, fontSize, width, bgHeight, marginXPx, marginTopPx, marginBottomPx) {
        const availableHeight = bgHeight - marginTopPx - marginBottomPx;
        const totalTextHeight = renderableLines.reduce((sum, line) => sum + line.height, 0);
        // Center text vertically
        const paddingTop = totalTextHeight < availableHeight
            ? Math.floor((availableHeight - totalTextHeight) / 2)
            : 0;
        let currentY = marginTopPx + paddingTop;
        for (const line of renderableLines) {
            if (line.segments.length === 0) {
                // Empty line
                currentY += line.height;
                continue;
            }
            // Calculate total width of line for centering
            const lineWidth = line.segments.reduce((sum, seg) => sum + seg.width, 0);
            const startX = marginXPx + Math.floor((width - 2 * marginXPx - lineWidth) / 2);
            let currentX = Math.max(marginXPx, startX);
            for (const segment of line.segments) {
                ctx.font = getFontString(fontSize, fontFamily, segment.styles);
                ctx.fillStyle = 'white';
                const yPos = currentY + line.maxAscent;
                ctx.fillText(segment.text, currentX, yPos);
                // Draw underline if needed
                if (segment.styles.has('underline')) {
                    const underlineY = yPos + 2;
                    ctx.strokeStyle = 'white';
                    ctx.lineWidth = 1;
                    ctx.beginPath();
                    ctx.moveTo(currentX, underlineY);
                    ctx.lineTo(currentX + segment.width, underlineY);
                    ctx.stroke();
                }
                currentX += segment.width;
            }
            currentY += line.height;
        }
    }
}
Captionato.DEFAULT_OPTIONS = {
    fontFamily: 'Montserrat',
    textPosition: 'bottom',
    backgroundHeight: 0.4,
    backgroundColor: 'rgba(0, 0, 0, 180)',
    marginHorizontal: 10,
    marginTop: 10,
    marginBottom: 10,
    transitionProportion: 0.2
};

// Convenience function for easy usage
async function captionImage(options) {
    return Captionato.captionImages(options);
}

export { Captionato, captionImage, getFontMetrics, getFontString, imageElementToCanvas, loadGoogleFonts, loadImageAsCanvas, parseHtmlText, parseRgbaString };
