export type FontFamily = 'Montserrat' | 'Nunito' | 'Poppins' | 'Roboto';
export type TextPosition = 'top' | 'bottom';
export type FontStyle = 'bold' | 'italic' | 'underline';
export interface CaptionOptions {
    imageUrl?: string;
    imageElement?: HTMLImageElement;
    imageCanvas?: HTMLCanvasElement;
    texts: string[];
    fontFamily?: FontFamily;
    textPosition?: TextPosition;
    backgroundHeight?: number;
    backgroundColor?: string;
    marginHorizontal?: number;
    marginTop?: number;
    marginBottom?: number;
    transitionProportion?: number;
}
export interface TextSegment {
    text: string;
    styles: Set<FontStyle>;
}
export interface RenderableSegment {
    text: string;
    styles: Set<FontStyle>;
    width: number;
    metrics: TextMetrics;
}
export interface RenderableLine {
    segments: RenderableSegment[];
    height: number;
    maxAscent: number;
}
export interface CaptionResult {
    success: boolean;
    canvas?: HTMLCanvasElement;
    dataUrl?: string;
    error?: string;
}
export interface FontMetrics {
    ascent: number;
    descent: number;
    height: number;
}
