import { CaptionOptions, CaptionResult } from './types';
export declare class Captionato {
    private static readonly DEFAULT_OPTIONS;
    /**
     * Create captions on images
     */
    static captionImages(options: CaptionOptions): Promise<CaptionResult[]>;
    private static captionImageInternal;
    private static createBackgroundWithTransition;
    private static calculateOptimalFontSize;
    private static fitLineToWidth;
    private static renderText;
}
