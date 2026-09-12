/**
 * Copyright (c) 2018-2024 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 * @author David Sehnal <david.sehnal@gmail.com>
 * @author Adam Midlik <midlik@gmail.com>
 */
import { FileHandle } from '../../mol-io/common/file-handle';
/** Create a file handle from either a file path or a URL (supports file://, http(s)://, gs:// protocols).  */
export declare function fileHandleFromPathOrUrl(pathOrUrl: string, name: string): Promise<FileHandle>;
export declare function fileHandleFromDescriptor(file: number, name: string): FileHandle;
/** Create a read-only file handle from a Google Cloud Storage URL (gs://bucket-name/file-name).  */
export declare function fileHandleFromGS(url: string, name: string): FileHandle;
/** Create a read-only file handle from a HTTP or HTTPS URL.  */
export declare function fileHandleFromHTTP(url: string, name: string): FileHandle;
