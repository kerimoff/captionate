import { FontFamily, FontStyle, TextSegment, FontMetrics } from './types';
/**
 * Parse RGBA color string to RGBA values
 */
export declare function parseRgbaString(rgbaStr: string): [number, number, number, number];
/**
 * Parse HTML text with styling tags into structured segments
 */
export declare function parseHtmlText(htmlText: string): TextSegment[][];
/**
 * Get font string for canvas context
 */
export declare function getFontString(fontSize: number, fontFamily: FontFamily, styles: Set<FontStyle>): string;
/**
 * Load Google Fonts dynamically
 */
export declare function loadGoogleFonts(fontFamilies: FontFamily[]): Promise<void>;
/**
 * Get approximate font metrics for canvas text
 */
export declare function getFontMetrics(ctx: CanvasRenderingContext2D, fontSize: number): FontMetrics;
/**
 * Load image from URL and return as canvas
 */
export declare function loadImageAsCanvas(imageUrl: string): Promise<HTMLCanvasElement>;
/**
 * Convert HTMLImageElement to canvas
 */
export declare function imageElementToCanvas(img: HTMLImageElement): HTMLCanvasElement;
