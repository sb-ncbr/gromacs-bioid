export declare const compose: (path1: string, path2: string) => string;
export { compose as composePaths };
/**
 * Convert a schema path (i.e. JSON pointer) to an array by splitting
 * at the '/' character and removing all schema-specific keywords.
 *
 * The returned value can be used to de-reference a root object by folding over it
 * and de-referencing the single segments to obtain a new object.
 *
 *
 * @param {string} schemaPath the schema path to be converted
 * @returns {string[]} an array containing only non-schema-specific segments
 */
export declare const toDataPathSegments: (schemaPath: string) => string[];
/**
 * Convert a schema path (i.e. JSON pointer) to a data path.
 *
 * Data paths can be used in field change event handlers like handleChange.
 *
 * @example
 * toDataPath('#/properties/foo/properties/bar') === 'foo.bar')
 *
 * @param {string} schemaPath the schema path to be converted
 * @returns {string} the data path
 */
export declare const toDataPath: (schemaPath: string) => string;
/**
 * Encodes the given segment to be used as part of a JSON Pointer
 *
 * JSON Pointer has special meaning for "/" and "~", therefore these must be encoded
 */
export declare const encode: (segment: string) => string;
/**
 * Decodes a given JSON Pointer segment to its "normal" representation
 */
export declare const decode: (pointerSegment: string) => string;
/**
 * Transform a dotted path to a uiSchema properties path
 * @param path a dotted prop path to a schema value (i.e. articles.comment.author)
 * @return the uiSchema properties path (i.e. /properties/articles/properties/comment/properties/author)
 */
export declare const getPropPath: (path: string) => string;
