import {
  CaptionOptions,
  CaptionResult,
  FontFamily,
  TextPosition,
  FontStyle,
  TextSegment,
  RenderableSegment,
  RenderableLine
} from './types';
import {
  parseRgbaString,
  parseHtmlText,
  getFontString,
  getFontMetrics,
  loadImageAsCanvas,
  imageElementToCanvas,
  loadGoogleFonts
} from './utils';

export class Captionato {
  private static readonly DEFAULT_OPTIONS = {
    fontFamily: 'Montserrat' as FontFamily,
    textPosition: 'bottom' as TextPosition,
    backgroundHeight: 0.4,
    backgroundColor: 'rgba(0, 0, 0, 180)',
    marginHorizontal: 10,
    marginTop: 10,
    marginBottom: 10,
    transitionProportion: 0.2
  };

  /**
   * Create captions on images
   */
  static async captionImages(options: CaptionOptions): Promise<CaptionResult[]> {
    const opts = { ...this.DEFAULT_OPTIONS, ...options };
    
    // Load Google Fonts if needed
    try {
      await loadGoogleFonts([opts.fontFamily]);
    } catch (error) {
      console.warn('Failed to load Google Fonts:', error);
    }

    // Get source canvas
    let sourceCanvas: HTMLCanvasElement;
    try {
      if (options.imageUrl) {
        sourceCanvas = await loadImageAsCanvas(options.imageUrl);
      } else if (options.imageElement) {
        sourceCanvas = imageElementToCanvas(options.imageElement);
      } else if (options.imageCanvas) {
        sourceCanvas = options.imageCanvas;
      } else {
        throw new Error('No image source provided');
      }
    } catch (error) {
      return [{ 
        success: false, 
        error: error instanceof Error ? error.message : 'Failed to load image' 
      }];
    }

    const results: CaptionResult[] = [];

    for (const text of opts.texts) {
      try {
        const canvas = await this.captionImageInternal(
          sourceCanvas,
          text,
          opts.fontFamily,
          opts.textPosition,
          opts.backgroundHeight,
          opts.backgroundColor,
          opts.marginHorizontal,
          opts.marginTop,
          opts.marginBottom,
          opts.transitionProportion
        );

        results.push({
          success: true,
          canvas,
          dataUrl: canvas.toDataURL('image/png')
        });
      } catch (error) {
        results.push({
          success: false,
          error: error instanceof Error ? error.message : 'Failed to process text'
        });
      }
    }

    return results;
  }

  private static async captionImageInternal(
    originalCanvas: HTMLCanvasElement,
    textContent: string,
    fontFamily: FontFamily,
    textPosition: TextPosition,
    backgroundHeight: number,
    backgroundColor: string,
    marginHorizontal: number,
    marginTop: number,
    marginBottom: number,
    transitionProportion: number
  ): Promise<HTMLCanvasElement> {
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
    this.createBackgroundWithTransition(
      overlayCtx,
      width,
      bgHeight,
      baseR,
      baseG,
      baseB,
      baseA,
      textPosition,
      transitionProportion
    );

    // Parse and render text
    const logicalLinesStyled = parseHtmlText(textContent);
    
    if (logicalLinesStyled.some(line => line.length > 0)) {
      const { fontSize, renderableLines } = this.calculateOptimalFontSize(
        overlayCtx,
        logicalLinesStyled,
        fontFamily,
        width,
        bgHeight,
        marginXPx,
        marginTopPx,
        marginBottomPx
      );

      if (fontSize > 0 && renderableLines.length > 0) {
        this.renderText(
          overlayCtx,
          renderableLines,
          fontFamily,
          fontSize,
          width,
          bgHeight,
          marginXPx,
          marginTopPx,
          marginBottomPx
        );
      }
    }

    // Composite overlay onto main canvas
    const yPosition = textPosition === 'bottom' ? height - bgHeight : 0;
    ctx.drawImage(overlayCanvas, 0, yPosition);

    return canvas;
  }

