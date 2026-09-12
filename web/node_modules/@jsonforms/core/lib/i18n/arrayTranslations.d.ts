export interface ArrayDefaultTranslation {
    key: ArrayTranslationEnum;
    default: (variable?: string) => string;
}
export declare enum ArrayTranslationEnum {
    addTooltip = "addTooltip",
    addAriaLabel = "addAriaLabel",
    removeTooltip = "removeTooltip",
    upAriaLabel = "upAriaLabel",
    downAriaLabel = "downAriaLabel",
    noSelection = "noSelection",
    removeAriaLabel = "removeAriaLabel",
    noDataMessage = "noDataMessage",
    deleteDialogTitle = "deleteDialogTitle",
    deleteDialogMessage = "deleteDialogMessage",
    deleteDialogAccept = "deleteDialogAccept",
    deleteDialogDecline = "deleteDialogDecline",
    up = "up",
    down = "down"
}
export type ArrayTranslations = {
    [key in ArrayTranslationEnum]?: string;
};
export declare const arrayDefaultTranslations: ArrayDefaultTranslation[];
