export interface CombinatorDefaultTranslation {
    key: CombinatorTranslationEnum;
    default: (variable?: string) => string;
}
export declare enum CombinatorTranslationEnum {
    clearDialogTitle = "clearDialogTitle",
    clearDialogMessage = "clearDialogMessage",
    clearDialogAccept = "clearDialogAccept",
    clearDialogDecline = "clearDialogDecline"
}
export type CombinatorTranslations = {
    [key in CombinatorTranslationEnum]?: string;
};
export declare const combinatorDefaultTranslations: CombinatorDefaultTranslation[];
