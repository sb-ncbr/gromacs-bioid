import { ErrorTranslator, JsonFormsI18nState, Translator, JsonFormsState } from '../store';
export declare const fetchLocale: (state?: JsonFormsI18nState) => string;
export declare const fetchTranslator: (state?: JsonFormsI18nState) => Translator;
export declare const fetchErrorTranslator: (state?: JsonFormsI18nState) => ErrorTranslator;
export declare const getLocale: (state: JsonFormsState) => string;
export declare const getTranslator: () => (state: JsonFormsState) => Translator;
export declare const getErrorTranslator: () => (state: JsonFormsState) => ErrorTranslator;
