import { Captionato } from './captionato';
import { CaptionOptions } from './types';

export { Captionato } from './captionato';
export {
  CaptionOptions,
  CaptionResult,
  FontFamily,
  TextPosition,
  FontStyle,
  TextSegment,
  RenderableSegment,
  RenderableLine,
  FontMetrics
} from './types';
export {
  parseRgbaString,
  parseHtmlText,
  getFontString,
  loadGoogleFonts,
  getFontMetrics,
  loadImageAsCanvas,
  imageElementToCanvas
} from './utils';

// Convenience function for easy usage
export async function captionImage(options: CaptionOptions) {
  return Captionato.captionImages(options);
}