  private static createBackgroundWithTransition(
    ctx: CanvasRenderingContext2D,
    width: number,
    bgHeight: number,
    baseR: number,
    baseG: number,
    baseB: number,
    baseA: number,
    textPosition: TextPosition,
    transitionProportion: number
  ): void {
    const transitionHeightPx = Math.floor(bgHeight * transitionProportion);
    
    if (transitionHeightPx > 0 && bgHeight > 0) {
      // Create gradient
      const gradient = ctx.createLinearGradient(0, 0, 0, bgHeight);
      
      if (textPosition === 'bottom') {
        // Gradient from transparent at top to opaque at bottom
        gradient.addColorStop(0, `rgba(${baseR}, ${baseG}, ${baseB}, 0)`);
        gradient.addColorStop(transitionProportion, `rgba(${baseR}, ${baseG}, ${baseB}, ${baseA / 255})`);
        gradient.addColorStop(1, `rgba(${baseR}, ${baseG}, ${baseB}, ${baseA / 255})`);
      } else {
        // Gradient from opaque at top to transparent at bottom
        gradient.addColorStop(0, `rgba(${baseR}, ${baseG}, ${baseB}, ${baseA / 255})`);
        gradient.addColorStop(1 - transitionProportion, `rgba(${baseR}, ${baseG}, ${baseB}, ${baseA / 255})`);
        gradient.addColorStop(1, `rgba(${baseR}, ${baseG}, ${baseB}, 0)`);
      }
      
      ctx.fillStyle = gradient;
    } else {
      ctx.fillStyle = `rgba(${baseR}, ${baseG}, ${baseB}, ${baseA / 255})`;
    }
    
    ctx.fillRect(0, 0, width, bgHeight);
  }

  private static calculateOptimalFontSize(
    ctx: CanvasRenderingContext2D,
    logicalLinesStyled: TextSegment[][],
    fontFamily: FontFamily,
    width: number,
    bgHeight: number,
    marginXPx: number,
    marginTopPx: number,
    marginBottomPx: number
  ): { fontSize: number; renderableLines: RenderableLine[] } {
    let bestFontSize = 0;
    let finalRenderableLines: RenderableLine[] = [];

    const maxFontSize = Math.min(bgHeight, width, 200);
    const availableWidth = width - 2 * marginXPx;
    const availableHeight = bgHeight - marginTopPx - marginBottomPx;

    for (let fontSize = 1; fontSize <= maxFontSize; fontSize++) {
      const renderableLines: RenderableLine[] = [];
      let totalHeight = 0;
      let canFit = true;

      for (const logicalLine of logicalLinesStyled) {
        if (!canFit) break;

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
        const lineSegments = this.fitLineToWidth(
          ctx,
          logicalLine,
          fontFamily,
          fontSize,
          availableWidth
        );

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
      } else {
        break;
      }
    }

    return { fontSize: bestFontSize, renderableLines: finalRenderableLines };
  }

  private static fitLineToWidth(
    ctx: CanvasRenderingContext2D,
    logicalLine: TextSegment[],
    fontFamily: FontFamily,
    fontSize: number,
    availableWidth: number
  ): RenderableSegment[][] {
    const lines: RenderableSegment[][] = [];
    let currentLine: RenderableSegment[] = [];
    let currentWidth = 0;

    for (const segment of logicalLine) {
      const words = segment.text.split(/(\s+)/);
      
      for (const word of words) {
        if (!word) continue;

        ctx.font = getFontString(fontSize, fontFamily, segment.styles);
        const wordWidth = ctx.measureText(word).width;
        const metrics = ctx.measureText(word);

        const renderableSegment: RenderableSegment = {
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
        } else {
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

  private static renderText(
    ctx: CanvasRenderingContext2D,
    renderableLines: RenderableLine[],
    fontFamily: FontFamily,
    fontSize: number,
    width: number,
    bgHeight: number,
    marginXPx: number,
    marginTopPx: number,
    marginBottomPx: number
  ): void {
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