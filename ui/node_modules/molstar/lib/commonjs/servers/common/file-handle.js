"use strict";
/**
 * Copyright (c) 2018-2024 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 * @author David Sehnal <david.sehnal@gmail.com>
 * @author Adam Midlik <midlik@gmail.com>
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.fileHandleFromPathOrUrl = fileHandleFromPathOrUrl;
exports.fileHandleFromDescriptor = fileHandleFromDescriptor;
exports.fileHandleFromGS = fileHandleFromGS;
exports.fileHandleFromHTTP = fileHandleFromHTTP;
const tslib_1 = require("tslib");
const fs = tslib_1.__importStar(require("fs"));
const node_fetch_1 = tslib_1.__importDefault(require("node-fetch"));
const file_handle_1 = require("../../mol-io/common/file-handle");
const simple_buffer_1 = require("../../mol-io/common/simple-buffer");
const mol_util_1 = require("../../mol-util");
const file_1 = require("../volume/common/file");
const google_cloud_storage_1 = require("./google-cloud-storage");
/** Create a file handle from either a file path or a URL (supports file://, http(s)://, gs:// protocols).  */
async function fileHandleFromPathOrUrl(pathOrUrl, name) {
    if (pathOrUrl.startsWith('gs://')) {
        return fileHandleFromGS(pathOrUrl, name);
    }
    else if (pathOrUrl.startsWith('http://') || pathOrUrl.startsWith('https://')) {
        return fileHandleFromHTTP(pathOrUrl, name);
    }
    else if (pathOrUrl.startsWith('file://')) {
        return fileHandleFromDescriptor(await (0, file_1.openRead)(pathOrUrl.slice('file://'.length)), name);
    }
    else {
        return fileHandleFromDescriptor(await (0, file_1.openRead)(pathOrUrl), name);
    }
}
function fileHandleFromDescriptor(file, name) {
    if (fs === undefined)
        throw new Error('fs module not available');
    return {
        name,
        readBuffer: (position, sizeOrBuffer, length, byteOffset) => {
            return new Promise((res, rej) => {
                let outBuffer;
                if (typeof sizeOrBuffer === 'number') {
                    byteOffset = (0, mol_util_1.defaults)(byteOffset, 0);
                    length = (0, mol_util_1.defaults)(length, sizeOrBuffer);
                    outBuffer = simple_buffer_1.SimpleBuffer.fromArrayBuffer(new ArrayBuffer(sizeOrBuffer));
                }
                else {
                    byteOffset = (0, mol_util_1.defaults)(byteOffset, 0);
                    length = (0, mol_util_1.defaults)(length, sizeOrBuffer.length);
                    outBuffer = sizeOrBuffer;
                }
                fs.read(file, outBuffer, byteOffset, length, position, (err, bytesRead, buffer) => {
                    if (err) {
                        rej(err);
                        return;
                    }
                    if (length !== bytesRead) {
                        console.warn(`byteCount ${length} and bytesRead ${bytesRead} differ`);
                    }
                    res({ bytesRead, buffer });
                });
            });
        },
        writeBuffer: (position, buffer, length) => {
            length = (0, mol_util_1.defaults)(length, buffer.length);
            return new Promise((res, rej) => {
                fs.write(file, buffer, 0, length, position, (err, written) => {
                    if (err)
                        rej(err);
                    else
                        res(written);
                });
            });
        },
        writeBufferSync: (position, buffer, length) => {
            length = (0, mol_util_1.defaults)(length, buffer.length);
            return fs.writeSync(file, buffer, 0, length, position);
        },
        close: () => {
            try {
                if (file !== void 0)
                    fs.close(file, mol_util_1.noop);
            }
            catch (e) {
            }
        }
    };
}
/** Create a read-only file handle from a Google Cloud Storage URL (gs://bucket-name/file-name).  */
function fileHandleFromGS(url, name) {
    return {
        name,
        readBuffer: async (position, sizeOrBuffer, length, byteOffset) => {
            let outBuffer;
            if (typeof sizeOrBuffer === 'number') {
                length = (0, mol_util_1.defaults)(length, sizeOrBuffer);
                outBuffer = simple_buffer_1.SimpleBuffer.fromArrayBuffer(new ArrayBuffer(sizeOrBuffer));
            }
            else {
                length = (0, mol_util_1.defaults)(length, sizeOrBuffer.length);
                outBuffer = sizeOrBuffer;
            }
            let data;
            try {
                data = await (0, google_cloud_storage_1.downloadGs)(url, { decompress: false, start: position, end: position + length - 1 });
            }
            catch (err) {
                err.isFileNotFound = true;
                throw err;
            }
            const bytesRead = data.copy(outBuffer, byteOffset);
            if (length !== bytesRead) {
                console.warn(`byteCount ${length} and bytesRead ${bytesRead} differ`);
            }
            return { bytesRead, buffer: outBuffer };
        },
        writeBuffer: () => {
            throw new Error('Writing to Google Cloud Storage file handle not supported');
        },
        writeBufferSync: () => {
            throw new Error('Writing to Google Cloud Storage file handle not supported');
        },
        close: () => { },
    };
}
/** Create a read-only file handle from a HTTP or HTTPS URL.  */
function fileHandleFromHTTP(url, name) {
    let innerHandle = undefined;
    return {
        name,
        readBuffer: async (position, sizeOrBuffer, length, byteOffset) => {
            if (!innerHandle) {
                const response = await (0, node_fetch_1.default)(url);
                if (response.ok) {
                    const buffer = await response.buffer();
                    innerHandle = file_handle_1.FileHandle.fromBuffer(buffer, name);
                }
                else {
                    const error = new Error(`fileHandleFromHTTP: Fetch failed with status code ${response.status}`);
                    error.isFileNotFound = true;
                    throw error;
                }
            }
            return innerHandle.readBuffer(position, sizeOrBuffer, length, byteOffset);
        },
        writeBuffer: () => {
            throw new Error('Writing to HTTP(S) file handle not supported');
        },
        writeBufferSync: () => {
            throw new Error('Writing to HTTP(S) file handle not supported');
        },
        close: () => { },
    };
}
