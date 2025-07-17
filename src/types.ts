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
  backgroundHeight?: number; // 0.0 - 1.0
  backgroundColor?: string; // rgba format
  marginHorizontal?: number; // percentage
  marginTop?: number; // percentage  
  marginBottom?: number; // percentage
  transitionProportion?: number; // 0.0 - 1.0
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