import { CaptionOptions } from './types';
export { Captionato } from './captionato';
export { CaptionOptions, CaptionResult, FontFamily, TextPosition, FontStyle, TextSegment, RenderableSegment, RenderableLine, FontMetrics } from './types';
export { parseRgbaString, parseHtmlText, getFontString, loadGoogleFonts, getFontMetrics, loadImageAsCanvas, imageElementToCanvas } from './utils';
export declare function captionImage(options: CaptionOptions): Promise<import("./types").CaptionResult[]>;
